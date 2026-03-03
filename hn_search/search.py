from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from hn_search.preprocessor import preprocess_stories,preprocess_text
from sentence_transformers import SentenceTransformer


"""These below two funcs for TF-IDF"""
#to build the tf-idf index
def build_index(stories:list)->tuple:
    vectorizer=TfidfVectorizer()
    #extracts the text(stemmed) from the whole docs
    preprocessed_stories=[story["preprocessed_text"] for story in stories]
    #vectorize them using tf-idf
    tfidf_matrix=vectorizer.fit_transform(preprocessed_stories)
    return (vectorizer,tfidf_matrix)


def search(query,stories,vectorizer,tfidf_matrix,top_k=10)->list:
    #preprocessing the query
    preprocessed_query=preprocess_text(query)
    #vectorize the query
    query_vector=vectorizer.transform([preprocessed_query])
    #Compute cosine similarity
    scores=cosine_similarity(query_vector,tfidf_matrix)
    #get the top 10 indicies
    top_indices=scores[0].argsort()[::-1][:top_k]
    
    result=[]
    #add its similarity score to the dict
    for i in top_indices:
        story=stories[i].copy()
        story["score"]=float(scores[0][i])
        result.append(story)
    return result    

    
model=SentenceTransformer("all-MiniLM-L6-v2")    
"""The following two funcs for vector search"""
# to vectorize the api stories
def build_vector_index(stories):
    
    texts=[story["text"] for story in stories]
    embeddings=model.encode(texts)
    return embeddings #returns a np array


# to vectorize the query and perform similar search
def vector_search(query,stories,vector_matrix,top_k=10):
    #vectorize the query
    vectorized_query=model.encode([query])
    #compute cosine similarity
    scores=cosine_similarity(vectorized_query,vector_matrix)
    #get the top 10 indicies
    top_indices=scores[0].argsort()[::-1][:top_k]
    
    result=[]
    #add its similarity score to the dict
    for i in top_indices:
        story=stories[i].copy()
        story["score"]=float(scores[0][i])
        result.append(story)
    return result    


"""combinig tfidf + vector search (using weighted avg)"""
def hybrid_search(query,stories,vectorizer,tfidf_matrix,vector_matrix,top_k=10,tfidf_weight=0.4,vector_weight=0.6):
    #get both result
    tfidf_results=search(query,stories,vectorizer,tfidf_matrix,top_k=20)
    vector_search_results=vector_search(query,stories,vector_matrix,top_k=20)
    
    #combinig both scores based on the story id
    combined={}
    for story in tfidf_results:
        combined[story["id"]]={
            "story":story,
            "tfidf_score":story["score"],
            "vector_score":0.0
        }
    for story in vector_search_results:
        if story['id'] in combined:
            combined[story["id"]]["vector_score"]=story["score"]
        else:
            combined[story["id"]]={
            "story":story,
            "tfidf_score":0.0,
            "vector_score":story["score"]
        }
    
    #calculating the final score by giving 60% to vector search and 40% to tfidf
    for item in combined.values():
        item["final_score"]=(tfidf_weight*item["tfidf_score"])+(vector_weight*item["vector_score"])
        
    #sort the final score dsc
    sorted_results=sorted(combined.values(),key=lambda x:x['final_score'],reverse=True)
    
    #from that result - take the top_k
    results=[]
    for item in sorted_results[:top_k]:
        story=item["story"].copy()
        story["score"]=float(item["final_score"])
        results.append(story)
    return results    
        
        
        
        
        
               
    
        
        
        
        
              
    

