from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import logging

from app.core.database import init_db
from app.api import admin, evaluation, auth, ws

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
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

# Startup Database Initialization
@app.on_event("startup")
def startup_event():
    logger.info("Initializing database and pgvector extensions...")
    init_db()
    logger.info("Database initialization completed.")

# Register API Routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(evaluation.router)
app.include_router(evaluation.download_router)
app.include_router(ws.router)

# Mount static files directory
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Root Redirect to Web Portal
@app.get("/", include_in_schema=False)
def redirect_to_portal():
    return RedirectResponse(url="/static/index.html")

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
