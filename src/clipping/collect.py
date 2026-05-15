"""
Coleta diária de notícias via RSS + Claude Haiku para relevância.
Roda às 11h UTC via GitHub Actions (collect.yml).
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser

from src.common.claude import score_noticias
from src.common.config import settings
from src.common.sheets import append_noticias

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

RSS_FEEDS: dict[str, list[str]] = {
    "tech": [
        "https://news.google.com/rss/search?q=Salesforce+OR+SAP+OR+Microsoft+OR+Oracle+OR+AWS+OR+ServiceNow+OR+Workday+OR+OpenAI+OR+IBM+OR+Atlassian+OR+Jira+OR+Slack+OR+Figma+OR+Crowdstrike&hl=pt-BR&gl=BR&ceid=BR:pt&tbs=qdr:d",
        "https://tecnoblog.net/feed/",
        "https://mittechreview.com.br/feed/",
        "https://www.infomoney.com.br/feed/",
    ],
    "financial": [
        "https://news.google.com/rss/search?q=Mastercard+OR+Visa+OR+Cielo+OR+Stone+OR+Elo+OR+Getnet+OR+PagSeguro+OR+Nubank+OR+Pix+OR+fintech+OR+Fiserv+OR+B3+OR+Serasa&hl=pt-BR&gl=BR&ceid=BR:pt&tbs=qdr:d",
        "https://finsiders.com.br/feed/",
        "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    ],
    "marketing": [
        "https://news.google.com/rss/search?q=Google+Ads+OR+Meta+Business+OR+Adobe+OR+HubSpot+OR+Appsflyer+OR+publicidade+digital+OR+adtech+OR+martech&hl=pt-BR&gl=BR&ceid=BR:pt&tbs=qdr:d",
        "https://www.meioemensagem.com.br/feed/",
    ],
}


def _parse_feed(url: str, cutoff: datetime) -> list[dict[str, str]]:
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries:
            pub = entry.get("published_parsed") or entry.get("updated_parsed")
            if pub:
                dt = datetime(*pub[:6], tzinfo=timezone.utc)
                if dt < cutoff:
                    continue
            title = (entry.get("title") or "").replace('"', "'")
            link = entry.get("link") or ""
            if title and link:
                items.append({"title": title, "link": link})
        return items[:20]
    except Exception as exc:
        logger.warning("Feed parse failed %s: %s", url[:60], exc)
        return []


async def collect_category(categoria: str, urls: list[str], cutoff: datetime) -> list[dict[str, Any]]:
    items: list[dict[str, str]] = []
    for url in urls:
        items.extend(await asyncio.to_thread(_parse_feed, url, cutoff))
    if not items:
        return []
    scored = await score_noticias(items, categoria)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [
        {
            "data": today,
            "titulo": s.get("title", s.get("titulo", ""))[:200],
            "link": s.get("link", ""),
            "categoria": categoria,
            "score_ia": s.get("score", 0),
            "motivo": s.get("motivo", ""),
            "score_humano": "",
            "status": "pendente",
            "origem": "automatico",
        }
        for s in scored
    ]


async def run() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    all_rows: list[dict[str, Any]] = []

    for categoria, urls in RSS_FEEDS.items():
        rows = await collect_category(categoria, urls, cutoff)
        all_rows.extend(rows)
        logger.info("[%s] %d notícias relevantes", categoria, len(rows))

    if not all_rows:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        all_rows = [{"data": today, "titulo": "sem_noticias", "link": "", "categoria": "",
                     "score_ia": 0, "motivo": "", "score_humano": "", "status": "ignorado", "origem": "automatico"}]

    await asyncio.to_thread(append_noticias, all_rows)
    logger.info("Total saved: %d", len(all_rows))


if __name__ == "__main__":
    asyncio.run(run())
