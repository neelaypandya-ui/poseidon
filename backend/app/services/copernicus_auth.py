import time
import logging

import aiohttp

from app.config import settings

logger = logging.getLogger("poseidon.copernicus_auth")

TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu"
    "/auth/realms/CDSE/protocol/openid-connect/token"
)

# Separate caches for catalog vs download tokens (different audiences)
_catalog_token: str | None = None
_catalog_expires: float = 0.0
_download_token: str | None = None
_download_expires: float = 0.0


async def _request_token(data: dict[str, str]) -> tuple[str, float]:
    """Request a token from the CDSE identity provider."""
    async with aiohttp.ClientSession() as session:
        async with session.post(TOKEN_URL, data=data) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(
                    f"Copernicus token request failed ({resp.status}): {body}"
                )
            payload = await resp.json()
    token = payload["access_token"]
    expires_in = payload.get("expires_in", 600)
    return token, time.time() + expires_in


async def get_access_token() -> str:
    """Token for STAC catalog (SH client_credentials or password grant)."""
    global _catalog_token, _catalog_expires

    if _catalog_token and time.time() < _catalog_expires - 30:
        return _catalog_token

    if settings.copernicus_client_id and settings.copernicus_client_secret:
        data = {
            "grant_type": "client_credentials",
            "client_id": settings.copernicus_client_id,
            "client_secret": settings.copernicus_client_secret,
        }
    elif settings.copernicus_username and settings.copernicus_password:
        data = {
            "grant_type": "password",
            "client_id": "cdse-public",
            "username": settings.copernicus_username,
            "password": settings.copernicus_password,
        }
    else:
        raise ValueError("No Copernicus credentials configured in .env")

    _catalog_token, _catalog_expires = await _request_token(data)
    logger.info("Copernicus catalog token refreshed")
    return _catalog_token


async def get_download_token() -> str:
    """Token for data download (requires password grant with cdse-public client)."""
    global _download_token, _download_expires

    if _download_token and time.time() < _download_expires - 30:
        return _download_token

    if settings.copernicus_username and settings.copernicus_password:
        data = {
            "grant_type": "password",
            "client_id": "cdse-public",
            "username": settings.copernicus_username,
            "password": settings.copernicus_password,
        }
    else:
        raise ValueError(
            "COPERNICUS_USERNAME and COPERNICUS_PASSWORD required in .env for data download"
        )

    _download_token, _download_expires = await _request_token(data)
    logger.info("Copernicus download token refreshed")
    return _download_token
