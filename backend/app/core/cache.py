import redis.asyncio as aioredis
import json
import structlog
from typing import Any, Optional
from app.core.config import settings

logger = structlog.get_logger(__name__)

_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> Optional[aioredis.Redis]:
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            await _redis_client.ping()
            logger.info("redis_connected", url=settings.REDIS_URL.split("@")[-1])
        except Exception as e:
            logger.warning("redis_unavailable", error=str(e), detail="caching disabled")
            _redis_client = None
    return _redis_client


async def cache_get(key: str) -> Optional[Any]:
    from app.core.metrics import record_cache_hit, record_cache_miss
    client = await get_redis()
    if not client:
        return None
    try:
        value = await client.get(key)
        if value:
            record_cache_hit(key)
            logger.debug("cache_hit", key=key)
            return json.loads(value)
        record_cache_miss(key)
        logger.debug("cache_miss", key=key)
    except Exception as e:
        logger.warning("cache_get_error", key=key, error=str(e))
    return None


async def cache_set(key: str, value: Any, ttl: int = settings.CACHE_TTL) -> bool:
    client = await get_redis()
    if not client:
        return False
    try:
        await client.setex(key, ttl, json.dumps(value))
        logger.debug("cache_set", key=key, ttl=ttl)
        return True
    except Exception as e:
        logger.warning("cache_set_error", key=key, error=str(e))
        return False


async def cache_delete(key: str) -> bool:
    client = await get_redis()
    if not client:
        return False
    try:
        await client.delete(key)
        return True
    except Exception as e:
        logger.warning("cache_delete_error", key=key, error=str(e))
        return False


def make_cache_key(*parts: str) -> str:
    return ":".join(["pip", *[p.upper() for p in parts]])
