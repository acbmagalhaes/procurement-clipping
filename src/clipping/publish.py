"""
Publicação semanal do clipping no LinkedIn.
Cron sexta-feira → lê Sheets → seleciona top 5 por categoria → gera post LinkedIn
→ envia ao Telegram para aprovação humana → bot publica se aprovado.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton

from src.common.config import settings
from src.common.sheets import get_news_last_n_days
from src.common.claude import select_top_news, generate_linkedin_post

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

MAX_MSG = 3800  # Telegram limit is 4096; leave margin


def _score_final(r: dict) -> float:
    score_ia = float(r.get("score_ia") or 0)
    raw = r.get("score_humano")
    if raw == "" or raw is None:
        return score_ia
    try:
        sh = float(raw)
        if sh == 0:
            return -1  # exclude
        return round((sh * 2 + score_ia) / 3, 1)
    except (ValueError, TypeError):
        return score_ia


def _split_by_category(news: list[dict]) -> tuple[list, list, list]:
    tech, financial, marketing = [], [], []
    for r in news:
        sf = _score_final(r)
        if sf < 0:
            continue
        item = {
            "titulo": r.get("titulo", ""),
            "link": r.get("link", ""),
            "score_ia": float(r.get("score_ia") or 0),
            "score_humano": r.get("score_humano", ""),
            "score_final": sf,
            "motivo": r.get("motivo", ""),
        }
        cat = str(r.get("categoria", "")).lower()
        if cat == "tech":
            tech.append(item)
        elif cat == "financial":
            financial.append(item)
        elif cat == "marketing":
            marketing.append(item)
    tech.sort(key=lambda x: x["score_final"], reverse=True)
    financial.sort(key=lambda x: x["score_final"], reverse=True)
    marketing.sort(key=lambda x: x["score_final"], reverse=True)
    return tech, financial, marketing


def _build_post_structure(selected: dict[str, list]) -> tuple[str, str]:
    """Build post template with placeholders. Returns (estrutura, destaque_justificativa)."""
    tech = selected.get("tech", [])
    financial = selected.get("financial", [])
    marketing = selected.get("marketing", [])

    # Destaque: first of tech, fallback financial, fallback marketing
    destaque_titulo = destaque_just = destaque_cat = ""
    if tech:
        destaque_titulo, destaque_cat, destaque_just = tech[0]["titulo"], "tech", tech[0].get("justificativa", "") or tech[0].get("motivo", "")
    elif financial:
        destaque_titulo, destaque_cat, destaque_just = financial[0]["titulo"], "financial", financial[0].get("justificativa", "") or financial[0].get("motivo", "")
    elif marketing:
        destaque_titulo, destaque_cat, destaque_just = marketing[0]["titulo"], "marketing", marketing[0].get("justificativa", "") or marketing[0].get("motivo", "")

    def section(cat_key: str, icon: str, title: str, items: list) -> str:
        if not items and destaque_cat != cat_key:
            return ""
        lines = [f"## {icon} {title}"]
        for it in items:
            if it["titulo"] == destaque_titulo:
                lines.append(f"📌 {it['titulo']}\n[RESUMO_EXECUTIVO]")
            else:
                prefix = "🔹" if cat_key == "tech" else "👉"
                lines.append(f"{prefix} {it['titulo']}")
        return "\n".join(lines)

    sec_tech = section("tech", "🤖", "TECNOLOGIA", tech)
    sec_fin = section("financial", "🏦", "SERVIÇOS FINANCEIROS", financial)
    sec_mkt = section("marketing", "📣", "MARKETING", marketing)

    estrutura = (
        "# 🗞️ CLIPPING SEMANAL | Procurement & Supply Chain Intelligence\n\n"
        "[ABERTURA]\n\n"
        + (sec_tech + "\n\n" if sec_tech else "")
        + (sec_fin + "\n\n" if sec_fin else "")
        + (sec_mkt + "\n\n" if sec_mkt else "")
        + "---\n[PERGUNTA]\n\n[HASHTAGS]"
    )
    return estrutura, destaque_just


def _split_message(text: str) -> list[str]:
    if len(text) <= MAX_MSG:
        return [text]
    parts = []
    remaining = text
    while remaining:
        if len(remaining) <= MAX_MSG:
            parts.append(remaining)
            break
        cut = remaining.rfind("\n", 0, MAX_MSG)
        if cut == -1:
            cut = MAX_MSG
        parts.append(remaining[:cut])
        remaining = remaining[cut:].lstrip()
    return parts


async def run() -> None:
    news = get_news_last_n_days(7)
    if not news:
        logger.info("Sem notícias na semana.")
        return

    tech, financial, marketing = _split_by_category(news)
    logger.info("Notícias: tech=%d, financial=%d, marketing=%d", len(tech), len(financial), len(marketing))

    selected = await select_top_news(tech, financial, marketing)
    logger.info("selected keys: tech=%d, financial=%d, marketing=%d",
                len(selected.get("tech", [])), len(selected.get("financial", [])), len(selected.get("marketing", [])))
    estrutura, destaque_just = _build_post_structure(selected)
    logger.info("estrutura preview: %s", estrutura[:300])

    post_text = await generate_linkedin_post(estrutura, destaque_just)
    logger.info("Post gerado (%d chars)", len(post_text))

    bot = Bot(settings.telegram_bot_token)
    parts = _split_message(post_text)
    total = len(parts)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Publicar no LinkedIn", callback_data="clipping:approve"),
            InlineKeyboardButton("🗑 Descartar", callback_data="clipping:reject"),
        ]
    ])

    for i, part in enumerate(parts, 1):
        prefix = f"📄 Parte {i}/{total}\n\n" if total > 1 else ""
        text = prefix + part
        markup = keyboard if i == total else None
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=markup,
        )

    logger.info("Post enviado ao Telegram para aprovação.")


if __name__ == "__main__":
    asyncio.run(run())
