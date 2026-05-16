# ARCHITECT — procurement-clipping

## Layout: src/
```
procurement-clipping/
├── src/
│   ├── clipping/
│   │   ├── collect.py       # Fluxo 1: RSS fetch + avaliação IA
│   │   ├── publish.py       # Fluxo 2: geração e envio do post semanal
│   │   └── bot.py           # Bot persistente: /add, callbacks LinkedIn
│   ├── bot/
│   │   └── clipping_bot.py  # PRÉ-EXISTENTE — não remover
│   └── common/
│       ├── config.py        # Pydantic BaseSettings
│       ├── sheets.py        # gspread wrapper
│       └── claude.py        # Haiku relevance + Sonnet post generation
├── tests/
├── Procfile
└── pyproject.toml
```

**Nota**: `src/bot/clipping_bot.py` é um arquivo pré-existente com implementação alternativa (`score_noticias`, `_post_to_linkedin`, callback `linkedin:publicar`). Mantê-lo sem modificação — o novo código usa `src/clipping/`.

## Fluxo de dados

```
[Fluxo 1 — Cron 11h UTC, diário]
GH Actions → src.clipping.collect.run()
    └─→ RSS_FEEDS (9 URLs, 3 categorias)
          └─→ asyncio.gather(fetch todos) via aiohttp
                └─→ claude.evaluate_relevance(items, categoria)
                      → score_ia, motivo por artigo
                └─→ sheets.append_news(artigos com score_ia ≥ 6)

[Fluxo 2 — Cron 11h UTC, sexta-feira]
GH Actions → src.clipping.publish.run()
    └─→ sheets.get_news_last_n_days(7)
          └─→ _score_final() para cada artigo
                └─→ claude.select_top_news(tech=[], financial=[], marketing=[])
                      └─→ claude.generate_linkedin_post(estrutura, destaque_just)
                            └─→ _split_message() (≤3800 chars)
                                  └─→ Telegram com InlineKeyboard:
                                      [clipping:approve | clipping:reject]

[Bot persistente]
Railway → src.clipping.bot (ApplicationBuilder polling)
    ├─→ handle_link: CommandHandler('/add')
    └─→ handle_callback: CallbackQueryHandler('clipping:')
          ├─→ clipping:approve → _post_linkedin() + sheets.update_status('publicado')
          └─→ clipping:reject  → sheets.update_status('rejeitado')
```

## Google Sheets — aba `NOTICIAS`

| Coluna | Tipo | Quem escreve |
|--------|------|--------------|
| data | date | collect.py |
| titulo | str | collect.py |
| link | str | collect.py / /add manual |
| categoria | str | tech/financial/marketing |
| score_ia | int (1-10) | claude.evaluate_relevance |
| motivo | str | claude.evaluate_relevance |
| score_humano | int (0-5) | futuro: via Telegram |
| status | str | pendente/publicado/rejeitado |
| origem | str | URL do feed RSS |

Sheet ID: `1OpRpvkgBsckdrTrKbRPA_ajcqLu9dryCH-pE8Bj_KMM`

## Score final
```python
def _score_final(score_ia: int, score_humano: int) -> float:
    if score_humano == 0:
        return 0  # excluído do pool semanal
    return (score_humano * 2 + score_ia) / 3
```

## Decisões arquiteturais

| Decisão | Alternativa | Motivo |
|---------|-------------|--------|
| Haiku para relevância (não Sonnet) | Sonnet | ~100 artigos/dia × 5 dias = custo alto; Haiku suficiente para score 1-10 |
| Sonnet para gerar post LinkedIn | Haiku | Post é conteúdo público que representa o usuário — qualidade importa |
| aiohttp para fetch RSS | requests | async fetch dos 9 feeds em paralelo; feedparser processa depois |
| callback `clipping:approve/reject` | URL button | PTB usa callback_data string; prefixo `clipping:` permite filtrar no handler |
| LinkedIn API opcional | Obrigatório | Token OAuth expira; fallback para instrução manual no Telegram |
| `score_humano == 0` → excluído | Incluir com score baixo | Evita posts sobre notícias que o usuário não leu/validou |

## Dependências externas

- **Claude Haiku** (`claude-haiku-4-5-20251001`): avaliação de relevância (barato, alta volume)
- **Claude Sonnet** (`claude-sonnet-4-6`): geração do post LinkedIn (qualidade)
- **feedparser**: parse de RSS/Atom
- **aiohttp**: fetch async das URLs dos feeds
- **LinkedIn API** (`/v2/ugcPosts`): publicação (opcional — requer `LINKEDIN_ACCESS_TOKEN`)
- **gspread**: Sheets NOTICIAS
