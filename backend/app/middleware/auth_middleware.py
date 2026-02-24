"""JWT authentication middleware and dependency.

When `auth_enabled` is False (default), all requests pass through
with a synthetic anonymous user. When True, a valid JWT Bearer token
is required on protected endpoints.
"""

import logging

from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings
from app.services.auth_service import decode_token

logger = logging.getLogger("poseidon.auth_middleware")

security = HTTPBearer(auto_error=False)


async def get_current_user(request: Request) -> dict:
    """FastAPI dependency: extract and validate JWT from Authorization header.

    If auth_enabled is False, returns an anonymous user context.
    """
    if not settings.auth_enabled:
        return {"id": 0, "username": "anonymous", "role": "admin"}

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authentication token")

    token = auth_header.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {
        "id": int(payload.get("sub", 0)),
        "username": payload.get("username", "unknown"),
        "role": payload.get("role", "viewer"),
    }


def require_role(*roles: str):
    """Dependency factory: require the user to have one of the given roles."""
    async def checker(request: Request):
        user = await get_current_user(request)
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker
