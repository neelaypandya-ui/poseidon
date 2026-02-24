"""Audit log REST endpoints."""

import logging

from fastapi import APIRouter, Query

from app.database import get_db

logger = logging.getLogger("poseidon.api.audit")

router = APIRouter()


@router.get("")
async def list_audit_logs(
    hours: int = Query(24, ge=1, le=720),
    path_filter: str | None = Query(None),
    username: str | None = Query(None),
    limit: int = Query(200, ge=1, le=2000),
):
    """Query recent audit log entries."""
    db = get_db()
    conditions = ["created_at > NOW() - make_interval(hours => $1)"]
    params: list = [hours]
    idx = 2

    if path_filter:
        conditions.append(f"path ILIKE ${idx}")
        params.append(f"%{path_filter}%")
        idx += 1

    if username:
        conditions.append(f"username = ${idx}")
        params.append(username)
        idx += 1

    where = " AND ".join(conditions)

    rows = await db.fetch(
        f"""
        SELECT id, user_id, username, method, path, status_code,
               client_ip, response_time_ms, created_at
        FROM audit_log
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT {limit}
        """,
        *params,
    )

    return {
        "count": len(rows),
        "entries": [
            {
                "id": r["id"],
                "user_id": r["user_id"],
                "username": r["username"],
                "method": r["method"],
                "path": r["path"],
                "status_code": r["status_code"],
                "client_ip": r["client_ip"],
                "response_time_ms": r["response_time_ms"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
    }


@router.get("/stats")
async def audit_stats(hours: int = Query(24, ge=1, le=720)):
    """Get audit log statistics."""
    db = get_db()

    row = await db.fetchrow(
        """
        SELECT COUNT(*) as total_requests,
               COUNT(DISTINCT username) as unique_users,
               AVG(response_time_ms) as avg_response_ms,
               MAX(response_time_ms) as max_response_ms,
               COUNT(*) FILTER (WHERE status_code >= 400) as error_count
        FROM audit_log
        WHERE created_at > NOW() - make_interval(hours => $1)
        """,
        hours,
    )

    return {
        "period_hours": hours,
        "total_requests": row["total_requests"],
        "unique_users": row["unique_users"],
        "avg_response_ms": round(float(row["avg_response_ms"] or 0), 2),
        "max_response_ms": round(float(row["max_response_ms"] or 0), 2),
        "error_count": row["error_count"],
    }
