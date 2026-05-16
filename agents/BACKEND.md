# BACKEND — procurement-clipping

## Padrões obrigatórios
- Python 3.11+ com type hints
- `logger = logging.getLogger(__name__)` em todo módulo
- `try/except Exception: logger.exception(...)` — nunca `print()` para erros
- Pydantic v2 BaseSettings; `SettingsConfigDict(env_file=".env")`
- `async/await` para I/O (aiohttp, Telegram)
- Módulos executáveis via `python -m src.clipping.collect`

## Módulos e responsabilidades

### `src/common/config.py`
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    ANTHROPIC_API_KEY: str
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID: str
    GOOGLE_SHEET_ID: str = "1OpRpvkgBsckdrTrKbRPA_ajcqLu9dryCH-pE8Bj_KMM"
    GOOGLE_SERVICE_ACCOUNT_JSON: str
    LINKEDIN_ACCESS_TOKEN: str | None = None
    LINKEDIN_AUTHOR_URN: str | None = None  # "urn:li:person:XXXXXXXX"
```

### `src/common/sheets.py`
Aba: `NOTICIAS`. Colunas: data, titulo, link, categoria, score_ia, motivo, score_humano, status, origem
- `append_news(items: list[dict])` — grava batch de artigos
- `get_news_last_n_days(n: int) -> list[dict]` — para publish.py
- `update_status(link: str, status: str)` — após publicar/rejeitar

### `src/common/claude.py`
```python
async def evaluate_relevance(items: list[dict], categoria: str) -> list[dict]:
    # Modelo: claude-haiku-4-5-20251001
    # Prompt: avaliar relevância de cada artigo para Head of Procurement
    # Score 1-10; retorna lista com score_ia e motivo adicionados

async def select_top_news(
    tech: list[dict], financial: list[dict], marketing: list[dict]
) -> dict[str, list[dict]]:
    # Seleciona 2-3 melhores por categoria

async def generate_linkedin_post(estrutura: dict, destaque_just: str) -> str:
    # Modelo: claude-sonnet-4-6
    # Template: [ABERTURA] + [RESUMO_EXECUTIVO] + [PERGUNTA] + [HASHTAGS]
    # Retorna texto ≤3800 chars
```

### `src/clipping/collect.py`
```python
RSS_FEEDS = {
    "tech": [
        "https://supplychaindigital.com/rss.xml",
        "https://spendmatters.com/feed/",
        "https://www.procurementmag.com/rss",
        "https://www.theprocurement.com/feed",
    ],
    "financial": [
        "https://valor.globo.com/rss",
        "https://feeds.bloomberg.com/businessnews/news.rss",
        "https://feeds.reuters.com/reuters/businessNews",
    ],
    "marketing": [
        "https://business.linkedin.com/marketing-solutions/blog/rss",
        "https://contentmarketinginstitute.com/feed/",
    ],
}

async def run(dry_run: bool = False):
    # asyncio.gather() para fetch todos os feeds
    # feedparser.parse() por feed
    # claude.evaluate_relevance() por categoria
    # Se não dry_run: sheets.append_news()
    # Se dry_run: apenas print dos artigos relevantes
```
Executável: `python -m src.clipping.collect` ou `python -m src.clipping.collect --dry-run`

### `src/clipping/publish.py`
```python
def _score_final(score_ia: int, score_humano: int) -> float:
    if score_humano == 0:
        return 0.0
    return (score_humano * 2 + score_ia) / 3

def _build_post_structure(top_news: dict) -> dict:
    # Monta dict com seções: abertura, resumo_executivo, pergunta, hashtags

def _split_message(text: str, max_len: int = 3800) -> str:
    # Trunca se necessário (raro com Sonnet)

async def run():
    # 1. sheets.get_news_last_n_days(7)
    # 2. _score_final() e filtra > 0
    # 3. claude.select_top_news()
    # 4. claude.generate_linkedin_post()
    # 5. Telegram com InlineKeyboard [clipping:approve | clipping:reject]
```

### `src/clipping/bot.py`
```python
async def handle_link(update, context):
    # CommandHandler para "/add <url> <categoria>"
    # Busca título via feedparser/aiohttp
    # sheets.append_news([{titulo, link, categoria, score_humano=3, ...}])

async def handle_callback(update, context):
    # Filtra callback_data com prefixo "clipping:"
    # clipping:approve → _post_linkedin() se LINKEDIN_ACCESS_TOKEN
    # clipping:reject  → sheets.update_status(link, 'rejeitado')

async def _post_linkedin(post_text: str):
    # aiohttp POST para https://api.linkedin.com/v2/ugcPosts
    # Headers: Authorization: Bearer {LINKEDIN_ACCESS_TOKEN}
    # Body: ugcPost com lifecycleState: PUBLISHED
```

### `src/bot/clipping_bot.py` (pré-existente)
Não modificar. Contém: `score_noticias()`, `append_noticias()`, `_post_to_linkedin()`, callback pattern `linkedin:publicar`/`linkedin:descartar`. API alternativa mantida para compatibilidade.

## Como rodar localmente
```bash
# Coleta manual
python -m src.clipping.collect --dry-run   # sem gravar no Sheets

# Publicação manual (sexta)
python -m src.clipping.publish

# Bot
python -m src.clipping.bot
```
