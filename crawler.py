import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL=os.getenv("HACKERNEWS_BASE_URL")

# to get the top 200 ids
async def fetch_top_story_ids(limit:int=200):
    async with httpx.AsyncClient(timeout=10.0) as client:
        response= await client.get(f'{BASE_URL}topstories.json')
        data=response.json()
        return data[:limit]
        
# to get each stories using id
async def fetch_single_story(client:httpx.AsyncClient,id):
    try:
        response=await client.get(f'{BASE_URL}item/{id}.json')
        data=response.json()
        
        if data is not None:
            if data["type"]=="story":
                return {
                    "id": data["id"],
                    "title": data["title"],
                    "text": data["title"]+" "+data.get("text",""),
                    "url": data.get("url",""),
                    "score": data["score"],  
                }    
    except:
        return None

  
async def fetch_all_stories(limit=200,keyword=None):
    """
    if user asked anyting-->keyword
        -call fecth id-to fetch those id
        -then using id fetch each story and store it in a list
        -fliter out none stoires
        -if keyowrd given then filter that specific stories and return
    """  
    ids= await fetch_top_story_ids(limit)
    async with httpx.AsyncClient(timeout=10.0) as client:
        result=await asyncio.gather(*[fetch_single_story(client,id)for id in ids]) 
        stories=[r for r in result if r is not None]
        if keyword:
            stories=[s for s in stories if keyword.lower() in s["title"].lower()]
            
        return stories    
    
    
# if __name__=="__main__":
#     stories=asyncio.run(fetch_all_stories(limit=10))
#     for s in stories:
#         print(s['title'])    
         