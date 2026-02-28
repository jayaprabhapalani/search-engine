from fastapi import FastAPI
from crawler import fetch_all_stories
from preprocessor import preprocess_stories
from search import build_index,search

app=FastAPI()

app_state={
    "stories":[],
    "vectorizer":None,
    "tfidf_matrix":None
    
}

@app.post("/index")
async def post_query():
    stories= await fetch_all_stories()
    preprocessed_stories=preprocess_stories(stories)
    (vectorizer,tfidf_matrix)=build_index(preprocessed_stories) # or indexed_vectors=build_index(preprocessed_stories)
    app_state["stories"]=preprocessed_stories
    app_state["vectorizer"]=vectorizer # or indexed_vectors[0]
    app_state["tfidf_matrix"]=tfidf_matrix # or indexed_vectors[1]
    return len(preprocessed_stories) # or len(indexed_vectors)

@app.get("/search")
async def search_query(q:str):
    result=search(q,app_state["stories"],app_state["vectorizer"],app_state["tfidf_matrix"])
    return result