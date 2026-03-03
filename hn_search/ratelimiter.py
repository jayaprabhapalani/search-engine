import time
import uuid

WINDOW_SIZE_SECONDS=60
async def check_rate_limit(redis_client,ip,limit=10,window=60)->bool:
   
    key=f"rate_limit:{ip}"
    now=time.time()
    
    #define window
    window_start=now-WINDOW_SIZE_SECONDS
    
    # Atomic operations via Redis Pipeline
    async with redis_client.pipeline(transaction=True) as pipe:
        #remove old entries
        pipe.zremrangebyscore(key, 0, window_start)

        #cnt the current entries
        pipe.zcard(key)
        
        #Add current request
        unique_req_id=f"{now}:{uuid.uuid4()}"
        pipe.zadd(key,{unique_req_id: now})
        
        #set TTL
        pipe.expire(key,WINDOW_SIZE_SECONDS)
        
        #execute pipeline
        result=await pipe.execute()
        
    current_cnt=result[1]
    
    if current_cnt>=limit:
        return False
    return True
        
    
