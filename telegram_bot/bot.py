"""
Telegram Bot for Pi Crypto Insight.

Wraps every incoming message with per-user rate limiting before
delegating to the agent pipeline.
"""

import logging
import os
from typing import Optional

from telegram_bot.rate_limiter import TelegramRateLimiter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiter (module-level singleton)
# ---------------------------------------------------------------------------
rate_limiter = TelegramRateLimiter()

# ---------------------------------------------------------------------------
# Telegram Bot token — must be set via TELEGRAM_BOT_TOKEN env var
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")


# ---------------------------------------------------------------------------
# Message handler (public entry point)
# ---------------------------------------------------------------------------


async def handle_message(user_id: int, text: str) -> str:
    """
    Process an incoming Telegram message.

    This is the main entry point called by the Telegram long-polling
    or webhook handler.  Rate limiting is checked first; if the user
    exceeds limits a friendly message is returned immediately.

    Args:
        user_id: Telegram user ID.
        text: Message text from the user.

    Returns:
        Reply text to send back to the user.
    """
    # 1. Rate-limit check
    allowed, reason = rate_limiter.is_allowed(user_id)
    if not allowed:
        logger.warning("Rate limited user %s: %s", user_id, reason)
        return reason

    # 2. Delegate to agent pipeline (existing logic)
    #    Replace the placeholder below with your actual agent call.
    return await _process_with_agent(user_id, text)


# ---------------------------------------------------------------------------
# Internal: agent processing (placeholder — integrate with LangGraph)
# ---------------------------------------------------------------------------


async def _process_with_agent(user_id: int, text: str) -> str:
    """
    Send user message through the LangGraph agent pipeline.

    TODO: Wire this up to the actual ManagerAgent / core.agents flow.
    """
    logger.info("Processing message from user %s: %.80s", user_id, text)
    # Placeholder response — replace with real agent invocation
    return f"[Agent response placeholder] You said: {text}"


# ---------------------------------------------------------------------------
# Long-polling entry point (blocking, for running as a standalone process)
# ---------------------------------------------------------------------------


async def run_polling() -> None:
    """
    Start the Telegram bot in long-polling mode.

    Requires the ``python-telegram-bot`` library to be installed.
    Set TELEGRAM_BOT_TOKEN env var before calling.
    """
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN environment variable is not set. "
            "Cannot start Telegram bot."
        )

    try:
        from telegram import Update
        from telegram.ext import Application, CommandHandler, MessageHandler, filters
    except ImportError:
        raise RuntimeError(
            "python-telegram-bot is not installed. Run: pip install python-telegram-bot"
        )

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # --- Command handlers ---
    async def start_command(update: Update, context: object) -> None:
        """Handle /start command."""
        user = update.effective_user
        if user is None:
            return
        reply = (
            "👋 歡迎使用 Pi Crypto Insight Bot！\n\n"
            "我可以幫您分析加密貨幣市場、提供即時數據和社區動態。\n\n"
            "直接輸入問題即可開始對話。"
        )
        await update.message.reply_text(reply)  # type: ignore[union-attr]

    async def help_command(update: Update, context: object) -> None:
        """Handle /help command."""
        user = update.effective_user
        if user is None:
            return
        remaining = rate_limiter.get_remaining(user.id)
        reply = (
            "📊 *Pi Crypto Insight Bot* — 使用說明\n\n"
            "• 直接輸入問題來獲取市場分析\n"
            "• 每分鐘最多 10 則訊息\n"
            f"• 每天最多 100 則訊息\n\n"
            f"今日剩餘次數：{remaining['day_remaining']}\n"
            f"本分鐘剩餘次數：{remaining['minute_remaining']}"
        )
        await update.message.reply_text(reply, parse_mode="Markdown")  # type: ignore[union-attr]

    async def status_command(update: Update, context: object) -> None:
        """Handle /status command — show remaining quota."""
        user = update.effective_user
        if user is None:
            return
        remaining = rate_limiter.get_remaining(user.id)
        reply = (
            f"📊 配額狀態\n\n"
            f"本分鐘剩餘：{remaining['minute_remaining']} / 10\n"
            f"今日剩餘：{remaining['day_remaining']} / 100"
        )
        await update.message.reply_text(reply)  # type: ignore[union-attr]

    # --- Message handler (with rate limiting) ---
    async def message_handler(update: Update, context: object) -> None:
        """Handle text messages with rate limiting."""
        user = update.effective_user
        if user is None:
            return
        text = update.message.text or ""  # type: ignore[union-attr]
        if not text.strip():
            return

        reply = await handle_message(user.id, text)
        await update.message.reply_text(reply)  # type: ignore[union-attr]

    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("Telegram bot starting in polling mode...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()  # type: ignore[union-attr]
    try:
        # Block until interrupted
        import asyncio

        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Telegram bot shutting down...")
    finally:
        await app.updater.stop()  # type: ignore[union-attr]
        await app.stop()
        await app.shutdown()
