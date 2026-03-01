from fastapi import FastAPI,Depends
from crawler import fetch_all_stories
from preprocessor import preprocess_stories
from search import build_index,search
from database import engine,Base,SessionLocal
import models
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Stories
from sqlalchemy import select

app=FastAPI()

app_state={
    "stories":[],
    "vectorizer":None,
    "tfidf_matrix":None
    
}

@app.on_event("startup")
async def startup():
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
    
    (vectorizer,tfidf_matrix)=build_index(preprocessed_stories) 
    app_state["stories"]=preprocessed_stories
    app_state["vectorizer"]=vectorizer 
    app_state["tfidf_matrix"]=tfidf_matrix 
    
    return {"message":f"Indexed {len(preprocessed_stories)} stories"}

@app.get("/search")
async def search_query(q:str):
    result=search(q,app_state["stories"],app_state["vectorizer"],app_state["tfidf_matrix"])
    return result