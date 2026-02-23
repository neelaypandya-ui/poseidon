from fastapi import APIRouter

from app.api.vessels import router as vessels_router
from app.api.positions import router as positions_router
from app.api.alerts import router as alerts_router

api_router = APIRouter()
api_router.include_router(vessels_router, prefix="/vessels", tags=["vessels"])
api_router.include_router(positions_router, tags=["positions"])
api_router.include_router(alerts_router, prefix="/alerts", tags=["alerts"])
