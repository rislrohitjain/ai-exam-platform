import os
import re
import logging
from urllib.parse import urlparse, parse_qs

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.compiler import compiles
from pgvector.sqlalchemy import Vector
from app.core.config import settings

logger = logging.getLogger("database")

# True when running inside Vercel or any AWS Lambda environment
IS_SERVERLESS = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

HAS_PGVECTOR = False  # determined lazily on first connection

# ---------------------------------------------------------------------------
# pgvector SQLAlchemy compile hooks
# ---------------------------------------------------------------------------
@compiles(Vector, 'sqlite')
def compile_vector_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(Vector, 'postgresql')
def compile_vector_postgresql(type_, compiler, **kw):
    if HAS_PGVECTOR:
        return f"VECTOR({type_.dim})"
    return "TEXT"

# ---------------------------------------------------------------------------
# Lazy engine — never created at import time
# ---------------------------------------------------------------------------
Base = declarative_base()

_engine = None
_SessionLocal = None


def _build_pg_engine(raw_url: str):
    """
    Parse and sanitise a PostgreSQL DATABASE_URL, build and return an engine.
    Strips query params psycopg2 cannot handle (channel_binding, sslmode)
    and passes SSL mode via connect_args instead.
    """
    parsed = urlparse(raw_url)
    qs = parse_qs(parsed.query)

    connect_args = {"connect_timeout": 5}   # short timeout — fail fast

    if "sslmode" in qs:
        connect_args["sslmode"] = qs["sslmode"][0]
    elif parsed.hostname in ("localhost", "127.0.0.1", "::1"):
        connect_args["sslmode"] = "prefer"
    else:
        connect_args["sslmode"] = "require"  # safe default for hosted DBs

    # Rebuild URL with no query string — psycopg2 chokes on unknown params
    clean_url = parsed._replace(query="").geturl()

    if IS_SERVERLESS:
        # NullPool: no persistent connections — essential for serverless
        from sqlalchemy.pool import NullPool
        engine = create_engine(
            clean_url,
            connect_args=connect_args,
            poolclass=NullPool,
        )
    else:
        engine = create_engine(
            clean_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=2,
            pool_recycle=300,
        )

    return engine


def _make_engine():
    """
    Build the SQLAlchemy engine.
    Called once lazily on first DB access — NOT at module import time.
    """
    raw_url = settings.DATABASE_URL

    if raw_url.startswith("postgresql"):
        logger.info("Connecting to PostgreSQL database...")
        try:
            eng = _build_pg_engine(raw_url)
            # Quick connectivity test
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("PostgreSQL connection established.")
            return eng
        except Exception as exc:
            if IS_SERVERLESS:
                logger.critical(
                    f"[VERCEL] PostgreSQL connection failed: {exc}. "
                    "Ensure DATABASE_URL is set correctly in Vercel → Settings → Environment Variables."
                )
                raise RuntimeError(
                    f"Database unavailable on Vercel: {exc}. "
                    "Set DATABASE_URL in Vercel Environment Variables."
                ) from exc
            logger.warning(f"PostgreSQL failed ({exc}), falling back to SQLite.")

    if IS_SERVERLESS:
        raise RuntimeError(
            "No valid DATABASE_URL configured for Vercel. "
            "Add a PostgreSQL DATABASE_URL in Vercel → Settings → Environment Variables."
        )

    sqlite_url = "sqlite:///./ai_exam_db.db"
    logger.info(f"Using SQLite: {sqlite_url}")
    return create_engine(sqlite_url, connect_args={"check_same_thread": False})


def get_engine():
    """Return the shared engine, creating it on first call."""
    global _engine, _SessionLocal, HAS_PGVECTOR
    if _engine is None:
        _engine = _make_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

        # Detect pgvector support once after engine is ready
        if "sqlite" not in _engine.url.drivername:
            try:
                with _engine.connect() as conn:
                    res = conn.execute(
                        text("SELECT 1 FROM pg_type WHERE typname = 'vector'")
                    ).scalar()
                    if not res:
                        try:
                            with _engine.begin() as t:
                                t.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                            res = conn.execute(
                                text("SELECT 1 FROM pg_type WHERE typname = 'vector'")
                            ).scalar()
                        except Exception:
                            pass
                    HAS_PGVECTOR = bool(res)
                    if HAS_PGVECTOR:
                        logger.info("pgvector extension active.")
                    else:
                        logger.warning("pgvector not found — using TEXT fallback.")
            except Exception as e:
                logger.warning(f"pgvector check failed: {e}")
                HAS_PGVECTOR = False

    return _engine


def get_session_local():
    """Return the SessionLocal factory, initialising engine if needed."""
    get_engine()  # ensures _SessionLocal is set
    return _SessionLocal


# Keep a module-level SessionLocal reference for code that imports it directly
# This is a proxy — actual factory is created lazily on first use
class _LazySessionLocal:
    """Proxy that initialises the real SessionLocal on first call."""
    def __call__(self, *args, **kwargs):
        return get_session_local()(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(get_session_local(), name)


SessionLocal = _LazySessionLocal()


def get_db():
    """FastAPI dependency: yields a DB session and closes it after the request."""
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Creates all tables and runs lightweight migrations.
    Called from FastAPI startup — deferred until the first real request on Vercel.
    """
    eng = get_engine()
    sl = get_session_local()

    try:
        Base.metadata.create_all(bind=eng)
        logger.info("Database schemas created/verified.")

        # Migration: add any missing columns automatically
        user_cols    = ["plain_password TEXT", "name TEXT", "father_name TEXT"]
        question_cols = ["option_a TEXT", "option_b TEXT", "option_c TEXT", "option_d TEXT"]

        with eng.connect() as conn:
            # Users table migrations
            for col_def in user_cols:
                col = col_def.split()[0]
                trans = conn.begin()
                try:
                    conn.execute(text(f"SELECT {col} FROM users LIMIT 1"))
                    trans.commit()
                except Exception:
                    trans.rollback()
                    trans = conn.begin()
                    try:
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_def}"))
                        trans.commit()
                        logger.info(f"Migration: added column {col} to users.")
                    except Exception as err:
                        trans.rollback()
                        logger.error(f"Migration failed for users.{col}: {err}")

            # Questions table migrations
            for col in ["option_a", "option_b", "option_c", "option_d"]:
                trans = conn.begin()
                try:
                    conn.execute(text(f"SELECT {col} FROM questions LIMIT 1"))
                    trans.commit()
                except Exception:
                    trans.rollback()
                    trans = conn.begin()
                    try:
                        conn.execute(text(f"ALTER TABLE questions ADD COLUMN {col} TEXT"))
                        trans.commit()
                        logger.info(f"Migration: added column {col} to questions.")
                    except Exception as err:
                        trans.rollback()
                        logger.error(f"Migration failed for {col}: {err}")

        # Seed default accounts if the users table is empty
        from app.models.db_models import User
        from app.api.auth import hash_password

        db = sl()
        try:
            if db.query(User).count() == 0:
                db.add_all([
                    User(
                        username="admin",
                        hashed_password=hash_password("admin123"),
                        roles="admin,instructor,candidate",
                    ),
                    User(
                        username="rohan_gupta",
                        hashed_password=hash_password("student123"),
                        roles="candidate",
                    ),
                ])
                db.commit()
                logger.info("Seeded default accounts: admin / rohan_gupta")
        except Exception as e:
            logger.error(f"Seeding failed: {e}")
        finally:
            db.close()

    except Exception as e:
        logger.critical(f"init_db failed: {e}")
