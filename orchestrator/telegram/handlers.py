"""
Telegram handlers — command handlers and message handlers for the bot.

Commands:
  /start   — welcome message
  /new     — start a new idea thread
  /status  — show active threads
  /threads — list active and completed threads for this chat
  /switch  — switch active thread
  /kill    — kill current thread
  /help    — show available commands

Free text:
  - If an active interrupted thread exists → resume it
  - Otherwise → treat as a new idea
"""

from __future__ import annotations

import uuid
import logging
import traceback
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from langgraph.types import Command

from orchestrator.telegram.formatter import split_message

logger = logging.getLogger(__name__)

# ── Fallback In-memory State ──────────────────────────────────────────
_active_threads: dict[int, dict] = {}
# Concurrency Locks (Thread-safe execution)
_thread_locks: dict[str, asyncio.Lock] = {}


def get_thread_lock(thread_id: str) -> asyncio.Lock:
    """Get or create an asyncio.Lock for a specific thread_id."""
    if thread_id not in _thread_locks:
        _thread_locks[thread_id] = asyncio.Lock()
    return _thread_locks[thread_id]


async def save_active_thread(chat_id: int, thread_id: str, idea_preview: str, pool) -> None:
    """Save the active thread_id for this chat_id."""
    if pool:
        try:
            async with pool.connection() as conn:
                # Mark other active threads as completed for this chat
                await conn.execute(
                    "UPDATE chat_threads SET status = 'completed' WHERE chat_id = %s",
                    (chat_id,)
                )
                # Insert the new thread as active
                await conn.execute(
                    """
                    INSERT INTO chat_threads (chat_id, thread_id, status, idea_summary)
                    VALUES (%s, %s, 'active', %s)
                    ON CONFLICT (thread_id) DO UPDATE 
                    SET status = 'active', idea_summary = %s
                    """,
                    (chat_id, thread_id, idea_preview, idea_preview),
                )
            return
        except Exception as e:
            logger.error(f"Error saving active thread to DB: {e}")

    # Fallback to in-memory
    _active_threads[chat_id] = {
        "thread_id": thread_id,
        "status": "active",
        "idea_preview": idea_preview,
    }


