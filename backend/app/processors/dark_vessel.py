import asyncio
import math
import logging
from datetime import datetime, timezone

from app.config import settings
from app.database import get_db

logger = logging.getLogger("poseidon.dark_vessel")

# Earth radius in nautical miles
EARTH_RADIUS_NM = 3440.065


def dead_reckon(lat: float, lon: float, sog: float, cog: float, hours: float) -> tuple[float, float]:
    """Project position forward using speed and course over ground."""
    if sog is None or cog is None or sog <= 0:
        return lat, lon

    distance_nm = sog * hours
    cog_rad = math.radians(cog)
    lat_rad = math.radians(lat)

    delta_lat = (distance_nm / 60) * math.cos(cog_rad)
    delta_lon = (distance_nm / 60) * math.sin(cog_rad) / math.cos(lat_rad)

    new_lat = lat + delta_lat
    new_lon = lon + delta_lon

    # Clamp
    new_lat = max(-90, min(90, new_lat))
    new_lon = ((new_lon + 180) % 360) - 180

    return new_lat, new_lon


async def run_dark_vessel_detector():
    logger.info("Dark vessel detector starting...")
    while True:
        try:
            await asyncio.sleep(settings.dark_vessel_check_interval)
            await _detect_dark_vessels()
        except asyncio.CancelledError:
            logger.info("Dark vessel detector cancelled")
            return
        except Exception as e:
            logger.error(f"Dark vessel detection error: {e}")
            await asyncio.sleep(10)


async def _detect_dark_vessels():
    db = get_db()

    gap_hours = settings.dark_vessel_gap_hours
    active_window = settings.dark_vessel_active_window_hours

    async with db.acquire() as conn:
        # Find vessels that went dark: last position > gap_hours ago but active within active_window
        dark_vessels = await conn.fetch(
            """
            SELECT lv.mmsi, ST_X(lv.geom) as lon, ST_Y(lv.geom) as lat,
                   lv.sog, lv.cog, lv.timestamp,
                   EXTRACT(EPOCH FROM (NOW() - lv.timestamp)) / 3600.0 as hours_since
            FROM latest_vessel_positions lv
            WHERE lv.timestamp < NOW() - make_interval(hours => $1)
              AND lv.timestamp > NOW() - make_interval(hours => $2)
              AND lv.sog > 0.5
            """,
            gap_hours,
            active_window,
        )

        if not dark_vessels:
            return

        new_alerts = 0
        for v in dark_vessels:
            # Check if already has active alert
            existing = await conn.fetchval(
                """
                SELECT id FROM dark_vessel_alerts
                WHERE mmsi = $1 AND status = 'active'
                """,
                v["mmsi"],
            )
            if existing:
                continue

            hours_since = float(v["hours_since"])
            sog = float(v["sog"] or 0)
            cog = float(v["cog"] or 0)
            pred_lat, pred_lon = dead_reckon(
                v["lat"], v["lon"], sog, cog, hours_since
            )
            search_radius = (sog or 1) * hours_since * 0.5

            await conn.execute(
                """
                INSERT INTO dark_vessel_alerts
                    (mmsi, last_known_geom, predicted_geom, last_sog, last_cog,
                     gap_hours, search_radius_nm, last_seen_at)
                VALUES ($1, ST_SetSRID(ST_MakePoint($2, $3), 4326),
                        ST_SetSRID(ST_MakePoint($4, $5), 4326),
                        $6, $7, $8, $9, $10)
                """,
                v["mmsi"],
                float(v["lon"]), float(v["lat"]),
                pred_lon, pred_lat,
                sog, cog,
                hours_since,
                search_radius,
                v["timestamp"],
            )
            new_alerts += 1

        # Auto-resolve alerts for vessels that reappeared
        resolved = await conn.execute(
            """
            UPDATE dark_vessel_alerts SET
                status = 'resolved',
                resolved_at = NOW()
            WHERE status = 'active'
              AND mmsi IN (
                  SELECT mmsi FROM latest_vessel_positions
                  WHERE timestamp > NOW() - make_interval(hours => $1)
              )
            """,
            gap_hours,
        )

        if new_alerts > 0:
            logger.info(f"Dark vessel detection: {new_alerts} new alerts")
        resolved_count = resolved.split()[-1] if resolved else "0"
        if resolved_count != "0":
            logger.info(f"Dark vessel detection: {resolved_count} alerts resolved")
