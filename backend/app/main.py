import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db, close_db, init_redis, close_redis
from app.ingestors.ais_stream import run_ais_stream
from app.ingestors.redis_buffer import run_buffer_flush
from app.processors.dark_vessel import run_dark_vessel_detector
from app.processors.sar_cfar import run_sar_matcher
from app.processors.viirs_anomaly import run_viirs_fetcher
from app.processors.spoof_detector import run_spoof_detector
from app.processors.aoi_monitor import run_aoi_monitor
from app.processors.eez_monitor import run_eez_monitor
from app.processors.acoustic_fetcher import run_acoustic_fetcher
from app.processors.report_scheduler import run_report_scheduler
from app.services.coastline_service import init_coastline_buffer
from app.services.eez_service import init_eez_zones
from app.services.webcam_service import seed_webcams
from app.services.cmems_service import fetch_currents
from app.api.router import api_router
from app.api.ws import ws_router
from app.middleware.audit_middleware import AuditMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("poseidon")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Poseidon...")
    await init_db()
    await init_redis()
    await init_coastline_buffer()

    # Initialize EEZ zones into memory
    try:
        eez_count = await init_eez_zones()
        logger.info("EEZ zones loaded: %d", eez_count)
    except Exception as e:
        logger.warning("EEZ zones init skipped: %s", e)

    # Seed port webcams
    try:
        await seed_webcams()
    except Exception as e:
        logger.warning("Webcam seeding skipped: %s", e)

    # Pre-load ocean currents cache
    try:
        await fetch_currents()
    except Exception as e:
        logger.warning("CMEMS currents init skipped: %s", e)

    logger.info("Database, Redis, and coastline buffer initialized")

    tasks = [
        asyncio.create_task(run_ais_stream(), name="ais_stream"),
        asyncio.create_task(run_buffer_flush(), name="buffer_flush"),
        asyncio.create_task(run_dark_vessel_detector(), name="dark_vessel"),
        asyncio.create_task(run_sar_matcher(), name="sar_matcher"),
        asyncio.create_task(run_viirs_fetcher(), name="viirs_fetcher"),
        asyncio.create_task(run_spoof_detector(), name="spoof_detector"),
        asyncio.create_task(run_aoi_monitor(), name="aoi_monitor"),
        asyncio.create_task(run_eez_monitor(), name="eez_monitor"),
        asyncio.create_task(run_acoustic_fetcher(), name="acoustic_fetcher"),
        asyncio.create_task(run_report_scheduler(), name="report_scheduler"),
    ]

    yield

    logger.info("Shutting down background tasks...")
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    await close_db()
    await close_redis()
    logger.info("Poseidon stopped.")


app = FastAPI(
    title="Poseidon Maritime Intelligence",
    version="0.2.0",
    lifespan=lifespan,
)

# Audit middleware (chain of custody logging)
app.add_middleware(AuditMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