async def get_active_thread(chat_id: int, pool) -> dict | None:
    """Get the current active thread_id for this chat_id."""
    if pool:
        try:
            async with pool.connection() as conn:
                cur = await conn.execute(
                    """
                    SELECT thread_id, status, idea_summary 
                    FROM chat_threads 
                    WHERE chat_id = %s AND status = 'active'
                    ORDER BY created_at DESC 
                    LIMIT 1
                    """,
                    (chat_id,),
                )
                row = await cur.fetchone()
                if row:
                    return {
                        "thread_id": row["thread_id"],
                        "status": row["status"],
                        "idea_preview": row["idea_summary"],
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting active thread from DB: {e}")

    # Fallback to in-memory
    return _active_threads.get(chat_id)


async def delete_active_thread(chat_id: int, pool, thread_id: str = None) -> None:
    """Mark the active thread (or a specific thread) as completed."""
    if pool:
        try:
            async with pool.connection() as conn:
                if thread_id:
                    await conn.execute(
                        "UPDATE chat_threads SET status = 'completed' WHERE thread_id = %s",
                        (thread_id,)
                    )
                else:
                    await conn.execute(
                        "UPDATE chat_threads SET status = 'completed' WHERE chat_id = %s AND status = 'active'",
                        (chat_id,)
                    )
            return
        except Exception as e:
            logger.error(f"Error deleting active thread from DB: {e}")

    # Fallback to in-memory
    if chat_id in _active_threads:
        del _active_threads[chat_id]


# ── Command Handlers ──────────────────────────────────────────────────

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "🧠 *Research Idea Evaluator*\n\n"
        "I help you rigorously evaluate research ideas by:\n"
        "• Grounding them in real literature (arXiv + Semantic Scholar)\n"
        "• Scoring on 4 axes (soundness, novelty, compute, failure mode)\n"
        "• Discussing with you conversationally\n"
        "• Running toy & full-scale experiments\n\n"
        "*Commands:*\n"
        "/new <idea> — Submit a new research idea\n"
        "/status — Check active thread\n"
        "/threads — List past/active threads\n"
        "/switch <id> — Switch active thread\n"
        "/kill — Kill current thread\n"
        "/help — Show this message\n\n"
        "Or just send me a research idea as free text!",
        parse_mode="Markdown",
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await start_handler(update, context)


async def new_idea_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, override_idea_text: str = None):
    """Handle /new <idea text> command."""
    graph = context.bot_data.get("graph")
    pool = context.bot_data.get("db_pool")
    if not graph:
        await update.message.reply_text("❌ System not ready. Please try again later.")
        return

    # Extract idea text after /new
    if override_idea_text:
        idea_text = override_idea_text
    else:
        idea_text = update.message.text
        if idea_text.startswith("/new"):
            idea_text = idea_text[4:].strip()

    if not idea_text:
        await update.message.reply_text(
            "Please provide your research idea after /new.\n"
            "Example: `/new Use spectral preconditioning to accelerate PINN training`",
            parse_mode="Markdown",
        )
        return

    chat_id = update.effective_chat.id
    thread_id = str(uuid.uuid4())

    await update.message.reply_text(
        f"🔬 Starting evaluation...\n"
        f"Thread: `{thread_id[:8]}...`\n\n"
        f"Processing your idea through triage → literature search → "
        f"rubric scoring → discussion...",
        parse_mode="Markdown",
    )

    # Compile config and initial state
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "idea_id": thread_id,
        "raw_idea": idea_text,
        "discussion_log": [],
    }

    # Lock and run thread execution
    lock = get_thread_lock(thread_id)
    async with lock:
        try:
            # Call asynchronously to support DB checkpointers natively without blocking
            result = await graph.ainvoke(initial_state, config)

            # Track this thread
            await save_active_thread(chat_id, thread_id, idea_text[:50], pool)

            # Check for interrupts and send them
            await _send_interrupt_if_any(update, context, graph, config)

        except Exception as e:
            logger.error(f"Error starting idea thread: {e}\n{traceback.format_exc()}")
            await update.message.reply_text(
                f"❌ Error processing idea: {str(e)[:200]}"
            )


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    pool = context.bot_data.get("db_pool")
    chat_id = update.effective_chat.id
    thread_info = await get_active_thread(chat_id, pool)

    if not thread_info:
        await update.message.reply_text(
            "No active threads. Send a research idea to start!"
        )
        return

    await update.message.reply_text(
        f"📋 *Active Thread*\n\n"
        f"ID: `{thread_info['thread_id'][:8]}...`\n"
        f"Status: {thread_info['status']}\n"
        f"Idea: {thread_info.get('idea_preview', 'N/A')}",
        parse_mode="Markdown",
    )


