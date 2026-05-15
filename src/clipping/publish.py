"""
Publicação semanal — seleciona top notícias, gera post LinkedIn, envia para aprovação via Telegram.
Roda às sextas-feiras 11h UTC via GitHub Actions (publish.yml).
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
import telegram

from src.common.claude import generate_linkedin_post, select_top_noticias
from src.common.config import settings
from src.common.sheets import get_noticias_semana

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

MAX_TG = 3800  # safe Telegram message limit


def _score_final(r: dict) -> float:
    score_ia = float(str(r.get("score_ia", 0) or 0))
    sh_raw = r.get("score_humano", "")
    try:
        sh = float(str(sh_raw))
        return round((sh * 2 + score_ia) / 3, 1)
    except (ValueError, TypeError):
        return score_ia


def _group_by_category(rows: list[dict]) -> tuple[list, list, list]:
    tech, financial, marketing = [], [], []
    for r in rows:
        sh_raw = r.get("score_humano", "")
        try:
            if float(str(sh_raw)) == 0:
                continue  # explicitly removed by human
        except (ValueError, TypeError):
            pass
        link = str(r.get("link", ""))
        if not link.startswith("http"):
            continue
        cat = str(r.get("categoria", "")).lower().strip()
        if "fin" in cat or "pagam" in cat or "banco" in cat:
            cat = "financial"
        elif "market" in cat or "midia" in cat or "publi" in cat:
            cat = "marketing"
        else:
            cat = "tech"
        item = {
            "titulo": str(r.get("titulo", ""))[:200],
            "link": link,
            "score_ia": float(str(r.get("score_ia", 0) or 0)),
            "score_humano": r.get("score_humano", ""),
            "score_final": _score_final(r),
            "motivo": str(r.get("motivo", "")),
        }
        if cat == "tech":
            tech.append(item)
        elif cat == "financial":
            financial.append(item)
        else:
            marketing.append(item)

    tech.sort(key=lambda x: x["score_final"], reverse=True)
    financial.sort(key=lambda x: x["score_final"], reverse=True)
    marketing.sort(key=lambda x: x["score_final"], reverse=True)
    return tech, financial, marketing


def _build_post_structure(selected: dict[str, list]) -> tuple[str, str, str]:
    """Returns (estrutura, destaque_titulo, destaque_just)."""
    all_items = (
        [("tech", i) for i in selected.get("tech", [])]
        + [("financial", i) for i in selected.get("financial", [])]
        + [("marketing", i) for i in selected.get("marketing", [])]
    )
    destaque_titulo = destaque_just = destaque_cat = ""
    for cat, item in all_items:
        if item.get("titulo"):
            destaque_titulo = item["titulo"]
            destaque_just = item.get("justificativa", "")
            destaque_cat = cat
            break

    emoji_map = {"tech": "🤖", "financial": "🏦", "marketing": "📣"}
    cat_label = {"tech": "TECNOLOGIA", "financial": "SERVIÇOS FINANCEIROS", "marketing": "MARKETING"}

    sections = []
    for cat in ("tech", "financial", "marketing"):
        items = selected.get(cat, [])
        if not items:
            continue
        sec = f"## {emoji_map[cat]} {cat_label[cat]}\n"
        for i, item in enumerate(items):
            titulo = item.get("titulo", "")
            if i == 0 and cat == destaque_cat:
                sec += f"📌 {titulo}\n[RESUMO_EXECUTIVO]\n"
            else:
                sec += f"🔹 {titulo}\n"
        sections.append(sec)

    estrutura = (
        "# 🗞️ CLIPPING SEMANAL | Procurement & Supply Chain Intelligence\n\n"
        "[ABERTURA]\n\n"
        + "\n".join(sections)
        + "\n---\n[PERGUNTA]\n\n[HASHTAGS]"
    )
    return estrutura, destaque_titulo, destaque_just


def _split_message(text: str) -> list[str]:
    if len(text) <= MAX_TG:
        return [text]
    parts = []
    remaining = text
    while remaining:
        if len(remaining) <= MAX_TG:
            parts.append(remaining)
            break
        cut = remaining.rfind("\n", 0, MAX_TG)
        if cut == -1:
            cut = MAX_TG
        parts.append(remaining[:cut])
        remaining = remaining[cut:].strip()
    return parts


async def _post_to_linkedin(text: str) -> bool:
    if not settings.linkedin_access_token or not settings.linkedin_person_id:
        logger.warning("LinkedIn credentials not configured.")
        return False
    body = {
        "author": settings.linkedin_person_id,
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
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.linkedin.com/v2/ugcPosts",
            json=body,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status in (200, 201):
                logger.info("LinkedIn post published.")
                return True
            text_resp = await resp.text()
            logger.error("LinkedIn publish failed %d: %s", resp.status, text_resp[:300])
            return False


async def run() -> None:
    bot = telegram.Bot(settings.telegram_bot_token)
    now = datetime.now(timezone.utc)
    rows = await asyncio.to_thread(get_noticias_semana, 7)

    if not rows:
        await bot.send_message(chat_id=settings.telegram_chat_id, text="ℹ️ Nenhuma notícia esta semana para publicar.")
        return

    tech, financial, marketing = _group_by_category(rows)
    periodo = f"{(now - timedelta(days=7)).strftime('%Y-%m-%d')} a {now.strftime('%Y-%m-%d')}"
    selected = await select_top_noticias(tech, financial, marketing, periodo)

    estrutura, destaque_titulo, destaque_just = _build_post_structure(selected)
    post_text = await generate_linkedin_post(estrutura, destaque_just)

    # Send to Telegram with approval buttons
    keyboard = [[
        telegram.InlineKeyboardButton("✅ Publicar no LinkedIn", callback_data="linkedin:publicar"),
        telegram.InlineKeyboardButton("🗑 Descartar", callback_data="linkedin:descartar"),
    ]]
    parts = _split_message(post_text)
    for i, part in enumerate(parts):
        is_last = i == len(parts) - 1
        markup = telegram.InlineKeyboardMarkup(keyboard) if is_last else None
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=part,
            parse_mode="Markdown",
            reply_markup=markup,
        )

    # Store post text for callback (bot reads from sheet or env — here we log it)
    logger.info("Weekly post sent for approval. Length: %d chars", len(post_text))


if __name__ == "__main__":
    asyncio.run(run())
