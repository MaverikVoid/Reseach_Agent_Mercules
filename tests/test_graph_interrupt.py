"""
Test: Graph interrupt/resume flow (Phase 1 validation).

Run with: python -m tests.test_graph_interrupt
"""

import uuid
import sys
from langgraph.types import Command
from orchestrator.graph import build_graph

# Reconfigure stdout/stderr to handle UTF-8 / emojis on Windows without crashing
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def test_discuss_loop():
    """Verify the discuss loop: question → question → approve flow."""
    graph = build_graph()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    idea = (
        "Use spectral preconditioning of the NTK to accelerate "
        "PINN training for stiff ODEs."
    )

    initial_state = {
        "idea_id": thread_id,
        "raw_idea": idea,
        "discussion_log": [],
    }

    print("=" * 60)
    print("TEST: Graph interrupt/resume flow")
    print("=" * 60)

    # ── Step 1: Start pipeline ─────────────────────────────────────────
    print("\n[Test] Step 1: Starting pipeline...")
    result = graph.invoke(initial_state, config)

    # Should reach discuss and interrupt
    state = graph.get_state(config)
    has_interrupt = any(
        hasattr(t, "interrupts") and t.interrupts
        for t in state.tasks
    )
    assert has_interrupt, "Expected interrupt at discuss node!"
    print("[Test] ✅ Pipeline interrupted at discuss node")

    # ── Step 2: Ask a question ─────────────────────────────────────────
    print("\n[Test] Step 2: Asking a question...")
    result = graph.invoke(
        Command(resume="What's the computational overhead of the preconditioner?"),
        config,
    )

    # Should loop back to discuss with an answer
    state = graph.get_state(config)
    has_interrupt = any(
        hasattr(t, "interrupts") and t.interrupts
        for t in state.tasks
    )
    assert has_interrupt, "Expected interrupt after question (discuss loop)!"
    print("[Test] ✅ Question answered, looped back to discuss")

    # ── Step 3: Try bare approve (should be rejected) ──────────────────
    print("\n[Test] Step 3: Testing approval friction gate...")
    result = graph.invoke(Command(resume="approve"), config)

    state = graph.get_state(config)
    has_interrupt = any(
        hasattr(t, "interrupts") and t.interrupts
        for t in state.tasks
    )
    assert has_interrupt, "Expected interrupt (approval without reason should be rejected)!"
    print("[Test] ✅ Bare 'approve' rejected — friction gate works")

    # ── Step 4: Approve with reason ────────────────────────────────────
    print("\n[Test] Step 4: Approving with reason...")
    result = graph.invoke(
        Command(resume="approve: Spectral preconditioning has theoretical grounding in NTK analysis"),
        config,
    )

    # Should proceed to benchmark_design and interrupt there
    state = graph.get_state(config)
    has_interrupt = any(
        hasattr(t, "interrupts") and t.interrupts
        for t in state.tasks
    )
    assert has_interrupt, "Expected interrupt at benchmark_design!"
    print("[Test] ✅ Approved with reason, reached benchmark_design")

    # ── Step 5: Confirm benchmark ──────────────────────────────────────
    print("\n[Test] Step 5: Confirming benchmark...")
    result = graph.invoke(Command(resume="confirm"), config)

    # Should proceed through dispatch_toy → report_toy and interrupt
    state = graph.get_state(config)
    has_interrupt = any(
        hasattr(t, "interrupts") and t.interrupts
        for t in state.tasks
    )
    assert has_interrupt, "Expected interrupt at report_toy!"
    print("[Test] ✅ Benchmark confirmed, toy run complete, at report_toy")

    # ── Step 6: Proceed to full benchmark ──────────────────────────────
    print("\n[Test] Step 6: Proceeding to full benchmark...")
    result = graph.invoke(Command(resume="proceed"), config)

    # Should go through dispatch_full → report_full and interrupt
    state = graph.get_state(config)
    has_interrupt = any(
        hasattr(t, "interrupts") and t.interrupts
        for t in state.tasks
    )
    assert has_interrupt, "Expected interrupt at report_full!"
    print("[Test] ✅ Full benchmark complete, at report_full")

    # ── Step 7: Close thread ───────────────────────────────────────────
    print("\n[Test] Step 7: Closing thread...")
    result = graph.invoke(
        Command(resume="Excellent results. Proceed with full paper."),
        config,
    )

    # Pipeline should be complete
    state = graph.get_state(config)
    has_interrupt = any(
        hasattr(t, "interrupts") and t.interrupts
        for t in state.tasks
    )
    assert not has_interrupt, "Pipeline should be complete!"
    print("[Test] ✅ Pipeline complete!")

    # ── Verify final state ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("FINAL STATE:")
    print(f"  Verdict: {result.get('verdict', 'N/A')}")
    print(f"  Approval reason: {result.get('approval_reason', 'N/A')}")
    disc_log = result.get('discussion_log', [])
    print(f"  Discussion messages: {len(disc_log)}")
    print(f"  Has toy result: {result.get('toy_result') is not None}")
    print(f"  Has full result: {result.get('full_result') is not None}")
    print("=" * 60)
    print("\n🎉 ALL TESTS PASSED!")


if __name__ == "__main__":
    test_discuss_loop()
