"""Forensic message queries and summaries."""

import logging

from app.database import get_db

logger = logging.getLogger("poseidon.forensics")


async def get_forensic_messages(
    mmsi: int, hours: int = 24, flagged_only: bool = False, limit: int = 200
) -> list[dict]:
    db = get_db()
    async with db.acquire() as conn:
        where = "mmsi = $1 AND timestamp > NOW() - make_interval(hours => $2)"
        if flagged_only:
            where += (
                " AND (flag_impossible_speed OR flag_sart_on_non_sar"
                " OR flag_no_identity OR flag_position_jump)"
            )

        rows = await conn.fetch(
            f"""
            SELECT id, mmsi, message_type, raw_json,
                   flag_impossible_speed, flag_sart_on_non_sar,
                   flag_no_identity, flag_position_jump,
                   prev_distance_nm, implied_speed_knots,
                   receiver_class, lat, lon, sog, timestamp, received_at
            FROM ais_raw_messages
            WHERE {where}
            ORDER BY timestamp DESC
            LIMIT $3
            """,
            mmsi,
            hours,
            limit,
        )

        return [
            {
                "id": r["id"],
                "mmsi": r["mmsi"],
                "message_type": r["message_type"],
                "raw_json": r["raw_json"],
                "flag_impossible_speed": r["flag_impossible_speed"],
                "flag_sart_on_non_sar": r["flag_sart_on_non_sar"],
                "flag_no_identity": r["flag_no_identity"],
                "flag_position_jump": r["flag_position_jump"],
                "prev_distance_nm": r["prev_distance_nm"],
                "implied_speed_knots": r["implied_speed_knots"],
                "receiver_class": r["receiver_class"],
                "lat": r["lat"],
                "lon": r["lon"],
                "sog": r["sog"],
                "timestamp": r["timestamp"].isoformat() if r["timestamp"] else None,
                "received_at": r["received_at"].isoformat() if r["received_at"] else None,
            }
            for r in rows
        ]


async def get_forensic_summary(mmsi: int, hours: int = 24) -> dict:
    db = get_db()
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE flag_impossible_speed) AS impossible_speed,
                COUNT(*) FILTER (WHERE flag_sart_on_non_sar) AS sart_on_non_sar,
                COUNT(*) FILTER (WHERE flag_no_identity) AS no_identity,
                COUNT(*) FILTER (WHERE flag_position_jump) AS position_jump,
                COUNT(*) FILTER (WHERE receiver_class = 'terrestrial') AS terrestrial,
                COUNT(*) FILTER (WHERE receiver_class = 'satellite') AS satellite,
                COUNT(*) FILTER (WHERE receiver_class = 'unknown') AS receiver_unknown
            FROM ais_raw_messages
            WHERE mmsi = $1 AND timestamp > NOW() - make_interval(hours => $2)
            """,
            mmsi,
            hours,
        )

        total = row["total"]
        terr = row["terrestrial"]
        sat = row["satellite"]

        return {
            "mmsi": mmsi,
            "hours": hours,
            "total_messages": total,
            "flags": {
                "impossible_speed": row["impossible_speed"],
                "sart_on_non_sar": row["sart_on_non_sar"],
                "no_identity": row["no_identity"],
                "position_jump": row["position_jump"],
            },
            "receiver_breakdown": {
                "terrestrial": terr,
                "terrestrial_pct": round(terr / total * 100, 1) if total else 0,
                "satellite": sat,
                "satellite_pct": round(sat / total * 100, 1) if total else 0,
                "unknown": row["receiver_unknown"],
            },
        }
