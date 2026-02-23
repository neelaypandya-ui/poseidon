import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as aioredis

from app.database import get_redis

logger = logging.getLogger("poseidon.ws")

ws_router = APIRouter()

# Track connected clients
clients: set[WebSocket] = set()


@ws_router.websocket("/ws/vessels")
async def vessel_ws(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    logger.info(f"WebSocket client connected ({len(clients)} total)")

    try:
        r = get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe("ais:live")

        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                try:
                    parsed = json.loads(data)
                    # Only forward position messages to frontend
                    if parsed.get("type") == "position":
                        await websocket.send_text(data)
                except (json.JSONDecodeError, TypeError):
                    pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        clients.discard(websocket)
        logger.info(f"WebSocket client disconnected ({len(clients)} total)")