async def threads_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /threads command — list all threads for this chat."""
    pool = context.bot_data.get("db_pool")
    chat_id = update.effective_chat.id

    if pool:
        try:
            async with pool.connection() as conn:
                cur = await conn.execute(
                    """
                    SELECT thread_id, status, idea_summary, created_at 
                    FROM chat_threads 
                    WHERE chat_id = %s 
                    ORDER BY created_at DESC 
                    LIMIT 10
                    """,
                    (chat_id,),
                )
                rows = await cur.fetchall()

                if not rows:
                    await update.message.reply_text("No threads found. Send a research idea to start!")
                    return

                msg = "📚 *Your Research Threads:*\n\n"
                for row in rows:
                    status_emoji = "🟢" if row["status"] == "active" else "⚪"
                    msg += (
                        f"{status_emoji} ID: `{row['thread_id'][:8]}` ({row['status']})\n"
                        f"   Idea: {row['idea_summary']}...\n\n"
                    )
                msg += "To switch active thread, use: `/switch <thread_id>`"
                await update.message.reply_text(msg, parse_mode="Markdown")
                return
        except Exception as e:
            logger.error(f"Error listing threads: {e}")

    # Fallback to active thread only
    thread_info = await get_active_thread(chat_id, None)
    if not thread_info:
        await update.message.reply_text("No active threads.")
    else:
        await update.message.reply_text(
            f"Active Thread:\n"
            f"ID: `{thread_info['thread_id'][:8]}`\n"
            f"Idea: {thread_info.get('idea_preview')}"
        )


async def switch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /switch <thread_id> command."""
    pool = context.bot_data.get("db_pool")
    chat_id = update.effective_chat.id

    args = context.args
    if not args:
        await update.message.reply_text("Please specify a thread ID to switch to.\nExample: `/switch abc12345`")
        return

    target_id_prefix = args[0].strip()

    if pool:
        try:
            async with pool.connection() as conn:
                # Find matching thread_id by prefix
                cur = await conn.execute(
                    """
                    SELECT thread_id, idea_summary 
                    FROM chat_threads 
                    WHERE chat_id = %s AND thread_id LIKE %s
                    LIMIT 1
                    """,
                    (chat_id, f"{target_id_prefix}%"),
                )
                row = await cur.fetchone()

                if not row:
                    await update.message.reply_text("❌ Thread not found.")
                    return

                target_thread_id = row["thread_id"]

                # Mark all other active threads for this chat as completed
                await conn.execute(
                    "UPDATE chat_threads SET status = 'completed' WHERE chat_id = %s",
                    (chat_id,)
                )

                # Mark target thread as active
                await conn.execute(
                    "UPDATE chat_threads SET status = 'active' WHERE thread_id = %s",
                    (target_thread_id,)
                )

                await update.message.reply_text(
                    f"🔄 Switched active thread to:\n"
                    f"ID: `{target_thread_id[:8]}...`\n"
                    f"Idea: {row['idea_summary']}...",
                    parse_mode="Markdown"
                )
                return
        except Exception as e:
            logger.error(f"Error switching threads: {e}")
            await update.message.reply_text(f"❌ Error switching thread: {e}")
            return

    await update.message.reply_text("Multi-thread switching requires Postgres.")


async def kill_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /kill command — kill the current active thread."""
    pool = context.bot_data.get("db_pool")
    chat_id = update.effective_chat.id
    thread_info = await get_active_thread(chat_id, pool)

    if not thread_info:
        await update.message.reply_text("No active thread to kill.")
        return

    thread_id = thread_info["thread_id"]
    await delete_active_thread(chat_id, pool, thread_id)
    await update.message.reply_text(
        f"💀 Thread `{thread_id[:8]}...` killed.\n"
        f"Send a new idea to start fresh.",
        parse_mode="Markdown",
    )


# ── Message / Callback Handlers ───────────────────────────────────────

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle free text messages.
    - If there's an active interrupted thread → resume it
    - Otherwise → treat as a new idea
    """
    graph = context.bot_data.get("graph")
    pool = context.bot_data.get("db_pool")
    if not graph:
        await update.message.reply_text("❌ System not ready. Please try again later.")
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text.strip()

    if not user_text:
        return

    thread_info = await get_active_thread(chat_id, pool)

    if thread_info:
        thread_id = thread_info["thread_id"]
        config = {"configurable": {"thread_id": thread_id}}

        lock = get_thread_lock(thread_id)
        async with lock:
            try:
                # Check if the thread has a pending interrupt
                graph_state = await graph.aget_state(config)
                has_interrupt = any(
                    hasattr(task, "interrupts") and task.interrupts
                    for task in graph_state.tasks
                )

                if has_interrupt:
                    await update.message.reply_text("⏳ Processing your reply...")

                    # Resume graph asynchronously
                    result = await graph.ainvoke(Command(resume=user_text), config)

                    # Send next interrupt if any
                    await _send_interrupt_if_any(update, context, graph, config)

                    # Check completion status
                    graph_state = await graph.aget_state(config)
                    has_new_interrupt = any(
                        hasattr(task, "interrupts") and task.interrupts
                        for task in graph_state.tasks
                    )

                    if not has_new_interrupt:
                        # Pipeline completed
                        verdict = result.get("verdict", "unknown")
                        await update.message.reply_text(
                            f"✅ Pipeline complete!\n"
                            f"Verdict: *{verdict}*\n"
                            f"Messages exchanged: {len(result.get('discussion_log', []))}",
                            parse_mode="Markdown",
                        )
                        await delete_active_thread(chat_id, pool, thread_id)
                else:
                    await update.message.reply_text(
                        "Previous thread complete. Starting new evaluation..."
                    )
                    await delete_active_thread(chat_id, pool, thread_id)
                    await new_idea_handler(update, context, override_idea_text=user_text)

            except Exception as e:
                logger.error(f"Error resuming thread: {e}\n{traceback.format_exc()}")
                await update.message.reply_text(
                    f"❌ Error: {str(e)[:200]}\n\n"
                    f"Thread may be in an inconsistent state. "
                    f"Use /kill to reset and try again."
                )
    else:
        # No active thread — treat as new idea
        await new_idea_handler(update, context, override_idea_text=user_text)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()

    action = query.data
    graph = context.bot_data.get("graph")
    pool = context.bot_data.get("db_pool")
    if not graph:
        await query.edit_message_text("❌ System not ready.")
        return

    chat_id = update.effective_chat.id
    thread_info = await get_active_thread(chat_id, pool)

    if not thread_info:
        await query.edit_message_text("No active thread.")
        return

    thread_id = thread_info["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    lock = get_thread_lock(thread_id)
    async with lock:
        try:
            await query.edit_message_text(f"⏳ Processing: {action}...")
            result = await graph.ainvoke(Command(resume=action), config)
            await _send_interrupt_if_any(
                update, context, graph, config, chat_id=chat_id
            )

            # Check completion
            graph_state = await graph.aget_state(config)
            has_interrupt = any(
                hasattr(task, "interrupts") and task.interrupts
                for task in graph_state.tasks
            )
            if not has_interrupt:
                verdict = result.get("verdict", "unknown")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ Pipeline complete! Verdict: *{verdict}*",
                    parse_mode="Markdown",
                )
                await delete_active_thread(chat_id, pool, thread_id)

        except Exception as e:
            logger.error(f"Error in callback: {e}\n{traceback.format_exc()}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Error: {str(e)[:200]}",
            )


