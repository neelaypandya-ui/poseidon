import asyncpg
import redis.asyncio as aioredis
from app.config import settings

db_pool: asyncpg.Pool | None = None
redis_pool: aioredis.Redis | None = None


async def init_db() -> asyncpg.Pool:
    global db_pool
    db_pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=5,
        max_size=20,
    )
    return db_pool


async def close_db():
    global db_pool
    if db_pool:
        await db_pool.close()
        db_pool = None


async def init_redis() -> aioredis.Redis:
    global redis_pool
    redis_pool = aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
    )
    return redis_pool


async def close_redis():
    global redis_pool
    if redis_pool:
        await redis_pool.close()
        redis_pool = None


def get_db() -> asyncpg.Pool:
    assert db_pool is not None, "Database pool not initialized"
    return db_pool


def get_redis() -> aioredis.Redis:
    assert redis_pool is not None, "Redis pool not initialized"
    return redis_pool
