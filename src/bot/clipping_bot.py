"""
Bot Telegram always-on para procurement-clipping.
- Recebe links manuais → Claude extrai título + score → salva no Sheets
- Processa callbacks de aprovação de posts LinkedIn
"""

import asyncio
import logging
import re
from datetime import datetime, timezone

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from src.clipping.publish import _post_to_linkedin
from src.common.claude import score_noticias
from src.common.config import settings
from src.common.sheets import append_noticias

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def _classify_link(link: str, categoria: str = "tech") -> dict:
    prompt_items = [{"title": link, "link": link}]
    scored = await score_noticias(prompt_items, categoria)
    if scored:
        return scored[0]
    return {"title": link, "link": link, "score": 9, "categoria": categoria, "motivo": "adicionado manualmente"}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()

    # /add <link> [categoria]
    if text.lower().startswith("/add "):
        parts = text.split()
        link = parts[1] if len(parts) > 1 else ""
        categoria = parts[2] if len(parts) > 2 else "tech"
    elif text.startswith("http://") or text.startswith("https://"):
        link = text
        categoria = "tech"
    else:
        await update.message.reply_text(
            "ℹ️ Para adicionar notícia manualmente:\n\n"
            "🔗 Cole o link direto\nou\n"
            "📝 /add <link> <categoria>\n\n"
            "Categorias: tech | financial | marketing"
        )
        return

    if not link.startswith("http"):
        await update.message.reply_text("❌ Link inválido. Envie uma URL completa.")
        return

    classified = await _classify_link(link, categoria)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = {
        "data": today,
        "titulo": str(classified.get("title", classified.get("titulo", link)))[:200],
        "link": link,
        "categoria": str(classified.get("categoria", categoria)),
        "score_ia": classified.get("score", 9),
        "motivo": "adicionado manualmente",
        "score_humano": "",
        "status": "pendente",
        "origem": "manual",
    }
    await asyncio.to_thread(append_noticias, [row])
    await update.message.reply_text(
        f"✅ Notícia salva!\n\n"
        f"📌 {row['titulo']}\n"
        f"🏷 {row['categoria']}\n"
        f"⭐ Score IA: {row['score_ia']}\n\n"
        f"_Será incluída no clipping semanal._",
        parse_mode="Markdown",
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    if not data.startswith("linkedin:"):
        return

    action = data.split(":")[1]

    if action == "descartar":
        await query.edit_message_text("🗑 Post descartado.")
        return

    # action == "publicar"
    # Retrieve stored post text
    post_text = (context.bot_data or {}).get("linkedin_post", "")
    if not post_text:
        # Fallback: extract text from the message itself
        post_text = query.message.text or ""

    ok = await _post_to_linkedin(post_text)
    if ok:
        await query.edit_message_text("✅ Post publicado no LinkedIn!")
    else:
        await query.edit_message_text(
            "❌ Falha ao publicar. Verifique LINKEDIN_ACCESS_TOKEN e LINKEDIN_PERSON_ID."
        )


def main() -> None:
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=r"^linkedin:"))
    logger.info("procurement-clipping bot iniciado.")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
