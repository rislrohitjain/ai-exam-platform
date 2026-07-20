from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import jwt
import datetime
import hashlib
from typing import Optional, List, Dict, Any

from app.core.database import get_db
from app.models.db_models import User
from app.core.config import settings

router = APIRouter(prefix="/api/auth", tags=["Authentication API"])
security = HTTPBearer()

SECRET_KEY = settings.PDF_SECRET_KEY
ALGORITHM = "HS256"
SALT = "ai_exam_platform_salt_2026"

# --- Pydantic Schemas ---
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6, max_length=100)
    role: str = Field("candidate", pattern="^(admin|candidate)$")
    organization_id: Optional[int] = None

class UserLogin(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str          # Primary role (first role)
    roles: str         # Full list of comma-separated roles
    organization_id: Optional[int] = None

# --- Helper Cryptography Functions ---
def hash_password(password: str) -> str:
    """
    Hashes a password securely using PBKDF2 with SHA-256.
    """
    pw_hash = hashlib.pbkdf2_hmac(
        'sha256', 
        password.encode('utf-8'), 
        SALT.encode('utf-8'), 
        100000
    )
    return pw_hash.hex()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain text password matches the hashed version.
    """
    return hash_password(plain_password) == hashed_password

def create_access_token(username: str, roles: str, organization_id: Optional[int] = None) -> str:
    """
    Generates a JWT access token containing sub, roles, and organization_id.
    """
    payload = {
        "sub": username,
        "roles": roles,
        "org_id": organization_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

# --- Authentication Dependency ---
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to validate JWT tokens and retrieve the authenticated user object.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
        
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return user

# --- Role-Verification Factories ---
def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency to enforce admin access role.
    """
    allowed_roles = current_user.roles.split(",")
    if "admin" not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to perform this action"
        )
    return current_user

def require_instructor(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency to enforce instructor/admin access role.
    """
    allowed_roles = current_user.roles.split(",")
    if "instructor" not in allowed_roles and "admin" not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Instructor or administrator privileges required to perform this action"
        )
    return current_user

def require_candidate(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency to enforce candidate (student) access role.
    """
    allowed_roles = current_user.roles.split(",")
    if "candidate" not in allowed_roles and "admin" not in allowed_roles and "instructor" not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student candidate privileges required to perform this action"
        )
    return current_user

# --- Authentication Endpoints ---
@router.get("/organizations", response_model=List[Dict[str, Any]])
def get_public_organizations(db: Session = Depends(get_db)):
    """
    Lists all active organizations dynamically for public registration dropdowns.
    """
    from app.models.db_models import Organization
    orgs = db.query(Organization).all()
    return [{"id": o.id, "name": o.name, "type": o.type} for o in orgs]

@router.post("/register")
def register_user(payload: UserRegister, db: Session = Depends(get_db)):
    """
    Registers a new system user mapped optionally to an organization.
    """
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username is already taken")
        
    hashed_pw = hash_password(payload.password)
    user = User(
        username=payload.username,
        hashed_password=hashed_pw,
        plain_password=payload.password,
        roles=payload.role,
        organization_id=payload.organization_id
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "User registered successfully", "username": user.username, "roles": user.roles}

@router.post("/login", response_model=TokenResponse)
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticates user credentials and returns a JWT access token.
    """
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
        
    token = create_access_token(user.username, user.roles, user.organization_id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.roles.split(",")[0],
        "roles": user.roles,
        "organization_id": user.organization_id
    }
