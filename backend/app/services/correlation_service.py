"""Spoof-to-dark correlation: detect coordinated spoof-and-hide operations.

When a spoofed signal appears, did any real vessel nearby go dark at the same time?
This cross-references spoof_signals with dark_vessel_alerts and AIS gaps.
"""

import logging

from app.database import get_db

logger = logging.getLogger("poseidon.correlation")


async def find_spoof_dark_correlations(
    time_window_hours: float = 2.0,
    spatial_radius_nm: float = 100.0,
    limit: int = 50,
) -> list[dict]:
    """Find spoof signals that coincide with nearby vessels going dark.

    A correlation exists when:
    - A spoof_signal was detected within `time_window_hours` of a dark_vessel_alert
    - The dark vessel's last known position is within `spatial_radius_nm` of the spoof
    """
    db = get_db()
    radius_m = spatial_radius_nm * 1852.0

    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                ss.id AS spoof_id,
                ss.mmsi AS spoof_mmsi,
                ss.anomaly_type,
                ST_X(ss.geom) AS spoof_lon,
                ST_Y(ss.geom) AS spoof_lat,
                ss.detected_at AS spoof_time,
                ss.details AS spoof_details,
                da.id AS alert_id,
                da.mmsi AS dark_mmsi,
                ST_X(da.last_known_geom) AS dark_lon,
                ST_Y(da.last_known_geom) AS dark_lat,
                da.last_seen_at AS dark_last_seen,
                da.detected_at AS dark_detected_at,
                da.gap_hours,
                v.name AS dark_vessel_name,
                v.ship_type AS dark_vessel_type,
                ST_Distance(
                    ss.geom::geography,
                    da.last_known_geom::geography
                ) / 1852.0 AS distance_nm,
                ABS(EXTRACT(EPOCH FROM ss.detected_at - da.last_seen_at)) / 3600.0 AS time_gap_hours
            FROM spoof_signals ss
            JOIN dark_vessel_alerts da
                ON ST_DWithin(
                    ss.geom::geography,
                    da.last_known_geom::geography,
                    $1
                )
                AND ABS(EXTRACT(EPOCH FROM ss.detected_at - da.last_seen_at)) < $2 * 3600
            JOIN vessels v ON v.mmsi = da.mmsi
            WHERE ss.mmsi != da.mmsi
            ORDER BY ABS(EXTRACT(EPOCH FROM ss.detected_at - da.last_seen_at)),
                     ST_Distance(ss.geom::geography, da.last_known_geom::geography)
            LIMIT $3
            """,
            radius_m,
            time_window_hours,
            limit,
        )

        return [
            {
                "spoof_signal": {
                    "id": r["spoof_id"],
                    "mmsi": r["spoof_mmsi"],
                    "anomaly_type": r["anomaly_type"],
                    "lon": r["spoof_lon"],
                    "lat": r["spoof_lat"],
                    "time": r["spoof_time"].isoformat() if r["spoof_time"] else None,
                    "details": r["spoof_details"],
                },
                "dark_vessel": {
                    "alert_id": r["alert_id"],
                    "mmsi": r["dark_mmsi"],
                    "name": r["dark_vessel_name"],
                    "ship_type": r["dark_vessel_type"],
                    "lon": r["dark_lon"],
                    "lat": r["dark_lat"],
                    "last_seen": r["dark_last_seen"].isoformat() if r["dark_last_seen"] else None,
                    "alert_detected": r["dark_detected_at"].isoformat() if r["dark_detected_at"] else None,
                    "gap_hours": r["gap_hours"],
                },
                "correlation": {
                    "distance_nm": round(r["distance_nm"], 1) if r["distance_nm"] else None,
                    "time_gap_hours": round(r["time_gap_hours"], 2) if r["time_gap_hours"] else None,
                },
            }
            for r in rows
        ]


async def get_correlation_summary() -> dict:
    """High-level summary of spoof-dark correlations."""
    db = get_db()
    async with db.acquire() as conn:
        total_spoofs = await conn.fetchval(
            "SELECT COUNT(*) FROM spoof_signals"
        )
        total_dark = await conn.fetchval(
            "SELECT COUNT(*) FROM dark_vessel_alerts WHERE status = 'active'"
        )
        correlated = await conn.fetchval(
            """
            SELECT COUNT(DISTINCT ss.id)
            FROM spoof_signals ss
            JOIN dark_vessel_alerts da
                ON ST_DWithin(ss.geom::geography, da.last_known_geom::geography, 185200)
                AND ABS(EXTRACT(EPOCH FROM ss.detected_at - da.last_seen_at)) < 7200
            WHERE ss.mmsi != da.mmsi
            """
        )

        return {
            "total_spoof_signals": total_spoofs,
            "active_dark_alerts": total_dark,
            "correlated_pairs": correlated,
        }
