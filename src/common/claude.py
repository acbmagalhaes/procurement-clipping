import asyncio
import json
import logging
import re
from typing import Any

import anthropic

from src.common.config import settings

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_RELEVANCE_SYSTEM = """Você é um analista de inteligência de mercado para um Head of Procurement brasileiro.
Dado uma lista de notícias, selecione apenas as relevantes para procurement corporativo:
- Fornecedores de software/SaaS/cloud/IA
- Meios de pagamento, fintechs, processadoras
- Agências, adtech, martech, plataformas de marketing
- Impacto em contratos corporativos, M&A, novos produtos enterprise

Atribua score 1-10. Retorne APENAS JSON:
{"items":[{"title":"titulo","link":"url","score":8,"categoria":"tech|financial|marketing","motivo":"justificativa"}]}

Se nenhuma relevante: {"items":[]}"""


async def evaluate_relevance(items: list[dict], categoria: str) -> list[dict[str, Any]]:
    """Evaluate news relevance for a given category. Returns items with score >= 6."""
    if not items:
        return []

    user_msg = f"Categoria obrigatória: {categoria}\n\nNotícias:\n{json.dumps(items, ensure_ascii=False)}"

    response = await asyncio.to_thread(
        _client.messages.create,
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=_RELEVANCE_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = response.content[0].text
    clean = re.sub(r"```json|```", "", raw).strip()
    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if not match:
        logger.warning("Claude Haiku returned no JSON for %s", categoria)
        return []
    try:
        data = json.loads(match.group())
        relevant = [i for i in data.get("items", []) if int(i.get("score", 0)) >= 6]
        return relevant
    except (json.JSONDecodeError, ValueError):
        logger.exception("JSON decode error from relevance check")
        return []


_SELECT_SYSTEM = """Você é Augusto Magalhaes, Head of Procurement.
Selecione as 5 notícias MAIS RELEVANTES de cada categoria.
Priorize score_final maior. Elimine notícias com conceito duplicado (mesmo assunto — mantenha a de maior score).
Retorne APENAS JSON:
{"tech":[{"titulo":"...","link":"...","justificativa":"..."}],"financial":[...],"marketing":[...]}"""

_POST_SYSTEM = """Você é Augusto Magalhaes, Head of Procurement & Logistics, 15 anos de experiência no Brasil.
Preencha APENAS os 4 marcadores no post. NÃO altere nada mais.

MARCADORES:
• [ABERTURA] → 2-3 frases analíticas sobre o tema dominante da semana. Sem links.
• [RESUMO_EXECUTIVO] → 2-3 linhas de análise prática sobre a notícia 📌 para gestores de procurement. Sem link.
• [PERGUNTA] → pergunta direta de engajamento
• [HASHTAGS] → exatamente 5 hashtags relevantes

PROIBIDO:
- Adicionar links em qualquer lugar
- Alterar itens 🔹 ou 👉
- Reordenar ou remover notícias
- Criar novos marcadores"""


async def select_top_news(tech: list, financial: list, marketing: list) -> dict[str, list]:
    """Claude Haiku selects top 5 per category."""
    prompt = (
        f"TECNOLOGIA ({len(tech)}):\n{json.dumps(tech[:8], ensure_ascii=False)}\n\n"
        f"FINANCEIRO ({len(financial)}):\n{json.dumps(financial[:8], ensure_ascii=False)}\n\n"
        f"MARKETING ({len(marketing)}):\n{json.dumps(marketing[:8], ensure_ascii=False)}"
    )
    response = await asyncio.to_thread(
        _client.messages.create,
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=_SELECT_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text
    logger.info("select_top_news raw response: %s", raw[:800])
    clean = re.sub(r"```json|```", "", raw).strip()

    # Find the first { and match to its closing } by counting depth
    start = clean.find("{")
    if start == -1:
        logger.warning("select_top_news: no JSON object found in response")
        return {"tech": [], "financial": [], "marketing": []}
    depth = 0
    end = -1
    for i, c in enumerate(clean[start:], start):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        logger.warning("select_top_news: unmatched braces in response")
        return {"tech": [], "financial": [], "marketing": []}
    try:
        result = json.loads(clean[start : end + 1])
        logger.info("select_top_news parsed: tech=%d, financial=%d, marketing=%d",
                    len(result.get("tech", [])), len(result.get("financial", [])), len(result.get("marketing", [])))
        return result
    except json.JSONDecodeError:
        logger.warning("select_top_news: JSON decode failed. Extracted: %s", clean[start : end + 1][:300])
        return {"tech": [], "financial": [], "marketing": []}


async def generate_linkedin_post(estrutura: str, destaque_justificativa: str) -> str:
    """Claude Sonnet fills in the post placeholders."""
    prompt = (
        f"CONTEXTO DA NOTÍCIA DESTAQUE (para o [RESUMO_EXECUTIVO]):\n{destaque_justificativa}\n\n"
        f"POST PARA PREENCHER:\n\n{estrutura}"
    )
    response = await asyncio.to_thread(
        _client.messages.create,
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=_POST_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
