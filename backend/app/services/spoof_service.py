"""Spoof cluster query service."""

import logging

from app.database import get_db

logger = logging.getLogger("poseidon.spoof_service")


async def get_spoof_clusters(status: str = "active", limit: int = 50) -> list[dict]:
    db = get_db()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, signal_count,
                   ST_X(centroid) AS centroid_lon, ST_Y(centroid) AS centroid_lat,
                   radius_nm, window_start, window_end, anomaly_types,
                   status, created_at
            FROM spoof_clusters
            WHERE status = $1::alert_status
            ORDER BY created_at DESC
            LIMIT $2
            """,
            status,
            limit,
        )

        return [
            {
                "id": r["id"],
                "signal_count": r["signal_count"],
                "centroid_lon": r["centroid_lon"],
                "centroid_lat": r["centroid_lat"],
                "radius_nm": r["radius_nm"],
                "window_start": r["window_start"].isoformat() if r["window_start"] else None,
                "window_end": r["window_end"].isoformat() if r["window_end"] else None,
                "anomaly_types": r["anomaly_types"] or [],
                "status": r["status"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]


async def get_spoof_cluster_detail(cluster_id: int) -> dict | None:
    db = get_db()
    async with db.acquire() as conn:
        cluster = await conn.fetchrow(
            """
            SELECT id, signal_count,
                   ST_X(centroid) AS centroid_lon, ST_Y(centroid) AS centroid_lat,
                   radius_nm, window_start, window_end, anomaly_types,
                   status, created_at
            FROM spoof_clusters
            WHERE id = $1
            """,
            cluster_id,
        )

        if not cluster:
            return None

        signals = await conn.fetch(
            """
            SELECT id, mmsi, anomaly_type,
                   ST_X(geom) AS lon, ST_Y(geom) AS lat,
                   sog, cog, nav_status, details, detected_at
            FROM spoof_signals
            WHERE cluster_id = $1
            ORDER BY detected_at
            """,
            cluster_id,
        )

        return {
            "id": cluster["id"],
            "signal_count": cluster["signal_count"],
            "centroid_lon": cluster["centroid_lon"],
            "centroid_lat": cluster["centroid_lat"],
            "radius_nm": cluster["radius_nm"],
            "window_start": cluster["window_start"].isoformat() if cluster["window_start"] else None,
            "window_end": cluster["window_end"].isoformat() if cluster["window_end"] else None,
            "anomaly_types": cluster["anomaly_types"] or [],
            "status": cluster["status"],
            "created_at": cluster["created_at"].isoformat() if cluster["created_at"] else None,
            "signals": [
                {
                    "id": s["id"],
                    "mmsi": s["mmsi"],
                    "anomaly_type": s["anomaly_type"],
                    "lon": s["lon"],
                    "lat": s["lat"],
                    "sog": s["sog"],
                    "cog": s["cog"],
                    "nav_status": s["nav_status"],
                    "details": s["details"],
                    "detected_at": s["detected_at"].isoformat() if s["detected_at"] else None,
                }
                for s in signals
            ],
        }


async def get_spoof_signals_for_mmsi(mmsi: int, hours: int = 24) -> list[dict]:
    db = get_db()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, mmsi, anomaly_type,
                   ST_X(geom) AS lon, ST_Y(geom) AS lat,
                   sog, cog, nav_status, details, detected_at, cluster_id
            FROM spoof_signals
            WHERE mmsi = $1 AND detected_at > NOW() - make_interval(hours => $2)
            ORDER BY detected_at DESC
            """,
            mmsi,
            hours,
        )

        return [
            {
                "id": r["id"],
                "mmsi": r["mmsi"],
                "anomaly_type": r["anomaly_type"],
                "lon": r["lon"],
                "lat": r["lat"],
                "sog": r["sog"],
                "cog": r["cog"],
                "nav_status": r["nav_status"],
                "details": r["details"],
                "detected_at": r["detected_at"].isoformat() if r["detected_at"] else None,
                "cluster_id": r["cluster_id"],
            }
            for r in rows
        ]
