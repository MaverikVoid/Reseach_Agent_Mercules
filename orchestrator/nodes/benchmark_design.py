"""
Benchmark design node — proposes the smallest possible toy-scale benchmark
that could falsify the idea, then interrupts for human confirmation.

This gate exists because for non-standard domains (stiff PDE solvers vs.
MNIST), benchmark design is itself part of the research judgment.
"""

from __future__ import annotations

from langgraph.types import interrupt, Command
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import var_child_runnable_config
from orchestrator.state import IdeaState
from orchestrator.services.llm import call_llm


async def benchmark_design_node(state: IdeaState, config: RunnableConfig) -> dict | Command:
    """
    1. LLM proposes a minimal toy benchmark
    2. Interrupt for human confirmation
    3. On resume: accept, modify, or kill
    """
    raw_idea = state["raw_idea"]
    rubric = state.get("rubric", {})
    approval_reason = state.get("approval_reason", "")

    prompt = f"""You are a research experiment designer specializing in physics-informed ML and stiff PDE solvers.

APPROVED RESEARCH IDEA:
{raw_idea}

APPROVAL REASON:
{approval_reason}

RUBRIC ASSESSMENT:
  Soundness: {rubric.get('soundness', 'N/A')}
  Compute estimate: {rubric.get('compute_cost_estimate', 'N/A')}
  Failure mode: {rubric.get('failure_mode', 'N/A')}

Design the SMALLEST possible toy-scale benchmark that could falsify this idea. The goal is to spend minimal compute while getting a meaningful signal.

Requirements:
1. ONE specific problem (e.g., a single 1D stiff ODE, not a full equation suite)
2. Clear success/failure criteria (e.g., "error must beat baseline by X%")
3. Concrete baseline to compare against
4. Estimated runtime on CPU (no GPU for toy scale)
5. Kill criteria (when to stop early if it's clearly failing)

Format your response as:
PROBLEM: <specific problem>
BASELINE: <what to compare against>
SUCCESS CRITERION: <measurable threshold>
KILL CRITERION: <when to stop early>
ESTIMATED RUNTIME: <time estimate>
IMPLEMENTATION NOTES: <key details for code generation>
"""

    benchmark_proposal = call_llm(prompt, node="benchmark_design")

    print(f"\n[BenchmarkDesign] Proposed benchmark:")
    print(benchmark_proposal)

    # Set the ContextVar manually to bypass LangGraph context propagation bug on Python 3.10
    token = var_child_runnable_config.set(config)
    try:
        # ── Interrupt for confirmation ─────────────────────────────────────
        display = (
            "🔬 PROPOSED TOY BENCHMARK:\n\n"
            f"{benchmark_proposal}\n\n"
            "─── YOUR OPTIONS ───\n"
            "• Type 'confirm' to run this benchmark\n"
            "• Type 'modify: <your changes>' to adjust\n"
            "• Type 'kill' to cancel"
        )

        user_reply = interrupt(display)
    finally:
        var_child_runnable_config.reset(token)
    user_lower = user_reply.strip().lower()

    if user_lower == "kill":
        return {
            "verdict": "killed",
            "discussion_log": state.get("discussion_log", []) + [
                {"role": "user", "content": user_reply},
                {"role": "system", "content": "Benchmark killed by user."},
            ],
        }

    if user_lower.startswith("modify"):
        modification = user_reply.split(":", 1)[1].strip() if ":" in user_reply else user_reply
        # Re-run benchmark design with the modification
        updated_idea = f"{raw_idea}\n\nBENCHMARK MODIFICATION: {modification}"
        return Command(
            goto="benchmark_design",
            update={
                "raw_idea": updated_idea,
                "discussion_log": state.get("discussion_log", []) + [
                    {"role": "user", "content": user_reply},
                    {"role": "system", "content": "Benchmark modified. Re-designing..."},
                ],
            },
        )

    # Default: confirm
    benchmark_spec = {
        "proposal_text": benchmark_proposal,
        "idea": raw_idea,
        "confirmed_by_user": True,
        "user_confirmation": user_reply,
    }

    return {
        "benchmark_spec": benchmark_spec,
        "discussion_log": state.get("discussion_log", []) + [
            {"role": "user", "content": user_reply},
            {"role": "system", "content": "Benchmark confirmed. Dispatching toy run..."},
        ],
    }
