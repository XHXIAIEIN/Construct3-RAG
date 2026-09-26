# `src/` Directory

Runtime source for the HTTP service, offline Direct Lookup, and the CDN
ingestion that writes `data/`.

## Dependency Direction

Transport code maps HTTP data into application commands. Application workflows
depend on domain data and injected ports. Lookup, ingestion, and observability
are implementation packages behind those boundaries.

Keep Direct Lookup independent of ingestion. Compatibility modules may
re-export canonical implementations, but canonical packages must not import
their legacy `rag/` facades.

## Rules

- Direct Lookup and the FastAPI service are optional, and the service is
  Direct Lookup only: no model, no database, no network during import or a
  query.
- Removed: the Qdrant full mode with its embeddings, reranker and vector
  ingestion (`docs/decisions/remove-qdrant-full-mode.md`); QueryExpander,
  Lookup Tier 2/3, Semantic Chain/HyDE (`docs/decisions/refactoring-audit.md`).
  Vector or model retrieval belongs in a repository of its own that reads
  `data/`; it does not return here.
- Bad result: check data quality, field weights, routing and product scope
  before adding keywords, prompts or a model layer. A new keyword, prompt or
  model starts from a failing case with a checkable expected result;
  query-understanding changes start with
  `docs/decisions/query-understanding-refactor-requirements.md`.
- Public API change: `interfaces/http/models.py`, docs and compatibility
  tests in one change. Internal structures promise no compatibility.
- Schema layout (`en-US`, `zh-CN`): `lookup/schema_layout.py` owns it.
- Checks: `/health` reports schema readiness; a change to `/search` is run
  against the live service, not only the test client.

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
| `ports.py` | Lookup provider protocol |
| `search.py` | Canonical search workflow |
| `health.py` | Schema readiness |

`SearchWorkflow.execute(SearchCommand)` follows three stable stages:

1. `initialize` — normalize inputs and validate the command
2. `lookup` — run offline Direct Lookup
3. `respond` — build the transport-independent outcome

Validation is an `initialize` substep, not a fourth `SearchStage`. Keep
`SearchWorkflow.run()` only as the compatibility HTTP wrapper around the
canonical `execute()` workflow.

### `domain/`

Stable transport-independent lookup dataclasses. Domain modules must not load
data or FastAPI routes. `domain/api.py` is a legacy re-export of the canonical
DTOs in `interfaces/http/models.py`.

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

### `ingest/`

CDN fetch and export.

`c3_fetcher.py` fetches the CDN into the cache and exports the schema,
example, language-pack, and ts-defs trees there; `export_to_data()` then
replaces the matching `data/` directories, which is what the runtime reads.
The shared world-object ACEs are
not on the CDN endpoints it reads; `common_aces.py` loads them from
`common_aces.json`, an extract of the editor bundle kept next to it, and
`export_schemas()` merges that entry like any plugin.

### `settings/`

`__init__.py` owns `load_settings()` and the immutable, grouped `AppSettings`
tree. It reads the process environment and nothing else but the version in
the schema directory's `_index.json`, which is the release the service
reports. There is no `.env` file and no version setting: a refresh fetches
the latest stable release unless `--version` names another.

`settings/__init__.py` reads that version through
`src.lookup.schema_layout.schema_version`, so `settings` depends on that
one leaf of `lookup/`; nothing in `lookup/` depends back on `settings`.

### `observability/`

`trace.py` is the canonical request-local trace implementation shared by the
application, retrieval, and compatibility layers.

### `rag/`

Legacy import facades only:

| File | Purpose |
|------|---------|
| `lookup.py` | Configured compatibility facade for `lookup/` and legacy exports |
| `_trace.py` | Compatibility re-export of `observability/trace.py` |
| `messages.py` | Remaining lookup compatibility text templates |

New implementation code belongs in the canonical packages above. Do not add
business logic to these facades.

### `locale/`

Language-dependent lookup resources. All language data belongs in one JSON
catalog where translations sit side by side under stable concept IDs. Python
only loads, validates, merges, and formats that data. Query grammar and narrow
aliases do not belong in parser or transport control flow.

Every maintained catalog resource must colocate four fields with its values:
`purpose`, `source`, `consumers`, and `tests`. A stable key without provenance
or a production consumer is invalid. `gold:*` sources name real case IDs from
`tests/fixtures/query_gold.jsonl`; `schema:*`, `contract:*`, and `curated:*`
sources must state the specific authority or rationale.

| File | Purpose |
|------|---------|
| `catalog.json` | Stable query concepts with colocated `en-US` and `zh-CN` values |
| `resources.py` | Generic catalog validation, merging, typed rules, and format adapters |

## Entry Points

- Lookup/search API: `python -m uvicorn src.api:app --port 8765`
- Data initialization: `python scripts/init.py`
