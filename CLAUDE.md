# CLAUDE.md — procurement-clipping

## O que é este projeto
Curadoria de notícias para Head of Procurement. Coleta diária de 9 feeds RSS (tech/financial/marketing) → Claude Haiku avalia relevância → toda sexta Claude Sonnet gera post LinkedIn → aprovação via Telegram → publicação.

## Stack
- Python 3.11+, src/ layout
- `python-telegram-bot>=21.0` (modo polling no Railway)
- `anthropic` (`claude-haiku-4-5-20251001` para relevância, `claude-sonnet-4-6` para post LinkedIn)
- `feedparser>=6.0.0` para RSS
- `aiohttp>=3.9.0` para fetch async dos feeds e LinkedIn API
- `gspread` + service account para Google Sheets
- Pydantic v2 BaseSettings

## Variáveis de ambiente
### Obrigatórias
```
ANTHROPIC_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
GOOGLE_SHEET_ID=1OpRpvkgBsckdrTrKbRPA_ajcqLu9dryCH-pE8Bj_KMM
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
```
### Opcionais
```
LINKEDIN_ACCESS_TOKEN=   # expira em 60 dias — renovar manualmente
LINKEDIN_AUTHOR_URN=     # ex: urn:li:person:XXXXXXXX
```
Ver `.env.example`. **Nunca hardcodar valores no código.**

## Estrutura de pastas
```
procurement-clipping/
├── src/
│   ├── clipping/
│   │   ├── collect.py       # Cron diário: RSS fetch + avaliação IA
│   │   ├── publish.py       # Cron sexta: geração e envio do post
│   │   └── bot.py           # Bot: /add manual + callbacks LinkedIn
│   ├── bot/
│   │   └── clipping_bot.py  # PRÉ-EXISTENTE — não modificar
│   └── common/
│       ├── config.py
│       ├── sheets.py        # aba NOTICIAS
│       └── claude.py        # evaluate_relevance + generate_linkedin_post
├── agents/
├── docs/
├── tests/
├── Procfile                 # web: python -m src.clipping.bot
└── pyproject.toml
```

## Como rodar localmente
```bash
pip install -e ".[dev]"

# Coleta manual (sem gravar no Sheets)
python -m src.clipping.collect --dry-run

# Coleta real
python -m src.clipping.collect

# Publicação manual (sexta)
python -m src.clipping.publish

# Bot
python -m src.clipping.bot
```

## Status — checklist de funcionalidades
- [x] RSS fetch de 9 fontes (tech/financial/marketing)
- [x] Claude Haiku avalia relevância (score 1-10 + motivo)
- [x] Gravação no Sheets NOTICIAS com categoria e score_ia
- [x] Score final: (score_humano×2 + score_ia) / 3; exclui se score_humano=0
- [x] Claude Sonnet gera post LinkedIn com seções template
- [x] Post enviado via Telegram com botões clipping:approve / clipping:reject
- [x] LinkedIn API POST /v2/ugcPosts (opcional)
- [x] `/add <url> <categoria>` para entrada manual
- [ ] Score humano via Telegram (nota 1-5 por artigo)
- [ ] Renovação automática do LinkedIn token

## Google Sheets
Sheet ID: `1OpRpvkgBsckdrTrKbRPA_ajcqLu9dryCH-pE8Bj_KMM` — aba `NOTICIAS`

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| data | date | Data do artigo |
| titulo | str | Título |
| link | str | URL do artigo |
| categoria | str | tech/financial/marketing |
| score_ia | int | 1-10 |
| motivo | str | Justificativa do Claude |
| score_humano | int | 0-5 (0 = não avaliado) |
| status | str | pendente/publicado/rejeitado |
| origem | str | URL do feed RSS |

## Score final
```python
(score_humano × 2 + score_ia) / 3
# score_humano == 0 → excluído do pool semanal
```

## LinkedIn Token
Expira em 60 dias. Renovar manualmente via LinkedIn Developer Portal.
Atualizar `PC_LINKEDIN_ACCESS_TOKEN` no GitHub Secrets e no Railway.

## GitHub Actions — crons (secrets prefixo `PC_`)
| Workflow | Cron | Comando |
|----------|------|---------|
| `collect.yml` | `0 11 * * 1-5` (8h BRT dias úteis) | `python -m src.clipping.collect` |
| `publish.yml` | `0 11 * * 5` (8h BRT sexta) | `python -m src.clipping.publish` |

## Agentes disponíveis
- `agents/PRODUCT_OWNER.md` — fluxos 1/2, user stories, fontes RSS
- `agents/ARCHITECT.md` — fluxo de dados, score final, decisões
- `agents/BACKEND.md` — especificação de cada módulo, RSS_FEEDS dict
- `agents/SECURITY.md` — LinkedIn token, aprovação obrigatória, logs
- `agents/QA.md` — casos de teste score_final, evaluate_relevance, --dry-run
- `agents/DEVOPS.md` — GH Actions, Railway, renovação LinkedIn token

## Regras para contribuição
- Nunca hardcodar credenciais — sempre via env vars
- `src/bot/clipping_bot.py` é pré-existente — não modificar sem intenção explícita
- Publicação no LinkedIn SEMPRE via aprovação Telegram — nunca automático
- `logging.getLogger(__name__)` + `logger.exception()` em todo módulo
- LinkedIn token expirado não deve travar o bot — graceful fallback para instrução manual
