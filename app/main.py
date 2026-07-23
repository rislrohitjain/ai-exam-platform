from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
import logging
from logging.handlers import RotatingFileHandler

from app.core.config import settings
from app.core.database import init_db
from app.api import admin, evaluation, auth, ws

IS_SERVERLESS = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

# Safe logger configuration
log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log_level = logging.DEBUG if getattr(settings, "DEBUG", True) else logging.INFO

console_handler = logging.StreamHandler()
console_handler.setLevel(log_level)
console_handler.setFormatter(log_formatter)

handlers = [console_handler]

# Only attempt file logging in non-serverless local environment
if not IS_SERVERLESS:
    try:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        LOGS_DIR = os.path.join(BASE_DIR, "logs")
        os.makedirs(LOGS_DIR, exist_ok=True)

        app_file_handler = RotatingFileHandler(
            os.path.join(LOGS_DIR, "app.log"),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        app_file_handler.setLevel(log_level)
        app_file_handler.setFormatter(log_formatter)
        handlers.append(app_file_handler)

        error_file_handler = RotatingFileHandler(
            os.path.join(LOGS_DIR, "error.log"),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        error_file_handler.setLevel(logging.ERROR)
        error_file_handler.setFormatter(log_formatter)
        handlers.append(error_file_handler)
    except Exception as e:
        print(f"Notice: File logging disabled due to environment permissions: {e}")

root_logger = logging.getLogger()
root_logger.setLevel(log_level)
root_logger.handlers = handlers

logger = logging.getLogger("main")

# Initialize FastAPI with metadata
app = FastAPI(
    title="Advanced AI Exam & Evaluation Platform",
    description="Production-ready FastAPI backend for AI-assisted automated grading and verifiable certification.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup Database Initialization — runs in background thread so cold starts don't hang
@app.on_event("startup")
def startup_event():
    import threading
    def _init():
        try:
            logger.info("Background: initializing database...")
            init_db()
            logger.info("Background: database initialization complete.")
        except Exception as e:
            logger.error(f"Background DB init failed: {e}")
    threading.Thread(target=_init, daemon=True).start()


# Register API Routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(evaluation.router)
app.include_router(evaluation.download_router)
app.include_router(ws.router)

# Mount static files directory (guaranteed absolute path resolution)
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(STATIC_DIR):
    try:
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    except Exception as e:
        logger.warning(f"Static files could not be mounted: {e}")

# Database Connection Check Endpoint
@app.get("/checkdb")
@app.get("/api/checkdb")
def check_db_connection():
    """
    Check database connectivity and return status and connection details.
    """
    from sqlalchemy import text
    from app.core.database import get_engine
    from app.core.config import Settings
    from urllib.parse import urlparse

    current_settings = Settings()
    db_url = current_settings.DATABASE_URL
    parsed = urlparse(db_url)

    safe_url = db_url
    if parsed.password:
        safe_url = db_url.replace(parsed.password, "*****")

    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    db_name = parsed.path.lstrip('/') if parsed.path else "ai-exam-platform"
    username = parsed.username or "postgres"

    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()

        drivername = engine.url.drivername if hasattr(engine, 'url') else "postgresql"
        is_sqlite = "sqlite" in drivername

        return {
            "status": "connected",
            "message": "Database connection established successfully.",
            "database_type": "SQLite" if is_sqlite else "PostgreSQL",
            "details": {
                "host": host,
                "port": port,
                "database": db_name,
                "user": username,
                "connection_url": safe_url,
                "ping_result": result
            }
        }
    except Exception as exc:
        logger.error(f"DB connection check failed: {exc}")
        return {
            "status": "failed",
            "message": f"Database connection failed: {str(exc)}",
            "details": {
                "host": host,
                "port": port,
                "database": db_name,
                "user": username,
                "connection_url": safe_url,
                "error": str(exc)
            }
        }


# Root Route: Serve Portal HTML directly
@app.get("/", include_in_schema=False)
def redirect_to_portal():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return RedirectResponse(url="/docs")

# SPA Fallback Route for non-API client-side paths
@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str):
    if full_path.startswith("api/") or full_path in ("checkdb", "docs", "redoc", "openapi.json"):
        raise HTTPException(status_code=404, detail="Not Found")
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="Not Found")

if __name__ == "__main__":
    import uvicorn
    import socket

    local_ips = ["127.0.0.1"]
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127.") and ip not in local_ips:
                local_ips.append(ip)
    except Exception:
        pass

    print("\n" + "=" * 80)
    print("Advanced AI Exam & Evaluation Platform is Starting...")
    print("=" * 80)
    print("Web Portal Access Links:")
    for ip in local_ips:
        name = "Localhost" if ip == "127.0.0.1" else f"Local Network IP ({ip})"
        print(f"   http://{ip}:8000/static/index.html  [{name}]")
    print("=" * 80 + "\n")

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

