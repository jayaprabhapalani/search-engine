from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from preprocessor import preprocess_stories,preprocess_text


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
    
    
        
    

