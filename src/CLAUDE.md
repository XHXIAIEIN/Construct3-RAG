# `src/` Directory

Runtime source for the HTTP service, offline Direct Lookup, optional semantic
retrieval, and the ingestion pipeline.

## Dependency Direction

Transport code maps HTTP data into application commands. Application workflows
depend on domain data and injected ports. Lookup, retrieval, vector, ingestion,
and observability are implementation packages behind those boundaries.

Keep Direct Lookup independent of semantic retrieval, vector models, Qdrant,
and ingestion. Compatibility modules may re-export canonical implementations,
but canonical packages must not import their legacy `rag/` facades.

## Top-level Modules

| File | Purpose |
|------|---------|
| `api.py` | Thin FastAPI composition root and compatibility exports |
| `config.py` | Environment-backed runtime paths and feature settings |
| `collection_registry.py` | Typed loader and validation for collection metadata |
| `collections.json` | Canonical collection registry data |
| `collections.py` | Compatibility constants and routes derived from the typed registry |
| `schema_layout.py` | Shared schema locale/layout validation and path selection |

## Packages

### `interfaces/http/`

The HTTP boundary. `models.py` owns Pydantic request/response DTOs and transport
validation. `presenters.py` maps requests to application commands and application
outcomes back to HTTP responses. `playground.html` is the debug UI served at
`/playground`. Transport types do not belong in domain or lookup code.

### `application/`

Use-case orchestration and ports:

| File | Purpose |
|------|---------|
| `models.py` | Transport-independent commands, executions, outcomes, and `SearchStage` |
| `ports.py` | Lookup and semantic provider protocols/adapters |
| `search.py` | Canonical search workflow and exact cross-source deduplication |
| `health.py` | Readiness aggregation |

`SearchWorkflow.execute(SearchCommand)` follows five stable stages:

1. `initialize` — normalize inputs and validate the command
2. `lookup` — run offline Direct Lookup
3. `semantic` — optionally run semantic retrieval
4. `deduplicate` — remove only exact cross-source duplicates
5. `respond` — build the transport-independent outcome

Validation is an `initialize` substep, not a sixth `SearchStage`. Keep
`SearchWorkflow.run()` only as the compatibility HTTP wrapper around the
canonical `execute()` workflow.

### `domain/`

Stable transport-independent lookup and retrieval dataclasses. Domain modules
must not load data, models, Qdrant, or FastAPI routes. `domain/api.py` is a
legacy re-export of the canonical DTOs in `interfaces/http/models.py`.

### `lookup/`

Canonical offline Direct Lookup implementation:

| File | Purpose |
|------|---------|
| `service.py` | `LookupEngine` composition and lookup lifecycle |
| `handlers.py` | Intent-specific execution handlers |
| `formatting.py` | Pure result formatting helpers |
| `intent.py` | Deterministic query classification |
| `schema_index.py` | Plugin, behavior, ACE, and schema metadata index |
| `scripting_index.py` | Scripting API index |
| `term_index.py` | Curated terminology index built through public schema contracts |
| `examples_index.py` | Example lookup and public fallback-tag queries |
| `indexes.py` | Compatibility re-exports only |

Indexes expose public loading and query contracts. Callers must not inspect
another index's private fields.

### `retrieval/`

Canonical semantic retrieval implementation:

| File | Purpose |
|------|---------|
| `semantic.py` | `HybridRetriever`, Qdrant search/health, and optional reranking |
| `policy.py` | Query budgets, context tiers, and weighted RRF policies |
| `identity.py` | Stable result identities and exact deduplication |

### `vector/`

Canonical reusable vector adapters. `embedding.py` owns `EmbeddingModel` and
`sparse.py` owns `BM25Vectorizer`. Ingestion and retrieval import from this
package; `ingest/embedding.py` and `ingest/sparse.py` are compatibility exports.

### `ingest/`

CDN fetch/export, Markdown/SDK/schema/example parsing, vector-document building,
and Qdrant publication. `models.py` owns normalized parser records,
`contracts.py` owns vector documents/modes plus pipeline reports, and
`pipeline.py` owns the explicit publication workflow:

`prepare` → `validate` → `publish` → `verify`

Preparation materializes documents without Qdrant mutation. Validation must
complete before publication, and verification checks the published collection
counts. `indexer.py` remains the Qdrant adapter and command entry point.

### `observability/`

`trace.py` is the canonical request-local trace implementation shared by the
application, retrieval, and compatibility layers.

### `rag/`

Legacy import facades only:

| File | Purpose |
|------|---------|
| `lookup.py` | Configured compatibility facade for `lookup/` and legacy exports |
| `retriever.py` | Compatibility facade for `retrieval/semantic.py` and policies |
| `_trace.py` | Compatibility re-export of `observability/trace.py` |
| `messages.py` | Remaining lookup compatibility text templates |

New implementation code belongs in the canonical packages above. Do not add
business logic to these facades.

### `locale/`

Language-dependent retrieval resources. All language data belongs in one JSON
catalog where translations sit side by side under stable concept IDs. Python
only loads, validates, merges, and formats that data. Query grammar, narrow
aliases, and bilingual indexing hints do not belong in parser or transport
control flow.

Every maintained catalog resource must colocate four fields with its values:
`purpose`, `source`, `consumers`, and `tests`. A stable key without provenance
or a production consumer is invalid. `gold:*` sources name real case IDs from
`tests/fixtures/query_gold.jsonl`; `schema:*`, `contract:*`, and `curated:*`
sources must state the specific authority or rationale.

| File | Purpose |
|------|---------|
| `catalog.json` | Stable query/index concepts with colocated `en-US` and `zh-CN` values |
| `resources.py` | Generic catalog validation, merging, typed rules, and format adapters |

## Entry Points

- Lookup/search API: `python -m uvicorn src.api:app --port 8765`
- Data initialization: `python scripts/init.py`
- Vector index rebuild: `python -m src.ingest.indexer --rebuild`
