"""
Article enrichment: fetch → extract → store in story_content.
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timezone

import trafilatura
from sqlalchemy import select, or_, and_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from hn_search.chunker import build_chunks, save_chunks
from hn_search.database import SessionLocal
from hn_search.fetcher import fetch_article
from hn_search.models import Stories, StoryContent

logger = logging.getLogger(__name__)

_BATCH_SIZE = 200
_MAX_RETRIES = 2
_MIN_TEXT_CHARS = 200
_MAX_WORDS = 3000
_CONCURRENCY = 10


def _extract(html: str) -> str | None:
    text = trafilatura.extract(html, include_comments=False, include_tables=False)
    return text or None


def _cap_words(text: str) -> str:
    words = text.split()
    return " ".join(words[:_MAX_WORDS]) if len(words) > _MAX_WORDS else text


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def _process_one(story_id: int, url: str) -> dict:
    """Fetch and extract one story.  Returns a dict ready for upsert."""
    now = datetime.now(tz=timezone.utc)
    base = {"story_id": story_id, "fetched_at": now}
    try:
        html = await fetch_article(url)
        extracted = _extract(html)
        if not extracted or len(extracted) < _MIN_TEXT_CHARS:
            return {**base, "text": "", "content_hash": None, "word_count": 0,
                    "status": "empty", "last_error": None}
        capped = _cap_words(extracted)
        return {
            **base,
            "text": capped,
            "content_hash": _sha256(capped),
            "word_count": len(capped.split()),
            "status": "ok",
            "last_error": None,
        }
    except Exception as exc:
        logger.debug("Fetch failed story=%s url=%s: %s", story_id, url, exc)
        return {**base, "text": "", "content_hash": None, "word_count": 0,
                "status": "failed", "last_error": str(exc)[:500]}


async def enrich_batch() -> dict:
    """
    Select up to _BATCH_SIZE stories needing enrichment, process them,
    upsert story_content + rebuild chunks.  Returns stats dict.
    """
    async with SessionLocal() as db:
        eligible_subq = (
            select(StoryContent.story_id)
            .where(
                or_(
                    StoryContent.status == "ok",
                    StoryContent.status == "skipped",
                    StoryContent.status == "empty",
                    and_(
                        StoryContent.status == "failed",
                        StoryContent.attempts >= _MAX_RETRIES,
                    ),
                )
            )
        )
        rows = await db.execute(
            select(Stories.id, Stories.url, Stories.title, Stories.text)
            .where(Stories.url.isnot(None))
            .where(Stories.id.notin_(eligible_subq))
            .limit(_BATCH_SIZE)
        )
        candidates = rows.all()

    if not candidates:
        return {"processed": 0, "ok": 0, "empty": 0, "failed": 0, "skipped": 0}

    sem = asyncio.Semaphore(_CONCURRENCY)

    async def _bounded(sid, url, *_):
        async with sem:
            return await _process_one(sid, url)

    results = await asyncio.gather(*[_bounded(*row) for row in candidates])

    # Build a lookup of title/hn_text for chunk building
    meta: dict[int, tuple[str, str]] = {
        row[0]: (row[2] or "", row[3] or "") for row in candidates
    }

    story_ids = [r["story_id"] for r in results]
    async with SessionLocal() as db:
        existing = await db.execute(
            select(StoryContent.story_id, StoryContent.attempts)
            .where(StoryContent.story_id.in_(story_ids))
        )
        attempt_map: dict[int, int] = {sid: att for sid, att in existing.all()}

        rows_to_upsert = []
        for r in results:
            sid = r["story_id"]
            rows_to_upsert.append({**r, "attempts": attempt_map.get(sid, 0) + 1})

        stmt = pg_insert(StoryContent).values(rows_to_upsert)
        stmt = stmt.on_conflict_do_update(
            index_elements=["story_id"],
            set_={
                "text": stmt.excluded.text,
                "content_hash": stmt.excluded.content_hash,
                "word_count": stmt.excluded.word_count,
                "status": stmt.excluded.status,
                "attempts": stmt.excluded.attempts,
                "last_error": stmt.excluded.last_error,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )
        await db.execute(stmt)

        # Build and save chunks for ok/empty stories
        for r in results:
            if r["status"] not in ("ok", "empty"):
                continue
            sid = r["story_id"]
            title, hn_text = meta[sid]
            article_text = r["text"] if r["status"] == "ok" else None
            chunks = build_chunks(title, hn_text, article_text)
            await save_chunks(db, sid, chunks)

        await db.commit()

    counts: dict[str, int] = {"ok": 0, "empty": 0, "failed": 0, "skipped": 0}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    return {"processed": len(results), **counts}
