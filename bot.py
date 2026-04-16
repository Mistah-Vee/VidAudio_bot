import os
import re
from dataclasses import dataclass
from typing import Optional, Dict, Tuple

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

BOT_TOKEN = os.environ["8781452342:AAFvAObtdRM4IAFrb6d1rwfLmjfmIYqtigE"]
BASE_URL = os.environ.get("BASE_URL")          # only set on Railway
PORT = int(os.environ.get("PORT", "8080"))     # Railway provides PORT

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)

PendingKey = Tuple[int, int]  # (chat_id, user_id)

@dataclass
class PendingRequest:
    url: str

PENDING: Dict[PendingKey, PendingRequest] = {}


def extract_url(text: str) -> Optional[str]:
    m = URL_RE.search(text or "")
    return m.group(0) if m else None


def make_key(chat_id: int, user_id: int) -> PendingKey:
    return (chat_id, user_id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send a link, then choose Audio or Video.")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = extract_url(update.message.text)
    if not url:
        return  # ignore non-links (keeps groups clean)

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    PENDING[make_key(chat_id, user_id)] = PendingRequest(url=url)

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("Audio", callback_data="mode:audio"),
        InlineKeyboardButton("Video", callback_data="mode:video"),
    ]])

    await update.message.reply_text(
        f"Link received:\n{url}\n\nChoose:",
        reply_markup=kb,
        disable_web_page_preview=True
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    data = q.data or ""
    if not data.startswith("mode:"):
        await q.edit_message_text("Unknown action. Send a link again.")
        return

    mode = data.split(":", 1)[1]
    chat_id = q.message.chat.id
    user_id = q.from_user.id

    pending = PENDING.get(make_key(chat_id, user_id))
    if not pending:
        await q.edit_message_text("No pending link for you here. Send a link again.")
        return

    await q.edit_message_text(
        f"Selected: {mode.upper()}\nURL: {pending.url}\n\n"
        "Phase 1 OK. Next: show quality options."
    )


def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(CallbackQueryHandler(on_callback))
    return app


if __name__ == "__main__":
    app = build_app()

    # LOCAL DEV (polling): BASE_URL not set
    if not BASE_URL:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    else:
        # PRODUCTION (webhook): BASE_URL set
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="telegram",
            webhook_url=f"{BASE_URL}/telegram",
            allowed_updates=Update.ALL_TYPES,
        )