import os
import re
from urllib.parse import urlparse, parse_qs

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.compiler import compiles
from pgvector.sqlalchemy import Vector
from app.core.config import settings
import logging

logger = logging.getLogger("database")

HAS_PGVECTOR = True

# True when running inside Vercel (or any serverless environment)
IS_SERVERLESS = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

# Compilation rule to make pgvector 'Vector' columns fall back to TEXT on SQLite
@compiles(Vector, 'sqlite')
def compile_vector_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(Vector, 'postgresql')
def compile_vector_postgresql(type_, compiler, **kw):
    global HAS_PGVECTOR
    if HAS_PGVECTOR:
        return f"VECTOR({type_.dim})"
    else:
        return "TEXT"

def _build_pg_engine(raw_url: str):
    """
    Parse and sanitise a PostgreSQL DATABASE_URL, then return a SQLAlchemy engine.

    Handles Neon / Supabase / Railway URLs that may include:
      ?sslmode=require&channel_binding=prefer
    psycopg2 does not accept channel_binding in the URL, so we strip all
    query params from the URL and pass only sslmode via connect_args.
    """
    parsed = urlparse(raw_url)
    qs     = parse_qs(parsed.query)

    connect_args = {"connect_timeout": 10}

    # Honour sslmode if present in the URL
    if "sslmode" in qs:
        connect_args["sslmode"] = qs["sslmode"][0]
    elif IS_SERVERLESS:
        # Hosted providers almost always require SSL — default to require
        connect_args["sslmode"] = "require"

    # Rebuild a clean URL with no query string (psycopg2 chokes on unknown params)
    clean_url = parsed._replace(query="").geturl()

    # Serverless: use NullPool so each lambda invocation gets its own connection
    # and there are no dangling connections when the function freezes.
    if IS_SERVERLESS:
        from sqlalchemy.pool import NullPool
        engine = create_engine(
            clean_url,
            connect_args=connect_args,
            poolclass=NullPool,
        )
        logger.info("Serverless mode: using NullPool for PostgreSQL.")
    else:
        engine = create_engine(
            clean_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=2,
            pool_recycle=300,
        )

    # Quick connection test
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    logger.info("Successfully established connection to PostgreSQL.")
    return engine


def get_engine():
    """
    Build the database engine.

    Priority:
      1. PostgreSQL when DATABASE_URL starts with 'postgresql'
      2. SQLite fallback for local development only.
         On Vercel (IS_SERVERLESS=True) the fallback is skipped and an error
         is raised immediately so the misconfiguration is obvious in the logs.
    """
    raw_url = settings.DATABASE_URL

    if raw_url.startswith("postgresql"):
        logger.info("Connecting to PostgreSQL database...")
        try:
            return _build_pg_engine(raw_url)
        except Exception as exc:
            if IS_SERVERLESS:
                # On Vercel a broken DB is a hard error — fail fast so the
                # 500 response body tells the developer exactly what to fix.
                logger.critical(
                    f"[VERCEL] PostgreSQL connection failed: {exc}. "
                    "Set a valid DATABASE_URL in Vercel Environment Variables "
                    "(Settings → Environment Variables). "
                    "Recommended free option: https://neon.tech"
                )
                raise RuntimeError(
                    "Database unavailable. Please configure DATABASE_URL in Vercel "
                    "Environment Variables. See logs for details."
                ) from exc
            logger.warning(f"PostgreSQL connection failed ({exc}). Falling back to local SQLite.")

    if IS_SERVERLESS:
        # Reached only if DATABASE_URL is not postgresql at all on Vercel
        raise RuntimeError(
            "No PostgreSQL DATABASE_URL configured for serverless deployment. "
            "Add DATABASE_URL to Vercel Environment Variables."
        )

    sqlite_url = "sqlite:///./ai_exam_db.db"
    logger.info(f"Using SQLite database at {sqlite_url}")
    return create_engine(sqlite_url, connect_args={"check_same_thread": False})

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Determine pgvector support immediately after engine connection is established
if "sqlite" not in engine.url.drivername:
    try:
        with engine.connect() as conn:
            res = conn.execute(text("SELECT 1 FROM pg_type WHERE typname = 'vector'")).scalar()
            if not res:
                try:
                    with engine.begin() as trans:
                        trans.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                    res = conn.execute(text("SELECT 1 FROM pg_type WHERE typname = 'vector'")).scalar()
                except Exception:
                    pass
            HAS_PGVECTOR = bool(res)
            if HAS_PGVECTOR:
                logger.info("pgvector extension detected and activated on PostgreSQL.")
            else:
                logger.warning("pgvector extension not found in PostgreSQL. Using TEXT fallback representation.")
    except Exception as e:
        logger.warning(f"Error checking pgvector: {e}. Falling back to standard TEXT representation for Vector columns.")
        HAS_PGVECTOR = False
else:
    HAS_PGVECTOR = False

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Creates database tables using the compiled vector representation fallbacks and runs dynamic column migrations.
    """

    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schemas created successfully.")
        
        # Automatic migration: Add option columns to questions table if they are missing
        with engine.connect() as conn:
            for col in ["option_a", "option_b", "option_c", "option_d"]:
                trans = conn.begin()
                try:
                    # Test if the column exists
                    conn.execute(text(f"SELECT {col} FROM questions LIMIT 1"))
                    trans.commit()
                except Exception:
                    # Rollback the failed SELECT transaction so connection is usable
                    trans.rollback()
                    
                    # Start a new transaction for ALTER TABLE
                    trans = conn.begin()
                    try:
                        conn.execute(text(f"ALTER TABLE questions ADD COLUMN {col} TEXT"))
                        trans.commit()
                        logger.info(f"Database Migration: Added column {col} to questions table.")
                    except Exception as migration_err:
                        trans.rollback()
                        logger.error(f"Failed to add column {col} to questions table: {migration_err}")



        
        # Seed default administrative and candidate test accounts if empty
        from app.models.db_models import User
        from app.api.auth import hash_password
        
        db = SessionLocal()
        try:
            if db.query(User).count() == 0:
                admin_user = User(
                    username="admin",
                    hashed_password=hash_password("admin123"),
                    roles="admin,instructor,candidate" # Admins get all roles by default
                )
                candidate_user = User(
                    username="rohan_gupta",
                    hashed_password=hash_password("student123"),
                    roles="candidate"
                )
                db.add_all([admin_user, candidate_user])
                db.commit()
                logger.info("Database seeded with test accounts: admin/admin123 and rohan_gupta/student123")
        except Exception as seed_err:
            logger.error(f"Failed to seed default accounts: {seed_err}")
        finally:
            db.close()
    except Exception as e:
        logger.critical(f"Critical error creating schemas: {e}")

