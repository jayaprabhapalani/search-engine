from hn_search.celery_app import celery_app
from hn_search.crawler import fetch_all_stories
from hn_search.preprocessor import preprocess_stories
from hn_search.database import SessionLocal
from hn_search.models import Stories
from sqlalchemy import select
import asyncio
import redis
import os
from dotenv import load_dotenv

load_dotenv()

async def save_stories_to_db(preprocessed):
    async with SessionLocal() as db:
        for story in preprocessed:
            result=await db.execute(select(Stories).where(Stories.id==story["id"])) #returns obj not none
            existing=result.scalar_one_or_none()   # to get actual value
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
 
REDIS_URL=os.getenv("REDIS_URL")                
                   
def flush_cache():
    redis_client=redis.from_url(REDIS_URL,encoding="utf-8",decode_responses=True)
    redis_client.flushdb()
    redis_client.close()

@celery_app.task
def reindex_stories():
    #fetch stories
    stories=asyncio.run(fetch_all_stories())
    preprocessed=preprocess_stories(stories)
    
    #save to DB using asyncio.run()
    asyncio.run(save_stories_to_db(preprocessed))
    
    #flush redis
    flush_cache()
    
    return f"Reindexed {len(preprocessed)} stories"

