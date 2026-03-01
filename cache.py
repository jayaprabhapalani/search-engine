import redis.asyncio as redis
from redis.asyncio.client import Redis
import os
from dotenv import load_dotenv
import json


load_dotenv()

REDIS_URL=os.getenv("REDIS_URL")
CACHE_TTL_SECONDS=1800 #half-an hour

def get_redis()->Redis:
    return redis.from_url(REDIS_URL,encoding="utf-8",decode_responses=True)

# Checks if a cached result exists for this query
async def get_cached_result(redis_client:Redis,query):
    cache_key=f"search:{query}"
    
    #check if the data is in cache
    cached_data=await redis_client.get(cache_key)
    if cached_data:
        return {
            "result":json.loads(cached_data),
            "cache":"hit"
        }
    return None

# Stores search results in Redis with an expiry time. 
async def set_cached_result(redis_client:Redis,query,results,ttl=3600):
    cache_key=f"search:{query}"
    
    await redis_client.setex(cache_key,ttl,json.dumps(results))
    return {
        "key":cache_key,
        "value":results,
        "cached":"True"
    }
       
    