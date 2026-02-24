"""JWT authentication service.

Handles user registration, login, password hashing, and JWT token generation.
Auth is gated behind the `auth_enabled` config flag.
"""

import logging
from datetime import datetime, timezone, timedelta

from passlib.context import CryptContext
from jose import jwt, JWTError

from app.database import get_db
from app.config import settings

logger = logging.getLogger("poseidon.auth_service")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def register_user(username: str, email: str, password: str, role: str = "analyst") -> dict:
    """Register a new user. Returns user dict (without password)."""
    db = get_db()
    hashed = hash_password(password)

    try:
        row = await db.fetchrow(
            """
            INSERT INTO users (username, email, hashed_password, role)
            VALUES ($1, $2, $3, $4)
            RETURNING id, username, email, role, is_active, created_at
            """,
            username, email, hashed, role,
        )
    except Exception as e:
        if "unique" in str(e).lower():
            raise ValueError("Username or email already exists")
        raise

    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "role": row["role"],
        "is_active": row["is_active"],
        "created_at": row["created_at"].isoformat(),
    }


async def authenticate_user(username: str, password: str) -> dict | None:
    """Authenticate a user by username and password. Returns user dict or None."""
    db = get_db()
    row = await db.fetchrow(
        "SELECT id, username, email, hashed_password, role, is_active FROM users WHERE username = $1",
        username,
    )

    if not row:
        return None

    if not row["is_active"]:
        return None

    if not verify_password(password, row["hashed_password"]):
        return None

    # Update last login
    await db.execute(
        "UPDATE users SET last_login = NOW() WHERE id = $1",
        row["id"],
    )

    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "role": row["role"],
    }


async def get_user_by_id(user_id: int) -> dict | None:
    """Look up a user by ID."""
    db = get_db()
    row = await db.fetchrow(
        "SELECT id, username, email, role, is_active, created_at, last_login FROM users WHERE id = $1",
        user_id,
    )
    if not row:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "role": row["role"],
        "is_active": row["is_active"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "last_login": row["last_login"].isoformat() if row["last_login"] else None,
    }
