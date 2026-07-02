"""
Literature search node — queries arXiv + Semantic Scholar, ranks by
embedding similarity, and generates an LLM delta summary.

Uses real API calls and embedding-based ranking.
"""

from __future__ import annotations

import logging

from orchestrator.state import IdeaState
from orchestrator.services.llm import call_llm
from orchestrator.services.literature import search_papers
from orchestrator.services.embeddings import embed_text, embed_batch, rank_by_similarity
from orchestrator.config import MAX_PAPERS, SEMANTIC_SCHOLAR_API_KEY

logger = logging.getLogger(__name__)


def lit_search_node(state: IdeaState) -> dict:
    """
    Search literature for papers related to the idea, rank by embedding
    similarity, and produce a delta summary.

    Uses real arXiv + Semantic Scholar API calls.
    Falls back to mock data only if both APIs fail.
    """
    raw_idea = state["raw_idea"]
    logger.info(f"[LitSearch] Searching for: {raw_idea[:80]}...")
    print(f"\n[LitSearch] Searching literature for: {raw_idea[:80]}...")

    # ── Search real APIs ───────────────────────────────────────────────
    papers = search_papers(
        raw_idea,
        max_results=MAX_PAPERS,
        semantic_scholar_api_key=SEMANTIC_SCHOLAR_API_KEY,
    )

    if not papers:
        logger.warning("[LitSearch] No papers found from APIs, using fallback")
        print("[LitSearch] Warning: no papers found from APIs")
        papers = _get_fallback_papers()

    # ── Rank by embedding similarity ───────────────────────────────────
    try:
        idea_embedding = embed_text(raw_idea)

        # Embed paper abstracts (use title + abstract for better matching)
        paper_texts = [
            f"{p['title']}. {p.get('abstract', '')}" for p in papers
        ]
        paper_embeddings = embed_batch(paper_texts)

        # Rank
        papers = rank_by_similarity(idea_embedding, paper_embeddings, papers)
        print(f"[LitSearch] Ranked {len(papers)} papers by embedding similarity")

    except Exception as e:
        logger.warning(f"[LitSearch] Embedding ranking failed: {e}")
        print(f"[LitSearch] Warning: embedding ranking failed, using raw order")
        # Add dummy similarity scores
        for i, p in enumerate(papers):
            p["similarity"] = max(0.9 - i * 0.05, 0.3)

    # ── LLM delta summary ──────────────────────────────────────────────
    papers_text = "\n\n".join(
        f"[{i+1}] {p['title']} ({p.get('authors', 'Unknown')})\n"
        f"    Abstract: {p.get('abstract', 'N/A')[:300]}\n"
        f"    Similarity: {p.get('similarity', 0):.2f}\n"
        f"    URL: {p.get('url', 'N/A')}"
        for i, p in enumerate(papers[:10])  # Top 10 for the summary
    )

    summary_prompt = f"""You are a research literature analyst. Given a research idea and the closest papers found in the literature, write a concise delta summary.

RESEARCH IDEA:
{raw_idea}

CLOSEST PAPERS:
{papers_text}

INSTRUCTIONS:
- State what the closest papers do (reference them by [number] and title)
- Explain specifically how this idea differs from existing work
- Be specific — cite paper numbers, not vague statements
- Do NOT give generic praise. Focus on the actual delta.
- If the idea appears to be covered by existing work, say so honestly.
- Keep it to 3-5 sentences.
"""

    lit_summary = call_llm(summary_prompt, node="lit_summary")

    print(f"[LitSearch] Found {len(papers)} papers")
    print(f"[LitSearch] Summary: {lit_summary[:150]}...")

    return {
        "closest_papers": papers[:MAX_PAPERS],
        "lit_summary": lit_summary,
    }


def _get_fallback_papers() -> list[dict]:
    """Fallback mock papers if APIs fail."""
    return [
        {
            "title": "Physics-Informed Neural Networks: A Deep Learning Framework "
                     "for Solving Forward and Inverse Problems Involving Nonlinear PDEs",
            "authors": "M. Raissi, P. Perdikaris, G.E. Karniadakis",
            "abstract": "We introduce physics-informed neural networks that are "
                        "trained to solve supervised learning tasks while respecting "
                        "any given laws of physics described by general nonlinear PDEs.",
            "similarity": 0.85,
            "url": "https://arxiv.org/abs/1711.10561",
            "source": "fallback",
        },
    ]
