from fastapi import FastAPI,Depends,Request
from fastapi.responses import JSONResponse
from hn_search.crawler import fetch_all_stories
from hn_search.preprocessor import preprocess_stories
from hn_search.search import build_index,search,build_vector_index,hybrid_search
from hn_search.database import engine,Base,SessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
from hn_search.database import get_db
from hn_search.models import Stories,SearchAnalytics
from sqlalchemy import select
from hn_search.cache import get_cached_result,get_redis,set_cached_result
from hn_search.ratelimiter import check_rate_limit
import math
from hn_search.trie import Trie
import re
from sqlalchemy import func
from hn_search.tasks import reindex_stories
from fastapi.middleware.cors import CORSMiddleware

app=FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
async def search_query(q:str,page:int=1,page_size:int=5,db:AsyncSession=Depends(get_db)):
    #for pagination
    top_k=page*page_size
    
    cached_result=await get_cached_result(app_state["redis"],q,page,page_size)
    if cached_result:
        return cached_result
    
    result=hybrid_search(q,app_state["stories"],app_state["vectorizer"],app_state["tfidf_matrix"],app_state["vector_matrix"],top_k=top_k)
    
    #page calculation
    total=len(result)
    total_pages=math.ceil(total/page_size)
    
    #store the searched data and result cnt in search analytics
    search_analytics=SearchAnalytics(query=q,results_count=total)
    db.add(search_analytics)
    await db.commit()
     
    #for pagination
    start=(page-1)*page_size
    end=start+page_size
    paginated=result[start:end]
    
    await set_cached_result(app_state["redis"],q,page,page_size,{
        "results": paginated,
        "page": page,
        "total_pages": total_pages,
        "total": total
    })
    
    return {
        "results":paginated,
        "page":page,
        "page_size":page_size,
        "total":total,
        "total_pages":total_pages
        
    }


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
         