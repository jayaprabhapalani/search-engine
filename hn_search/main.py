import asyncio
import logging
import math
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from hn_search.cache import (
    build_pool_key, bump_index_version, get_cached_pool,
    get_index_version, get_redis, set_cached_pool,
)
from hn_search.database import SessionLocal, engine, get_db, init_pgvector
from hn_search.embeddings import EMBEDDING_MODEL
from hn_search.models import Chunk, ChunkEmbedding, SearchAnalytics, Stories
from hn_search.preprocessor import clean_html, preprocess_text
from hn_search.ratelimiter import check_rate_limit
from hn_search.search import build_index, hybrid_search
from hn_search.trie import Trie
from hn_search.utils import normalize_query

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

CANDIDATE_POOL_SIZE = 50
DEFAULT_PAGE_SIZE = 5
MAX_PAGE_SIZE = 20
MAX_QUERY_LENGTH = 200
INDEX_POLL_SECONDS = int(os.getenv("INDEX_POLL_SECONDS", "30"))
REINDEX_COOLDOWN_SECONDS = int(os.getenv("REINDEX_COOLDOWN_SECONDS", "300"))
_REINDEX_COOLDOWN_KEY = "hn:reindex_cooldown"
_LAST_INGEST_KEY = "hn:last_ingest_stats"


# ---------------------------------------------------------------------------
# Index snapshot
# ---------------------------------------------------------------------------

@dataclass
class IndexSnapshot:
    chunks: list           # all chunks (keyword search)
    vec_chunks: list       # subset with embeddings: [{chunk_id, chunk}]
    vector_matrix: Optional[np.ndarray]  # (len(vec_chunks), 384) float32
    story_map: dict        # story_id -> story_meta dict
    vectorizer: object
    tfidf_matrix: object
    trie: object
    version: int
    doc_count: int
    chunk_count: int
    embedded_count: int
    loaded_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


# ---------------------------------------------------------------------------
# App state
# ---------------------------------------------------------------------------

_index: Optional[IndexSnapshot] = None
_reload_lock = asyncio.Lock()
_redis = None


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ResultItem(BaseModel):
    id: int
    title: str
    url: Optional[str] = None
    hn_url: str
    relevance: float = PydanticField(..., description="Relevance score rounded to 4 decimals")
    points: int = 0
    domain: Optional[str] = None
    descendants: int = 0
    created_at: Optional[str] = None
    snippet: str

class SearchResponse(BaseModel):
    results: list[ResultItem]
    page: int
    page_size: int
    total: int
    total_pages: int
    capped: bool

class TopSearchItem(BaseModel):
    query: str
    count: int

class ZeroSearchItem(BaseModel):
    query: str
    timestamp: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def to_result_item(story: dict) -> dict:
    ca = story.get("created_at")
    return {
        "id": story["id"],
        "title": story["title"],
        "url": story.get("url") or None,
        "hn_url": f"https://news.ycombinator.com/item?id={story['id']}",
        "relevance": story["relevance"],
        "points": story.get("points") or 0,
        "domain": story.get("domain"),
        "descendants": story.get("descendants") or 0,
        "created_at": ca.isoformat() if hasattr(ca, "isoformat") else ca,
        "snippet": story.get("snippet", ""),
    }


async def _record_analytics(normalized_q: str, total: int) -> None:
    try:
        async with SessionLocal() as db:
            db.add(SearchAnalytics(query=normalized_q, results_count=total))
            await db.commit()
    except Exception as e:
        logger.warning("Analytics write failed: %s", e)


# ---------------------------------------------------------------------------
# Index loader
# ---------------------------------------------------------------------------

