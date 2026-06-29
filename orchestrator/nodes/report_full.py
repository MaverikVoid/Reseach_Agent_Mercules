"""
Report full node — final interrupt presenting full-scale benchmark results.

Pushes results + plots, logs final verdict and discussion history.
"""

from __future__ import annotations

from langgraph.types import interrupt
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import var_child_runnable_config
from orchestrator.state import IdeaState


def _format_full_results(state: IdeaState) -> str:
    """Format full benchmark results for final report."""
    full = state.get("full_result", {})
    metrics = full.get("metrics", {})

    sections = [
        "🏆 FULL-SCALE BENCHMARK RESULTS:",
        f"  Platform: {full.get('compute_platform', 'unknown')}",
        f"  GPU: {full.get('gpu_type', 'N/A')}",
        f"  Runtime: {full.get('runtime_seconds', 'N/A')}s",
        f"  Status: {full.get('status', 'unknown')}",
    ]

    if metrics:
        sections.append("\n📊 FINAL METRICS:")
        for k, v in metrics.items():
            if isinstance(v, float):
                sections.append(f"  {k}: {v:.4f}")
            else:
                sections.append(f"  {k}: {v}")

    if full.get("logs_url"):
        sections.append(f"\n📎 Full logs: {full['logs_url']}")

    # Summary of the entire journey
    discussion_log = state.get("discussion_log", [])
    sections.append(
        f"\n📋 DISCUSSION HISTORY: {len(discussion_log)} messages exchanged"
    )
    sections.append(f"✅ Approval reason: {state.get('approval_reason', 'N/A')}")

    sections.append(
        "\n─── FINAL VERDICT ───\n"
        "This idea has completed the full evaluation pipeline.\n"
        "Results and discussion history have been logged.\n"
        "Type any final notes to close this thread."
    )

    return "\n".join(sections)


async def report_full_node(state: IdeaState, config: RunnableConfig) -> dict:
    """
    Final report: present full benchmark results, get final notes,
    close the thread.
    """
    display = _format_full_results(state)

    print(f"\n[ReportFull] Presenting final results...")
    print(display)

    # Set the ContextVar manually to bypass LangGraph context propagation bug on Python 3.10
    token = var_child_runnable_config.set(config)
    try:
        # Final interrupt — user can add closing notes
        final_notes = interrupt(display)
    finally:
        var_child_runnable_config.reset(token)

    discussion_log = list(state.get("discussion_log", []))
    discussion_log.append({"role": "user", "content": f"Final notes: {final_notes}"})
    discussion_log.append({
        "role": "system",
        "content": "Pipeline complete. Thread closed.",
    })

    return {
        "discussion_log": discussion_log,
        "verdict": "approved",  # Reached the end = approved and verified
    }
