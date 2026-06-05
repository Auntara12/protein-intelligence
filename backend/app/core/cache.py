import redis.asyncio as aioredis
import json
import logging
from typing import Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            await _redis_client.ping()
            logger.info("Redis connected.")
        except Exception as e:
            logger.warning(f"Redis unavailable: {e}. Caching disabled.")
            _redis_client = None
    return _redis_client


async def cache_get(key: str) -> Optional[Any]:
    client = await get_redis()
    if not client:
        return None
    try:
        value = await client.get(key)
        if value:
            return json.loads(value)
    except Exception as e:
        logger.warning(f"Cache get error for {key}: {e}")
    return None


async def cache_set(key: str, value: Any, ttl: int = settings.CACHE_TTL) -> bool:
    client = await get_redis()
    if not client:
        return False
    try:
        await client.setex(key, ttl, json.dumps(value))
        return True
    except Exception as e:
        logger.warning(f"Cache set error for {key}: {e}")
        return False


async def cache_delete(key: str) -> bool:
    client = await get_redis()
    if not client:
        return False
    try:
        await client.delete(key)
        return True
    except Exception as e:
        logger.warning(f"Cache delete error for {key}: {e}")
        return False


def make_cache_key(*parts: str) -> str:
    return ":".join(["pip", *[p.upper() for p in parts]])
