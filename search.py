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
    preprocessed_query=preprocess_text(query)
        
    

