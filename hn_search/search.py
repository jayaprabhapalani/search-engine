from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from hn_search.preprocessor import preprocess_stories, preprocess_text
from sentence_transformers import SentenceTransformer

MIN_VECTOR_SCORE = 0.30  # drop candidates with no keyword match and vector score below this

model = SentenceTransformer("all-MiniLM-L6-v2")


def build_index(stories: list) -> tuple:
    vectorizer = TfidfVectorizer()
    preprocessed_stories = [story["preprocessed_text"] for story in stories]
    tfidf_matrix = vectorizer.fit_transform(preprocessed_stories)
    return (vectorizer, tfidf_matrix)


def build_vector_index(stories):
    texts = [story["text"] for story in stories]
    return model.encode(texts)


def search(query, stories, vectorizer, tfidf_matrix, top_k=10) -> list:
    preprocessed_query = preprocess_text(query)
    query_vector = vectorizer.transform([preprocessed_query])
    scores = cosine_similarity(query_vector, tfidf_matrix)
    top_indices = scores[0].argsort()[::-1][:top_k]
    result = []
    for i in top_indices:
        story = stories[i].copy()
        story["score"] = float(scores[0][i])
        result.append(story)
    return result


def vector_search(query, stories, vector_matrix, top_k=10) -> list:
    vectorized_query = model.encode([query])
    scores = cosine_similarity(vectorized_query, vector_matrix)
    top_indices = scores[0].argsort()[::-1][:top_k]
    result = []
    for i in top_indices:
        story = stories[i].copy()
        story["score"] = float(scores[0][i])
        result.append(story)
    return result


def hybrid_search(
    query, stories, vectorizer, tfidf_matrix, vector_matrix,
    top_k=50, tfidf_weight=0.4, vector_weight=0.6
) -> list:
    # Retrieve depth = pool size so the union can fill all slots
    tfidf_results = search(query, stories, vectorizer, tfidf_matrix, top_k=top_k)
    vector_results = vector_search(query, stories, vector_matrix, top_k=top_k)

    combined = {}
    for story in tfidf_results:
        combined[story["id"]] = {
            "story": story,
            "tfidf_score": story["score"],
            "vector_score": 0.0,
        }
    for story in vector_results:
        if story["id"] in combined:
            combined[story["id"]]["vector_score"] = story["score"]
        else:
            combined[story["id"]] = {
                "story": story,
                "tfidf_score": 0.0,
                "vector_score": story["score"],
            }

    # Relevance cutoff: drop pure-vector hits below the minimum threshold
    filtered = {
        sid: item for sid, item in combined.items()
        if item["tfidf_score"] > 0 or item["vector_score"] >= MIN_VECTOR_SCORE
    }

    for item in filtered.values():
        item["final_score"] = (
            tfidf_weight * item["tfidf_score"] + vector_weight * item["vector_score"]
        )

    # Deterministic order: score desc, story id as tiebreaker
    sorted_results = sorted(
        filtered.values(),
        key=lambda x: (-x["final_score"], x["story"]["id"]),
    )

    results = []
    for item in sorted_results[:top_k]:
        story = item["story"].copy()
        story["score"] = float(item["final_score"])
        results.append(story)
    return results
