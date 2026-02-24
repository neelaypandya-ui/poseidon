"""Authentication REST endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr

from app.services.auth_service import (
    register_user,
    authenticate_user,
    create_access_token,
    get_user_by_id,
)
from app.middleware.auth_middleware import get_current_user

logger = logging.getLogger("poseidon.api.auth")

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str = "analyst"


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/register")
async def register(req: RegisterRequest):
    """Register a new user account."""
    try:
        user = await register_user(req.username, req.email, req.password, req.role)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"status": "registered", "user": user}


@router.post("/login")
async def login(req: LoginRequest):
    """Authenticate and receive a JWT access token."""
    user = await authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": str(user["id"]), "username": user["username"], "role": user["role"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
    }


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    """Return the current authenticated user."""
    if current_user.get("id") == 0:
        return current_user  # anonymous user when auth disabled
    user = await get_user_by_id(current_user["id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
