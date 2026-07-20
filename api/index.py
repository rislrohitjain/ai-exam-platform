import sys
import traceback
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("vercel_entry")

try:
    logger.info("Loading FastAPI application...")
    from app.main import app
    logger.info("FastAPI application loaded successfully.")
except Exception as exc:
    # If the real app fails to import, serve a diagnostic app instead of
    # a cryptic NOT_FOUND so the error is visible in browser / logs.
    logger.error(f"FATAL: Failed to import app.main — {exc}\n{traceback.format_exc()}")

    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    _import_error = str(exc)
    _traceback    = traceback.format_exc()

    app = FastAPI(title="Boot Error")

    @app.get("/{full_path:path}")
    def show_boot_error(full_path: str):
        return JSONResponse(
            status_code=500,
            content={
                "error":     "Application failed to start",
                "detail":    _import_error,
                "traceback": _traceback,
                "hint":      "Check Vercel function logs or fix the import error above.",
            },
        )
