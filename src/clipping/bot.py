"""
Bot Telegram persistente para procurement-clipping.
- Recebe links manuais → Claude Haiku avalia → Sheets
- Recebe callback_query de aprovação → LinkedIn API ou aviso
"""

import asyncio
import logging
from datetime import datetime, timezone

import aiohttp
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

from src.common.config import settings
from src.common.claude import evaluate_relevance
from src.common.sheets import append_news

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def _post_linkedin(text: str) -> bool:
    """Post to LinkedIn using REST API. Returns True on success."""
    if not settings.linkedin_access_token or not settings.linkedin_author_urn:
        return False
    payload = {
        "author": settings.linkedin_author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    headers = {
        "Authorization": f"Bearer {settings.linkedin_access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.linkedin.com/v2/ugcPosts",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status in (200, 201):
                    logger.info("Post publicado no LinkedIn.")
                    return True
                text_resp = await resp.text()
                logger.error("LinkedIn API erro %d: %s", resp.status, text_resp[:200])
    except Exception:
        logger.exception("LinkedIn post falhou")
    return False


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_chat.id) != settings.telegram_chat_id:
        return

    msg_text = (update.message.text or "").strip()
    is_link = msg_text.startswith("http://") or msg_text.startswith("https://")
    is_add_cmd = msg_text.lower().startswith("/add ")

    if not (is_link or is_add_cmd):
        await update.message.reply_text(
            "ℹ️ Para adicionar notícia manualmente:\n\n"
            "🔗 Cole o link direto\nou\n"
            "📝 /add <link> <categoria>\n\n"
            "Categorias: tech | financial | marketing"
        )
        return

    link = msg_text
    categoria = "tech"
    if is_add_cmd:
        parts = msg_text.split()
        link = parts[1] if len(parts) > 1 else ""
        categoria = parts[2] if len(parts) > 2 else "tech"

    if not link.startswith("http"):
        await update.message.reply_text("❌ Link inválido.")
        return

    await update.message.reply_text("⏳ Avaliando relevância...")

    relevant = await evaluate_relevance([{"title": link, "link": link}], categoria)
    item = relevant[0] if relevant else {
        "title": link, "link": link, "score": 9, "categoria": categoria, "motivo": "adicionado manualmente"
    }

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = {
        "data": today,
        "titulo": str(item.get("title", link))[:200],
        "link": link,
        "categoria": categoria,
        "score_ia": item.get("score", 9),
        "motivo": "adicionado manualmente",
        "score_humano": "",
        "status": "pendente",
        "origem": "manual",
    }

    try:
        append_news([row])
    except Exception:
        logger.exception("Sheets append falhou")
        await update.message.reply_text("❌ Erro ao salvar. Tente novamente.")
        return

    await update.message.reply_text(
        f"✅ Notícia salva!\n\n"
        f"📌 {row['titulo']}\n"
        f"🏷 {categoria}\n"
        f"⭐ Score IA: {row['score_ia']}\n\n"
        f"Será incluída no clipping semanal."
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    if not data.startswith("clipping:"):
        return

    action = data.split(":")[1]

    if action == "reject":
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id=settings.telegram_chat_id,
            text="🗑 Post descartado."
        )
        return

    # approve — retrieve post text from message
    post_text = query.message.text or ""
    ok = await _post_linkedin(post_text)

    if ok:
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id=settings.telegram_chat_id,
            text="✅ Post publicado no LinkedIn!"
        )
    else:
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=(
                "⚠️ LinkedIn não configurado ou erro na API.\n"
                "Publique manualmente o texto acima."
            )
        )


def main() -> None:
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(MessageHandler(filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=r"^clipping:"))
    logger.info("procurement-clipping bot iniciado.")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
