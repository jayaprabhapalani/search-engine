import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from hn_search.preprocessor import preprocess_text, tokenize

MIN_VECTOR_SCORE = 0.30
_RETRIEVAL_DEPTH = 150
_SNIPPET_CHARS = 250


# ---------------------------------------------------------------------------
# Index builders
# ---------------------------------------------------------------------------

def build_index(chunks: list[dict]) -> tuple:
    """chunks: list of {preprocessed_text, ...}. Returns (vectorizer, tfidf_matrix)."""
    vectorizer = TfidfVectorizer(
        analyzer="word",
        tokenizer=lambda t: t.split(),
        preprocessor=None,
        token_pattern=None,
        lowercase=False,
    )
    texts = [c["preprocessed_text"] for c in chunks]
    tfidf_matrix = vectorizer.fit_transform(texts)
    return vectorizer, tfidf_matrix


# ---------------------------------------------------------------------------
# Snippet helper
# ---------------------------------------------------------------------------

def _make_snippet(chunk_text: str) -> str:
    if len(chunk_text) <= _SNIPPET_CHARS:
        return chunk_text
    trimmed = chunk_text[:_SNIPPET_CHARS]
    last_space = trimmed.rfind(" ")
    return (trimmed[:last_space] if last_space > 0 else trimmed) + "…"


# ---------------------------------------------------------------------------
# Per-retriever helpers
# ---------------------------------------------------------------------------

def _keyword_search(
    query: str,
    chunks: list[dict],
    vectorizer,
    tfidf_matrix,
    top_k: int,
) -> list[dict]:
    tokens = tokenize(query)
    if not tokens:
        return []
    qv = vectorizer.transform([" ".join(tokens)])
    # Sparse dot product — TF-IDF rows are already L2-normalised
    scores = (tfidf_matrix @ qv.T).toarray().ravel()
    if scores.max() == 0:
        return []
    idx = np.argpartition(scores, -min(top_k, len(scores)))[-top_k:]
    idx = idx[np.argsort(scores[idx])[::-1]]
    return [{"chunk": chunks[i], "score": float(scores[i])} for i in idx if scores[i] > 0]


def _vector_search(
    query_vec: np.ndarray,
    vec_chunks: list[dict],
    vector_matrix: np.ndarray,
    top_k: int,
) -> list[dict]:
    """
    query_vec: (1, D) normalized float32.
    vec_chunks: parallel list to vector_matrix rows — each has chunk_id + chunk dict.
    """
    scores = (vector_matrix @ query_vec.T).ravel()
    k = min(top_k, len(scores))
    idx = np.argpartition(scores, -k)[-k:]
    idx = idx[np.argsort(scores[idx])[::-1]]
    return [{"chunk": vec_chunks[i]["chunk"], "score": float(scores[i])} for i in idx]


# ---------------------------------------------------------------------------
# Group chunk hits → story results
# ---------------------------------------------------------------------------

def _group_by_story(
    chunk_hits: dict[int, dict],
    tfidf_weight: float,
    vector_weight: float,
) -> dict[int, dict]:
    by_story: dict[int, dict] = {}
    for item in chunk_hits.values():
        chunk = item["chunk"]
        sid = chunk["story_id"]
        final = tfidf_weight * item["tfidf_score"] + vector_weight * item["vector_score"]
        if sid not in by_story or final > by_story[sid]["final_score"]:
            by_story[sid] = {
                "story_meta": chunk["story_meta"],
                "final_score": final,
                "tfidf_score": item["tfidf_score"],
                "vector_score": item["vector_score"],
                "snippet": _make_snippet(chunk["chunk_text"]),
            }
    return by_story


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def hybrid_search(
    query: str,
    chunks: list[dict],
    vectorizer,
    tfidf_matrix,
    vector_matrix: np.ndarray | None,
    vec_chunks: list[dict] | None,
    top_k: int = 50,
    tfidf_weight: float = 0.4,
    vector_weight: float = 0.6,
) -> list[dict]:
    """
    chunks: all chunks (for keyword search).
    vec_chunks: subset that have embeddings, parallel to vector_matrix rows.
                Each entry: {chunk_id, chunk: <chunk dict>}.
    """
    from hn_search.embeddings import embed_texts

    kw_hits = _keyword_search(query, chunks, vectorizer, tfidf_matrix, _RETRIEVAL_DEPTH)

    vec_hits: list[dict] = []
    if vector_matrix is not None and vec_chunks:
        qv = embed_texts([query])  # already normalized, shape (1, D)
        vec_hits = _vector_search(qv, vec_chunks, vector_matrix, _RETRIEVAL_DEPTH)

    # Merge at chunk level keyed by chunk_id (fallback chunks use negative story_id)
    chunk_map: dict[int, dict] = {}
    for h in kw_hits:
        cid = h["chunk"]["chunk_id"]
        key = cid if cid is not None else -(h["chunk"]["story_id"])
        chunk_map[key] = {"chunk": h["chunk"], "tfidf_score": h["score"], "vector_score": 0.0}
    for h in vec_hits:
        cid = h["chunk"]["chunk_id"]
        key = cid if cid is not None else -(h["chunk"]["story_id"])
        if key in chunk_map:
            chunk_map[key]["vector_score"] = h["score"]
        else:
            chunk_map[key] = {"chunk": h["chunk"], "tfidf_score": 0.0, "vector_score": h["score"]}

    filtered = {
        k: v for k, v in chunk_map.items()
        if v["tfidf_score"] > 0 or v["vector_score"] >= MIN_VECTOR_SCORE
    }

    by_story = _group_by_story(filtered, tfidf_weight, vector_weight)

    sorted_stories = sorted(
        by_story.values(),
        key=lambda x: (-x["final_score"], x["story_meta"]["id"]),
    )

    results = []
    for item in sorted_stories[:top_k]:
        m = item["story_meta"]
        results.append({
            "id": m["id"],
            "title": m["title"],
            "url": m.get("url"),
            "hn_url": f"https://news.ycombinator.com/item?id={m['id']}",
            "relevance": round(item["final_score"], 4),
            "points": m.get("points", 0),
            "domain": m.get("domain"),
            "descendants": m.get("descendants", 0),
            "created_at": m.get("created_at"),
            "snippet": item["snippet"],
        })
    return results
