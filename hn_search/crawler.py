import asyncio
import logging
import os
import random
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

from hn_search.preprocessor import clean_html

load_dotenv()

logger = logging.getLogger(__name__)

BASE_URL = os.getenv("HACKERNEWS_BASE_URL", "https://hacker-news.firebaseio.com/v0/")
_CONCURRENCY = 20
_MAX_RETRIES = 3
_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
_LIMITS = httpx.Limits(max_connections=30, max_keepalive_connections=20)


async def _get_with_retry(client: httpx.AsyncClient, url: str) -> httpx.Response:
    for attempt in range(_MAX_RETRIES):
        try:
            resp = await client.get(url)
            if resp.status_code == 404:
                resp.raise_for_status()
            if resp.status_code in (429,) or resp.status_code >= 500:
                retry_after = float(resp.headers.get("Retry-After", 0))
                wait = max(retry_after, (2 ** attempt) + random.uniform(0, 1))
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(wait)
                    continue
            resp.raise_for_status()
            return resp
        except httpx.TimeoutException:
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep((2 ** attempt) + random.uniform(0, 1))
                continue
            raise
        except httpx.HTTPStatusError:
            raise
    raise RuntimeError(f"Exhausted retries for {url}")


async def fetch_feed_ids(feed: str) -> list[int]:
    """Return the full list of story IDs for a named feed."""
    async with httpx.AsyncClient(timeout=_TIMEOUT, limits=_LIMITS, follow_redirects=True) as client:
        resp = await _get_with_retry(client, f"{BASE_URL}{feed}.json")
        return list(dict.fromkeys(resp.json()))  # dedupe, preserve order


async def _fetch_item(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    item_id: int,
) -> dict | None:
    async with sem:
        try:
            resp = await _get_with_retry(client, f"{BASE_URL}item/{item_id}.json")
            data = resp.json()
        except Exception as e:
            logger.warning("Failed to fetch item %s: %s", item_id, e)
            return None

        if not data:
            return None
        if data.get("deleted") or data.get("dead"):
            return None
        if data.get("type") != "story":
            return None
        if not data.get("title"):
            return None

        ts = data.get("time")
        created_at = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None

        return {
            "id": data["id"],
            "title": data["title"],
            "text": data["title"] + " " + clean_html(data.get("text", "")),
            "url": data.get("url") or None,
            "score": data.get("score", 0),
            "descendants": data.get("descendants", 0),
            "created_at": created_at,
        }


async def fetch_stories_by_ids(ids: list[int]) -> tuple[list[dict], dict]:
    """Fetch story details for a list of IDs. Returns (stories, stats)."""
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, limits=_LIMITS, follow_redirects=True
    ) as client:
        sem = asyncio.Semaphore(_CONCURRENCY)
        results = await asyncio.gather(
            *[_fetch_item(client, sem, id_) for id_ in ids],
            return_exceptions=False,
        )

    stories = [r for r in results if r is not None]
    stats = {
        "requested": len(ids),
        "fetched": len(stories),
        "skipped": len(ids) - len(stories),
        "failed": 0,
    }
    logger.info("Crawl complete: %s", stats)
    return stories, stats


# Kept for backwards compatibility (tests, etc.)
async def fetch_all_stories(
    limit: int = 200,
    feed: str = "topstories",
) -> tuple[list[dict], dict]:
    ids = (await fetch_feed_ids(feed))[:limit]
    return await fetch_stories_by_ids(ids)
