import sqlite3
import logging
from pathlib import Path
from app.core.config import settings

logger = logging.getLogger(__name__)

def init_db():
    db_path = settings.db_path
    # Create parent directories if they don't exist
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS profile_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL,
        resume_name TEXT,
        papers_names TEXT,
        portfolio_url TEXT,
        github_url TEXT,
        scholar_url TEXT,
        error_message TEXT,
        profile_path TEXT
    );
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS web_cache (
        url TEXT PRIMARY KEY,
        content TEXT NOT NULL,
        fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {db_path}")

def get_cache(url: str) -> str | None:
    db_path = settings.db_path
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT content FROM web_cache WHERE url = ?", (url,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        logger.error(f"Error reading from cache for {url}: {e}")
        return None

def set_cache(url: str, content: str):
    db_path = settings.db_path
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO web_cache (url, content) VALUES (?, ?)", (url, content))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error writing to cache for {url}: {e}")

def log_run(status: str, resume_name: str, papers_names: str, portfolio_url: str, github_url: str, scholar_url: str, error_message: str = None, profile_path: str = None):
    db_path = settings.db_path
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO profile_runs 
            (status, resume_name, papers_names, portfolio_url, github_url, scholar_url, error_message, profile_path) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (status, resume_name, papers_names, portfolio_url, github_url, scholar_url, error_message, profile_path))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error logging run to database: {e}")
