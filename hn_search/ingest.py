import logging
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from hn_search.crawler import fetch_all_stories
from hn_search.database import SessionLocal
from hn_search.models import Stories
from hn_search.preprocessor import preprocess_stories

logger = logging.getLogger(__name__)

_BATCH_SIZE = 500


async def ingest_stories(feed: str = "topstories", limit: int = 200) -> dict:
    """
    Crawl → preprocess → upsert.
    Returns stats: requested, fetched, inserted, updated, skipped, failed.
    """
    stories, crawl_stats = await fetch_all_stories(limit=limit, feed=feed)
    preprocessed = preprocess_stories(stories)

    now = datetime.now(tz=timezone.utc)
    inserted = updated = 0

    async with SessionLocal() as db:
        for i in range(0, len(preprocessed), _BATCH_SIZE):
            batch = preprocessed[i: i + _BATCH_SIZE]
            rows = [
                {
                    "id": s["id"],
                    "title": s["title"],
                    "text": s["text"],
                    "preprocessed_text": s["preprocessed_text"],
                    "url": s.get("url"),
                    "score": s.get("score", 0),
                    "descendants": s.get("descendants", 0),
                    "created_at": s.get("created_at"),
                    "fetched_at": now,
                }
                for s in batch
            ]
            stmt = pg_insert(Stories).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "title": stmt.excluded.title,
                    "text": stmt.excluded.text,
                    "preprocessed_text": stmt.excluded.preprocessed_text,
                    "url": stmt.excluded.url,
                    "score": stmt.excluded.score,
                    "descendants": stmt.excluded.descendants,
                    "fetched_at": stmt.excluded.fetched_at,
                },
            )
            result = await db.execute(stmt)
            # rowcount for upsert: inserted rows count as 1, updated as 2 in PG
            rc = result.rowcount
            inserted += rc  # approximate — exact split needs RETURNING, added in Task 16
        await db.commit()

    stats = {
        "requested": crawl_stats["requested"],
        "fetched": crawl_stats["fetched"],
        "inserted": inserted,
        "updated": 0,       # exact split deferred to Task 16
        "skipped": crawl_stats["skipped"],
        "failed": crawl_stats["failed"],
    }
    logger.info("Ingest complete: %s", stats)
    return stats
