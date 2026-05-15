"""Anthropic client wrapper for procurement-clipping."""

import asyncio
import json
import logging
import re
from typing import Any

import anthropic

from src.common.config import settings

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_CAT_NORM = {
    "tech": "tech", "financial": "financial", "marketing": "marketing",
    "financ": "financial", "fintech": "financial", "pagam": "financial", "banco": "financial",
    "market": "marketing", "midia": "marketing", "publi": "marketing",
    "tecn": "tech", "software": "tech", "cloud": "tech",
}


def _norm_cat(raw: str) -> str:
    c = raw.lower().strip()
    if c in ("tech", "financial", "marketing"):
        return c
    for key, val in _CAT_NORM.items():
        if key in c:
            return val
    return "tech"


async def score_noticias(items: list[dict], categoria: str) -> list[dict[str, Any]]:
    """
    Ask Claude Haiku to score a list of news items for relevance to Head of Procurement.
    Returns items with score >= 6.
    """
    cat_desc = {
        "tech": "fornecedores de software/SaaS/cloud/IA, contratos corporativos, demissões por IA, M&A tech, produtos enterprise",
        "financial": "meios de pagamento, fintechs, processadoras, bancos digitais, regulação financeira, produtos financeiros corporativos",
        "marketing": "agências de publicidade, adtech, martech, mídia digital, plataformas de anúncios, campanhas corporativas",
    }
    prompt = (
        f"Analise estas notícias. Selecione as relevantes para um Head of Procurement brasileiro: "
        f"{cat_desc.get(categoria, '')}.\n\n"
        f"Atribua score 1-10 de relevância.\n\n"
        f"Retorne APENAS JSON válido:\n"
        f'{{\"items\":[{{\"title\":\"titulo sem aspas duplas\",\"link\":\"url\",\"score\":8,'
        f'\"categoria\":\"{categoria}\",\"motivo\":\"justificativa\"}}]}}\n\n'
        f"Se nenhuma relevante: {{\"items\":[]}}\n\n"
        f"Notícias:\n{json.dumps(items, ensure_ascii=False)}"
    )
    response = await asyncio.to_thread(
        _client.messages.create,
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```", "", raw).strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group())
        return [i for i in data.get("items", []) if (i.get("score") or 0) >= 6]
    except Exception:
        logger.exception("score_noticias parse failed")
        return []


async def select_top_noticias(tech: list, financial: list, marketing: list, periodo: str) -> dict[str, list]:
    """Claude Haiku selects top 5 per category, deduplicating by topic."""
    prompt = (
        "Você é Augusto Magalhães, Head of Procurement. Selecione as 5 notícias MAIS RELEVANTES "
        "de cada categoria para o clipping semanal do LinkedIn.\n\n"
        "Priorize score_final maior. Elimine notícias com conceito duplicado (mantenha só a de maior score).\n\n"
        "Retorne APENAS JSON:\n"
        "{\"tech\":[{\"titulo\":\"...\",\"link\":\"...\",\"justificativa\":\"...\"}],"
        "\"financial\":[...],\"marketing\":[...]}\n\n"
        f"Período: {periodo}\n\n"
        f"TECNOLOGIA ({len(tech)}):\n{json.dumps(tech[:8], ensure_ascii=False)}\n\n"
        f"FINANCEIRO ({len(financial)}):\n{json.dumps(financial[:8], ensure_ascii=False)}\n\n"
        f"MARKETING ({len(marketing)}):\n{json.dumps(marketing[:8], ensure_ascii=False)}"
    )
    response = await asyncio.to_thread(
        _client.messages.create,
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```", "", raw).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        return {"tech": [], "financial": [], "marketing": []}
    try:
        return json.loads(raw[start : end + 1])
    except Exception:
        logger.exception("select_top_noticias parse failed")
        return {"tech": [], "financial": [], "marketing": []}


async def generate_linkedin_post(estrutura: str, destaque_just: str) -> str:
    """Claude Sonnet fills in ABERTURA, RESUMO_EXECUTIVO, PERGUNTA, HASHTAGS placeholders."""
    prompt = (
        "Você é Augusto Magalhães, Head of Procurement & Logistics, 15 anos de experiência no Brasil.\n\n"
        "Preencha APENAS os 4 marcadores abaixo no post. NÃO altere nada mais.\n\n"
        "MARCADORES:\n"
        "• [ABERTURA] → 2-3 frases analíticas sobre o tema dominante da semana. Sem links.\n"
        "• [RESUMO_EXECUTIVO] → 2-3 linhas de análise prática sobre a notícia 📌 para gestores de procurement. Sem link.\n"
        "• [PERGUNTA] → pergunta direta de engajamento para a audiência\n"
        "• [HASHTAGS] → exatamente 5 hashtags relevantes\n\n"
        "PROIBIDO:\n"
        "- Adicionar links em qualquer lugar\n"
        "- Adicionar texto nos itens 🔹 ou 👉 — ficam EXATAMENTE como estão\n"
        "- Reordenar ou remover notícias\n"
        "- Criar novos marcadores ou seções\n\n"
        f"CONTEXTO DA NOTÍCIA DESTAQUE:\n{destaque_just}\n\n"
        f"POST PARA PREENCHER:\n\n{estrutura}"
    )
    response = await asyncio.to_thread(
        _client.messages.create,
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()
