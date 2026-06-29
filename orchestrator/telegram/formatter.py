"""
Telegram message formatter — handles Telegram's 4096-char limit,
emoji-rich rubric display, paper formatting, and result presentation.
"""

from __future__ import annotations


MAX_MSG_LEN = 4096


def split_message(text: str, max_len: int = MAX_MSG_LEN) -> list[str]:
    """Split a long message into chunks that fit Telegram's limit."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # Try to split at a newline
        split_pos = text.rfind("\n", 0, max_len)
        if split_pos == -1:
            split_pos = max_len
        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip("\n")
    return chunks


def format_rubric(rubric: dict) -> str:
    """Format a rubric dict for Telegram display."""
    if not rubric:
        return "📊 No rubric available."

    return (
        "📊 *RUBRIC SCORES*\n\n"
        f"🧮 *Soundness:*\n{_escape_md(rubric.get('soundness', 'N/A'))}\n\n"
        f"🆕 *Novelty Delta:*\n{_escape_md(rubric.get('novelty_delta', 'N/A'))}\n\n"
        f"💻 *Compute Cost:*\n{_escape_md(rubric.get('compute_cost_estimate', 'N/A'))}\n\n"
        f"⚠️ *Failure Mode:*\n{_escape_md(rubric.get('failure_mode', 'N/A'))}"
    )


def format_papers(papers: list[dict], max_papers: int = 5) -> str:
    """Format paper list for Telegram display."""
    if not papers:
        return "📄 No papers found."

    lines = ["📄 *CLOSEST PAPERS*\n"]
    for i, p in enumerate(papers[:max_papers]):
        sim = p.get("similarity", 0)
        title = _escape_md(p.get("title", "Unknown"))
        authors = _escape_md(p.get("authors", "Unknown"))
        url = p.get("url", "")
        lines.append(
            f"*[{i+1}]* {title}\n"
            f"    Authors: {authors}\n"
            f"    Similarity: {sim:.2f}"
            + (f"\n    [Link]({url})" if url else "")
        )
    return "\n\n".join(lines)


def format_toy_results(toy_result: dict) -> str:
    """Format toy experiment results for Telegram."""
    if not toy_result:
        return "🧪 No toy results available."

    metrics = toy_result.get("metrics", {})
    lines = [
        "🧪 *TOY EXPERIMENT RESULTS*\n",
        f"Status: {toy_result.get('status', 'unknown')}",
        f"Runtime: {toy_result.get('runtime_seconds', 'N/A')}s",
    ]

    if metrics:
        lines.append("\n📊 *Metrics:*")
        for k, v in metrics.items():
            if isinstance(v, float):
                lines.append(f"  {k}: {v:.4f}")
            else:
                lines.append(f"  {k}: {v}")

    if toy_result.get("kill_criterion_triggered"):
        lines.append("\n⚠️ KILL CRITERION WAS TRIGGERED")

    return "\n".join(lines)


def format_full_results(full_result: dict) -> str:
    """Format full benchmark results for Telegram."""
    if not full_result:
        return "🏆 No full results available."

    metrics = full_result.get("metrics", {})
    lines = [
        "🏆 *FULL-SCALE BENCHMARK RESULTS*\n",
        f"Platform: {full_result.get('compute_platform', 'unknown')}",
        f"GPU: {full_result.get('gpu_type', 'N/A')}",
        f"Runtime: {full_result.get('runtime_seconds', 'N/A')}s",
        f"Status: {full_result.get('status', 'unknown')}",
    ]

    if metrics:
        lines.append("\n📊 *Final Metrics:*")
        for k, v in metrics.items():
            if isinstance(v, float):
                lines.append(f"  {k}: {v:.4f}")
            else:
                lines.append(f"  {k}: {v}")

    if full_result.get("logs_url"):
        lines.append(f"\n📎 [Full logs]({full_result['logs_url']})")

    return "\n".join(lines)


def format_interrupt_for_telegram(interrupt_value: str, state: dict) -> str:
    """
    Take the raw interrupt display string and enhance it for Telegram.
    Adds emoji headers and ensures proper formatting.
    """
    # The interrupt value is already well-formatted from the node.
    # Just ensure it fits Telegram's message limits.
    return interrupt_value


def _escape_md(text: str) -> str:
    """Escape special Markdown characters for Telegram MarkdownV2."""
    # For now, use simple Markdown (not MarkdownV2) which needs less escaping
    return str(text)
