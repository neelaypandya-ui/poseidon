"""EEZ boundary crossing monitor.

Background task that checks vessel positions against EEZ boundaries
and records entry/exit events.
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.database import get_db
from app.services.eez_service import find_eez_for_point, record_eez_event

logger = logging.getLogger("poseidon.eez_monitor")

# Track last known EEZ per vessel: mmsi -> eez_id | None
_vessel_eez_state: dict[int, int | None] = {}

CHECK_INTERVAL = 120  # seconds


async def run_eez_monitor() -> None:
    """Background task: periodically check vessel positions against EEZ zones."""
    logger.info("EEZ monitor starting (interval=%ds)", CHECK_INTERVAL)

    # Wait for EEZ zones to be loaded
    await asyncio.sleep(10)

    while True:
        try:
            await _check_eez_crossings()
        except asyncio.CancelledError:
            logger.info("EEZ monitor cancelled")
            return
        except Exception as e:
            logger.error("EEZ monitor error: %s", e)

        await asyncio.sleep(CHECK_INTERVAL)


async def _check_eez_crossings() -> None:
    """Check all active vessels for EEZ boundary crossings."""
    db = get_db()

    rows = await db.fetch(
        """
        SELECT mmsi, ST_X(geom) AS lon, ST_Y(geom) AS lat, timestamp
        FROM latest_vessel_positions
        WHERE timestamp > NOW() - INTERVAL '30 minutes'
        """
    )

    events_created = 0

    for r in rows:
        mmsi = r["mmsi"]
        lon = float(r["lon"])
        lat = float(r["lat"])
        ts = r["timestamp"]

        current_eez = find_eez_for_point(lon, lat)
        current_eez_id = current_eez["id"] if current_eez else None

        prev_eez_id = _vessel_eez_state.get(mmsi)

        if current_eez_id != prev_eez_id:
            # State changed — record events
            if prev_eez_id is not None:
                # Exit from previous EEZ
                # We don't have the previous EEZ name cached, so just record the ID
                await record_eez_event(
                    mmsi, prev_eez_id, "", "exit", lon, lat, ts,
                )
                events_created += 1

            if current_eez_id is not None:
                # Entry into new EEZ
                await record_eez_event(
                    mmsi, current_eez_id, current_eez["name"],
                    "entry", lon, lat, ts,
                )
                events_created += 1

            _vessel_eez_state[mmsi] = current_eez_id

    if events_created > 0:
        logger.info("EEZ monitor: %d crossing events recorded", events_created)
