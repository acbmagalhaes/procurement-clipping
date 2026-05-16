# DEVOPS — procurement-clipping

## Deploy: Railway
- `Procfile`: `web: python -m src.clipping.bot`
- Bot roda em modo polling (não webhook)
- Variáveis de ambiente no painel Railway (sem prefixo PC_ em produção)

## GitHub Actions — workflows

### `.github/workflows/collect.yml` (Fluxo 1)
```yaml
on:
  schedule:
    - cron: '0 11 * * 1-5'   # 8h BRT, seg-sex
  workflow_dispatch:
jobs:
  collect:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -e .
      - run: python -m src.clipping.collect
    env:
      ANTHROPIC_API_KEY: ${{ secrets.PC_ANTHROPIC_API_KEY }}
      TELEGRAM_BOT_TOKEN: ${{ secrets.PC_TELEGRAM_BOT_TOKEN }}
      TELEGRAM_CHAT_ID: ${{ secrets.PC_TELEGRAM_CHAT_ID }}
      GOOGLE_SHEET_ID: ${{ secrets.PC_GOOGLE_SHEET_ID }}
      GOOGLE_SERVICE_ACCOUNT_JSON: ${{ secrets.PC_GOOGLE_SERVICE_ACCOUNT_JSON }}
```

### `.github/workflows/publish.yml` (Fluxo 2)
```yaml
on:
  schedule:
    - cron: '0 11 * * 5'   # 8h BRT, sexta-feira
  workflow_dispatch:
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -e .
      - run: python -m src.clipping.publish
    env:
      ANTHROPIC_API_KEY: ${{ secrets.PC_ANTHROPIC_API_KEY }}
      TELEGRAM_BOT_TOKEN: ${{ secrets.PC_TELEGRAM_BOT_TOKEN }}
      TELEGRAM_CHAT_ID: ${{ secrets.PC_TELEGRAM_CHAT_ID }}
      GOOGLE_SHEET_ID: ${{ secrets.PC_GOOGLE_SHEET_ID }}
      GOOGLE_SERVICE_ACCOUNT_JSON: ${{ secrets.PC_GOOGLE_SERVICE_ACCOUNT_JSON }}
      LINKEDIN_ACCESS_TOKEN: ${{ secrets.PC_LINKEDIN_ACCESS_TOKEN }}
      LINKEDIN_AUTHOR_URN: ${{ secrets.PC_LINKEDIN_AUTHOR_URN }}
```

## Secrets do GitHub (prefixo `PC_`)
```
PC_ANTHROPIC_API_KEY
PC_TELEGRAM_BOT_TOKEN
PC_TELEGRAM_CHAT_ID
PC_GOOGLE_SHEET_ID
PC_GOOGLE_SERVICE_ACCOUNT_JSON
PC_LINKEDIN_ACCESS_TOKEN      [opcional]
PC_LINKEDIN_AUTHOR_URN        [opcional]
```

## Dependências no pyproject.toml
```toml
dependencies = [
    "anthropic>=0.40.0",
    "python-telegram-bot>=21.0",
    "gspread>=6.0.0",
    "google-auth>=2.29.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "feedparser>=6.0.0",
    "aiohttp>=3.9.0",
]
```

## Monitoramento
- Falhas de cron → email automático GitHub
- Se nenhum artigo com score ≥ 6 no dia → collect.py loga warning (não falha o workflow)
- publish.py sem artigos suficientes → envia mensagem de aviso no Telegram (não publica)

## LinkedIn Token — alerta de expiração
Token OAuth expira em 60 dias. Renovar manualmente:
1. Gerar novo token no LinkedIn Developer Portal
2. Atualizar `PC_LINKEDIN_ACCESS_TOKEN` nos GitHub Secrets
3. Atualizar variável no Railway

## Checklist de release
- [ ] `.env` no `.gitignore`
- [ ] Todos os PC_* secrets configurados no GitHub
- [ ] Railway com variáveis sem prefixo PC_
- [ ] collect.yml com `1-5` no cron (só dias úteis)
- [ ] publish.yml com `* * 5` no cron (só sextas)
- [ ] `workflow_dispatch` ativado para teste manual
- [ ] `src/bot/clipping_bot.py` preservado no repo
