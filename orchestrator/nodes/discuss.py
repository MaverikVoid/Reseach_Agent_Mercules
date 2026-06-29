"""
Discuss node — the conversational core of the pipeline.

Uses interrupt() to pause the graph and present the rubric + papers
to the user.  On resume, classifies the user's intent and routes:
  - question  → answer, append to log, loop back to discuss
  - refine    → update raw_idea, route back to rubric_score
  - approve   → requires a one-line reason (friction gate), proceed
  - kill      → set verdict, end thread
"""

from __future__ import annotations

from langgraph.types import interrupt, Command
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import var_child_runnable_config
from orchestrator.state import IdeaState
from orchestrator.services.llm import call_llm, classify_intent


def _format_rubric_for_display(state: IdeaState) -> str:
    """Format rubric + papers into a readable summary for the user."""
    rubric = state.get("rubric", {})
    papers = state.get("closest_papers", [])
    lit_summary = state.get("lit_summary", "")
    duplicate_of = state.get("duplicate_of")

    sections = []

    # Duplicate warning
    if duplicate_of:
        sim = state.get("duplicate_similarity", 0)
        sections.append(
            f"⚠️  DUPLICATE ALERT: This idea is {sim:.0%} similar to "
            f"idea '{duplicate_of}'. Review before proceeding."
        )

    # Literature summary
    if lit_summary:
        sections.append(f"📚 LITERATURE DELTA:\n{lit_summary}")

    # Top papers
    if papers:
        paper_lines = []
        for i, p in enumerate(papers[:5]):
            sim = p.get("similarity", 0)
            paper_lines.append(
                f"  [{i+1}] {p['title']}\n"
                f"      Authors: {p.get('authors', 'N/A')}\n"
                f"      Similarity: {sim:.2f}  |  {p.get('url', 'N/A')}"
            )
        sections.append("📄 CLOSEST PAPERS:\n" + "\n".join(paper_lines))

    # Rubric
    if rubric:
        sections.append(
            "📊 RUBRIC SCORES:\n"
            f"  🧮 Soundness: {rubric.get('soundness', 'N/A')}\n\n"
            f"  🆕 Novelty Delta: {rubric.get('novelty_delta', 'N/A')}\n\n"
            f"  💻 Compute Cost: {rubric.get('compute_cost_estimate', 'N/A')}\n\n"
            f"  ⚠️  Failure Mode: {rubric.get('failure_mode', 'N/A')}"
        )

    sections.append(
        "─── YOUR OPTIONS ───\n"
        "• Ask a question or comment (free text)\n"
        "• Type 'refine: <your refinement>' to modify the idea\n"
        "• Type 'approve: <one-line reason>' to proceed to benchmark\n"
        "• Type 'kill' to reject this idea"
    )

    return "\n\n".join(sections)


async def discuss_node(state: IdeaState, config: RunnableConfig) -> dict | Command:
    """
    Conversational loop: present rubric, wait for user input, classify
    intent, and route accordingly.
    """
    discussion_log = list(state.get("discussion_log", []))

    # Set the ContextVar manually to bypass LangGraph context propagation bug on Python 3.10
    token = var_child_runnable_config.set(config)
    try:
        # ── Present rubric and interrupt for user input ────────────────────
        display = _format_rubric_for_display(state)

        print(f"\n[Discuss] Presenting rubric to user...")
        print(display)

        # This pauses the graph — the user's reply comes back as the
        # return value of interrupt()
        user_reply = interrupt(display)
    finally:
        var_child_runnable_config.reset(token)

    # ── Classify intent ────────────────────────────────────────────────
    intent = classify_intent(user_reply)
    print(f"[Discuss] User replied: {user_reply[:100]}...")
    print(f"[Discuss] Classified intent: {intent}")

    # Append user message to discussion log
    discussion_log.append({"role": "user", "content": user_reply})

    # ── Route based on intent ──────────────────────────────────────────

    if intent == "kill":
        discussion_log.append({
            "role": "system",
            "content": "Idea killed by user.",
        })
        return {
            "discussion_log": discussion_log,
            "verdict": "killed",
        }

    if intent == "approve":
        # Extract the reason after "approve:" prefix
        reason = user_reply
        if ":" in user_reply:
            reason = user_reply.split(":", 1)[1].strip()

        if not reason or reason.lower() in ("approve", "yes", "y", "ok"):
            # Friction gate: require a real reason
            discussion_log.append({
                "role": "system",
                "content": "⚠️  Approval requires a one-line reason. "
                           "Please type 'approve: <your reason>' — "
                           "this prevents rubber-stamping.",
            })
            # Loop back to discuss
            return Command(
                goto="discuss",
                update={
                    "discussion_log": discussion_log,
                },
            )

        discussion_log.append({
            "role": "system",
            "content": f"Idea approved. Reason: {reason}",
        })
        return {
            "discussion_log": discussion_log,
            "verdict": "approved",
            "approval_reason": reason,
        }

    if intent == "refine":
        # Extract the refinement text
        refinement = user_reply
        if ":" in user_reply:
            refinement = user_reply.split(":", 1)[1].strip()

        discussion_log.append({
            "role": "system",
            "content": f"Idea refined. Routing back to rubric scoring with "
                       f"updated idea.",
        })
        # Route back to rubric_score with updated idea
        return Command(
            goto="rubric_score",
            update={
                "raw_idea": refinement if refinement else state["raw_idea"],
                "discussion_log": discussion_log,
                "verdict": "refine",
            },
        )

    # intent == "question" (default)
    # Answer the question using LLM with full context
    context = (
        f"Research idea: {state['raw_idea']}\n\n"
        f"Literature summary: {state.get('lit_summary', 'N/A')}\n\n"
        f"Rubric: {state.get('rubric', {})}\n\n"
        f"Previous discussion:\n"
        + "\n".join(
            f"  {msg['role']}: {msg['content']}"
            for msg in discussion_log[-10:]  # last 10 messages for context
        )
    )

    answer = call_llm(
        f"The user asks: {user_reply}\n\n"
        f"Context:\n{context}\n\n"
        f"Answer the user's question thoroughly. Reference specific papers "
        f"or rubric scores where relevant. Be direct and honest.",
        node="discuss",
    )

    discussion_log.append({"role": "system", "content": answer})

    # Loop back to discuss
    return Command(
        goto="discuss",
        update={
            "discussion_log": discussion_log,
        },
    )
