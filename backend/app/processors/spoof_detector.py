"""Background processor: detect AIS spoofing anomalies and cluster them.

When new spoof clusters are created, automatically tasks SAR scene search
and VIIRS nighttime light fetch at the cluster coordinates.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database import get_db

logger = logging.getLogger("poseidon.spoof_detector")


async def run_spoof_detector():
    logger.info("Spoof detector starting...")
    while True:
        try:
            await asyncio.sleep(settings.spoof_scan_interval)
            await _detect_anomalies()
            await _cluster_signals()
        except asyncio.CancelledError:
            logger.info("Spoof detector cancelled")
            return
        except Exception as e:
            logger.error(f"Spoof detection error: {e}")
            await asyncio.sleep(10)


async def _detect_anomalies():
    """Scan recent vessel_positions for spoofing anomalies and insert into spoof_signals."""
    db = get_db()
    speed_threshold = settings.spoof_impossible_speed_knots
    window_min = settings.spoof_cluster_window_minutes

    async with db.acquire() as conn:
        # Impossible speed (>50kn, excluding 102.3 no-data marker)
        impossible = await conn.fetch(
            """
            SELECT vp.mmsi, ST_X(vp.geom) AS lon, ST_Y(vp.geom) AS lat,
                   vp.sog, vp.cog, vp.nav_status, vp.timestamp
            FROM vessel_positions vp
            WHERE vp.timestamp > NOW() - make_interval(secs => $1)
              AND vp.sog > $2
              AND ABS(vp.sog - 102.3) > 0.1
              AND NOT EXISTS (
                  SELECT 1 FROM spoof_signals ss
                  WHERE ss.mmsi = vp.mmsi AND ss.anomaly_type = 'impossible_speed'
                    AND ss.detected_at > NOW() - make_interval(secs => $1)
                    AND ABS(EXTRACT(EPOCH FROM ss.detected_at - vp.timestamp)) < 60
              )
            """,
            settings.spoof_scan_interval,
            speed_threshold,
        )

        for r in impossible:
            await conn.execute(
                """
                INSERT INTO spoof_signals (mmsi, anomaly_type, geom, sog, cog, nav_status, details, detected_at)
                VALUES ($1, 'impossible_speed', ST_SetSRID(ST_MakePoint($2, $3), 4326),
                        $4, $5, $6, $7::jsonb, $8)
                """,
                r["mmsi"], r["lon"], r["lat"], r["sog"], r["cog"], r["nav_status"],
                f'{{"sog": {r["sog"]}}}',
                r["timestamp"],
            )

        # SART on non-SAR vessel
        sart = await conn.fetch(
            """
            SELECT vp.mmsi, ST_X(vp.geom) AS lon, ST_Y(vp.geom) AS lat,
                   vp.sog, vp.cog, vp.nav_status, vp.timestamp
            FROM vessel_positions vp
            JOIN vessels v ON v.mmsi = vp.mmsi
            WHERE vp.timestamp > NOW() - make_interval(secs => $1)
              AND vp.nav_status = 'ais_sart'
              AND v.ship_type != 'sar'
              AND NOT EXISTS (
                  SELECT 1 FROM spoof_signals ss
                  WHERE ss.mmsi = vp.mmsi AND ss.anomaly_type = 'sart_on_non_sar'
                    AND ss.detected_at > NOW() - make_interval(secs => $1)
              )
            """,
            settings.spoof_scan_interval,
        )

        for r in sart:
            await conn.execute(
                """
                INSERT INTO spoof_signals (mmsi, anomaly_type, geom, sog, cog, nav_status, details, detected_at)
                VALUES ($1, 'sart_on_non_sar', ST_SetSRID(ST_MakePoint($2, $3), 4326),
                        $4, $5, $6, '{"reason": "ais_sart on non-sar vessel"}'::jsonb, $7)
                """,
                r["mmsi"], r["lon"], r["lat"], r["sog"], r["cog"], r["nav_status"],
                r["timestamp"],
            )

        # No identity (no name, no IMO, no callsign)
        no_id = await conn.fetch(
            """
            SELECT vp.mmsi, ST_X(vp.geom) AS lon, ST_Y(vp.geom) AS lat,
                   vp.sog, vp.cog, vp.nav_status, vp.timestamp
            FROM vessel_positions vp
            JOIN vessels v ON v.mmsi = vp.mmsi
            WHERE vp.timestamp > NOW() - make_interval(secs => $1)
              AND v.name IS NULL AND v.imo IS NULL AND v.callsign IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM spoof_signals ss
                  WHERE ss.mmsi = vp.mmsi AND ss.anomaly_type = 'no_identity'
                    AND ss.detected_at > NOW() - make_interval(secs => $1)
              )
            """,
            settings.spoof_scan_interval,
        )

        for r in no_id:
            await conn.execute(
                """
                INSERT INTO spoof_signals (mmsi, anomaly_type, geom, sog, cog, nav_status, details, detected_at)
                VALUES ($1, 'no_identity', ST_SetSRID(ST_MakePoint($2, $3), 4326),
                        $4, $5, $6, '{"reason": "no name/imo/callsign"}'::jsonb, $7)
                """,
                r["mmsi"], r["lon"], r["lat"], r["sog"], r["cog"], r["nav_status"],
                r["timestamp"],
            )

        # Position jumps (>100nm in <5min between sequential positions)
        jumps = await conn.fetch(
            """
            WITH recent AS (
                SELECT mmsi, geom, timestamp,
                       LAG(geom) OVER (PARTITION BY mmsi ORDER BY timestamp) AS prev_geom,
                       LAG(timestamp) OVER (PARTITION BY mmsi ORDER BY timestamp) AS prev_ts
                FROM vessel_positions
                WHERE timestamp > NOW() - make_interval(secs => $1)
            )
            SELECT mmsi, ST_X(geom) AS lon, ST_Y(geom) AS lat,
                   ST_Distance(geom::geography, prev_geom::geography) / 1852.0 AS dist_nm,
                   EXTRACT(EPOCH FROM timestamp - prev_ts) / 60.0 AS dt_min,
                   timestamp
            FROM recent
            WHERE prev_geom IS NOT NULL
              AND ST_Distance(geom::geography, prev_geom::geography) / 1852.0 > 100
              AND EXTRACT(EPOCH FROM timestamp - prev_ts) / 60.0 < 5
              AND NOT EXISTS (
                  SELECT 1 FROM spoof_signals ss
                  WHERE ss.mmsi = recent.mmsi AND ss.anomaly_type = 'position_jump'
                    AND ss.detected_at > NOW() - make_interval(secs => $1)
                    AND ABS(EXTRACT(EPOCH FROM ss.detected_at - recent.timestamp)) < 60
              )
            """,
            settings.spoof_scan_interval,
        )

        for r in jumps:
            await conn.execute(
                """
                INSERT INTO spoof_signals (mmsi, anomaly_type, geom, details, detected_at)
                VALUES ($1, 'position_jump', ST_SetSRID(ST_MakePoint($2, $3), 4326),
                        $4::jsonb, $5)
                """,
                r["mmsi"], r["lon"], r["lat"],
                f'{{"distance_nm": {r["dist_nm"]:.1f}, "dt_minutes": {r["dt_min"]:.1f}}}',
                r["timestamp"],
            )

        total = len(impossible) + len(sart) + len(no_id) + len(jumps)
        if total > 0:
            logger.info(
                f"Spoof anomalies detected: {len(impossible)} impossible_speed, "
                f"{len(sart)} sart, {len(no_id)} no_identity, {len(jumps)} position_jump"
            )


async def _cluster_signals():
    """Group ungrouped spoof_signals within time windows into clusters."""
    db = get_db()
    window_min = settings.spoof_cluster_window_minutes

    async with db.acquire() as conn:
        # Get ungrouped signals
        ungrouped = await conn.fetch(
            """
            SELECT id, mmsi, anomaly_type, geom, detected_at
            FROM spoof_signals
            WHERE cluster_id IS NULL
            ORDER BY detected_at
            """
        )

        if not ungrouped:
            return

        # Simple time-window clustering
        clusters = []
        current_cluster = [ungrouped[0]]

        for sig in ungrouped[1:]:
            time_diff = (sig["detected_at"] - current_cluster[0]["detected_at"]).total_seconds() / 60.0
            if time_diff <= window_min:
                current_cluster.append(sig)
            else:
                if len(current_cluster) >= 2:
                    clusters.append(current_cluster)
                current_cluster = [sig]

        if len(current_cluster) >= 2:
            clusters.append(current_cluster)

        for cluster_signals in clusters:
            signal_ids = [s["id"] for s in cluster_signals]
            anomaly_types = list(set(str(s["anomaly_type"]) for s in cluster_signals))
            window_start = cluster_signals[0]["detected_at"]
            window_end = cluster_signals[-1]["detected_at"]

            # Create cluster with centroid computed by PostGIS
            cluster_id = await conn.fetchval(
                """
                INSERT INTO spoof_clusters (signal_count, centroid, radius_nm,
                                            window_start, window_end, anomaly_types)
                SELECT
                    $1,
                    ST_Centroid(ST_Collect(geom)),
                    COALESCE(
                        MAX(ST_Distance(geom::geography, ST_Centroid(ST_Collect(geom) OVER ())::geography)) / 1852.0,
                        0
                    ),
                    $2, $3, $4::text[]
                FROM spoof_signals WHERE id = ANY($5)
                RETURNING id
                """,
                len(signal_ids),
                window_start,
                window_end,
                anomaly_types,
                signal_ids,
            )

            if cluster_id is None:
                # Fallback: simpler insert without inline window function
                cluster_id = await conn.fetchval(
                    """
                    WITH pts AS (
                        SELECT ST_Collect(geom) AS collected,
                               ST_Centroid(ST_Collect(geom)) AS centroid
                        FROM spoof_signals WHERE id = ANY($5)
                    )
                    INSERT INTO spoof_clusters (signal_count, centroid, radius_nm,
                                                window_start, window_end, anomaly_types)
                    SELECT $1, pts.centroid, 0, $2, $3, $4::text[]
                    FROM pts
                    RETURNING id
                    """,
                    len(signal_ids),
                    window_start,
                    window_end,
                    anomaly_types,
                    signal_ids,
                )

            if cluster_id:
                await conn.execute(
                    "UPDATE spoof_signals SET cluster_id = $1 WHERE id = ANY($2)",
                    cluster_id,
                    signal_ids,
                )
                # Auto-task SAR + VIIRS intelligence at cluster location
                centroid = await conn.fetchrow(
                    "SELECT ST_X(centroid) AS lon, ST_Y(centroid) AS lat FROM spoof_clusters WHERE id = $1",
                    cluster_id,
                )
                if centroid and centroid["lon"] is not None:
                    asyncio.create_task(
                        _auto_task_intelligence(cluster_id, centroid["lon"], centroid["lat"])
                    )

        if clusters:
            logger.info(f"Created {len(clusters)} spoof clusters from {len(ungrouped)} ungrouped signals")


async def _auto_task_intelligence(cluster_id: int, lon: float, lat: float):
    """Auto-task SAR and VIIRS intelligence collection at spoof cluster coordinates."""
    margin = 0.83  # ~50nm in degrees
    bbox = (lon - margin, lat - margin, lon + margin, lat + margin)

    # Auto-task SAR scene search
    try:
        from app.services.sar_service import search_scenes

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        scenes = await search_scenes(
            bbox=bbox,
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
            limit=5,
        )
        if scenes:
            logger.info(
                "Auto-tasked SAR: %d scenes near spoof cluster %d (%.2f, %.2f)",
                len(scenes), cluster_id, lon, lat,
            )
    except Exception as e:
        logger.warning("SAR auto-task failed for cluster %d: %s", cluster_id, e)

    # Auto-task VIIRS nighttime light fetch
    try:
        from app.services.viirs_service import fetch_viirs_data, detect_anomalies

        inserted = await fetch_viirs_data(bbox=bbox, days=2)
        if inserted > 0:
            anomaly_count = await detect_anomalies(bbox=bbox)
            logger.info(
                "Auto-tasked VIIRS: %d obs, %d anomalies near spoof cluster %d",
                inserted, anomaly_count, cluster_id,
            )
    except Exception as e:
        logger.warning("VIIRS auto-task failed for cluster %d: %s", cluster_id, e)