async def _build_snapshot(version: int) -> Optional[IndexSnapshot]:
    """Read stories, chunks, and embeddings from DB. Returns None if no data."""
    async with SessionLocal() as db:
        story_rows = (await db.execute(select(Stories))).scalars().all()
        chunk_rows = (await db.execute(
            select(Chunk).order_by(Chunk.story_id, Chunk.chunk_index)
        )).scalars().all()
        # Read embeddings for current model
        emb_rows = (await db.execute(
            select(ChunkEmbedding.chunk_id, ChunkEmbedding.embedding)
            .where(ChunkEmbedding.model == EMBEDDING_MODEL)
        )).all()

    if not story_rows:
        return None

    story_map: dict[int, dict] = {
        s.id: {
            "id": s.id,
            "title": s.title or "",
            "url": s.url,
            "domain": s.domain,
            "points": s.score or 0,
            "descendants": s.descendants or 0,
            "created_at": s.created_at,
        }
        for s in story_rows
    }

    # Build embedding lookup: chunk_id -> vector
    emb_map: dict[int, list] = {cid: vec for cid, vec in emb_rows}

    chunks: list[dict] = []
    chunked_stories: set[int] = set()
    for c in chunk_rows:
        meta = story_map.get(c.story_id)
        if meta is None:
            continue
        chunked_stories.add(c.story_id)
        chunks.append({
            "chunk_id": c.id,
            "story_id": c.story_id,
            "chunk_index": c.chunk_index,
            "chunk_text": c.text,
            "preprocessed_text": preprocess_text(c.text),
            "title": meta["title"],
            "story_meta": meta,
        })

    # Fallback for stories with no chunks yet
    for s in story_rows:
        if s.id in chunked_stories:
            continue
        raw = clean_html(s.text or "")
        fallback_text = ((s.title or "") + " " + raw).strip()
        chunks.append({
            "chunk_id": None,
            "story_id": s.id,
            "chunk_index": 0,
            "chunk_text": fallback_text,
            "preprocessed_text": preprocess_text(fallback_text),
            "title": s.title or "",
            "story_meta": story_map[s.id],
        })

    if not chunks:
        return None

    # Build vector matrix from DB embeddings (only chunks that have one)
    vec_chunks: list[dict] = []
    vec_list: list = []
    for c in chunks:
        cid = c["chunk_id"]
        if cid is not None and cid in emb_map:
            vec_chunks.append({"chunk_id": cid, "chunk": c})
            vec_list.append(emb_map[cid])

    vector_matrix: Optional[np.ndarray] = None
    if vec_list:
        vector_matrix = np.array(vec_list, dtype=np.float32)

    # CPU-bound: build TF-IDF in a thread so we don't block the event loop
    vectorizer, tfidf_matrix = await asyncio.to_thread(build_index, chunks)

    trie = Trie()
    for meta in story_map.values():
        for word in meta["title"].lower().split():
            trie.insert(word)

    return IndexSnapshot(
        chunks=chunks,
        vec_chunks=vec_chunks,
        vector_matrix=vector_matrix,
        story_map=story_map,
        vectorizer=vectorizer,
        tfidf_matrix=tfidf_matrix,
        trie=trie,
        version=version,
        doc_count=len(story_map),
        chunk_count=len(chunks),
        embedded_count=len(vec_chunks),
    )


async def load_app_state_from_db() -> None:
    """Rebuild the index snapshot from DB. Atomic swap at the end."""
    global _index
    async with _reload_lock:
        version = await get_index_version(_redis)
        try:
            snapshot = await _build_snapshot(version)
        except Exception as e:
            logger.error("Index build failed: %s", e)
            return
        if snapshot is not None:
            _index = snapshot
            logger.info(
                "Index loaded: %d stories, %d chunks, %d embedded at version %d",
                snapshot.doc_count, snapshot.chunk_count, snapshot.embedded_count, version,
            )
        else:
            logger.info("No stories in DB — skipping index build")


def _build_snapshot_sync(version: int) -> Optional[IndexSnapshot]:
    """Synchronous wrapper so we can run _build_snapshot in a thread."""
    return asyncio.run(_build_snapshot(version))


# ---------------------------------------------------------------------------
# Background poller
# ---------------------------------------------------------------------------

async def _poll_index() -> None:
    while True:
        try:
            await asyncio.sleep(INDEX_POLL_SECONDS)
            current_version = await get_index_version(_redis)
            snap = _index
            if snap is None or snap.version != current_version:
                logger.info(
                    "Index stale (snapshot=%s, redis=%s) — reloading",
                    snap.version if snap else None,
                    current_version,
                )
                await load_app_state_from_db()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("Poller error (will retry): %s", e)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis
    _redis = get_redis()

    await init_pgvector()
    await load_app_state_from_db()

    if _index is None:
        logger.info("Empty DB on startup — enqueuing initial reindex")
        from hn_search.tasks import reindex_stories
        reindex_stories.delay()

    poller = asyncio.create_task(_poll_index())

    yield

    poller.cancel()
    try:
        await poller
    except asyncio.CancelledError:
        pass
    await _redis.aclose()
    await engine.dispose()
    logger.info("Shutdown complete")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(lifespan=lifespan)

_cors_origins = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    try:
        allowed = await check_rate_limit(_redis, request.client.host)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests. Please slow down!"},
            )
    except Exception as e:
        logger.warning("Rate limiter error (fail-open): %s", e)
    return await call_next(request)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/index/status")
