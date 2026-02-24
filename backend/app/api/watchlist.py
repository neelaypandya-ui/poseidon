from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.watchlist_service import (
    get_watchlist, add_to_watchlist, remove_from_watchlist, is_watched,
)

router = APIRouter()


class WatchlistAdd(BaseModel):
    mmsi: int
    label: str | None = None
    reason: str | None = None


@router.get("")
async def list_watchlist():
    items = await get_watchlist()
    return {"count": len(items), "watchlist": items}


@router.post("")
async def add_watch(body: WatchlistAdd):
    return await add_to_watchlist(body.mmsi, body.label, body.reason)


@router.delete("/{mmsi}")
async def remove_watch(mmsi: int):
    deleted = await remove_from_watchlist(mmsi)
    if not deleted:
        raise HTTPException(status_code=404, detail="MMSI not on watchlist")
    return {"status": "removed", "mmsi": mmsi}


@router.get("/{mmsi}/check")
async def check_watched(mmsi: int):
    return {"mmsi": mmsi, "watched": await is_watched(mmsi)}
