"""
LLM service — thin wrapper around the OpenAI SDK pointed at OpenRouter.

Provides:
  call_llm()          — general-purpose completion
  classify_intent()   — cheap intent classification for the discuss loop
"""

from __future__ import annotations

import time
import logging

from openai import OpenAI
from orchestrator.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    MODEL_ROUTING,
    DEFAULT_MODEL,
    NVIDIA_API_KEY,
)

logger = logging.getLogger(__name__)


def _get_nvidia_client() -> OpenAI:
    """Lazy singleton for NVIDIA NIM API client."""
    if not hasattr(_get_nvidia_client, "_client"):
        key = NVIDIA_API_KEY.strip('"' + "'")
        _get_nvidia_client._client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=key,
        )
    return _get_nvidia_client._client


def _get_client() -> OpenAI:
    """Lazy singleton — avoids import-time network calls."""
    if not hasattr(_get_client, "_client"):
        _get_client._client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
            default_headers={
                "X-Title": "Research Idea Evaluator",
            },
        )
    return _get_client._client


def call_llm(
    prompt: str,
    *,
    node: str | None = None,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 1500,
    system: str | None = None,
    retries: int = 3,
) -> str:
    """
    Call an LLM via OpenRouter.

    Parameters
    ----------
    prompt : str
        The user-role message content.
    node : str, optional
        Graph node name — used to look up the model in MODEL_ROUTING.
    model : str, optional
        Explicit model slug; overrides node-based routing.
    temperature : float
        Sampling temperature.
    max_tokens : int
        Max response tokens. Kept low to stay within credit limits.
    system : str, optional
        System-role message prepended to the conversation.
    retries : int
        Number of retries on rate limit / transient errors.

    Returns
    -------
    str
        The assistant's reply text.
    """
    resolved_model = model or MODEL_ROUTING.get(node or "", DEFAULT_MODEL)

    # Determine client (OpenRouter or NVIDIA NIM)
    is_nvidia_model = (
        resolved_model.startswith("nvidia/") or 
        resolved_model.startswith("meta/") or 
        resolved_model.startswith("mistralai/")
    )
    if NVIDIA_API_KEY and is_nvidia_model:
        client = _get_nvidia_client()
        logger.info(f"Routing request to NVIDIA API for model: {resolved_model}")
    else:
        client = _get_client()

    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=resolved_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            error_str = str(e)
            # Handle rate limits and credit errors
            if "429" in error_str or "rate" in error_str.lower():
                wait = (attempt + 1) * 5
                logger.warning(f"Rate limited, waiting {wait}s (attempt {attempt+1}/{retries})")
                time.sleep(wait)
                continue
            elif "402" in error_str or "credits" in error_str.lower():
                # Try with fewer tokens
                if max_tokens > 500:
                    logger.warning(f"Credit limit hit, reducing max_tokens to {max_tokens // 2}")
                    max_tokens = max_tokens // 2
                    continue
                else:
                    logger.error(f"Insufficient credits even at {max_tokens} tokens")
                    raise
            else:
                if attempt < retries - 1:
                    wait = (attempt + 1) * 2
                    logger.warning(f"LLM error: {error_str[:100]}, retrying in {wait}s")
                    time.sleep(wait)
                    continue
                raise

    raise RuntimeError(f"LLM call failed after {retries} retries")


def classify_intent(user_text: str) -> str:
    """
    Classify a user reply in the discuss loop.

    Returns one of: "approve", "refine", "kill", "question".
    Uses the cheapest/fastest model available.
    """
    system_prompt = (
        "You are an intent classifier for a research idea discussion system. "
        "Given the user's message, classify their intent as exactly ONE of:\n"
        "  approve  — user wants to approve the idea and proceed\n"
        "  refine   — user wants to modify/refine the idea\n"
        "  kill     — user wants to reject/kill the idea\n"
        "  question — user is asking a follow-up question or making a comment\n\n"
        "Respond with ONLY the single word (lowercase, no punctuation)."
    )

    result = call_llm(
        user_text,
        node="intent_classify",
        system=system_prompt,
        temperature=0.0,
        max_tokens=10,
    )

    intent = result.strip().lower().rstrip(".")
    if intent not in {"approve", "refine", "kill", "question"}:
        # Default to question if classification is ambiguous
        intent = "question"
    return intent
