# tests/ Directory

No external services required (no Qdrant, no GPU).

## Test Files

| File | Content | Cases |
|------|---------|-------|
| `test_lookup.py` | Query routing + lookup engine | 61 |
| `test_api.py` | API endpoint behavior (mocked) | 14 |
| `test_api_models.py` | Pydantic model validation | 7 |
| `test_schema_parser_cdn.py` | CDN schema parsing | 6 |
| `test_examples_parser_cdn.py` | CDN examples parsing | 2 |
| `test_c3_fetcher.py` | CDN fetcher | 10 |
| `test_query_expander.py` | Query expansion | 30 |
| `test_retriever.py` | Vector retriever (mocked) | 13 |
| `test_semantic_chain.py` | Semantic chain routing | 22 |
| `test_examples_parser.py` | Examples parser | 7 |

## Evaluation

| File | Purpose | Usage |
|------|---------|-------|
| `eval_lookup.py` | Lookup quality regression tests (17 cases) | `python tests/eval_lookup.py` |
| `playground.html` | Interactive API test UI | Served at `/playground` |

## Commands

```bash
python -m pytest tests/ -v              # all unit tests
python tests/eval_lookup.py             # lookup quality check
python tests/eval_lookup.py -v          # verbose: show matches
python tests/eval_lookup.py -k collision  # filter by keyword
```

## Conventions

- File naming: `test_<module_name>.py`
- Tests run without Docker or GPU
- `eval_lookup.py` is not a pytest file — run directly
