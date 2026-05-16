# QA — procurement-clipping

## Estrutura de testes
```
tests/
├── test_score_final.py        # unit: _score_final() com edge cases
├── test_evaluate_relevance.py # unit: parse resposta Claude Haiku
├── test_generate_post.py      # unit: post ≤3800 chars, seções presentes
├── test_sheets_mock.py        # integration: append_news, get_news_last_n_days
└── test_collect_dry_run.py    # integration: --dry-run não grava no Sheets
```

## Casos de teste prioritários

### `_score_final()` — lógica de score
| score_ia | score_humano | Esperado |
|---------|-------------|---------|
| 8 | 0 | 0.0 (excluído) |
| 8 | 5 | (5×2 + 8) / 3 = 6.0 |
| 6 | 3 | (3×2 + 6) / 3 = 4.0 |
| 10 | 5 | (5×2 + 10) / 3 = 6.67 |
| 1 | 1 | (1×2 + 1) / 3 = 1.0 |

### `evaluate_relevance()` — parse Claude Haiku
| Cenário | Esperado |
|---------|---------|
| Resposta JSON com lista | cada item tem score_ia (int 1-10) e motivo |
| Claude retorna markdown ```json``` | parse correto (strip backticks) |
| Artigo sobre procurement direto | score_ia ≥ 7 |
| Artigo genérico de tecnologia sem relação | score_ia ≤ 4 |
| Lista vazia de itens | retorna lista vazia sem exceção |

### `generate_linkedin_post()` — formato e tamanho
| Cenário | Esperado |
|---------|---------|
| Input normal (2 notícias/categoria) | `len(post) <= 3800` |
| Input com muitos artigos | ainda ≤ 3800 chars (Claude/split_message) |
| Seções presentes | ABERTURA + RESUMO_EXECUTIVO + PERGUNTA detectáveis |
| Hashtags de procurement | #procurement ou #compras no texto |

### `collect.py --dry-run`
- Deve printar artigos relevantes no stdout
- Não deve chamar `sheets.append_news()` (mock verifica que não foi chamado)

### `handle_link` (`/add` command)
| Entrada | Esperado |
|---------|---------|
| `/add https://example.com tech` | append_news chamado com link e categoria='tech' |
| `/add` sem argumentos | mensagem de uso no Telegram |
| Chat não autorizado | silencioso, sem ação |

## Nota sobre `src/bot/clipping_bot.py`
Arquivo pré-existente — não incluir nos testes novos. Se tiver testes legados, mantê-los.

## Como rodar
```bash
pytest tests/ -v
pytest tests/test_score_final.py -v  # apenas unit tests
```

## Critérios mínimos
- `_score_final(*, score_humano=0)` sempre retorna 0.0
- `generate_linkedin_post()` nunca retorna string >3800 chars
- `--dry-run` não tem efeitos colaterais no Sheets
- Todos os unit tests passam sem variáveis de ambiente reais (usar mocks)
