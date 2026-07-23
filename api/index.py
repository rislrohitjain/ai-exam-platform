import os
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("vercel_entry")

# Add project root to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Set VERCEL environment variable explicitly
os.environ["VERCEL"] = "1"

try:
    logger.info("Loading FastAPI application...")
    from app.main import app
    logger.info("FastAPI application loaded successfully.")
except Exception as exc:
    import traceback
    logger.error(f"FATAL: Failed to import app.main — {exc}\n{traceback.format_exc()}")
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    _import_error = str(exc)
    _traceback = traceback.format_exc()

    app = FastAPI(title="Boot Error")

    @app.api_route("/", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
    def show_boot_error(full_path: str = ""):
        return JSONResponse(
            status_code=500,
            content={
                "error": "Application failed to start",
                "detail": _import_error,
                "traceback": _traceback,
                "hint": "Check Vercel function logs or fix the import error above.",
            },
        )

# Vercel entrypoint exports
handler = app
