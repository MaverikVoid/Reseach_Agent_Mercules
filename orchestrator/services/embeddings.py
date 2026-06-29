"""
Embeddings service — sentence-transformers for embedding text,
with pgvector operations for storage and similarity search.

Phase 1-3: embedding functions only (no pgvector store).
Phase 4+: full pgvector integration.
"""

from __future__ import annotations

import logging
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy-loaded model
_model = None


def _get_model():
    """Lazy-load the sentence-transformers model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            from orchestrator.config import EMBEDDING_MODEL_NAME
            logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
            _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
            logger.info("Embedding model loaded successfully")
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Using fallback hash-based embeddings."
            )
            _model = "fallback"
    return _model


def embed_text(text: str) -> np.ndarray:
    """
    Embed a single text string.

    Returns a normalized 384-dimensional vector.
    Falls back to a hash-based pseudo-embedding if sentence-transformers
    is not installed.
    """
    model = _get_model()

    if model == "fallback":
        return _fallback_embed(text)

    embedding = model.encode(text, normalize_embeddings=True)
    return np.array(embedding, dtype=np.float32)


def embed_batch(texts: list[str]) -> np.ndarray:
    """
    Embed a batch of texts.

    Returns array of shape (n, 384).
    """
    model = _get_model()

    if model == "fallback":
        return np.array([_fallback_embed(t) for t in texts], dtype=np.float32)

    embeddings = model.encode(texts, normalize_embeddings=True, batch_size=32)
    return np.array(embeddings, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def rank_by_similarity(
    query_embedding: np.ndarray,
    paper_embeddings: np.ndarray,
    papers: list[dict],
) -> list[dict]:
    """
    Rank papers by cosine similarity to the query embedding.

    Adds a 'similarity' field to each paper dict and returns
    sorted (highest similarity first).
    """
    similarities = np.dot(paper_embeddings, query_embedding)

    for i, paper in enumerate(papers):
        paper["similarity"] = float(similarities[i])

    return sorted(papers, key=lambda p: p["similarity"], reverse=True)


def _fallback_embed(text: str) -> np.ndarray:
    """
    Hash-based pseudo-embedding for when sentence-transformers is
    not available. NOT suitable for real similarity — only for
    testing the pipeline.
    """
    import hashlib
    h = hashlib.sha384(text.encode()).digest()
    vec = np.frombuffer(h, dtype=np.uint8).astype(np.float32)
    vec = vec / (np.linalg.norm(vec) + 1e-8)
    return vec


# ── pgvector operations (Phase 4+) ────────────────────────────────────

async def store_idea_embedding(
    idea_id: str,
    embedding: np.ndarray,
    pool,
    idea_text: str = "",
) -> None:
    """Store an idea's embedding in pgvector for future dedup."""
    # Phase 4 implementation
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO idea_embeddings (idea_id, embedding, idea_text, created_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (idea_id) DO UPDATE SET embedding = %s
            """,
            (idea_id, embedding.tolist(), idea_text, embedding.tolist()),
        )


async def find_similar_ideas(
    embedding: np.ndarray,
    pool,
    top_k: int = 5,
    threshold: float = 0.8,
) -> list[dict]:
    """
    Find similar past ideas via pgvector cosine similarity search.

    Returns list of {idea_id, similarity, idea_text}.
    """
    # Phase 4 implementation
    async with pool.connection() as conn:
        rows = await conn.execute(
            """
            SELECT idea_id, idea_text,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM idea_embeddings
            WHERE 1 - (embedding <=> %s::vector) > %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (embedding.tolist(), embedding.tolist(), threshold,
             embedding.tolist(), top_k),
        ).fetchall()

        return [
            {
                "idea_id": row["idea_id"],
                "idea_text": row["idea_text"],
                "similarity": row["similarity"],
            }
            for row in rows
        ]
