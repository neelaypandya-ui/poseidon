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
from app.api.router import api_router
from app.api.ws import ws_router

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
    logger.info("Database and Redis pools initialized")

    tasks = [
        asyncio.create_task(run_ais_stream(), name="ais_stream"),
        asyncio.create_task(run_buffer_flush(), name="buffer_flush"),
        asyncio.create_task(run_dark_vessel_detector(), name="dark_vessel"),
        asyncio.create_task(run_sar_matcher(), name="sar_matcher"),
        asyncio.create_task(run_viirs_fetcher(), name="viirs_fetcher"),
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
    version="0.1.0",
    lifespan=lifespan,
)

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