async def index_status():
    import json
    snap = _index
    redis_version = await get_index_version(_redis)
    last_stats = None
    try:
        raw = await _redis.get(_LAST_INGEST_KEY)
        if raw:
            last_stats = json.loads(raw)
    except Exception:
        pass

    chunk_count = snap.chunk_count if snap else 0
    embedded_count = snap.embedded_count if snap else 0
    coverage = round(embedded_count / chunk_count * 100, 1) if chunk_count > 0 else 0.0

    return {
        "snapshot_version": snap.version if snap else None,
        "doc_count": snap.doc_count if snap else 0,
        "chunk_count": chunk_count,
        "embedded_count": embedded_count,
        "embedding_coverage_pct": coverage,
        "embedding_model": EMBEDDING_MODEL,
        "loaded_at": snap.loaded_at.isoformat() if snap else None,
        "redis_version": redis_version,
        "stale": (snap.version != redis_version) if snap else True,
        "last_ingest": last_stats,
    }


@app.post("/reindex", status_code=202)
async def reindex():
    from hn_search.tasks import reindex_stories
    try:
        ttl = await _redis.ttl(_REINDEX_COOLDOWN_KEY)
        if ttl > 0:
            raise HTTPException(
                status_code=429,
                detail=f"Recently refreshed. Try again in {ttl} seconds.",
            )
        await _redis.set(_REINDEX_COOLDOWN_KEY, "1", ex=REINDEX_COOLDOWN_SECONDS)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Cooldown check failed (proceeding): %s", e)

    task = reindex_stories.delay()
    return {"message": "Reindexing started", "task_id": task.id}


@app.get("/search", response_model=SearchResponse)
async def search_query(
    request: Request,
    background_tasks: BackgroundTasks,
    q: str = Query(..., min_length=1, max_length=MAX_QUERY_LENGTH),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
):
    nq = normalize_query(q)
    if not nq:
        raise HTTPException(status_code=422, detail="q must not be blank")

    snap = _index
    if snap is None:
        raise HTTPException(status_code=503, detail="Index not ready. Try again shortly.")

    pool_key = build_pool_key(nq, snap.version)
    pool = await get_cached_pool(_redis, pool_key)
    cache_status = "HIT"

    if pool is None:
        cache_status = "MISS"
        raw_pool = await asyncio.to_thread(
            hybrid_search,
            nq,
            snap.chunks,
            snap.vectorizer,
            snap.tfidf_matrix,
            snap.vector_matrix,
            snap.vec_chunks,
            CANDIDATE_POOL_SIZE,
        )
        pool = [to_result_item(s) for s in raw_pool]
        await set_cached_pool(_redis, pool_key, pool)

    total = len(pool)
    capped = total == CANDIDATE_POOL_SIZE
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    if page == 1:
        background_tasks.add_task(_record_analytics, nq, total)

    if total > 0 and page > total_pages:
        body = SearchResponse(
            results=[], page=page, page_size=page_size,
            total=total, total_pages=total_pages, capped=capped,
        )
        resp = Response(content=body.model_dump_json(), media_type="application/json")
        resp.headers["X-Cache"] = cache_status
        return resp

    start = (page - 1) * page_size
    body = SearchResponse(
        results=pool[start: start + page_size],
        page=page, page_size=page_size,
        total=total, total_pages=total_pages, capped=capped,
    )
    resp = Response(content=body.model_dump_json(), media_type="application/json")
    resp.headers["X-Cache"] = cache_status
    return resp


@app.get("/autocomplete")
async def autocomplete(q: str):
    snap = _index
    if snap is None or snap.trie is None:
        return []
    return snap.trie.search(q)


@app.get("/analytics/top-searches", response_model=list[TopSearchItem])
async def top_searches(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SearchAnalytics.query, func.count(SearchAnalytics.query).label("count"))
        .group_by(SearchAnalytics.query)
        .order_by(func.count(SearchAnalytics.query).desc())
        .limit(10)
    )
    return [{"query": row[0], "count": row[1]} for row in result.all()]


@app.get("/analytics/zero-searches", response_model=list[ZeroSearchItem])
async def zero_searches(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SearchAnalytics.query, SearchAnalytics.timestamp)
        .where(SearchAnalytics.results_count == 0)
        .order_by(SearchAnalytics.timestamp.desc())
        .limit(20)
    )
    return [{"query": row[0], "timestamp": str(row[1])} for row in result.all()]
