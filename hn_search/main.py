import os
import math
from fastapi import FastAPI, Depends, Request, Query, HTTPException
from fastapi.responses import JSONResponse
from hn_search.crawler import fetch_all_stories
from hn_search.preprocessor import preprocess_stories
from hn_search.search import build_index, build_vector_index, hybrid_search
from hn_search.database import engine, Base, SessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
from hn_search.database import get_db
from hn_search.models import Stories, SearchAnalytics
from sqlalchemy import select, func
from hn_search.cache import get_cached_result, get_redis, set_cached_result
from hn_search.ratelimiter import check_rate_limit
from hn_search.trie import Trie
from hn_search.tasks import reindex_stories
from fastapi.middleware.cors import CORSMiddleware

CANDIDATE_POOL_SIZE = 50
DEFAULT_PAGE_SIZE = 5
MAX_PAGE_SIZE = 20
MAX_QUERY_LENGTH = 200

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

app_state={
    "stories":[],
    "vectorizer":None,
    "tfidf_matrix":None,
    "vector_matrix":None,
    "redis":None,
    "trie":None
    
}

"""middlewares"""


#rate-limiting implementation
@app.middleware("http")
async def rate_limit_middleware(request:Request,call_next):
    ip=request.client.host
    allowed=await check_rate_limit(app_state["redis"],ip)
    
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "error":"Too many requests.Please slow down!"
            }
        )
    response=await call_next(request)
    return response    



@app.on_event("startup")
async def startup():
    #get cache
    app_state["redis"]=get_redis()
    #to create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    #reload stories table from db into memory
    async with SessionLocal() as db:
        result=await db.execute(select(Stories)) 
        stories=result.scalars().all()
        if stories:
            app_state["stories"]=[{
            "id": s.id,
            "title": s.title,
            "text": s.text,
            "preprocessed_text": s.preprocessed_text,
            "url": s.url,
            "score": s.score 
            }
            for s in stories ]
        
        if app_state["stories"]:
            vectorizer,tfidf_matrix=build_index(app_state["stories"]) 
            app_state["vectorizer"]=vectorizer
            app_state["tfidf_matrix"]=tfidf_matrix   
            app_state["vector_matrix"]=build_vector_index(app_state["stories"])
         
         #split the title into words ,lowercase it then add each word into trie for autocompletion 
        trie=Trie() 
        for story in stories:
            title=story.title.lower()
            words=title.split()
            for word in words:
                trie.insert(word)
        app_state["trie"]=trie 
               
        


@app.post("/index")
async def post_query(db:AsyncSession=Depends(get_db)):
    stories= await fetch_all_stories()
    preprocessed_stories=preprocess_stories(stories)
    for story in preprocessed_stories:
        result=await db.execute(select(Stories).where(Stories.id == story["id"]))
        existing=result.scalar_one_or_none()
        if not existing:
            new_story=Stories(
                id=story["id"],
                title=story["title"],
                text=story["text"],
                preprocessed_text=story["preprocessed_text"],
                url=story["url"],
                score=story["score"]
            )
            db.add(new_story)
    await db.commit() 
    await app_state["redis"].flushdb()  
    
    (vectorizer,tfidf_matrix)=build_index(preprocessed_stories) 
    app_state["stories"]=preprocessed_stories
    app_state["vectorizer"]=vectorizer 
    app_state["tfidf_matrix"]=tfidf_matrix 
    app_state["vector_matrix"]=build_vector_index(stories)
    
    #split the title into words ,lowercase it then add each word into trie for autocompletion
    trie=Trie() 
    for story in stories:
        title=story["title"].lower()
        words=title.split()
        for word in words:
            trie.insert(word)
    app_state["trie"]=trie        
    
    return {"message":f"Indexed {len(preprocessed_stories)} stories"}


@app.get("/search")
async def search_query(
    q: str = Query(..., min_length=1, max_length=MAX_QUERY_LENGTH),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
):
    q = q.strip()
    if not q:
        raise HTTPException(status_code=422, detail="q must not be blank")

    # 503 if index not ready
    if not app_state["stories"] or app_state["vectorizer"] is None:
        raise HTTPException(status_code=503, detail="Index not ready. Call POST /index first.")

    cached = await get_cached_result(app_state["redis"], q, page, page_size)
    if cached:
        return cached

    pool = hybrid_search(
        q,
        app_state["stories"],
        app_state["vectorizer"],
        app_state["tfidf_matrix"],
        app_state["vector_matrix"],
        top_k=CANDIDATE_POOL_SIZE,
    )

    total = len(pool)
    capped = total == CANDIDATE_POOL_SIZE
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    # Log analytics only on page 1 (prevents inflation from paging)
    if page == 1:
        db.add(SearchAnalytics(query=q, results_count=total))
        await db.commit()

    # Out-of-range page
    if total > 0 and page > total_pages:
        return {"results": [], "page": page, "page_size": page_size,
                "total": total, "total_pages": total_pages, "capped": capped}

    start = (page - 1) * page_size
    paginated = pool[start: start + page_size]

    payload = {
        "results": paginated,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "capped": capped,
    }
    await set_cached_result(app_state["redis"], q, page, page_size, payload)
    return payload


@app.post("/reindex")
async def reindex():
    reindex_stories.delay()
    return {"message":"Reindexing started in background"}
    
    

#auto-complete (using trie)
@app.get("/autocomplete")
async def autocomplete(q:str):
    return app_state["trie"].search(q)
 
 
# analytics -returns the cnts of the query
@app.get('/analytics/top-searches')
async def top_searches(db:AsyncSession=Depends(get_db)):
    result=await db.execute(
        select(SearchAnalytics.query,func.count(SearchAnalytics.query).label("count"))
        .group_by(SearchAnalytics.query)
        .order_by(func.count(SearchAnalytics.query).desc())
        .limit(10)
    )
    rows=result.all() #eg:rows is a list of tuples like [("python", 45), ("fastapi", 32), ...]
    
    return [{"query":row[0],"count":row[1]} for row in rows]
    

# to get the zero result searchs
@app.get('/analytics/zero-searches')
async def zero_searches(db:AsyncSession=Depends(get_db)):
    result=await db.execute(
        select(SearchAnalytics.query,SearchAnalytics.timestamp)
        .where(SearchAnalytics.results_count==0)
        .order_by(SearchAnalytics.timestamp.desc())
        .limit(20)
    )
    
    rows=result.all()
    
    return [{"query":row[0],"timestamp":row[1]} for row in rows]
         