"""
Report toy node — presents toy-scale experiment results via interrupt().

User decides: proceed to full benchmark, refine, or kill.
"""

from __future__ import annotations

from langgraph.types import interrupt, Command
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import var_child_runnable_config
from orchestrator.state import IdeaState


def _format_toy_results(state: IdeaState) -> str:
    """Format toy experiment results for display."""
    toy = state.get("toy_result", {})
    metrics = toy.get("metrics", {})
    logs = toy.get("logs", "")

    sections = [
        "🧪 TOY EXPERIMENT RESULTS:",
        f"  Status: {toy.get('status', 'unknown')}",
        f"  Runtime: {toy.get('runtime_seconds', 'N/A')}s",
    ]

    if metrics:
        sections.append("\n📊 METRICS:")
        for k, v in metrics.items():
            if isinstance(v, float):
                sections.append(f"  {k}: {v:.4f}")
            else:
                sections.append(f"  {k}: {v}")

    if toy.get("kill_criterion_triggered"):
        sections.append("\n⚠️  KILL CRITERION WAS TRIGGERED — results may be unreliable.")

    if logs:
        # Truncate long logs
        log_preview = logs[:500]
        if len(logs) > 500:
            log_preview += "\n  ... (truncated)"
        sections.append(f"\n📝 LOGS:\n{log_preview}")

    sections.append(
        "\n─── YOUR OPTIONS ───\n"
        "• Type 'proceed' to run the full-scale benchmark\n"
        "• Type 'refine: <changes>' to modify and re-run\n"
        "• Type 'kill' to stop here"
    )

    return "\n".join(sections)


async def report_toy_node(state: IdeaState, config: RunnableConfig) -> dict | Command:
    """
    Present toy results and get user decision.
    """
    display = _format_toy_results(state)

    print(f"\n[ReportToy] Presenting toy results to user...")
    print(display)

    # Set the ContextVar manually to bypass LangGraph context propagation bug on Python 3.10
    token = var_child_runnable_config.set(config)
    try:
        user_reply = interrupt(display)
    finally:
        var_child_runnable_config.reset(token)
    user_lower = user_reply.strip().lower()

    discussion_log = list(state.get("discussion_log", []))
    discussion_log.append({"role": "user", "content": user_reply})

    if user_lower == "kill":
        discussion_log.append({
            "role": "system",
            "content": "Idea killed after toy experiment.",
        })
        return {
            "discussion_log": discussion_log,
            "verdict": "killed",
        }

    if user_lower.startswith("refine"):
        modification = user_reply.split(":", 1)[1].strip() if ":" in user_reply else ""
        discussion_log.append({
            "role": "system",
            "content": f"Refining benchmark: {modification}",
        })
        return Command(
            goto="benchmark_design",
            update={
                "discussion_log": discussion_log,
                "toy_result": None,  # Clear old results
            },
        )

    # Default: proceed to full benchmark
    discussion_log.append({
        "role": "system",
        "content": "Toy results accepted. Proceeding to full-scale benchmark.",
    })
    return {
        "discussion_log": discussion_log,
        "full_benchmark_spec": {
            "toy_spec": state.get("benchmark_spec"),
            "toy_result": state.get("toy_result"),
            "scale": "full",
        },
    }
