# SECURITY — procurement-clipping

## Regras absolutas

### 1. Credenciais nunca no código
Vars críticas:
- `LINKEDIN_ACCESS_TOKEN` — acesso de escrita no perfil LinkedIn do usuário
- `ANTHROPIC_API_KEY` — custo financeiro se vazado
- `GOOGLE_SERVICE_ACCOUNT_JSON` — acesso ao Sheets corporativo

`.env` no `.gitignore`. `.env.example` com nomes mas sem valores.

### 2. Autorização do bot Telegram
```python
if str(update.effective_chat.id) != settings.TELEGRAM_CHAT_ID:
    return  # silencioso — não confirmar que bot existe
```
Válido tanto para CommandHandler `/add` quanto para CallbackQueryHandler `clipping:`.

### 3. LinkedIn OAuth Token
- `LINKEDIN_ACCESS_TOKEN` é um token OAuth 2.0 com validade de 60 dias
- Nunca logar o token (nem os primeiros caracteres)
- Renovação manual necessária a cada 60 dias — documentar no CLAUDE.md
- O `LINKEDIN_AUTHOR_URN` identifica o perfil — não é secret, mas não deve aparecer em logs públicos

### 4. Conteúdo publicado no LinkedIn
- O post gerado pelo Claude é enviado ao Telegram para **aprovação obrigatória** antes de publicar
- Nunca publicar automaticamente sem aprovação humana (nenhuma rota de publicação direta no collect.py ou publish.py)
- O callback `clipping:approve` é o único gatilho de publicação

### 5. RSS feeds externos
- Não há autenticação para os feeds RSS públicos
- Conteúdo de feeds não é tratado como confiável: usar apenas `title`, `link`, `published` dos itens
- Não executar nenhum JavaScript ou conteúdo dinâmico dos feeds

### 6. Logs
```python
# Certo
logger.info("[collect] %d artigos relevantes de '%s'", count, categoria)
# Errado
logger.info("[collect] Response LinkedIn API: %s", response_body)
```

## Checklist de PR
- [ ] `.env` não em `git diff --cached`
- [ ] `LINKEDIN_ACCESS_TOKEN` não logado
- [ ] `update.effective_chat.id` validado nos handlers
- [ ] Nenhuma rota de publicação automática sem callback de aprovação
- [ ] `.env.example` atualizado
- [ ] `src/bot/clipping_bot.py` não modificado (pré-existente)

## GitHub Actions secrets (prefixo `PC_`)
```
PC_ANTHROPIC_API_KEY
PC_TELEGRAM_BOT_TOKEN
PC_TELEGRAM_CHAT_ID
PC_GOOGLE_SHEET_ID
PC_GOOGLE_SERVICE_ACCOUNT_JSON
PC_LINKEDIN_ACCESS_TOKEN      [opcional]
PC_LINKEDIN_AUTHOR_URN        [opcional]
```

## Renovação do LinkedIn Token
O token expira em 60 dias. Processo:
1. Acessar LinkedIn Developer Portal
2. Gerar novo access token via OAuth 2.0 flow
3. Atualizar secret `PC_LINKEDIN_ACCESS_TOKEN` no GitHub e variável no Railway
