# Architecture

## Product boundary

Construct3-RAG is a versioned, bilingual Construct 3 reference dataset first.
The HTTP service is an optional access layer over that data. Direct Lookup is
the default offline search path; Qdrant, embeddings, sparse vectors, and
reranking are explicit full-mode capabilities.

The project follows four dependency rules:

1. Data contracts do not load files, configuration, models, or services.
2. Application workflows depend on typed ports, never adapter internals.
3. Network/model work is lazy and cannot run during a LITE import or lookup.
4. Historical import paths are facades only; canonical modules never depend on
   a compatibility facade.

## Source layout

```text
src/
  api.py                         FastAPI composition root and public re-exports
  interfaces/http/
    models.py                    Pydantic request/response contracts
    presenters.py                Search/health outcome -> HTTP DTO mapping
  application/
    models.py                    SearchCommand, execution state, outcome, stages
    ports.py                     Lookup and semantic Protocols
    search.py                    Search SOP orchestration
    health.py                    Typed health aggregation
  domain/
    lookup.py                    Lookup intent/match/result records
    retrieval.py                 SearchResult, preset, and health records
  lookup/
    service.py                   Canonical deterministic LookupEngine
    intent.py                    Conservative query classification
    handlers.py                  Intent -> typed match execution
    formatting.py                Compatibility context rendering
    schema_index.py              Bilingual Schema repository
    term_index.py                Translation-term index
    examples_index.py            Example metadata index
    scripting_index.py           Script API index
    indexes.py                   Legacy index re-exports only
  retrieval/
    semantic.py                  Optional Qdrant semantic adapter
    identity.py                  The single stable-identity implementation
    policy.py                    Pure budgets, tiers, dedup, and fusion policy
  vector/
    embedding.py                 Shared lazy dense/native-sparse model adapter
    sparse.py                    Shared deterministic BM25 adapter
  ingest/
    contracts.py                 VectorDocument, VectorMode, pipeline reports
    pipeline.py                  Prepare -> validate -> publish -> verify SOP
    qdrant_adapter.py            Canonical Qdrant publication adapter
    indexer.py                   Historical facade and compatibility CLI
    models.py                    Normalized ACE/effect parser records
    *_parser.py                  Source-specific parsing/building
  collection_registry.py        Typed loader for collections.json
  collections.json              Collection names, manual routes, taxonomy
  settings.py                   Immutable, grouped settings loader
  config.py                     Historical constant facade and dotenv boundary
  schema_layout.py              Typed Schema manifest and snapshot validation
  observability/trace.py        Optional request-local diagnostics
  rag/
    lookup.py                    Historical Lookup facade
    retriever.py                 Historical semantic facade
    _trace.py                    Historical trace facade
```

`src/domain/api.py`, `src/ingest/embedding.py`, and
`src/ingest/sparse.py` are also compatibility re-exports. New code imports
HTTP contracts from `src.interfaces.http`, vector adapters from `src.vector`,
and search implementations from `src.lookup` / `src.retrieval`.

`src.settings.load_settings()` accepts an explicit environment mapping and
repository root, returning frozen path, Schema, runtime, vector, feature, and
legacy-compatibility groups. It does not load dotenv or probe external
services. `src.config` is the only dotenv/constant compatibility boundary;
canonical composition may consume the typed settings tree instead.

## Dependency direction

```text
HTTP request
    |
    v
interfaces/http/models.py
    |
    v
api.py -------------- dependency construction only
    |
    v
application/search.py -----> application/ports.py
    |                              |             |
    |                              v             v
    |                         lookup/service  retrieval/semantic
    v                              |             |
domain/* <-------------------------+-------------+
    ^                                            |
    +---------------- retrieval pure policy <----+

Explicit maintenance path:

ingest/pipeline.py -----> ingest/contracts.py
          |                       ^
          +---- parsers ----------+
          |
          +---- qdrant_adapter.py -> vector/* -> Qdrant
```

Static boundary tests reject `lookup -> rag`, runtime `retrieval -> ingest`,
and application calls to private retriever members.

## Search SOP

`SearchWorkflow` carries one `SearchCommand` through five stable stages:

| Stage | Responsibility | Data in state |
|---|---|---|
| `initialize` | Detect language and validate query/filter combinations | command, language |
| `lookup` | Run deterministic structured lookup when the mode permits | `LookupResponse` |
| `semantic` | Use the optional semantic port when full mode permits | `list[SearchResult]` |
| `deduplicate` | Remove only exact identities already returned by lookup | domain results |
| `respond` | Freeze `SearchOutcome`; the HTTP presenter maps it to DTOs | typed outcome |

Validation is part of initialization rather than a sixth public stage. Unknown
collections, blank queries, invalid language hints, and semantic filters on
lookup/list modes are rejected before LITE or Qdrant availability can affect
the result.

