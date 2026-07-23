import os
import sys

# Ensure project root directory is in sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

os.environ["VERCEL"] = "1"

# Import FastAPI application
from app.main import app as _app

# Top-level assignments for Vercel AST detection
app = _app
application = _app
handler = _app
