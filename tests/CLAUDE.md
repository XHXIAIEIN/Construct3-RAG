# `tests/` Directory

The pytest suite is offline by default: it requires neither Qdrant nor a GPU.
Live semantic evaluation is a separate workflow and must identify the exact
endpoint, collection, model, and frozen gold set used.

## Test Files

### Runtime and Module Boundaries

| File | Content |
|------|---------|
| `test_api.py` | Mocked endpoint behavior and application workflow integration |
| `test_api_models.py` | HTTP DTO validation and presenter mappings |
| `test_module_boundaries.py` | Canonical import direction, public ports, trace ownership, and stable five-stage search SOP |
| `test_setup.py` | Runtime setup and configuration smoke contracts |

`SearchStage` has exactly five stable values: `initialize`, `lookup`,
`semantic`, `deduplicate`, and `respond`. Request validation occurs inside
`initialize`; tests must not introduce a separate validation stage.

### Lookup and Retrieval

| File | Content |
|------|---------|
| `test_lookup.py` | Query routing, four indexes, handlers, and result formatting |
| `test_lookup_boundaries.py` | Legacy facade identity, canonical dependency direction, and public index contracts |
| `test_retriever.py` | Semantic retrieval, policies, health, and vector behavior with mocked backends |
| `test_locale.py` | Multilingual catalog layout, provenance, and derived rule contracts |

### Ingestion and Registry

| File | Content |
|------|---------|
| `test_ingest_contracts.py` | Vector mode/document validation and pipeline report contracts |
| `test_ingest_pipeline.py` | `prepare → validate → publish → verify` ordering and mutation boundary |
| `test_collection_registry.py` | Typed JSON registry validation and compatibility exports |
| `test_schema_layout.py` | Exported schema layout/path selection |
| `test_schema_parser_cdn.py` | CDN schema parsing |
| `test_examples_parser_cdn.py` | CDN examples parsing |
| `test_c3_fetcher.py` | CDN fetcher |
| `test_event_parser.py` | Event/script document parsing |
| `test_examples_parser.py` | Example parsing and metadata |
| `test_markdown_parser.py` | Manual Markdown parsing |

### Semantic Evaluation Infrastructure

| File | Content |
|------|---------|
| `test_semantic_eval.py` | Frozen split handling, stable IDs, metrics, and report contracts |
| `semantic_eval/` | Reusable semantic evaluation models, metrics, CLI, and live adapter |

## Evaluation

| File | Purpose |
|------|---------|
| `fixtures/query_gold.jsonl` | 72-query product gold set with stable IDs and evidence |
| `eval_query_quality.py` | Real ranked current/literal Direct Lookup quality runner with JSON diagnostics |
| `fixtures/semantic_gold.jsonl` | Frozen development/held-out semantic evaluation cases |
| `eval_semantic_quality.py` | Optional live semantic evaluation entry point |
| `eval_lookup.py` | Historical bare-ID compatibility diagnostic; not a product-quality gold test |

The product Direct Lookup quality command is:

```bash
python tests/eval_query_quality.py --strategy all --split all --output query-quality.json
```

Use its per-query JSON output to inspect route, intent, entity, ordering,
required/forbidden results, expansion source, ranking, and latency. Do not treat
`eval_lookup.py` as a substitute for this runner. Infrastructure failures in a
live semantic run invalidate the run; they are not quality scores.

## Commands

```bash
python -m pytest tests/ -v
python -m pytest tests/test_module_boundaries.py tests/test_lookup_boundaries.py -v
python -m pytest tests/test_ingest_contracts.py tests/test_ingest_pipeline.py tests/test_collection_registry.py -v
python tests/eval_query_quality.py --strategy all --split all --output query-quality.json
python tests/eval_lookup.py -v
```

## Conventions

- Name unit-test files `test_<module_name>.py`.
- Keep pytest deterministic and independent of Docker, Qdrant, and GPU state.
- Assert public contracts and facade identity instead of private implementation
  fields.
- Keep ingestion preparation and validation side-effect free; publication is
  the first stage allowed to mutate Qdrant.
- `eval_lookup.py` and both quality runners are scripts, not pytest files.
