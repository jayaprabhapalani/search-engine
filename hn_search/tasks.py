import asyncio
import logging
import os

import redis as sync_redis
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from hn_search.cache import INDEX_VERSION_KEY, REDIS_URL
from hn_search.celery_app import celery_app
from hn_search.database import engine

logger = logging.getLogger(__name__)

_LOCK_KEY = "hn:ingest_lock"
_LOCK_TTL = 360          # seconds — slightly longer than the soft time limit
_SOFT_LIMIT = 300        # seconds


def _bump_index_version_sync() -> None:
    client = sync_redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    try:
        client.incr(INDEX_VERSION_KEY)
    finally:
        client.close()


def _acquire_lock() -> bool:
    client = sync_redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    try:
        return bool(client.set(_LOCK_KEY, "1", nx=True, ex=_LOCK_TTL))
    finally:
        client.close()


def _release_lock() -> None:
    client = sync_redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    try:
        client.delete(_LOCK_KEY)
    finally:
        client.close()


async def _run_ingest() -> dict:
    from hn_search.ingest import ingest_stories
    try:
        return await ingest_stories()
    finally:
        # Dispose the engine so the next asyncio.run() gets a fresh pool
        await engine.dispose()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=_SOFT_LIMIT,
    name="hn_search.tasks.reindex_stories",
)
def reindex_stories(self: Task) -> dict | str:
    if not _acquire_lock():
        logger.info("Reindex skipped — another run is in progress")
        return "skipped"

    try:
        stats = asyncio.run(_run_ingest())
        _bump_index_version_sync()
        logger.info("Reindex task complete: %s", stats)
        return stats
    except SoftTimeLimitExceeded:
        logger.warning("Reindex task hit soft time limit")
        raise self.retry(countdown=120)
    except Exception as exc:
        logger.error("Reindex task failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=60)
    finally:
        _release_lock()
