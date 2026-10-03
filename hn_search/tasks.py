import asyncio
import json
import logging
import os
import time

import redis as sync_redis
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from hn_search.cache import INDEX_VERSION_KEY, REDIS_URL
from hn_search.celery_app import celery_app
from hn_search.database import engine

logger = logging.getLogger(__name__)

_LOCK_KEY = "hn:ingest_lock"
_LOCK_TTL = 600
_SOFT_LIMIT = 540
_LAST_INGEST_KEY = "hn:last_ingest_stats"

_ENRICH_LOCK_KEY = "hn:enrich_lock"
_ENRICH_LOCK_TTL = 900
_ENRICH_SOFT_LIMIT = 840
_ENRICH_TIME_LIMIT = 900

_EMBED_LOCK_KEY = "hn:embed_lock"
_EMBED_LOCK_TTL = 1800
_EMBED_SOFT_LIMIT = 1740
_EMBED_TIME_LIMIT = 1800
_EMBED_BATCH = 256


def _bump_index_version_sync() -> None:
    client = sync_redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    try:
        client.incr(INDEX_VERSION_KEY)
    finally:
        client.close()


def _write_ingest_stats_sync(stats: dict) -> None:
    client = sync_redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    try:
        client.set(_LAST_INGEST_KEY, json.dumps(stats))
    finally:
        client.close()


def _acquire_lock(key: str, ttl: int) -> bool:
    client = sync_redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    try:
        return bool(client.set(key, "1", nx=True, ex=ttl))
    finally:
        client.close()


def _release_lock(key: str) -> None:
    client = sync_redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    try:
        client.delete(key)
    finally:
        client.close()


