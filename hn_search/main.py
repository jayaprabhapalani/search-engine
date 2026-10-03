import os
import math
import logging
from fastapi import FastAPI, Depends, Request, Query, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from hn_search.crawler import fetch_all_stories
from hn_search.preprocessor import preprocess_stories, preprocess_text
from hn_search.search import build_index, build_vector_index, hybrid_search
from hn_search.database import engine, Base, SessionLocal
from hn_search.database import get_db
from hn_search.models import Stories, SearchAnalytics
from hn_search.cache import (
    get_redis, get_cached_pool, set_cached_pool,
    get_index_version, bump_index_version, build_pool_key,
)
from hn_search.ratelimiter import check_rate_limit
from hn_search.trie import Trie
from hn_search.tasks import reindex_stories
from hn_search.utils import normalize_query

logger = logging.getLogger(__name__)

CANDIDATE_POOL_SIZE = 50
DEFAULT_PAGE_SIZE = 5
MAX_PAGE_SIZE = 20
MAX_QUERY_LENGTH = 200
SNIPPET_LENGTH = 200

# --- Pydantic models ---

class ResultItem(BaseModel):
    id: int
    title: str
    url: Optional[str] = None
    score: float = Field(..., description="Relevance score rounded to 4 decimals")
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


# --- App setup ---

app = FastAPI()

_cors_origins = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app_state = {
    "stories": [],
    "vectorizer": None,
    "tfidf_matrix": None,
    "vector_matrix": None,
    "redis": None,
    "trie": None,
}


# --- Helpers ---

def make_snippet(text: str, title: str) -> str:
    """Strip the leading title from text and truncate to SNIPPET_LENGTH chars."""
    body = text[len(title):].strip() if text.startswith(title) else text.strip()
    return body[:SNIPPET_LENGTH] + ("…" if len(body) > SNIPPET_LENGTH else "")


def to_result_item(story: dict) -> dict:
    return {
        "id": story["id"],
        "title": story["title"],
        "url": story.get("url") or None,
        "score": round(story["score"], 4),
        "snippet": make_snippet(story.get("text", ""), story.get("title", "")),
    }


async def _record_analytics(normalized_q: str, total: int) -> None:
    try:
        async with SessionLocal() as db:
            db.add(SearchAnalytics(query=normalized_q, results_count=total))
            await db.commit()
    except Exception as e:
        logger.warning("Analytics write failed: %s", e)


# --- Middleware ---

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    try:
        ip = request.client.host
        allowed = await check_rate_limit(app_state["redis"], ip)
        if not allowed:
            return JSONResponse(status_code=429, content={"error": "Too many requests. Please slow down!"})
    except Exception as e:
        logger.warning("Rate limiter error (fail-open): %s", e)
    return await call_next(request)


# --- Startup ---

@app.on_event("startup")
async def startup():
    app_state["redis"] = get_redis()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        result = await db.execute(select(Stories))
        stories = result.scalars().all()
        if stories:
            app_state["stories"] = [
                {"id": s.id, "title": s.title, "text": s.text,
                 "preprocessed_text": preprocess_text(s.text),  # recompute — never stale
                 "url": s.url, "score": s.score}
                for s in stories
            ]

        if app_state["stories"]:
            vectorizer, tfidf_matrix = build_index(app_state["stories"])
            app_state["vectorizer"] = vectorizer
            app_state["tfidf_matrix"] = tfidf_matrix
            app_state["vector_matrix"] = build_vector_index(app_state["stories"])

        trie = Trie()
        for story in stories:
            for word in story.title.lower().split():
                trie.insert(word)
        app_state["trie"] = trie


# --- Routes ---

@app.post("/index")
async def post_query(db: AsyncSession = Depends(get_db)):
    stories = await fetch_all_stories()
    preprocessed_stories = preprocess_stories(stories)
    for story in preprocessed_stories:
        result = await db.execute(select(Stories).where(Stories.id == story["id"]))
        if not result.scalar_one_or_none():
            db.add(Stories(
                id=story["id"], title=story["title"], text=story["text"],
                preprocessed_text=story["preprocessed_text"],
                url=story["url"], score=story["score"],
            ))
    await db.commit()

    # Invalidate cache without touching rate-limit keys
    await bump_index_version(app_state["redis"])

    vectorizer, tfidf_matrix = build_index(preprocessed_stories)
    app_state["stories"] = preprocessed_stories
    app_state["vectorizer"] = vectorizer
    app_state["tfidf_matrix"] = tfidf_matrix
    app_state["vector_matrix"] = build_vector_index(stories)

    trie = Trie()
    for story in stories:
        for word in story["title"].lower().split():
            trie.insert(word)
    app_state["trie"] = trie

    return {"message": f"Indexed {len(preprocessed_stories)} stories"}


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

    if not app_state["stories"] or app_state["vectorizer"] is None:
        raise HTTPException(status_code=503, detail="Index not ready. Call POST /index first.")

    version = await get_index_version(app_state["redis"])
    pool_key = build_pool_key(nq, version)

    pool = await get_cached_pool(app_state["redis"], pool_key)
    cache_status = "HIT"

    if pool is None:
        cache_status = "MISS"
        raw_pool = hybrid_search(
            nq,
            app_state["stories"],
            app_state["vectorizer"],
            app_state["tfidf_matrix"],
            app_state["vector_matrix"],
            top_k=CANDIDATE_POOL_SIZE,
        )
        pool = [to_result_item(s) for s in raw_pool]
        await set_cached_pool(app_state["redis"], pool_key, pool)

    total = len(pool)
    capped = total == CANDIDATE_POOL_SIZE
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    # Analytics on page 1 only (hits and misses), using normalized query
    if page == 1:
        background_tasks.add_task(_record_analytics, nq, total)

    if total > 0 and page > total_pages:
        response_body = SearchResponse(
            results=[], page=page, page_size=page_size,
            total=total, total_pages=total_pages, capped=capped,
        )
        resp = Response(
            content=response_body.model_dump_json(),
            media_type="application/json",
        )
        resp.headers["X-Cache"] = cache_status
        return resp

    start = (page - 1) * page_size
    paginated = pool[start: start + page_size]

    response_body = SearchResponse(
        results=paginated, page=page, page_size=page_size,
        total=total, total_pages=total_pages, capped=capped,
    )
    resp = Response(
        content=response_body.model_dump_json(),
        media_type="application/json",
    )
    resp.headers["X-Cache"] = cache_status
    return resp


@app.post("/reindex")
async def reindex():
    reindex_stories.delay()
    return {"message": "Reindexing started in background"}


@app.get("/autocomplete")
async def autocomplete(q: str):
    if app_state["trie"] is None:
        return []
    return app_state["trie"].search(q)


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
