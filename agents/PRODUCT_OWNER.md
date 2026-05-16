# PRODUCT_OWNER — procurement-clipping

## Papel
Representar o Head of Procurement que precisa de um briefing semanal de notícias relevantes sobre tecnologia de compras, tendências de mercado e marketing B2B — entregue como post LinkedIn pronto para publicar.

## Contexto do produto
- **Problema core**: profissional de procurement passa horas lendo notícias dispersas. Precisa de curadoria inteligente + post LinkedIn já formatado para fortalecer sua marca pessoal.
- **Solução**: (1) coleta diária de RSS de 9 fontes relevantes; (2) Claude Haiku avalia relevância de cada artigo; (3) sexta-feira: Claude Sonnet gera post LinkedIn baseado nas melhores notícias da semana; (4) aprovação via Telegram antes de publicar.
- **Usuário-alvo**: uma pessoa — Head of Procurement — que quer presença no LinkedIn sem esforço de curadoria.

## Fluxos principais

### Fluxo 1 — Daily collect (cron 11h, segunda a sexta)
1. Fetch de 9 feeds RSS (tech/financial/marketing)
2. Claude Haiku avalia relevância de cada artigo (score 1-10)
3. Artigos com score ≥ 6 gravados no Sheets com categoria e motivo
4. Artigos avaliados pelo usuário (score_humano via Telegram) têm peso dobrado

### Fluxo 2 — Weekly publish (cron 11h sexta)
1. Busca artigos dos últimos 7 dias com score final ≥ 6
2. Score final: `(score_humano × 2 + score_ia) / 3`; artigos com `score_humano == 0` excluídos
3. Claude Sonnet gera post LinkedIn com [ABERTURA]/[RESUMO_EXECUTIVO]/[PERGUNTA]/[HASHTAGS]
4. Envia para Telegram com botões "Aprovar / Rejeitar"
5. Se aprovado → LinkedIn API (`/v2/ugcPosts`) + Sheets status='publicado'

## User Stories priorizadas

### Must have
- **US-01**: Todo dia recebo no Sheets um log de notícias relevantes de procurement, com score e motivo.
- **US-02**: Toda sexta recebo no Telegram um post LinkedIn rascunhado para aprovar.
- **US-03**: Ao clicar "Aprovar", o post é publicado no LinkedIn automaticamente (ou instrução manual se sem API).

### Should have
- **US-04**: Posso enviar links manualmente via `/add <link> <categoria>` no Telegram para adicionar ao pool.
- **US-05**: Post LinkedIn tem ≤3800 chars e termina com pergunta + hashtags relevantes de procurement.

### Nice to have
- **US-06**: Score humano: posso dar nota 1-5 para artigos via Telegram para influenciar o ranking final.

## Critérios de aceitação

| US | Critério |
|----|---------|
| US-01 | Cron 11h grava ≥1 notícia/dia nos dias úteis; score_ia ≥ 6 para aparecer |
| US-02 | Post enviado toda sexta antes das 12h; formato com seções reconhecíveis |
| US-03 | LinkedIn API `POST /v2/ugcPosts` com `lifecycleState: PUBLISHED` |
| US-04 | `/add` grava no Sheets com status='manual' e categoria informada |
| US-05 | `len(post) <= 3800` verificado antes de enviar para Telegram |

## Sheet ID
`1OpRpvkgBsckdrTrKbRPA_ajcqLu9dryCH-pE8Bj_KMM` — aba `NOTICIAS`

## Fontes RSS
- **Tech** (4): Supply Chain Digital, Spend Matters, Procurement Magazine, The Procurement
- **Financial** (3): Valor Econômico, Bloomberg BN, Reuters Business
- **Marketing** (2): LinkedIn Marketing Blog, Content Marketing Institute
