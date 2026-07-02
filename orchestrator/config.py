"""
Configuration module — loads .env, defines model routing, constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env from project root ────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)

# ── API Keys ───────────────────────────────────────────────────────────
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
KAGGLE_USERNAME: str = os.getenv("KAGGLE_USERNAME", "")
KAGGLE_KEY: str = os.getenv("KAGGLE_KEY", "")
RUNPOD_API_KEY: str = os.getenv("RUNPOD_API_KEY", "")
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://orchestrator:password@localhost:5432/research_ideas",
)
NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "")
SEMANTIC_SCHOLAR_API_KEY: str = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")

# ── OpenRouter base URL ────────────────────────────────────────────────
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# We dynamically choose the model slug based on whether the user provided an NVIDIA API key
if NVIDIA_API_KEY:
    DEFAULT_MODEL = "meta/llama-3.1-70b-instruct"
else:
    DEFAULT_MODEL = "openrouter/free"

# ── Model routing map ──────────────────────────────────────────────────
# Each graph node can use a different model.  Change slugs here, not in
# node code.  See https://openrouter.ai/models for available slugs.
MODEL_ROUTING: dict[str, str] = {
    # Reasoning-heavy nodes
    "rubric_score":      DEFAULT_MODEL,
    "discuss":           DEFAULT_MODEL,
    "benchmark_design":  DEFAULT_MODEL,
    "code_generation":   DEFAULT_MODEL,
    "lit_summary":       DEFAULT_MODEL,

    # Cheap / fast classification nodes
    "intent_classify":   DEFAULT_MODEL,
    "triage":            DEFAULT_MODEL,
}

# ── Embedding settings ─────────────────────────────────────────────────
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# ── Literature search ──────────────────────────────────────────────────
MAX_PAPERS = 20  # combined arXiv + Semantic Scholar results
SIMILARITY_DEDUP_THRESHOLD = 0.92  # cosine sim above this → flag as duplicate

# ── Toy experiment constraints ─────────────────────────────────────────
TOY_TIMEOUT_SEC = 300       # 5-minute wall-clock cap
TOY_MEM_LIMIT = "512m"      # Docker memory limit
TOY_NETWORK_DISABLED = True  # no outbound network by default

# ── Kaggle / RunPod ────────────────────────────────────────────────────
KAGGLE_POLL_INTERVAL_SEC = 30
RUNPOD_GPU_TYPE = "NVIDIA_GEFORCE_RTX_4090"
