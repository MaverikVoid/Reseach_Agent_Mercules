"""
Rubric scoring node — LLM scores the idea on 4 separate axes.

These are NEVER collapsed into a single number.  Each axis is a
qualitative assessment with explanation.
"""

from __future__ import annotations

from orchestrator.state import IdeaState
from orchestrator.services.llm import call_llm
import json
import re


def rubric_score_node(state: IdeaState) -> dict:
    """
    Score the research idea on four axes:
      1. Theoretical soundness (flag for manual derivation check)
      2. Novelty delta vs. retrieved papers (specific, not vibes)
      3. Compute cost estimate (GPU-hours for a believable toy result)
      4. Most likely failure mode

    Scores are qualitative strings, NOT numbers.
    """
    raw_idea = state["raw_idea"]
    lit_summary = state.get("lit_summary", "No literature search performed yet.")
    papers = state.get("closest_papers", [])

    papers_text = "\n".join(
        f"  [{i+1}] {p['title']} (sim={p.get('similarity', '?'):.2f})"
        for i, p in enumerate(papers[:10])
    )

    prompt = f"""You are a rigorous research evaluator. Score the following research idea on exactly four axes. For each axis, provide a detailed assessment (2-4 sentences). Do NOT collapse these into a single score.

RESEARCH IDEA:
{raw_idea}

LITERATURE CONTEXT:
{lit_summary}

CLOSEST PAPERS:
{papers_text}

Score on these four axes:

1. **Theoretical Soundness**: Does the math hold? Are there gaps in the reasoning? Flag specific areas that need manual derivation checks. Be honest — if the theoretical grounding is unclear, say so.

2. **Novelty Delta**: How does this differ from the retrieved papers? Be specific — reference paper numbers. Is this genuinely new, or a minor variation? If it's incremental, say so clearly.

3. **Compute Cost Estimate**: How many GPU-hours would a believable toy result require? Consider: model size, dataset, training iterations, hardware. Give a concrete estimate, not a vague range.

4. **Most Likely Failure Mode**: What's the single most probable way this idea fails? Be specific (e.g., "gradient instability in the stiff regime at CFL > 10" not "might not work").

Respond in EXACTLY this JSON format:
{{
  "soundness": "your assessment here",
  "novelty_delta": "your assessment here",
  "compute_cost_estimate": "your assessment here",
  "failure_mode": "your assessment here"
}}

Return ONLY the JSON. No markdown fences, no explanation outside the JSON.
"""

    response = call_llm(prompt, node="rubric_score", temperature=0.2)

    # Parse JSON from response (handle potential markdown fences)
    try:
        # Strip markdown code fences if present
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        rubric = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        # Fallback: try to extract JSON from the response
        match = re.search(r"\{[\s\S]*\}", response)
        if match:
            try:
                rubric = json.loads(match.group())
            except json.JSONDecodeError:
                rubric = {
                    "soundness": "Parse error — raw LLM response saved for review.",
                    "novelty_delta": response[:500],
                    "compute_cost_estimate": "Unable to parse",
                    "failure_mode": "Unable to parse",
                }
        else:
            rubric = {
                "soundness": "Parse error — raw LLM response saved for review.",
                "novelty_delta": response[:500],
                "compute_cost_estimate": "Unable to parse",
                "failure_mode": "Unable to parse",
            }

    # Ensure all four keys exist
    for key in ["soundness", "novelty_delta", "compute_cost_estimate", "failure_mode"]:
        if key not in rubric:
            rubric[key] = "Not assessed"

    print(f"\n[Rubric] Scoring complete:")
    for k, v in rubric.items():
        print(f"  {k}: {str(v)[:100]}...")

    return {"rubric": rubric}
