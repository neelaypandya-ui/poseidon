"""Background processor: monitor vessel entries/exits for Areas of Interest."""

import asyncio
import logging

from app.config import settings
from app.database import get_db

logger = logging.getLogger("poseidon.aoi_monitor")


async def run_aoi_monitor():
    """Continuously check vessel positions against active AOIs."""
    logger.info("AOI monitor starting...")
    while True:
        try:
            await asyncio.sleep(settings.aoi_check_interval)
            await _check_aoi_crossings()
        except asyncio.CancelledError:
            logger.info("AOI monitor cancelled")
            return
        except Exception as e:
            logger.error("AOI monitor error: %s", e)
            await asyncio.sleep(10)


async def _check_aoi_crossings():
    """Compare current vessel positions against AOI polygons.

    For each active AOI:
    - Find vessels now inside that weren't before -> entry event
    - Find vessels that were inside but aren't now -> exit event
    """
    db = get_db()
    async with db.acquire() as conn:
        # Get all active AOIs
        aois = await conn.fetch(
            "SELECT id, name FROM areas_of_interest WHERE active = TRUE"
        )

        if not aois:
            return

        total_entries = 0
        total_exits = 0

        for aoi in aois:
            aoi_id = aoi["id"]

            # Find vessels currently inside this AOI
            inside_now = await conn.fetch(
                """
                SELECT lvp.mmsi, ST_X(lvp.geom) AS lon, ST_Y(lvp.geom) AS lat,
                       lvp.sog, v.name AS vessel_name, v.ship_type
                FROM latest_vessel_positions lvp
                JOIN vessels v ON v.mmsi = lvp.mmsi
                JOIN areas_of_interest aoi ON aoi.id = $1
                WHERE ST_Contains(aoi.geom, lvp.geom)
                """,
                aoi_id,
            )
            inside_mmsis = {r["mmsi"] for r in inside_now}

            # Get previously tracked presence
            prev_presence = await conn.fetch(
                "SELECT mmsi FROM aoi_vessel_presence WHERE aoi_id = $1",
                aoi_id,
            )
            prev_mmsis = {r["mmsi"] for r in prev_presence}

            # New entries
            entered = inside_mmsis - prev_mmsis
            for r in inside_now:
                if r["mmsi"] in entered:
                    await conn.execute(
                        """
                        INSERT INTO aoi_vessel_presence (aoi_id, mmsi)
                        VALUES ($1, $2) ON CONFLICT DO NOTHING
                        """,
                        aoi_id, r["mmsi"],
                    )
                    await conn.execute(
                        """
                        INSERT INTO aoi_events (aoi_id, mmsi, event_type, vessel_name, ship_type, lon, lat, sog)
                        VALUES ($1, $2, 'entry', $3, $4, $5, $6, $7)
                        """,
                        aoi_id, r["mmsi"], r["vessel_name"], r["ship_type"],
                        r["lon"], r["lat"], r["sog"],
                    )
                    total_entries += 1

            # Exits
            exited = prev_mmsis - inside_mmsis
            for mmsi in exited:
                await conn.execute(
                    "DELETE FROM aoi_vessel_presence WHERE aoi_id = $1 AND mmsi = $2",
                    aoi_id, mmsi,
                )
                await conn.execute(
                    """
                    INSERT INTO aoi_events (aoi_id, mmsi, event_type)
                    VALUES ($1, $2, 'exit')
                    """,
                    aoi_id, mmsi,
                )
                total_exits += 1

        if total_entries > 0 or total_exits > 0:
            logger.info("AOI monitor: %d entries, %d exits", total_entries, total_exits)
