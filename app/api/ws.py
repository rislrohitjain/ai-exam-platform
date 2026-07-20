from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import Dict, Any, List
import json
import logging
import jwt

from app.core.database import SessionLocal
from app.models.db_models import User, QuestionPaper, Organization
from app.core.config import settings

logger = logging.getLogger("ws_activity")
router = APIRouter(prefix="/api/ws", tags=["WebSocket API"])

SECRET_KEY = settings.PDF_SECRET_KEY
ALGORITHM = "HS256"

class ConnectionManager:
    def __init__(self):
        # Maps active WebSocket connections to metadata dictionary: {websocket: {"username": "...", "roles": "..."}}
        self.active_connections: Dict[WebSocket, Dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[websocket] = {"username": "anonymous", "roles": "unknown"}

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    async def set_metadata(self, websocket: WebSocket, username: str, roles: str):
        if websocket in self.active_connections:
            self.active_connections[websocket] = {"username": username, "roles": roles}

    async def broadcast_to_admins(self, payload_dict: Dict[str, Any]):
        message_str = json.dumps(payload_dict)
        # Admins are identified by having 'admin' in their roles comma-separated string
        admins = [ws for ws, meta in self.active_connections.items() if "admin" in meta.get("roles", "")]
        for admin_ws in admins:
            try:
                await admin_ws.send_text(message_str)
            except Exception as e:
                logger.error(f"Error sending WebSocket broadcast: {e}")

    async def send_activity(self, username: str, action: str, details: str = ""):
        """
        Public method to broadcast user events. Resolves roles and organization names dynamically.
        """
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            if user:
                roles = user.roles
                org_name = user.organization.name if user.organization else "System Global"
            else:
                roles = "unknown"
                org_name = "System Global"
        except Exception:
            roles = "unknown"
            org_name = "System Global"
        finally:
            db.close()

        await self.broadcast_to_admins({
            "type": "activity",
            "username": username,
            "roles": roles,
            "org_name": org_name,
            "action": action,
            "details": details,
            "timestamp": timestamp
        })

manager = ConnectionManager()

@router.websocket("/activity")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data_str = await websocket.receive_text()
            try:
                data = json.loads(data_str)
            except Exception:
                continue

            event = data.get("event")
            
            # Authenticate the WebSocket connection using JWT bearer token
            if event == "auth":
                token = data.get("token")
                if not token:
                    continue
                
                try:
                    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                    username = payload.get("sub")
                    roles = payload.get("roles", "candidate")
                    
                    if username:
                        await manager.set_metadata(websocket, username, roles)
                        await manager.send_activity(username, "Logged In")
                except Exception as jwt_err:
                    logger.error(f"WS connection authentication failed: {jwt_err}")

            # Broadcast custom student/admin frontend actions to the dashboard
            elif event == "activity":
                meta = manager.active_connections.get(websocket, {})
                username = meta.get("username", "anonymous")
                action = data.get("action", "Idle")
                details = data.get("details", "")

                await manager.send_activity(username, action, details)
                
    except WebSocketDisconnect:
        meta = manager.active_connections.get(websocket, {})
        username = meta.get("username", "anonymous")
        
        manager.disconnect(websocket)
        if username != "anonymous":
            await manager.send_activity(username, "Disconnected")
