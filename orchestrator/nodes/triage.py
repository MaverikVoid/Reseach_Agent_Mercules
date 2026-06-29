"""
Triage node — checks for duplicate ideas via pgvector embedding similarity.

Phase 1: pass-through stub (no pgvector yet).
Phase 4: real implementation with embeddings.
"""

from __future__ import annotations

from orchestrator.state import IdeaState


def triage_node(state: IdeaState) -> dict:
    """
    Check if this idea is a duplicate of a previously submitted one.

    Phase 1 stub: always passes through with no duplicate flagged.
    Phase 4 will embed the raw_idea and query pgvector for similar past ideas.
    """
    print(f"\n[Triage] Checking idea for duplicates...")
    print(f"[Triage] Idea: {state['raw_idea'][:100]}...")

    # Phase 1: no pgvector, so no dedup
    # Phase 4 will:
    #   1. embed raw_idea via sentence-transformers
    #   2. query pgvector for cosine similarity > SIMILARITY_DEDUP_THRESHOLD
    #   3. if duplicate found, set duplicate_of and duplicate_similarity
    #   4. store this idea's embedding for future dedup

    print("[Triage] No duplicate found (stub — Phase 4 will add real dedup)")
    return {
        "duplicate_of": None,
        "duplicate_similarity": None,
    }
