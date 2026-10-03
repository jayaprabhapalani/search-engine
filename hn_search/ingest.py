import logging
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy.dialects.postgresql import insert as pg_insert

from hn_search.chunker import build_chunks, save_chunks
from hn_search.crawler import fetch_stories_by_ids, fetch_feed_ids
from hn_search.database import SessionLocal
from hn_search.models import Stories
from hn_search.preprocessor import preprocess_stories

logger = logging.getLogger(__name__)

_BATCH_SIZE = 500
_DEFAULT_FEEDS = "topstories,beststories,newstories,askstories,showstories"


def _parse_domain(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url).hostname or ""
        return host.removeprefix("www.") or None
    except Exception:
        return None


async def ingest_stories() -> dict:
    """
    Crawl configured feeds → dedupe → preprocess → upsert.
    Returns stats dict.
    """
    feeds = [
        f.strip()
        for f in os.getenv("HN_FEEDS", _DEFAULT_FEEDS).split(",")
        if f.strip()
    ]

    # Collect IDs from all feeds, dedupe while preserving first-seen order
    seen: dict[int, None] = {}
    for feed in feeds:
        try:
            ids = await fetch_feed_ids(feed)
            for id_ in ids:
                seen.setdefault(id_, None)
        except Exception as e:
            logger.warning("Failed to fetch feed %s: %s", feed, e)

    all_ids = list(seen.keys())
    logger.info("Collected %d unique IDs across %d feeds", len(all_ids), len(feeds))

    stories, crawl_stats = await fetch_stories_by_ids(all_ids)
    preprocessed = preprocess_stories(stories)

    now = datetime.now(tz=timezone.utc)
    inserted = 0

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
                    "domain": _parse_domain(s.get("url")),
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
                    "domain": stmt.excluded.domain,
                    "score": stmt.excluded.score,
                    "descendants": stmt.excluded.descendants,
                    "fetched_at": stmt.excluded.fetched_at,
                },
            )
            result = await db.execute(stmt)
            inserted += result.rowcount

            # Chunk URL-less stories (Ask HN, Show HN text posts, etc.) now;
            # stories with a URL are chunked later by the enrich task.
            for s in batch:
                if s.get("url"):
                    continue
                chunks = build_chunks(s["title"], s.get("text"), None)
                await save_chunks(db, s["id"], chunks)

        await db.commit()

    stats = {
        "feeds": feeds,
        "unique_ids": len(all_ids),
        "requested": crawl_stats["requested"],
        "fetched": crawl_stats["fetched"],
        "inserted": inserted,
        "skipped": crawl_stats["skipped"],
        "failed": crawl_stats["failed"],
    }
    logger.info("Ingest complete: %s", stats)
    return stats
