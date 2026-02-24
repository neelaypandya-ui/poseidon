"""Chain of custody audit logging middleware.

Logs every API request with user context, method, path, status,
client IP, and response time to the audit_log table.
"""

import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.database import get_db
from app.services.auth_service import decode_token

logger = logging.getLogger("poseidon.audit")


class AuditMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that logs every request to the audit_log table."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()

        # Extract user from JWT if present
        user_id = None
        username = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            payload = decode_token(token)
            if payload:
                user_id = int(payload.get("sub", 0)) or None
                username = payload.get("username")

        response = await call_next(request)

        elapsed_ms = (time.time() - start_time) * 1000

        # Skip health checks and websocket upgrades from audit
        path = request.url.path
        if path in ("/health", "/ws/vessels") or path.startswith("/docs") or path.startswith("/openapi"):
            return response

        # Async write to DB — fire and forget
        try:
            db = get_db()
            await db.execute(
                """
                INSERT INTO audit_log
                    (user_id, username, method, path, status_code,
                     client_ip, user_agent, response_time_ms)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                user_id,
                username,
                request.method,
                path,
                response.status_code,
                request.client.host if request.client else None,
                request.headers.get("user-agent", "")[:500],
                round(elapsed_ms, 2),
            )
        except Exception as e:
            # Never let audit logging break the request
            logger.debug("Audit log write failed: %s", e)

        return response
