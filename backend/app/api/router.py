from fastapi import APIRouter

from app.api.vessels import router as vessels_router
from app.api.positions import router as positions_router
from app.api.alerts import router as alerts_router
from app.api.sar import router as sar_router
from app.api.optical import router as optical_router
from app.api.viirs import router as viirs_router
from app.api.fusion import router as fusion_router
from app.api.acoustic import router as acoustic_router
from app.api.routes import router as routes_router
from app.api.risk import router as risk_router
from app.api.replay import router as replay_router

api_router = APIRouter()
api_router.include_router(vessels_router, prefix="/vessels", tags=["vessels"])
api_router.include_router(positions_router, tags=["positions"])
api_router.include_router(alerts_router, prefix="/alerts", tags=["alerts"])
api_router.include_router(sar_router, prefix="/sar", tags=["sar"])
api_router.include_router(optical_router, prefix="/optical", tags=["optical"])
api_router.include_router(viirs_router, prefix="/viirs", tags=["viirs"])
api_router.include_router(fusion_router, prefix="/fusion", tags=["fusion"])
api_router.include_router(acoustic_router, prefix="/acoustic", tags=["acoustic"])
api_router.include_router(routes_router, prefix="/routes", tags=["routes"])
api_router.include_router(risk_router, prefix="/risk", tags=["risk"])
api_router.include_router(replay_router, prefix="/replay", tags=["replay"])
