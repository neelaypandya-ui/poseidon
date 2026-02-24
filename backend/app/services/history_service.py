"""Historical MMSI query service."""

import logging

from app.database import get_db

logger = logging.getLogger("poseidon.history")


async def get_mmsi_history(mmsi: int) -> dict | None:
    db = get_db()
    async with db.acquire() as conn:
        # Check vessel exists
        exists = await conn.fetchval("SELECT 1 FROM vessels WHERE mmsi = $1", mmsi)
        if not exists:
            return None

        # Summary stats
        summary = await conn.fetchrow(
            """
            SELECT
                MIN(timestamp) AS first_seen,
                MAX(timestamp) AS last_seen,
                COUNT(*) AS total_positions,
                COUNT(DISTINCT DATE(timestamp)) AS days_active,
                ST_Extent(geom)::text AS bbox
            FROM vessel_positions
            WHERE mmsi = $1
            """,
            mmsi,
        )

        # Positions by day (last 90 days)
        daily = await conn.fetch(
            """
            SELECT DATE(timestamp) AS day, COUNT(*) AS count,
                   ST_Extent(geom)::text AS bbox
            FROM vessel_positions
            WHERE mmsi = $1 AND timestamp > NOW() - INTERVAL '90 days'
            GROUP BY DATE(timestamp)
            ORDER BY day DESC
            """,
            mmsi,
        )

        # Identity changes
        changes = await conn.fetch(
            """
            SELECT name, ship_type, callsign, imo, destination, observed_at
            FROM vessel_identity_history
            WHERE mmsi = $1
            ORDER BY observed_at DESC
            LIMIT 50
            """,
            mmsi,
        )

        return {
            "mmsi": mmsi,
            "first_seen": summary["first_seen"].isoformat() if summary["first_seen"] else None,
            "last_seen": summary["last_seen"].isoformat() if summary["last_seen"] else None,
            "total_positions": summary["total_positions"],
            "days_active": summary["days_active"],
            "geographic_spread": summary["bbox"],
            "positions_by_day": [
                {
                    "day": str(d["day"]),
                    "count": d["count"],
                    "bbox": d["bbox"],
                }
                for d in daily
            ],
            "identity_changes": [
                {
                    "name": c["name"],
                    "ship_type": c["ship_type"],
                    "callsign": c["callsign"],
                    "imo": c["imo"],
                    "destination": c["destination"],
                    "observed_at": c["observed_at"].isoformat() if c["observed_at"] else None,
                }
                for c in changes
            ],
        }
