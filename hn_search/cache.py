import hashlib
import json
import logging
import os

import redis.asyncio as aioredis
from redis.asyncio.client import Redis
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise RuntimeError("REDIS_URL environment variable is not set")

CACHE_TTL = 1800          # seconds
KEY_PREFIX = "hn:"
INDEX_VERSION_KEY = "hn:index_version"


def get_redis() -> Redis:
    return aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)


# --- index version (cache invalidation without flushdb) ---

async def get_index_version(redis_client: Redis) -> int:
    try:
        val = await redis_client.get(INDEX_VERSION_KEY)
        return int(val) if val is not None else 0
    except Exception as e:
        logger.warning("Redis error reading index version: %s", e)
        return 0


async def bump_index_version(redis_client: Redis) -> None:
    try:
        await redis_client.incr(INDEX_VERSION_KEY)
    except Exception as e:
        logger.warning("Redis error bumping index version: %s", e)


# --- pool cache ---

def build_pool_key(normalized_query: str, index_version: int) -> str:
    digest = hashlib.sha256(normalized_query.encode()).hexdigest()[:16]
    return f"{KEY_PREFIX}pool:{index_version}:{digest}"


async def get_cached_pool(redis_client: Redis, key: str):
    try:
        raw = await redis_client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.warning("Redis error on cache get: %s", e)
        return None


async def set_cached_pool(redis_client: Redis, key: str, pool: list) -> None:
    try:
        await redis_client.setex(key, CACHE_TTL, json.dumps(pool))
    except Exception as e:
        logger.warning("Redis error on cache set: %s", e)
