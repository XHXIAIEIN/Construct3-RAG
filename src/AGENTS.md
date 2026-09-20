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

Everything specific to the optional Qdrant stack — collection metadata, the
vector adapters, semantic retrieval, and the Qdrant publication adapter —
lives under `qdrant/`, so the whole optional path is one package: easy to
reason about, test, or remove as a unit. Ingestion parsers, Direct Lookup,
and the application/HTTP layers do not own any Qdrant-specific code.

## Rules

- Direct Lookup and the FastAPI service are optional over the committed
  data. The Qdrant stack (retrieval, multi-collection routing, reranker) is
  the optional full mode and stays only while a same-gold-set benchmark
  shows a gain over simple retrieval.
- Removed, and not to return without their own experiment and benchmark:
  QueryExpander, Lookup Tier 2/3, Semantic Chain/HyDE. Reasons in
  `docs/decisions/refactoring-audit.md`.
- Qdrant, embeddings, the reranker and any LLM are configured explicitly,
  detectable, switchable off, and fall back safely. An LLM result never
  overrides a high-confidence deterministic result.
- Look for the cause of a bad result in data quality, field weights, routing
  or product scope before adding keywords, prompts or a model layer. A new
  keyword, prompt or model starts from a failing case with a checkable
  expected result. Query-understanding changes start with the product
  direction review in
  `docs/decisions/query-understanding-refactor-requirements.md`, which owns
  the rules for expansion, synonyms, LLM checks and metrics.
- A public API change updates `interfaces/http/models.py`, the docs and the
  compatibility tests together. Internal structures promise no compatibility.
- Keep the `en-US` and `zh-CN` layout; `lookup/schema_layout.py` owns it.
- Checks: `/health` and `/search` must tell schema readiness apart from
  Qdrant status; a Qdrant or reranker check counts as live only when the
  service ran; a collection change is followed by a search for the old name.

## Top-level Modules

| File | Purpose |
|------|---------|
| `api.py` | Thin FastAPI composition root and compatibility exports |

## Packages

### `interfaces/http/`

The HTTP boundary. `models.py` owns Pydantic request/response DTOs and transport
validation. `presenters.py` maps requests to application commands and application
outcomes back to HTTP responses. `playground.html` is the debug UI served at
`/playground`: keep it plain and in the existing style, with no decorative
components. Transport types do not belong in domain or lookup code.

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
| `schema_layout.py` | Schema locale/layout validation and path selection, shared with `settings/` and `ingest/` |
| `scripting_index.py` | Scripting API index |
| `term_index.py` | Curated terminology index built through public schema contracts |
| `examples_index.py` | Example lookup and public fallback-tag queries |
| `indexes.py` | Compatibility re-exports only |

Indexes expose public loading and query contracts. Callers must not inspect
another index's private fields.

### `qdrant/`

Everything specific to the optional Qdrant vector-retrieval stack:

| File | Purpose |
|------|---------|
| `collection_registry.py` | Typed loader and validation for collection metadata |
| `collections.json` | Canonical collection registry data |
| `collections.py` | Compatibility constants and routes derived from the typed registry |
| `adapter.py` | Canonical Qdrant publication adapter (`Indexer`); `ingest/indexer.py` is the compatibility facade/CLI in front of it |
| `retrieval/semantic.py` | `HybridRetriever`, Qdrant search/health, and optional reranking |
| `retrieval/policy.py` | Query budgets, context tiers, and weighted RRF policies |
| `retrieval/identity.py` | Stable result identities and exact deduplication |
| `vector/embedding.py` | `EmbeddingModel` |
| `vector/sparse.py` | `BM25Vectorizer` |

`vector/` adapters are reusable: both `qdrant/adapter.py` (ingestion) and
`qdrant/retrieval/semantic.py` (runtime retrieval) import from it directly.
`ingest/embedding.py` and `ingest/sparse.py` stay in `ingest/` as
compatibility exports pointing at `qdrant/vector/`.

### `ingest/`

CDN fetch/export, Markdown/SDK/schema/example parsing, and vector-document
building. `models.py` owns normalized parser records, `contracts.py` owns
vector documents/modes plus pipeline reports, and `pipeline.py` owns the
explicit publication workflow:

`prepare` → `validate` → `publish` → `verify`

Preparation materializes documents without Qdrant mutation. Validation must
complete before publication, and verification checks the published collection
counts. Publication itself is `qdrant/adapter.py`; `indexer.py` remains the
compatibility facade and command entry point (`python -m src.ingest.indexer
--rebuild`).

`c3_fetcher.py` fetches the CDN into the cache and exports the schema,
example, language-pack, and ts-defs trees there; `export_to_data()` then
replaces the matching `data/` directories, which is what the runtime reads.
The shared world-object ACEs are
not on the CDN endpoints it reads; `common_aces.py` loads them from
`common_aces.json`, an extract of the editor bundle kept next to it, and
`export_schemas()` merges that entry like any plugin.

### `settings/`

`__init__.py` owns `load_settings()` and the immutable, grouped `AppSettings`
tree. It loads no dotenv file and probes nothing but the local schema
directory; every process entry point (`src.api`, each `scripts/*.py`) calls
`load_dotenv()` itself before calling `load_settings()`.

`settings/__init__.py` selects the schema directory through
`src.lookup.schema_layout.select_schema_dir`, so `settings` depends on that
one leaf of `lookup/`; nothing in `lookup/` depends back on `settings`.

### `observability/`

`trace.py` is the canonical request-local trace implementation shared by the
application, retrieval, and compatibility layers.

### `rag/`

Legacy import facades only:

| File | Purpose |
|------|---------|
| `lookup.py` | Configured compatibility facade for `lookup/` and legacy exports |
| `retriever.py` | Compatibility facade for `qdrant/retrieval/semantic.py` and policies |
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
