"""
Vigil — Authentication API Routes (backend/api/routes/auth.py)

Endpoints:
- POST /api/auth/login: Authenticate user, issue JWT bearer token.
- GET  /api/auth/me: Verify current session and retrieve authenticated profile.
- POST /api/auth/logout: Terminate current session.
- GET  /api/auth/users: List active system users.
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status, Header, Depends
from pydantic import BaseModel, EmailStr
from backend.workflows.user_service import (
    authenticate_user,
    create_access_token,
    decode_access_token,
    get_user_by_id,
    list_users,
)

logger = logging.getLogger("vigil.api.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


class UserDTO(BaseModel):
    user_id: str
    username: str
    email: str
    role: str
    team: str
    access: str
    full_name: str
    is_active: bool = True
    last_login_at: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserDTO


def get_current_user_payload(authorization: Optional[str] = Header(None)) -> dict:
    """Dependency to extract and validate Bearer token from the Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required or malformed.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.split("Bearer ")[1].strip()
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or token is invalid. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


@router.post("/login", response_model=LoginResponse, summary="User Login")
def login(request: LoginRequest):
    """
    Authenticate user credentials (username or email + password).
    Returns a signed JWT access token and user role profile.
    """
    user = authenticate_user(request.username.strip(), request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user)

    user_dto = UserDTO(
        user_id=user["user_id"],
        username=user["username"],
        email=user["email"],
        role=user["role"],
        team=user["team"],
        access=user.get("access_level", "All"),
        full_name=user.get("full_name", user["username"]),
        is_active=bool(user.get("is_active", True)),
        last_login_at=str(user["last_login_at"]) if user.get("last_login_at") else None,
    )

    logger.info(f"User '{user['username']}' authenticated successfully (Role: {user['role']}).")

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=user_dto,
    )


@router.get("/me", response_model=UserDTO, summary="Current User Profile")
def get_me(payload: dict = Depends(get_current_user_payload)):
    """
    Verify current JWT token and return profile details.
    """
    user_id = payload.get("sub") or payload.get("user_id")
    user = get_user_by_id(user_id) if user_id else None

    if not user:
        # Fallback to token payload values if DB temporary disconnect
        return UserDTO(
            user_id=payload.get("user_id", "USR-001"),
            username=payload.get("username", "admin"),
            email=payload.get("email", "audit.officer@vigil.com"),
            role=payload.get("role", "Audit Officer"),
            team=payload.get("team", "Compliance"),
            access=payload.get("access", "All"),
            full_name=payload.get("full_name", "Audit Officer"),
            is_active=True,
        )

    return UserDTO(
        user_id=user["user_id"],
        username=user["username"],
        email=user["email"],
        role=user["role"],
        team=user["team"],
        access=user.get("access_level", "All"),
        full_name=user.get("full_name", user["username"]),
        is_active=bool(user.get("is_active", True)),
        last_login_at=str(user["last_login_at"]) if user.get("last_login_at") else None,
    )


@router.post("/logout", summary="User Logout")
def logout():
    """Client logout acknowledgement."""
    return {"status": "ok", "message": "Successfully logged out."}


@router.get("/users", summary="List All Users")
def get_all_users(payload: dict = Depends(get_current_user_payload)):
    """Retrieve all users in the system."""
    users = list_users()
    return [
        {
            "user_id": u["user_id"],
            "username": u["username"],
            "email": u["email"],
            "role": u["role"],
            "team": u["team"],
            "access": u.get("access_level", "All"),
            "full_name": u.get("full_name", u["username"]),
            "is_active": bool(u.get("is_active", True)),
            "last_login_at": str(u["last_login_at"]) if u.get("last_login_at") else None,
        }
        for u in users
    ]
