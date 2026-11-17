"""Authentication endpoints for dashboard and API users."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from backend.care_models import LoginRequest
from backend.security import (
    authenticate_user,
    create_access_token,
    ensure_bootstrap_users,
    get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.on_event("startup")
def seed_authentication_accounts() -> None:
    ensure_bootstrap_users()


@router.post("/login")
def login(payload: LoginRequest):
    user = authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "expires_in": 8 * 60 * 60,
        "user": {
            "user_id": user["user_id"],
            "username": user["username"],
            "display_name": user.get("display_name", user["username"]),
            "role": user["role"],
        },
    }


@router.get("/me")
def get_me(user=Depends(get_current_user)):
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "display_name": user.get("display_name", user["username"]),
        "role": user["role"],
        "is_active": user.get("is_active", True),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