```text
SearchRequest (Pydantic)
    -> SearchCommand (frozen dataclass)
    -> SearchExecution (request-local mutable state)
    -> SearchOutcome (transport-independent result)
    -> SearchResponse (Pydantic presenter output)
```

Internal stable IDs and debug state never live in Pydantic private attributes
or temporary response dictionaries. Semantic docs, terms, and examples have
concrete OpenAPI item models, including their context tier.

### Default and full modes

- `LITE_MODE=true` is the default. It can construct Lookup but never constructs
  Qdrant, an embedding model, BM25, or a reranker.
- Full mode probes Qdrant before loading the embedding model. A recent outage
  fast-fails and degrades to lookup-only behavior.
- `mode=auto` means Lookup plus semantic retrieval when full mode is enabled.
  It is not permission to download a model or fetch data implicitly.

## Direct Lookup SOP

```text
query
  -> IntentClassifier
  -> named handler (ACE list/detail/search, properties, term, example)
  -> LookupMatch records
  -> optional compatibility context renderer
  -> LookupResponse
```

The service is independent from runtime configuration. `src.api` injects the
selected Schema path; the historical `src.rag.lookup` facade supplies the same
default only for legacy callers.

Direct Lookup is deliberately conservative:

- a hit requires non-empty structured matches;
- exact entity spans win over substring guesses;
- tutorial, comparison, concept, and solution requests fall back;
- directed aliases are scoped, single-hop, and deterministic;
- `_common` ACEs are searched only for compatible World-like objects;
- examples, terms, script APIs, properties, and ACEs retain typed identities.

The four repositories expose public loading/iteration/search methods. Callers
do not inspect another repository's private dictionaries.

## Semantic retrieval SOP

`HybridRetriever` is the optional Qdrant adapter behind `SemanticSearchPort`:

1. Probe backend availability without loading the model.
2. Resolve an explicit plugin/section/collection route or fixed default fanout.
3. Query named dense vectors and, when configured, named sparse vectors.
4. Apply the existing weighted RRF and optional reranker policy.
5. Enforce exact identity deduplication, result budget, and diversity backfill.
6. Optionally apply the adaptive threshold.

The adapter exposes public collection-search methods; the application workflow
does not call `_search()` or read Qdrant state fields. Its historical
`src.rag.retriever` path is a re-export facade.

Weighted RRF and reranking remain optional, evidence-gated features. The
frozen semantic gold set, identified live index, quality metrics, and latency
must support any change to their default status.

## Identity contract

`src/retrieval/identity.py` is the only identity authority. Lookup and semantic
results use equivalent stable keys, including:

```text
ace|plugin|<plugin_id>|<ace_type>|<ace_id>
ace|behavior|<behavior_id>|<ace_type>|<ace_id>
examples|<slug>
terms|<plugin_id>|<ace_type>|<ace_id>
script_api|<class>|<method>
```

Unknown identities are preserved rather than deduplicated heuristically.

## Data maintenance SOP

The maintenance path is separate from request handling. It builds a complete,
validated `VectorDocument` set before the first Qdrant mutation:

```text
prepare -> validate -> publish -> verify
```

BM25 is fitted from exactly the final document text set, including contextual
text and example event/script enrichment. Collection layout comes from the
typed JSON registry. See [data-pipeline.md](data-pipeline.md) for the detailed
contracts and the current non-atomic, per-collection publication boundary.

## Schema snapshot contract

`schema_layout.py` validates `_index.json` into `SchemaManifest`. A usable
snapshot must declare `en-US` and `zh-CN`, contain non-empty plugin, behavior,
and effect sections, and provide a parseable bilingual JSON file for every
manifest entry. Each locale directory also carries an `_index.json` with
display names; it must list exactly the manifest's ids, and
`schema_index.py` reads it to match effect names in queries. Runtime
selection prefers a complete version-matched cache, then the bundled
dataset. Explicit path overrides remain explicit.

No ordinary import or query refreshes the CDN. Fetch/export is an initialization
or maintenance action.

## Compatibility policy

Compatibility facades preserve established imports while callers migrate:

| Historical path | Canonical path |
|---|---|
| `src.domain.api` | `src.interfaces.http.models` |
| `src.rag.lookup` | `src.lookup` |
| `src.rag.retriever` | `src.retrieval.semantic` and pure retrieval modules |
| `src.rag._trace` | `src.observability.trace` |
| `src.ingest.embedding` | `src.vector.embedding` |
| `src.ingest.sparse` | `src.vector.sparse` |
| `src.ingest.indexer.index_all_data` | `src.ingest.pipeline.run_index_pipeline` |
| `src.config` constants | `src.settings.AppSettings` |

Facades may bind legacy defaults or names, but canonical modules must not import
them. Compatibility is checked by object-identity and import-boundary tests.
