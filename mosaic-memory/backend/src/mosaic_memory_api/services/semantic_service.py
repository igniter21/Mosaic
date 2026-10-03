"""Optional local semantic embeddings and reranking.

The base Mosaic feature-hash retrieval remains the zero-dependency fallback.
Install sentence-transformers to enable this module.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from functools import lru_cache


@lru_cache(maxsize=1)
def _embedding_model():
    from sentence_transformers import SentenceTransformer

    model_name = os.getenv("MOSAIC_SEMANTIC_MODEL", "all-MiniLM-L6-v2")
    return SentenceTransformer(model_name)


def semantic_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return True


def semantic_model_loaded() -> bool:
    """Avoid loading an optional transformer during an ordinary search request."""
    return _embedding_model.cache_info().currsize > 0


def embed(texts: Iterable[str]) -> list[list[float]]:
    model = _embedding_model()
    return model.encode(list(texts), normalize_embeddings=True).tolist()
