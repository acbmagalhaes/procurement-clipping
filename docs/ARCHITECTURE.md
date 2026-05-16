# ARCHITECTURE — procurement-clipping

## Diagrama de fluxo de dados

```
[FLUXO 1 — Cron 11h UTC, segunda a sexta]
┌─────────────────────────────────────────────────────────┐
│  GH Actions → src/clipping/collect.py                   │
│                                                         │
│  RSS_FEEDS (9 URLs, 3 categorias)                       │
│  ┌────────────────────────────────────────────────────┐ │
│  │  asyncio.gather([                                  │ │
│  │    fetch_feed("tech/supply_chain_digital"),        │ │
│  │    fetch_feed("tech/spend_matters"),               │ │
│  │    fetch_feed("tech/procurement_mag"),             │ │
│  │    fetch_feed("tech/the_procurement"),             │ │
│  │    fetch_feed("financial/valor"),                  │ │
│  │    fetch_feed("financial/bloomberg"),              │ │
│  │    fetch_feed("financial/reuters"),                │ │
│  │    fetch_feed("marketing/linkedin_blog"),          │ │
│  │    fetch_feed("marketing/cmi"),                    │ │
│  │  ])                                                │ │
│  └────────────────────────────────────────────────────┘ │
│  Por categoria:                                         │
│  claude.evaluate_relevance(items, categoria)            │
│  → score_ia (1-10) + motivo por artigo                 │
│                                                         │
│  sheets.append_news(artigos com score_ia ≥ 6)           │
└─────────────────────────────────────────────────────────┘

[FLUXO 2 — Cron 11h UTC, sexta-feira]
┌─────────────────────────────────────────────────────────┐
│  GH Actions → src/clipping/publish.py                   │
│  1. sheets.get_news_last_n_days(7) → artigos da semana  │
│  2. _score_final() por artigo                           │
│     if score_humano == 0: score = 0 (excluído)          │
│     else: (score_humano×2 + score_ia) / 3              │
│  3. filtra score > 0, agrupa por categoria              │
│  4. claude.select_top_news(tech, financial, marketing)  │
│  5. claude.generate_linkedin_post(estrutura)            │
│  6. _split_message() → ≤ 3800 chars                    │
│  7. Telegram: post preview + InlineKeyboard             │
│     [clipping:approve | clipping:reject]                │
└─────────────────────────────────────────────────────────┘

[BOT PERSISTENTE — Railway]
┌─────────────────────────────────────────────────────────┐
│  src/clipping/bot.py (polling 24/7)                     │
│                                                         │
│  /add <url> <categoria>                                 │
│  → sheets.append_news([{titulo, link, categoria}])      │
│                                                         │
│  callback: clipping:approve                             │
│  → _post_linkedin() via aiohttp POST /v2/ugcPosts       │
│     [se LINKEDIN_ACCESS_TOKEN configurado]              │
│  → sheets.update_status('publicado')                    │
│                                                         │
│  callback: clipping:reject                              │
│  → sheets.update_status('rejeitado')                    │
└─────────────────────────────────────────────────────────┘
```

## Componentes

| Componente | Onde roda | Trigger | Responsabilidade |
|-----------|-----------|---------|-----------------|
| `src/clipping/collect.py` | GH Actions | Cron diário seg-sex | RSS fetch + relevância |
| `src/clipping/publish.py` | GH Actions | Cron sexta | Post LinkedIn semanal |
| `src/clipping/bot.py` | Railway | Mensagem/callback Telegram | /add + aprovação LinkedIn |
| `src/bot/clipping_bot.py` | Railway (legado) | — | Pré-existente, não modificar |
| Google Sheets | Google Cloud | — | Persistência NOTICIAS |

## Score final — lógica de aprovação

```python
def _score_final(score_ia: int, score_humano: int) -> float:
    if score_humano == 0:
        return 0.0  # não avaliado → excluído
    return (score_humano * 2 + score_ia) / 3
```

**Racional**: score_humano=0 significa "não lido". Incluir artigos não lidos no post semanal seria publicar conteúdo que o usuário não validou. O peso duplo do score humano garante que a curadoria humana seja determinante.

## Google Sheets — schema

Sheet ID: `1OpRpvkgBsckdrTrKbRPA_ajcqLu9dryCH-pE8Bj_KMM` — aba `NOTICIAS`

```
data (date) | titulo (str) | link (str) | categoria (str)
score_ia (int 1-10) | motivo (str) | score_humano (int 0-5)
status (str) | origem (str)
```

Status lifecycle: `pendente` → `publicado` | `rejeitado`
Entrada manual (`/add`): entra com `score_humano=3` (neutro) para aparecer no pool.

## Template do post LinkedIn

```
[ABERTURA]
Linha de impacto, dado ou pergunta retórica.

[RESUMO_EXECUTIVO]
• [tech] Título notícia + insight 1 linha
• [financial] Título notícia + insight 1 linha  
• [marketing] Título notícia + insight 1 linha

[PERGUNTA]
Pergunta aberta para engajamento da audiência.

[HASHTAGS]
#procurement #supplychain #compras #gestaocompras
```

## Decisões de arquitetura

### Por que Haiku para relevância (não Sonnet)?
O collect.py processa ~50-100 artigos por dia × 5 dias/semana. Usar Sonnet seria ~20× mais caro para uma tarefa simples de scoring. Haiku é adequado para "este artigo é relevante para procurement? Score 1-10."

### Por que Sonnet para o post LinkedIn?
O post representa o profissional publicamente. Qualidade de escrita importa para engajamento. Sonnet produz textos mais fluidos e convincentes para conteúdo B2B.

### Por que `score_humano == 0` exclui o artigo?
Evita publicar conteúdo que o usuário não validou. O MVP não tem interface de score humano — todos os artigos do collect.py têm `score_humano=0` inicialmente. Isso significa que **o post semanal só funciona com artigos adicionados via `/add`** até que a interface de scoring seja implementada (v0.2).

### Por que aiohttp para fetch RSS (não feedparser direto)?
feedparser.parse() é síncrono e bloqueia para cada URL. Com 9 feeds, isso seria sequencial (~9s). `asyncio.gather()` + aiohttp faz todos os requests em paralelo (<2s total). feedparser processa o conteúdo depois do download.

### Por que LinkedIn API é opcional?
O token OAuth2 expira em 60 dias e precisa de renovação manual. O sistema deve funcionar mesmo sem token — o bot envia o texto do post para copiar/colar manualmente.

## Dependências e riscos

| Dependência | Risco | Mitigação |
|-------------|-------|-----------|
| Feeds RSS | Feed fora do ar ou URL mudou | `try/except` por feed; log warning; continua com demais |
| Claude Haiku | Retorna score não-int | Parse defensivo com `int(score)` ou fallback 5 |
| LinkedIn OAuth | Token expira em 60 dias | Documentado no CLAUDE.md; fallback manual |
| `score_humano=0` em todos artigos | Post semanal vazio | MVP: usar `/add` para popular; v0.2: scoring via Telegram |