# ── Internals ──────────────────────────────────────────────────────────

async def _send_interrupt_if_any(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    graph,
    config: dict,
    chat_id: int | None = None,
):
    """Check for interrupts in the graph state and send them to Telegram."""
    if chat_id is None:
        chat_id = update.effective_chat.id

    graph_state = await graph.aget_state(config)

    for task in graph_state.tasks:
        if hasattr(task, "interrupts") and task.interrupts:
            for intr in task.interrupts:
                display_text = str(intr.value)

                next_nodes = list(graph_state.next)

                # Add node-specific inline keyboard for common actions
                if "discuss" in next_nodes:
                    # Discuss node requires approve: <reason> or refine: <changes>.
                    # We do not show "Approve" button directly because approval requires typing a reason.
                    keyboard = [
                        [
                            InlineKeyboardButton("💀 Kill Idea", callback_data="kill"),
                        ]
                    ]
                elif "benchmark_design" in next_nodes:
                    # Benchmark design accepts confirm, modify, or kill
                    keyboard = [
                        [
                            InlineKeyboardButton("✔️ Confirm Benchmark", callback_data="confirm"),
                            InlineKeyboardButton("💀 Kill Idea", callback_data="kill"),
                        ]
                    ]
                elif "report_toy" in next_nodes:
                    # Report toy accepts proceed, refine, or kill
                    keyboard = [
                        [
                            InlineKeyboardButton("🚀 Proceed to Fullscale", callback_data="proceed"),
                            InlineKeyboardButton("💀 Kill Idea", callback_data="kill"),
                        ]
                    ]
                else:
                    keyboard = [
                        [
                            InlineKeyboardButton("💀 Kill Idea", callback_data="kill"),
                        ]
                    ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Split and send
                chunks = split_message(display_text)
                for i, chunk in enumerate(chunks):
                    if i == len(chunks) - 1:
                        # Last chunk gets the keyboard
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=chunk,
                            reply_markup=reply_markup,
                        )
                    else:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=chunk,
                        )
