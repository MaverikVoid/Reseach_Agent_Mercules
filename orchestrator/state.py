"""
IdeaState — the single shared state schema for the LangGraph pipeline.

Every node reads from / writes to fields in this TypedDict.
The schema is intentionally flat: LangGraph checkpointers serialise
TypedDicts natively, and flat dicts are easiest to inspect in Postgres.
"""

from __future__ import annotations

from typing import TypedDict, Literal, Optional


class IdeaState(TypedDict, total=False):
    # ── Identity ────────────────────────────────────────────────────────
    idea_id: str                     # = thread_id for checkpointing
    raw_idea: str                    # original idea text from user

    # ── Triage ──────────────────────────────────────────────────────────
    duplicate_of: Optional[str]      # idea_id of duplicate, if found
    duplicate_similarity: Optional[float]

    # ── Literature grounding ────────────────────────────────────────────
    lit_summary: Optional[str]       # LLM-generated delta summary
    closest_papers: Optional[list[dict]]
    # Each paper dict: {title, authors, abstract, similarity, url, source}

    # ── Rubric scoring ──────────────────────────────────────────────────
    rubric: Optional[dict]
    # {
    #   soundness:            str,   # flag for manual derivation check
    #   novelty_delta:        str,   # specific claim vs retrieved papers
    #   compute_cost_estimate: str,  # GPU-hours for a toy result
    #   failure_mode:         str,   # most likely failure mode
    # }

    # ── Discussion ──────────────────────────────────────────────────────
    discussion_log: list[dict]       # [{role: "user"|"system", content: str}, ...]
    verdict: Optional[Literal["approved", "refine", "killed"]]
    approval_reason: Optional[str]   # required friction — one-line reason

    # ── Benchmark design ────────────────────────────────────────────────
    benchmark_spec: Optional[dict]   # toy-scale benchmark definition

    # ── Toy experiment ──────────────────────────────────────────────────
    toy_result: Optional[dict]       # metrics, logs, error info

    # ── Full benchmark ──────────────────────────────────────────────────
    full_benchmark_spec: Optional[dict]
    full_result: Optional[dict]
