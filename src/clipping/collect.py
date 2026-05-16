"""
Coleta diária de RSS + Telegram manual.
Cron diário → RSS tech/financial/marketing → Claude Haiku filtra → Sheets.
Bot Telegram: recebe link → Claude avalia → Sheets com origem='manual'.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
import feedparser

from src.common.claude import evaluate_relevance
from src.common.sheets import append_news

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

RSS_FEEDS: dict[str, list[str]] = {
    "tech": [
        "https://news.google.com/rss/search?q=Salesforce+OR+SAP+OR+Microsoft+OR+Oracle+OR+AWS+OR+ServiceNow+OR+Workday+OR+OpenAI+OR+IBM+OR+Atlassian+OR+Jira+OR+Monday.com+OR+Notion+OR+Slack+OR+Figma+OR+Crowdstrike+OR+Zscaler&hl=pt-BR&gl=BR&ceid=BR:pt&tbs=qdr:d",
        "https://tecnoblog.net/feed/",
        "https://mittechreview.com.br/feed/",
        "https://www.infomoney.com.br/feed/",
    ],
    "financial": [
        "https://news.google.com/rss/search?q=Mastercard+OR+Visa+OR+Cielo+OR+Stone+OR+Elo+OR+Getnet+OR+PagSeguro+OR+Nubank+OR+Pix+OR+fintech+OR+Fiserv+OR+Tecban+OR+B3+OR+Serasa&hl=pt-BR&gl=BR&ceid=BR:pt&tbs=qdr:d",
        "https://finsiders.com.br/feed/",
        "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    ],
    "marketing": [
        "https://news.google.com/rss/search?q=Google+Ads+OR+Meta+Business+OR+Adobe+OR+HubSpot+OR+Appsflyer+OR+publicidade+digital+OR+adtech+OR+martech&hl=pt-BR&gl=BR&ceid=BR:pt&tbs=qdr:d",
        "https://www.meioemensagem.com.br/feed/",
    ],
}


async def _fetch_feed(session: aiohttp.ClientSession, url: str) -> list[dict]:
    """Fetch and parse RSS feed, returning entries from last 24h."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            text = await resp.text()
        feed = await asyncio.to_thread(feedparser.parse, text)
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        items = []
        for entry in feed.entries:
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published:
                from time import mktime
                dt = datetime.fromtimestamp(mktime(published), tz=timezone.utc)
                if dt < cutoff and len(feed.entries) >= 5:
                    continue
            title = entry.get("title", "").replace('"', "'")[:200]
            link = entry.get("link", "")
            if title and link:
                items.append({"title": title, "link": link})
        return items[:20]
    except Exception:
        logger.exception("Feed fetch falhou: %s", url[:80])
        return []


async def collect_category(session: aiohttp.ClientSession, categoria: str, urls: list[str]) -> list[dict]:
    """Fetch all RSS feeds for a category and evaluate relevance."""
    all_items: list[dict] = []
    tasks = [_fetch_feed(session, url) for url in urls]
    results = await asyncio.gather(*tasks)
    for r in results:
        all_items.extend(r)

    if not all_items:
        return []

    logger.info("[%s] %d artigos para avaliar", categoria, len(all_items))
    relevant = await evaluate_relevance(all_items, categoria)
    logger.info("[%s] %d relevantes (score >= 6)", categoria, len(relevant))
    return relevant


async def run(dry_run: bool = False) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    all_rows: list[dict[str, Any]] = []

    async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
        for categoria, urls in RSS_FEEDS.items():
            relevant = await collect_category(session, categoria, urls)
            for item in relevant:
                all_rows.append({
                    "data": today,
                    "titulo": str(item.get("title", ""))[:200],
                    "link": item.get("link", ""),
                    "categoria": categoria,
                    "score_ia": item.get("score", 0),
                    "motivo": item.get("motivo", ""),
                    "score_humano": "",
                    "status": "pendente",
                    "origem": "automatico",
                })

    if not all_rows:
        all_rows = [{
            "data": today, "titulo": "sem_noticias", "link": "", "categoria": "",
            "score_ia": 0, "motivo": "", "score_humano": "", "status": "ignorado", "origem": "automatico",
        }]

    if dry_run:
        for r in all_rows:
            print(f"[{r['categoria']}] {r['titulo'][:80]} — score={r['score_ia']}")
        logger.info("dry_run: %d notícias encontradas", len(all_rows))
        return

    try:
        append_news(all_rows)
        logger.info("Salvas %d notícias no Sheets.", len(all_rows))
    except Exception:
        logger.exception("Sheets append falhou")


if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv
    asyncio.run(run(dry_run=dry))
