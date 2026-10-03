"""
Backfill HN stories via the Algolia search API.

Usage:
    python -m hn_search.backfill --days 365 --min-points 100

Options:
    --days          How many days back to fetch (default: 365)
    --min-points    Minimum HN score to include (default: 100)
    --window-days   Initial window size in days (default: 7)
    --delay         Seconds between requests (default: 0.5)
    --progress-file Path to resumability file (default: .backfill_progress.json)
"""
import argparse
import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from sqlalchemy.dialects.postgresql import insert as pg_insert

from hn_search.database import SessionLocal, engine
from hn_search.models import Stories
from hn_search.preprocessor import clean_html, preprocess_text

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

_ALGOLIA_URL = "https://hn.algolia.com/api/v1/search"
_PAGE_SIZE = 1000  # Algolia max hitsPerPage
_HIT_CAP = 1000   # if a window returns this many hits, shrink the window
_BATCH_SIZE = 500
_MAX_RETRIES = 3


def _parse_domain(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url).hostname or ""
        return host.removeprefix("www.") or None
    except Exception:
        return None


def _window_key(start: datetime, end: datetime) -> str:
    return f"{int(start.timestamp())}_{int(end.timestamp())}"


def _load_progress(path: Path) -> set[str]:
    if path.exists():
        try:
            return set(json.loads(path.read_text()))
        except Exception:
            pass
    return set()


def _save_progress(path: Path, done: set[str]) -> None:
    path.write_text(json.dumps(sorted(done)))


async def _fetch_window(
    client: httpx.AsyncClient,
    start: datetime,
    end: datetime,
    min_points: int,
    delay: float,
) -> list[dict]:
    """Fetch all hits in [start, end) from Algolia, paginating."""
    hits = []
    page = 0
    while True:
        params = {
            "tags": "story",
            "numericFilters": (
                f"created_at_i>={int(start.timestamp())},"
                f"created_at_i<{int(end.timestamp())},"
                f"points>={min_points}"
            ),
            "hitsPerPage": _PAGE_SIZE,
            "page": page,
            "attributesToRetrieve": "objectID,title,url,points,num_comments,created_at,story_text",
        }
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await client.get(_ALGOLIA_URL, params=params, timeout=15.0)
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as e:
                if attempt == _MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(2 ** attempt)

        hits.extend(data.get("hits", []))
        nb_pages = data.get("nbPages", 1)
        page += 1
        if page >= nb_pages:
            break
        await asyncio.sleep(delay)

    return hits


def _hit_to_row(hit: dict, now: datetime) -> dict | None:
    story_id = hit.get("objectID")
    title = hit.get("title", "").strip()
    if not story_id or not title:
        return None
    try:
        story_id = int(story_id)
    except (ValueError, TypeError):
        return None

    url = hit.get("url") or None
    raw_text = clean_html(hit.get("story_text") or "")
    full_text = (title + " " + raw_text).strip()

    created_ts = hit.get("created_at")
    created_at = None
    if created_ts:
        try:
            created_at = datetime.fromisoformat(created_ts.replace("Z", "+00:00"))
        except Exception:
            pass

    return {
        "id": story_id,
        "title": title,
        "text": full_text,
        "preprocessed_text": preprocess_text(full_text),
        "url": url,
        "domain": _parse_domain(url),
        "score": hit.get("points") or 0,
        "descendants": hit.get("num_comments") or 0,
        "created_at": created_at,
        "fetched_at": now,
    }


async def _upsert_rows(rows: list[dict]) -> int:
    if not rows:
        return 0
    async with SessionLocal() as db:
        for i in range(0, len(rows), _BATCH_SIZE):
            batch = rows[i: i + _BATCH_SIZE]
            stmt = pg_insert(Stories).values(batch)
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
            await db.execute(stmt)
        await db.commit()
    return len(rows)


async def run_backfill(
    days: int,
    min_points: int,
    window_days: int,
    delay: float,
    progress_file: Path,
) -> None:
    done = _load_progress(progress_file)
    logger.info("Resuming: %d windows already completed", len(done))

    now = datetime.now(tz=timezone.utc)
    end = now
    start = now - timedelta(days=days)

    total_upserted = 0
    windows_done = 0

    async with httpx.AsyncClient(follow_redirects=True) as client:
        cursor = start
        while cursor < end:
            win_end = min(cursor + timedelta(days=window_days), end)
            key = _window_key(cursor, win_end)

            if key in done:
                logger.info("Skipping window %s (already done)", key)
                cursor = win_end
                continue

            logger.info(
                "Fetching window %s → %s",
                cursor.strftime("%Y-%m-%d"),
                win_end.strftime("%Y-%m-%d"),
            )

            try:
                hits = await _fetch_window(client, cursor, win_end, min_points, delay)
            except Exception as e:
                logger.error("Window %s failed: %s — skipping", key, e)
                cursor = win_end
                continue

            # If we hit the cap, shrink the window and retry
            if len(hits) >= _HIT_CAP and window_days > 1:
                window_days = max(1, window_days // 2)
                logger.warning(
                    "Hit cap (%d) — shrinking window to %d day(s) and retrying",
                    _HIT_CAP, window_days,
                )
                continue  # don't advance cursor

            rows = [r for hit in hits if (r := _hit_to_row(hit, now)) is not None]
            upserted = await _upsert_rows(rows)
            total_upserted += upserted

            done.add(key)
            _save_progress(progress_file, done)
            windows_done += 1

            logger.info(
                "Window done: %d hits → %d rows upserted (total so far: %d)",
                len(hits), upserted, total_upserted,
            )

            cursor = win_end
            await asyncio.sleep(delay)

    logger.info(
        "Backfill complete: %d windows, %d rows upserted",
        windows_done, total_upserted,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill HN stories from Algolia")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--min-points", type=int, default=100)
    parser.add_argument("--window-days", type=int, default=7)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--progress-file", type=Path, default=Path(".backfill_progress.json"))
    args = parser.parse_args()

    asyncio.run(
        run_backfill(
            days=args.days,
            min_points=args.min_points,
            window_days=args.window_days,
            delay=args.delay,
            progress_file=args.progress_file,
        )
    )
    asyncio.run(engine.dispose())


if __name__ == "__main__":
    main()
