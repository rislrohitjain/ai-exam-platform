import os
from app.core.config_local import local_settings, LocalSettings
from app.core.config_vercel import vercel_settings, VercelSettings

IS_SERVERLESS = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

def get_settings():
    """
    Returns appropriate settings object depending on environment:
    - On Vercel / Serverless: returns vercel_settings (configured for Neon DB)
    - On Localhost: returns local_settings (configured for Localhost PostgreSQL)
    Can be overridden by explicit environment variables if present.
    """
    if IS_SERVERLESS:
        return vercel_settings
    
    # If DATABASE_URL env var explicitly contains neon tech, use vercel settings
    env_db_url = os.getenv("DATABASE_URL", "")
    if "neon.tech" in env_db_url:
        return vercel_settings
        
    return local_settings

settings = get_settings()
Settings = LocalSettings if not IS_SERVERLESS else VercelSettings
