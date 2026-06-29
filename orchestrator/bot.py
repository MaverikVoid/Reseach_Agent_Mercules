"""
bot.py — Main entry point for the Research Idea Evaluator.

Runs the Telegram bot with long polling.  The LangGraph graph is
compiled with InMemorySaver (Phase 1-3) and stored in bot_data so
all handlers can access it.

Usage:
    python -m orchestrator.bot
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# Reconfigure stdout/stderr to handle UTF-8 / emojis on Windows without crashing
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from orchestrator.config import TELEGRAM_BOT_TOKEN
from orchestrator.graph import build_graph
from orchestrator.telegram.handlers import (
    start_handler,
    help_handler,
    new_idea_handler,
    status_handler,
    threads_handler,
    switch_handler,
    kill_handler,
    message_handler,
    callback_handler,
)


# ── Logging ────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Reduce noise from httpx/httpcore
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def post_init(application) -> None:
    """Initialize connection pool, DB schema, and compiled graph with Postgres checkpointer."""
    try:
        from orchestrator.services.db import get_pool, init_db
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        logger.info("Connecting to Postgres database...")
        pool = get_pool()
        await init_db()

        logger.info("Initializing AsyncPostgresSaver checkpointer...")
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()

        graph = build_graph(checkpointer)
        application.bot_data["graph"] = graph
        application.bot_data["db_pool"] = pool
        logger.info("LangGraph state machine successfully compiled with AsyncPostgresSaver checkpointer.")
    except Exception as e:
        logger.warning(
            f"Could not initialize Postgres database/checkpointer: {e}. "
            "Falling back to InMemorySaver."
        )
        from langgraph.checkpoint.memory import InMemorySaver
        checkpointer = InMemorySaver()
        graph = build_graph(checkpointer)
        application.bot_data["graph"] = graph
        application.bot_data["db_pool"] = None


async def post_shutdown(application) -> None:
    """Close the database connection pool cleanly."""
    pool = application.bot_data.get("db_pool")
    if pool:
        logger.info("Closing database connection pool...")
        await pool.close()
        logger.info("Database connection pool closed.")


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Research Agent Bot is running!")

    def log_message(self, format, *args):
        # Suppress logging HTTP requests to clean up logs
        return


def run_dummy_server():
    port = int(os.environ.get("PORT", 7860))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logger.info(f"Starting background health-check HTTP server on port {port}...")
    server.serve_forever()


def main():
    """Build graph, wire Telegram handlers, start polling."""
    # Start the background HTTP health check server for Hugging Face Spaces / Render deployment
    threading.Thread(target=run_dummy_server, daemon=True).start()

    # ── Validate config ────────────────────────────────────────────────
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
        logger.error(
            "TELEGRAM_BOT_TOKEN not set! "
            "Create a bot via @BotFather and add the token to .env"
        )
        sys.exit(1)

    # ── Build Telegram application ─────────────────────────────────────
    logger.info("Building Telegram application...")
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # ── Register handlers ──────────────────────────────────────────────
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("new", new_idea_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("threads", threads_handler))
    app.add_handler(CommandHandler("switch", switch_handler))
    app.add_handler(CommandHandler("kill", kill_handler))

    # Callback queries from inline keyboards
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Free text messages (must be last — catch-all)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler)
    )

    # ── Start polling ──────────────────────────────────────────────────
    logger.info("Starting Telegram bot (long polling)...")
    logger.info("Press Ctrl+C to stop.")
    app.run_polling(
        drop_pending_updates=True,  # Don't process messages sent while offline
    )


if __name__ == "__main__":
    main()
