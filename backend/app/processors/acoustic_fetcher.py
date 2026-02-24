"""Acoustic event fetcher / synthetic data generator.

Generates synthetic hydrophone events for demonstration purposes.
When NOAA PMEL real-time API becomes available, this will switch
to fetching real data.
"""

import asyncio
import math
import random
import logging
from datetime import datetime, timezone, timedelta

from app.database import get_db

logger = logging.getLogger("poseidon.acoustic_fetcher")

FETCH_INTERVAL = 600  # seconds (10 minutes)

# Known hydrophone array locations (approximate)
HYDROPHONE_ARRAYS = [
    {"name": "Equatorial Pacific", "lon": -110.0, "lat": 0.0},
    {"name": "Northeast Pacific", "lon": -130.0, "lat": 46.0},
    {"name": "Juan de Fuca", "lon": -130.3, "lat": 46.3},
    {"name": "Axial Seamount", "lon": -130.0, "lat": 45.9},
    {"name": "Indian Ocean (Diego Garcia)", "lon": 72.4, "lat": -7.3},
    {"name": "Atlantic (Azores)", "lon": -28.0, "lat": 38.0},
    {"name": "Mediterranean (Corsica)", "lon": 8.5, "lat": 42.0},
    {"name": "South Atlantic", "lon": -14.4, "lat": -7.9},
]

EVENT_TYPES = ["ship_noise", "seismic", "biological", "unknown", "explosion"]


async def run_acoustic_fetcher() -> None:
    """Background task: periodically generate/fetch acoustic events."""
    logger.info("Acoustic fetcher starting (interval=%ds)", FETCH_INTERVAL)
    await asyncio.sleep(30)  # Wait for DB init

    while True:
        try:
            count = await _fetch_or_generate()
            if count > 0:
                logger.info("Acoustic fetcher: %d events ingested", count)
        except asyncio.CancelledError:
            logger.info("Acoustic fetcher cancelled")
            return
        except Exception as e:
            logger.error("Acoustic fetcher error: %s", e)

        await asyncio.sleep(FETCH_INTERVAL)


async def _fetch_or_generate() -> int:
    """Generate synthetic acoustic events near hydrophone arrays.

    Each cycle generates 0-3 events per array with realistic properties.
    """
    db = get_db()
    count = 0
    now = datetime.now(timezone.utc)

    for array in HYDROPHONE_ARRAYS:
        # Each array has 0-3 events per cycle
        num_events = random.randint(0, 3)
        for _ in range(num_events):
            event_type = random.choices(
                EVENT_TYPES,
                weights=[50, 15, 20, 10, 5],
                k=1,
            )[0]

            # Random offset from array position (within ~200km)
            offset_lon = random.uniform(-2.0, 2.0)
            offset_lat = random.uniform(-2.0, 2.0)
            lon = array["lon"] + offset_lon
            lat = array["lat"] + offset_lat

            # Random bearing from array to event
            bearing = random.uniform(0, 360)

            # Magnitude depends on event type
            if event_type == "ship_noise":
                magnitude = random.uniform(80, 140)
            elif event_type == "explosion":
                magnitude = random.uniform(150, 220)
            elif event_type == "seismic":
                magnitude = random.uniform(100, 180)
            elif event_type == "biological":
                magnitude = random.uniform(60, 120)
            else:
                magnitude = random.uniform(70, 130)

            # Event time is slightly in the past (within last interval)
            event_time = now - timedelta(seconds=random.randint(0, FETCH_INTERVAL))

            try:
                await db.execute(
                    """
                    INSERT INTO acoustic_events
                        (source, event_type, geom, bearing, magnitude, event_time)
                    VALUES ($1, $2, ST_SetSRID(ST_MakePoint($3, $4), 4326), $5, $6, $7)
                    """,
                    array["name"],
                    event_type,
                    lon, lat, bearing, magnitude, event_time,
                )
                count += 1
            except Exception as e:
                logger.debug("Failed to insert acoustic event: %s", e)

    return count
