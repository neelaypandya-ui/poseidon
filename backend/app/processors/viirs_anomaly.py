"""Background task: periodically fetch VIIRS nighttime light data
and run anomaly detection.

Runs every 6 hours, following the same pattern as the dark vessel detector.
"""

import asyncio
import logging

from app.services.viirs_service import fetch_viirs_data, detect_anomalies

logger = logging.getLogger("poseidon.viirs_anomaly")

# Fetch interval: 6 hours
VIIRS_FETCH_INTERVAL_S = 6 * 3600


async def run_viirs_fetcher():
    """Background loop: fetch latest VIIRS global data and run anomaly detection."""
    logger.info("VIIRS fetcher background task starting...")

    # Initial delay — let the system stabilize before first fetch
    await asyncio.sleep(30)

    while True:
        try:
            logger.info("VIIRS fetcher: starting periodic fetch...")
            inserted = await fetch_viirs_data()
            logger.info("VIIRS fetcher: ingested %d observations", inserted)

            if inserted > 0:
                anomaly_count = await detect_anomalies()
                logger.info("VIIRS fetcher: detected %d anomalies", anomaly_count)

            logger.info(
                "VIIRS fetcher: cycle complete, sleeping %d seconds",
                VIIRS_FETCH_INTERVAL_S,
            )
            await asyncio.sleep(VIIRS_FETCH_INTERVAL_S)

        except asyncio.CancelledError:
            logger.info("VIIRS fetcher cancelled")
            return
        except Exception as e:
            logger.error("VIIRS fetcher error: %s", e)
            await asyncio.sleep(60)
