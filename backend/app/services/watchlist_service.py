"""Watchlist management — track vessels of interest."""

import logging

from app.database import get_db

logger = logging.getLogger("poseidon.watchlist")


async def get_watchlist() -> list[dict]:
    """Return all watchlisted vessels with latest position info."""
    db = get_db()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT w.id, w.mmsi, w.label, w.reason,
                   w.alert_on_position, w.alert_on_dark, w.alert_on_spoof,
                   w.created_at,
                   v.name AS vessel_name, v.ship_type, v.imo,
                   lvp.sog, lvp.nav_status,
                   ST_X(lvp.geom) AS lon, ST_Y(lvp.geom) AS lat,
                   lvp.timestamp AS last_seen
            FROM watchlist w
            LEFT JOIN vessels v ON v.mmsi = w.mmsi
            LEFT JOIN latest_vessel_positions lvp ON lvp.mmsi = w.mmsi
            ORDER BY w.created_at DESC
            """
        )

    return [
        {
            "id": r["id"],
            "mmsi": r["mmsi"],
            "label": r["label"],
            "reason": r["reason"],
            "alert_on_position": r["alert_on_position"],
            "alert_on_dark": r["alert_on_dark"],
            "alert_on_spoof": r["alert_on_spoof"],
            "created_at": r["created_at"].isoformat(),
            "vessel_name": r["vessel_name"],
            "ship_type": r["ship_type"],
            "imo": r["imo"],
            "lon": float(r["lon"]) if r["lon"] else None,
            "lat": float(r["lat"]) if r["lat"] else None,
            "sog": float(r["sog"]) if r["sog"] else None,
            "nav_status": r["nav_status"],
            "last_seen": r["last_seen"].isoformat() if r["last_seen"] else None,
        }
        for r in rows
    ]


async def add_to_watchlist(mmsi: int, label: str | None = None, reason: str | None = None) -> dict:
    """Add a vessel to the watchlist."""
    db = get_db()
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO watchlist (mmsi, label, reason)
            VALUES ($1, $2, $3)
            ON CONFLICT (mmsi) DO UPDATE SET
                label = COALESCE(EXCLUDED.label, watchlist.label),
                reason = COALESCE(EXCLUDED.reason, watchlist.reason)
            RETURNING id, mmsi, label, reason, created_at
            """,
            mmsi, label, reason,
        )

    logger.info("Added MMSI %d to watchlist: %s", mmsi, label or "no label")
    return {
        "id": row["id"],
        "mmsi": row["mmsi"],
        "label": row["label"],
        "reason": row["reason"],
        "created_at": row["created_at"].isoformat(),
    }


async def remove_from_watchlist(mmsi: int) -> bool:
    """Remove a vessel from the watchlist."""
    db = get_db()
    async with db.acquire() as conn:
        result = await conn.execute("DELETE FROM watchlist WHERE mmsi = $1", mmsi)
    deleted = result.split()[-1] != "0"
    if deleted:
        logger.info("Removed MMSI %d from watchlist", mmsi)
    return deleted


async def is_watched(mmsi: int) -> bool:
    """Check if a vessel is on the watchlist."""
    db = get_db()
    async with db.acquire() as conn:
        return await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM watchlist WHERE mmsi = $1)", mmsi,
        )
