import asyncio
import json
import pytest
import httpx

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _story(id_, **kwargs):
    base = {"id": id_, "type": "story", "title": f"Story {id_}", "score": 10, "time": 1700000000}
    base.update(kwargs)
    return base


def _make_transport(items: dict, top_ids: list, attempt_counts: dict | None = None):
    """
    items: {id: story_dict | None | Exception | list-of-responses}
    top_ids: list of ints for the topstories endpoint
    attempt_counts: mutable dict to track per-id call counts
    """
    if attempt_counts is None:
        attempt_counts = {}
    call_log = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "topstories" in url:
            return httpx.Response(200, json=top_ids)

        # extract id from URL like .../item/42.json
        id_ = int(url.split("/item/")[1].split(".")[0])
        call_log[id_] = call_log.get(id_, 0) + 1
        if attempt_counts is not None:
            attempt_counts[id_] = call_log[id_]

        val = items.get(id_)
        if val is None:
            return httpx.Response(200, json=None)
        if isinstance(val, list):
            # pop first response, use last repeatedly
            resp = val.pop(0) if len(val) > 1 else val[0]
            return resp
        if isinstance(val, httpx.Response):
            return val
        return httpx.Response(200, json=val)

    return httpx.MockTransport(handler)


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Patch crawler to use mock transport
# ---------------------------------------------------------------------------

import hn_search.crawler as crawler_mod


def _patched_fetch(transport, limit=10, feed="topstories"):
    import httpx
    original_client = httpx.AsyncClient

    async def _inner():
        async with httpx.AsyncClient(transport=transport) as client:
            # bypass the real client creation in fetch_all_stories
            from hn_search.crawler import _fetch_item, _get_with_retry, BASE_URL
            import asyncio as _asyncio

            resp = await _get_with_retry(client, f"{BASE_URL}{feed}.json")
            ids = list(dict.fromkeys(resp.json()[:limit]))
            sem = _asyncio.Semaphore(crawler_mod._CONCURRENCY)
            results = await _asyncio.gather(
                *[_fetch_item(client, sem, id_) for id_ in ids]
            )
        stories = [r for r in results if r is not None]
        skipped = len(ids) - len(stories)
        stats = {"requested": len(ids), "fetched": len(stories), "skipped": skipped, "failed": 0}
        return stories, stats

    return _asyncio_run(_inner())


def _asyncio_run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_skips_null_deleted_dead_job():
    items = {
        1: None,
        2: {"id": 2, "type": "story", "title": "T", "score": 1, "time": 1, "deleted": True},
        3: {"id": 3, "type": "story", "title": "T", "score": 1, "time": 1, "dead": True},
        4: {"id": 4, "type": "job", "title": "Job", "score": 0, "time": 1},
        5: _story(5),
    }
    transport = _make_transport(items, [1, 2, 3, 4, 5])
    stories, stats = _patched_fetch(transport, limit=5)
    ids = [s["id"] for s in stories]
    assert ids == [5]
    assert stats["skipped"] == 4


def test_missing_score_defaults_to_zero():
    items = {1: {"id": 1, "type": "story", "title": "No score", "time": 1}}
    transport = _make_transport(items, [1])
    stories, _ = _patched_fetch(transport, limit=1)
    assert stories[0]["score"] == 0


def test_retry_on_500_then_200():
    attempt_counts = {}
    items = {
        1: [
            httpx.Response(500),
            httpx.Response(200, json=_story(1)),
        ]
    }
    transport = _make_transport(items, [1], attempt_counts)
    stories, stats = _patched_fetch(transport, limit=1)
    assert len(stories) == 1
    assert attempt_counts.get(1, 0) == 2


def test_persistent_500_counted_as_skipped():
    items = {
        1: [httpx.Response(500), httpx.Response(500), httpx.Response(500)],
        2: _story(2),
    }
    transport = _make_transport(items, [1, 2])
    stories, stats = _patched_fetch(transport, limit=2)
    ids = [s["id"] for s in stories]
    assert 2 in ids
    assert 1 not in ids


def test_404_not_retried():
    attempt_counts = {}
    items = {1: httpx.Response(404)}
    transport = _make_transport(items, [1], attempt_counts)
    stories, _ = _patched_fetch(transport, limit=1)
    assert len(stories) == 0
    assert attempt_counts.get(1, 0) == 1   # only one attempt


def test_concurrency_never_exceeds_semaphore():
    import threading
    active = {"count": 0, "max": 0}
    lock = threading.Lock()

    base_items = {i: _story(i) for i in range(1, 51)}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "topstories" in url:
            return httpx.Response(200, json=list(range(1, 51)))
        id_ = int(url.split("/item/")[1].split(".")[0])
        with lock:
            active["count"] += 1
            active["max"] = max(active["max"], active["count"])
        import time; time.sleep(0.001)
        with lock:
            active["count"] -= 1
        return httpx.Response(200, json=base_items[id_])

    transport = httpx.MockTransport(handler)
    _patched_fetch(transport, limit=50)
    assert active["max"] <= crawler_mod._CONCURRENCY


def test_failing_topstories_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    with pytest.raises(Exception):
        _patched_fetch(transport, limit=5)
