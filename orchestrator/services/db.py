"""
Database service — manages connection pooling and table creation.

Tables:
  1. chat_threads    — maps Telegram chat_id to active/past LangGraph thread_ids
  2. idea_embeddings — stores raw ideas and their embeddings (pgvector) for dedup
"""

from __future__ import annotations

import logging
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from pgvector.psycopg import register_vector
from orchestrator.config import DATABASE_URL

logger = logging.getLogger(__name__)

# Lazy global pool
_pool: AsyncConnectionPool | None = None


def get_pool() -> AsyncConnectionPool:
    """Get or create the global async connection pool."""
    global _pool
    if _pool is None:
        logger.info(f"Initializing connection pool for {DATABASE_URL.split('@')[-1]}")
        _pool = AsyncConnectionPool(
            conninfo=DATABASE_URL,
            kwargs={"autocommit": True, "row_factory": dict_row, "connect_timeout": 2},
            open=False,
        )
    return _pool


async def init_db() -> None:
    """Initialize database tables, extensions, and checkpointer tables."""
    pool = get_pool()
    # Ensure pool is opened with a fast 2-second timeout
    await pool.open(timeout=2.0)

    async with pool.connection() as conn:
        logger.info("Initializing database schema...")
        
        # 1. Enable pgvector extension
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        # 2. Create chat_threads table
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_threads (
                chat_id BIGINT,
                thread_id VARCHAR(255) PRIMARY KEY,
                status VARCHAR(50) DEFAULT 'active',
                idea_summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        # Add index for fast chat searches
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_threads_chat_id ON chat_threads(chat_id);"
        )

        # 3. Create idea_embeddings table (384-dimensional sentence-transformer vectors)
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS idea_embeddings (
                idea_id VARCHAR(255) PRIMARY KEY REFERENCES chat_threads(thread_id) ON DELETE CASCADE,
                idea_text TEXT NOT NULL,
                embedding vector(384) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        
        # Create HNSW index for fast vector search if not exists
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_idea_embeddings_vector ON idea_embeddings USING hnsw (embedding vector_cosine_ops);"
        )
        
        logger.info("Database schema initialized successfully.")


async def register_vector_type(conn) -> None:
    """Register pgvector type handlers on a connection."""
    await register_vector(conn)
