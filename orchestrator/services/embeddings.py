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
import requests
from openai import OpenAI

from orchestrator.config import EMBEDDING_PROVIDER

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


def _embed_hf(text: str) -> Optional[np.ndarray]:
    """Call Hugging Face Inference API for all-MiniLM-L6-v2."""
    from orchestrator.config import HUGGINGFACEHUB_API_TOKEN
    if not HUGGINGFACEHUB_API_TOKEN:
        logger.warning("HUGGINGFACEHUB_API_TOKEN not set, falling back to local/fallback")
        return None
        
    api_url = "https://api-inference.huggingface.co/models/sentence-transformers/all-MiniLM-L6-v2"
    headers = {"Authorization": f"Bearer {HUGGINGFACEHUB_API_TOKEN}"}
    
    try:
        response = requests.post(api_url, headers=headers, json={"inputs": text}, timeout=15)
        if response.status_code == 200:
            res_data = response.json()
            if isinstance(res_data, list):
                return np.array(res_data, dtype=np.float32)
        logger.warning(f"HF Inference API error {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"HF Inference API connection error: {e}")
    return None


def _embed_batch_hf(texts: list[str]) -> Optional[np.ndarray]:
    """Call Hugging Face Inference API for a batch of texts."""
    from orchestrator.config import HUGGINGFACEHUB_API_TOKEN
    if not HUGGINGFACEHUB_API_TOKEN:
        return None
        
    api_url = "https://api-inference.huggingface.co/models/sentence-transformers/all-MiniLM-L6-v2"
    headers = {"Authorization": f"Bearer {HUGGINGFACEHUB_API_TOKEN}"}
    
    try:
        response = requests.post(api_url, headers=headers, json={"inputs": texts}, timeout=20)
        if response.status_code == 200:
            res_data = response.json()
            if isinstance(res_data, list) and len(res_data) > 0 and isinstance(res_data[0], list):
                return np.array(res_data, dtype=np.float32)
        logger.warning(f"HF Inference API error {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"HF Inference API connection error: {e}")
    return None


def _embed_nvidia(text: str) -> Optional[np.ndarray]:
    """Call NVIDIA Embeddings API, slice to 384 dimensions and normalize."""
    from orchestrator.config import NVIDIA_API_KEY
    if not NVIDIA_API_KEY:
        logger.warning("NVIDIA_API_KEY not set, falling back to local/fallback")
        return None
        
    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=NVIDIA_API_KEY
    )
    
    try:
        response = client.embeddings.create(
            input=[text],
            model="nvidia/nv-embedqa-e5-v5"
        )
        vector = response.data[0].embedding
        # Slice to 384 dimensions to match DB columns, and normalize
        vec = np.array(vector[:384], dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec
    except Exception as e:
        logger.error(f"NVIDIA Embeddings API error: {e}")
    return None


def embed_text(text: str) -> np.ndarray:
    """
    Embed a single text string using the configured provider.
    """
    logger.info(f"Embedding text with provider: {EMBEDDING_PROVIDER}")
    
    import os
    is_render = "RENDER" in os.environ
    
    if EMBEDDING_PROVIDER == "huggingface":
        vector = _embed_hf(text)
        if vector is not None:
            return vector
        if is_render:
            logger.warning("HF embedding failed on Render. Trying NVIDIA backup.")
            vector = _embed_nvidia(text)
            if vector is not None:
                return vector
            
    elif EMBEDDING_PROVIDER == "nvidia":
        vector = _embed_nvidia(text)
        if vector is not None:
            return vector
        if is_render:
            logger.warning("NVIDIA embedding failed on Render. Trying HF backup.")
            vector = _embed_hf(text)
            if vector is not None:
                return vector

    elif EMBEDDING_PROVIDER == "fallback":
        return _fallback_embed(text)

    # On Render, if API failed, NEVER load SentenceTransformer locally to prevent OOM
    if is_render:
        logger.error("All API embeddings failed on Render. Using hash-based fallback to prevent OOM.")
        return _fallback_embed(text)

    # Local loading fallback (for development with PyTorch installed)
    model = _get_model()
    if model == "fallback":
        return _fallback_embed(text)

    embedding = model.encode(text, normalize_embeddings=True)
    return np.array(embedding, dtype=np.float32)


def embed_batch(texts: list[str]) -> np.ndarray:
    """
    Embed a batch of texts.
    """
    logger.info(f"Embedding batch of {len(texts)} texts with provider: {EMBEDDING_PROVIDER}")
    
    import os
    is_render = "RENDER" in os.environ

    if EMBEDDING_PROVIDER == "huggingface":
        vectors = _embed_batch_hf(texts)
        if vectors is not None:
            return vectors
        if is_render:
            logger.warning("HF batch embedding failed on Render. Trying NVIDIA backup.")
            vectors = []
            for t in texts:
                v = _embed_nvidia(t)
                if v is None:
                    v = _fallback_embed(t)
                vectors.append(v)
            return np.array(vectors, dtype=np.float32)
            
    elif EMBEDDING_PROVIDER == "nvidia":
        vectors = []
        for t in texts:
            v = _embed_nvidia(t)
            if v is None:
                v = _fallback_embed(t)
            vectors.append(v)
        return np.array(vectors, dtype=np.float32)

    elif EMBEDDING_PROVIDER == "fallback":
        return np.array([_fallback_embed(t) for t in texts], dtype=np.float32)

    # On Render, if API failed, NEVER load SentenceTransformer locally to prevent OOM
    if is_render:
        logger.error("All API batch embeddings failed on Render. Using hash-based fallback to prevent OOM.")
        return np.array([_fallback_embed(t) for t in texts], dtype=np.float32)

    # Local loading fallback (for development with PyTorch installed)
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
