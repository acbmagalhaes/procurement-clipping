# PRD — procurement-clipping

## Visão
Transformar o Head of Procurement em uma referência no LinkedIn sobre tendências de supply chain, mercado financeiro e marketing B2B — com zero esforço de curadoria manual. Um post semanal de alto valor, gerado automaticamente e aprovado em 30 segundos.

## Problema
Profissionais de procurement têm pouco tempo para monitorar dezenas de fontes de notícias relevantes. O LinkedIn exige consistência de posts para construir marca pessoal. A combinação desses dois fatores (tempo escasso + necessidade de consistência) resulta em presença fraca no LinkedIn.

## Usuário
Um Head of Procurement que:
- Quer postar no LinkedIn toda semana sobre tendências do setor
- Não tem tempo para ler e curar notícias diariamente
- Quer aparecer como thought leader em procurement, supply chain e inovação

## Fluxos principais

### Fluxo 1 — Coleta diária (segunda a sexta, 8h BRT)
Fetch de 9 feeds RSS → Claude Haiku avalia relevância para procurement (score 1-10) → artigos relevantes (score ≥ 6) gravados no Sheets com categoria e motivo.

### Fluxo 2 — Post semanal (sexta, 8h BRT)
Busca artigos da semana com score final > 0 → Claude Sonnet seleciona os melhores por categoria e gera post LinkedIn → envia para Telegram com botões Aprovar/Rejeitar → se aprovado, publica via API (ou instrução manual).

## User Stories

### Épico 1 — Coleta inteligente
- **US-01**: Todo dia útil, artigos relevantes de 9 fontes RSS são avaliados e gravados no Sheets automaticamente.
- **US-02**: Cada artigo tem score de relevância (1-10) e motivo explicado pelo Claude, para eu entender por que foi selecionado.
- **US-03**: Posso adicionar links manualmente via `/add <url> <categoria>` no Telegram.

### Épico 2 — Post LinkedIn
- **US-04**: Toda sexta, recebo no Telegram um rascunho de post LinkedIn pronto para publicar.
- **US-05**: O post tem estrutura clara: abertura chamativa, resumo das notícias, pergunta de engajamento, hashtags.
- **US-06**: O post tem ≤3800 chars (limite LinkedIn).
- **US-07**: Ao clicar "Aprovar", o post é publicado no LinkedIn automaticamente (ou recebo o texto para copiar).

### Épico 3 — Controle de qualidade
- **US-08**: Artigos que eu não avaliou (score_humano=0) não aparecem no post semanal — só conteúdo validado.
- **US-09**: O score final considera minha avaliação com peso dobrado: `(score_humano×2 + score_ia) / 3`.
- **US-10**: Posso rejeitar um post e ele não é publicado; uma nova versão pode ser gerada.

## Roadmap

### v0.1 — MVP
- Coleta RSS automática (9 feeds)
- Haiku avalia relevância
- Post semanal via Sonnet
- Aprovação Telegram + LinkedIn API opcional

### v0.2 — Engajamento humano
- Score humano via Telegram (botões nota 1-5 por artigo)
- Histórico de posts publicados no Sheets

### v0.3 — Personalização
- Ajuste de template de post por preferência do usuário
- Categorias customizadas além de tech/financial/marketing

## Fontes RSS monitoradas

| Categoria | Feed |
|-----------|------|
| tech | Supply Chain Digital, Spend Matters, Procurement Magazine, The Procurement |
| financial | Valor Econômico, Bloomberg BN, Reuters Business |
| marketing | LinkedIn Marketing Blog, Content Marketing Institute |

## Métricas de sucesso
- **Cobertura**: ≥5 artigos relevantes por semana gravados no Sheets
- **Aprovação**: >60% dos posts gerados são aprovados sem edição
- **Consistência**: pelo menos 1 post publicado por mês no LinkedIn
- **Score quality**: artigos com score_ia ≥ 8 têm taxa de aprovação humana >80%