async def _run_ingest() -> dict:
    from hn_search.ingest import ingest_stories
    try:
        return await ingest_stories()
    finally:
        await engine.dispose()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=_SOFT_LIMIT,
    name="hn_search.tasks.reindex_stories",
)
def reindex_stories(self: Task) -> dict | str:
    if not _acquire_lock(_LOCK_KEY, _LOCK_TTL):
        logger.info("Reindex skipped — another run is in progress")
        return "skipped"

    t0 = time.time()
    try:
        stats = asyncio.run(_run_ingest())
        _bump_index_version_sync()
        stats["duration_seconds"] = round(time.time() - t0, 1)
        stats["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _write_ingest_stats_sync(stats)
        logger.info("Reindex task complete: %s", stats)
        enrich_stories.apply_async(countdown=5)
        return stats
    except SoftTimeLimitExceeded:
        logger.warning("Reindex task hit soft time limit")
        raise self.retry(countdown=120)
    except Exception as exc:
        logger.error("Reindex task failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=60)
    finally:
        _release_lock(_LOCK_KEY)


async def _run_enrich() -> dict:
    from hn_search.enricher import enrich_batch
    try:
        return await enrich_batch()
    finally:
        await engine.dispose()


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    soft_time_limit=_ENRICH_SOFT_LIMIT,
    time_limit=_ENRICH_TIME_LIMIT,
    name="hn_search.tasks.enrich_stories",
)
def enrich_stories(self: Task, _ingest_result=None) -> dict | str:
    """Fetch and extract article text for stories that lack content."""
    if not _acquire_lock(_ENRICH_LOCK_KEY, _ENRICH_LOCK_TTL):
        logger.info("Enrich skipped — another run is in progress")
        return "skipped"

    t0 = time.time()
    try:
        stats = asyncio.run(_run_enrich())
        stats["duration_seconds"] = round(time.time() - t0, 1)
        stats["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        logger.info("Enrich task complete: %s", stats)
        embed_chunks.apply_async(queue="embeddings", countdown=5)
        return stats
    except SoftTimeLimitExceeded:
        logger.warning("Enrich task hit soft time limit")
        return "timeout"
    except Exception as exc:
        logger.error("Enrich task failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=120)
    finally:
        _release_lock(_ENRICH_LOCK_KEY)


async def _run_embed_chunks() -> dict:
    """
    Embed all chunks that have no embedding row for the current model.
    Returns {embedded, remaining, chunks_per_sec}.
    """
    import numpy as np
    from sqlalchemy import select, text, delete
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from hn_search.database import SessionLocal, init_pgvector
    from hn_search.embeddings import EMBEDDING_MODEL, build_embed_input, embed_texts
    from hn_search.models import Chunk, ChunkEmbedding, Stories

    await init_pgvector()

    t0 = time.time()
    embedded_this_run = 0

    async with SessionLocal() as db:
        # Count remaining before we start
        remaining_q = await db.execute(
            text(
                """
                SELECT COUNT(*) FROM chunks c
                WHERE NOT EXISTS (
                    SELECT 1 FROM chunk_embeddings e
                    WHERE e.chunk_id = c.id AND e.model = :model
                )
                """
            ),
            {"model": EMBEDDING_MODEL},
        )
        total_remaining = remaining_q.scalar() or 0

    logger.info("embed_chunks: %d chunks need embedding (model=%s)", total_remaining, EMBEDDING_MODEL)

    while True:
        async with SessionLocal() as db:
            rows = (await db.execute(
                select(Chunk.id, Chunk.text, Chunk.story_id)
                .where(
                    ~Chunk.id.in_(
                        select(ChunkEmbedding.chunk_id).where(
                            ChunkEmbedding.model == EMBEDDING_MODEL
                        )
                    )
                )
                .order_by(Chunk.id)
                .limit(_EMBED_BATCH)
            )).all()

        if not rows:
            break

        chunk_ids = [r[0] for r in rows]
        story_ids = list({r[2] for r in rows})

        # Fetch titles for these stories
        async with SessionLocal() as db:
            title_rows = (await db.execute(
                select(Stories.id, Stories.title).where(Stories.id.in_(story_ids))
            )).all()
        title_map = {sid: (t or "") for sid, t in title_rows}

        inputs = [
            build_embed_input(title_map.get(r[2], ""), r[1])
            for r in rows
        ]

        batch_t0 = time.time()
        vecs: np.ndarray = await asyncio.to_thread(embed_texts, inputs)
        elapsed = time.time() - batch_t0
        cps = len(rows) / elapsed if elapsed > 0 else 0

        async with SessionLocal() as db:
            stmt = pg_insert(ChunkEmbedding).values([
                {
                    "chunk_id": chunk_ids[i],
                    "model": EMBEDDING_MODEL,
                    "embedding": vecs[i].tolist(),
                }
                for i in range(len(chunk_ids))
            ]).on_conflict_do_nothing()
            await db.execute(stmt)
            await db.commit()

        embedded_this_run += len(rows)
        logger.info(
            "embed_chunks: batch done — %d embedded this run, %.1f chunks/sec",
            embedded_this_run, cps,
        )

    elapsed_total = time.time() - t0

    # Count remaining after run
    async with SessionLocal() as db:
        remaining_q = await db.execute(
            text(
                """
                SELECT COUNT(*) FROM chunks c
                WHERE NOT EXISTS (
                    SELECT 1 FROM chunk_embeddings e
                    WHERE e.chunk_id = c.id AND e.model = :model
                )
                """
            ),
            {"model": EMBEDDING_MODEL},
        )
        still_remaining = remaining_q.scalar() or 0

    logger.info(
        "embed_chunks: run complete — %d embedded, %d still remaining, %.1fs",
        embedded_this_run, still_remaining, elapsed_total,
    )
    return {
        "embedded": embedded_this_run,
        "remaining": still_remaining,
        "duration_seconds": round(elapsed_total, 1),
    }


@celery_app.task(
    bind=True,
    soft_time_limit=_EMBED_SOFT_LIMIT,
    time_limit=_EMBED_TIME_LIMIT,
    name="hn_search.tasks.embed_chunks",
    queue="embeddings",
)
def embed_chunks(self: Task) -> dict | str:
    """Embed all un-embedded chunks. Re-enqueues itself if work remains."""
    if not _acquire_lock(_EMBED_LOCK_KEY, _EMBED_LOCK_TTL):
        logger.info("embed_chunks skipped — another run is in progress")
        return "skipped"

    try:
        stats = asyncio.run(_run_embed_chunks())

        if stats["embedded"] > 0:
            _bump_index_version_sync()

        if stats["remaining"] > 0:
            logger.info("embed_chunks: re-enqueuing for remaining %d chunks", stats["remaining"])
            embed_chunks.apply_async(queue="embeddings", countdown=5)

        return stats
    except SoftTimeLimitExceeded:
        logger.warning("embed_chunks hit soft time limit — re-enqueuing")
        embed_chunks.apply_async(queue="embeddings", countdown=10)
        return "timeout"
    except Exception as exc:
        logger.error("embed_chunks failed: %s", exc, exc_info=True)
        raise
    finally:
        _release_lock(_EMBED_LOCK_KEY)
        try:
            asyncio.run(engine.dispose())
        except Exception:
            pass
