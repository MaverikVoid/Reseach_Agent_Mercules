"""
LangGraph state machine — wires all 9 nodes into a single graph.

Phase 1: uses InMemorySaver + terminal I/O for testing.
Phase 2: swaps to AsyncPostgresSaver.
Phase 3: swaps terminal I/O for Telegram bot.

Run directly to test the graph interactively:
    python -m orchestrator.graph
"""

from __future__ import annotations

import uuid
import sys

# Reconfigure stdout/stderr to handle UTF-8 / emojis on Windows without crashing
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from langchain_core.runnables import RunnableLambda

from orchestrator.state import IdeaState
from orchestrator.nodes import (
    triage_node,
    lit_search_node,
    rubric_score_node,
    discuss_node,
    benchmark_design_node,
    dispatch_toy_node,
    report_toy_node,
    dispatch_full_node,
    report_full_node,
)


# ── Build the graph ────────────────────────────────────────────────────

def build_graph(checkpointer=None):
    """
    Construct and compile the IdeaState graph.

    Parameters
    ----------
    checkpointer : optional
        A LangGraph checkpointer (InMemorySaver, PostgresSaver, etc.).
        If None, uses InMemorySaver for local testing.

    Returns
    -------
    CompiledGraph
    """
    if checkpointer is None:
        checkpointer = InMemorySaver()

    builder = StateGraph(IdeaState)

    # ── Register nodes ─────────────────────────────────────────────────
    builder.add_node("triage", triage_node)
    builder.add_node("lit_search", lit_search_node)
    builder.add_node("rubric_score", rubric_score_node)
    builder.add_node("discuss", RunnableLambda(discuss_node))
    builder.add_node("benchmark_design", RunnableLambda(benchmark_design_node))
    builder.add_node("dispatch_toy", dispatch_toy_node)
    builder.add_node("report_toy", RunnableLambda(report_toy_node))
    builder.add_node("dispatch_full", dispatch_full_node)
    builder.add_node("report_full", RunnableLambda(report_full_node))

    # ── Edges: main pipeline ───────────────────────────────────────────

    # START → triage → lit_search → rubric_score → discuss
    builder.add_edge(START, "triage")
    builder.add_edge("triage", "lit_search")
    builder.add_edge("lit_search", "rubric_score")
    builder.add_edge("rubric_score", "discuss")

    # discuss routes via Command (goto) for question/refine loops,
    # or returns dict for approve/kill.
    # When discuss returns a dict with verdict="approved" → benchmark_design
    # When discuss returns a dict with verdict="killed" → END
    builder.add_conditional_edges(
        "discuss",
        _discuss_router,
        {
            "benchmark_design": "benchmark_design",
            END: END,
            # "discuss" and "rubric_score" are handled by Command(goto=...)
            # inside the node itself, so they don't need entries here.
        },
    )

    # benchmark_design → dispatch_toy (via Command for modify/kill, or dict for confirm)
    builder.add_conditional_edges(
        "benchmark_design",
        _benchmark_router,
        {
            "dispatch_toy": "dispatch_toy",
            END: END,
        },
    )

    # dispatch_toy → report_toy
    builder.add_edge("dispatch_toy", "report_toy")

    # report_toy routes: proceed → dispatch_full, refine → benchmark_design, kill → END
    builder.add_conditional_edges(
        "report_toy",
        _report_toy_router,
        {
            "dispatch_full": "dispatch_full",
            END: END,
        },
    )

    # dispatch_full → report_full → END
    builder.add_edge("dispatch_full", "report_full")
    builder.add_edge("report_full", END)

    return builder.compile(checkpointer=checkpointer)


# ── Routing functions ──────────────────────────────────────────────────

def _discuss_router(state: IdeaState) -> str:
    """Route after discuss node returns a dict (not a Command)."""
    verdict = state.get("verdict")
    if verdict == "approved":
        return "benchmark_design"
    if verdict == "killed":
        return END
    # Shouldn't reach here — question/refine use Command(goto=...)
    return END


def _benchmark_router(state: IdeaState) -> str:
    """Route after benchmark_design returns a dict."""
    if state.get("verdict") == "killed":
        return END
    if state.get("benchmark_spec"):
        return "dispatch_toy"
    return END


def _report_toy_router(state: IdeaState) -> str:
    """Route after report_toy returns a dict."""
    if state.get("verdict") == "killed":
        return END
    if state.get("full_benchmark_spec"):
        return "dispatch_full"
    return END


# ── Terminal test runner ───────────────────────────────────────────────

def run_terminal_test():
    """
    Interactive terminal test: submit an idea and walk through the
    full discuss loop manually.
    """
    print("=" * 60)
    print("  Research Idea Evaluator — Terminal Test (Phase 1)")
    print("=" * 60)

    graph = build_graph()

    # Get idea from user
    print("\nEnter your research idea (or press Enter for a default):")
    idea = input("> ").strip()
    if not idea:
        idea = (
            "Use spectral preconditioning of the NTK to accelerate "
            "PINN training for stiff ODEs. The key insight is that "
            "stiff systems create ill-conditioned NTK matrices, and "
            "a frequency-adaptive preconditioner could restore "
            "convergence speed without requiring implicit methods."
        )
        print(f"Using default idea: {idea[:80]}...")

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "idea_id": thread_id,
        "raw_idea": idea,
        "discussion_log": [],
    }

    print(f"\n[System] Thread ID: {thread_id}")
    print("[System] Starting pipeline...\n")

    # First invocation — runs until first interrupt
    result = graph.invoke(initial_state, config)

    # ── Resume loop ────────────────────────────────────────────────────
    while True:
        # Check for interrupts
        graph_state = graph.get_state(config)
        interrupts = graph_state.tasks

        has_interrupt = False
        for task in interrupts:
            if hasattr(task, "interrupts") and task.interrupts:
                has_interrupt = True
                # Display the interrupt payload
                for intr in task.interrupts:
                    print("\n" + "=" * 60)
                    print(intr.value)
                    print("=" * 60)

        if not has_interrupt:
            print("\n[System] Pipeline complete. No more interrupts.")
            print(f"\n[System] Final state:")
            print(f"  Verdict: {result.get('verdict', 'N/A')}")
            print(f"  Approval reason: {result.get('approval_reason', 'N/A')}")
            print(f"  Discussion messages: {len(result.get('discussion_log', []))}")
            break

        # Get user input
        print("\nYour reply:")
        user_input = input("> ").strip()
        if not user_input:
            print("[System] Empty input, skipping...")
            continue

        if user_input.lower() == "quit":
            print("[System] Exiting. Thread is saved and can be resumed.")
            break

        # Resume the graph
        result = graph.invoke(Command(resume=user_input), config)

    print("\n[System] Done.")


if __name__ == "__main__":
    run_terminal_test()
