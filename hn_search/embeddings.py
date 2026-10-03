"""
Lazy singleton for the sentence-transformer model plus embedding helpers.
"""
import os
import threading
from typing import Sequence

import numpy as np

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIM = 384
_ENCODE_BATCH = 256

_model = None
_model_lock = threading.Lock()


def get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                m = SentenceTransformer(EMBEDDING_MODEL)
                actual_dim = m.get_sentence_embedding_dimension()
                if actual_dim != EMBEDDING_DIM:
                    raise RuntimeError(
                        f"Model {EMBEDDING_MODEL!r} has dim {actual_dim}, expected {EMBEDDING_DIM}"
                    )
                _model = m
    return _model


def build_embed_input(title: str, chunk_text: str) -> str:
    """Single composition point — mirrors chunker.embed_text."""
    return f"{title}\n\n{chunk_text}"


def embed_texts(texts: Sequence[str]) -> np.ndarray:
    """
    Encode texts in batches, L2-normalize, return float32 (N, EMBEDDING_DIM).
    Normalized vectors make cosine similarity == dot product.
    """
    model = get_model()
    vecs = model.encode(
        list(texts),
        batch_size=_ENCODE_BATCH,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return vecs.astype(np.float32)
