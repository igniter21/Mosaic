"""Local semantic embeddings and reranking."""

from __future__ import annotations

import os
from collections.abc import Iterable
from functools import lru_cache


DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _embedding_model():
    from sentence_transformers import SentenceTransformer

    model_name = os.getenv(
        "MOSAIC_SEMANTIC_MODEL",
        DEFAULT_MODEL,
    ).strip()

    device = os.getenv(
        "MOSAIC_SEMANTIC_DEVICE",
        "auto",
    ).strip().lower()

    if device and device != "auto":
        return SentenceTransformer(
            model_name,
            device=device,
        )

    # Let SentenceTransformer select the best available device.
    return SentenceTransformer(model_name)


def semantic_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False

    return True


def semantic_model_name() -> str:
    return os.getenv(
        "MOSAIC_SEMANTIC_MODEL",
        DEFAULT_MODEL,
    ).strip()


def embed(texts: Iterable[str]) -> list[list[float]]:
    model = _embedding_model()

    batch_size = int(
        os.getenv(
            "MOSAIC_SEMANTIC_BATCH_SIZE",
            "32",
        )
    )

    return model.encode(
        list(texts),
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    ).tolist()