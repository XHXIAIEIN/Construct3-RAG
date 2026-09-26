# Architecture

## Product boundary

Construct3-RAG is a versioned, bilingual Construct 3 reference dataset first.
The HTTP service is an optional access layer over that data, and Direct Lookup
is all it does: deterministic, offline, with no model and no database behind it.

The `construct3-project` skill under `skills/` is outside this layout. Its
scripts import the standard library and each other, read `data/c3-schemas/`
directly, and run from a copy inside a game project with neither `src/` nor
the service. Its rules are in `skills/AGENTS.md`.

The project follows four dependency rules:

1. Data contracts do not load files, configuration, models, or services.
2. Application workflows depend on typed ports, never adapter internals.
3. No import and no query reaches the network or loads a model.
4. Each type has one import path; there are no re-export modules.

## Source layout

```text
src/
  api.py                         FastAPI composition root
  interfaces/http/
    models.py                    Pydantic request/response contracts
    presenters.py                Search/health outcome -> HTTP DTO mapping
    playground.html              Debug UI served at /playground
  application/
    models.py                    SearchCommand, execution state, outcome, stages
    ports.py                     Lookup Protocol
    search.py                    Search SOP orchestration
    health.py                    Typed health aggregation
  domain/
    lookup.py                    Lookup intent/match/result records
  lookup/
    service.py                   Canonical deterministic LookupEngine
    intent.py                    Conservative query classification
    handlers.py                  Intent -> typed match execution
    formatting.py                Compatibility context rendering
    schema_index.py              Bilingual Schema repository
    schema_layout.py             Typed Schema manifest and snapshot validation
    term_index.py                Translation-term index
    examples_index.py            Example metadata index
    scripting_index.py           Script API index
  ingest/
    c3_fetcher.py                CDN fetch, cache, schema/example/lang export
    common_aces.py               Shared world-object ACEs from common_aces.json
  locale/
    catalog.json                 Query vocabulary, grammar, and aliases per locale
    resources.py                 Catalog validation, merging, and format adapters
  settings/__init__.py           Immutable, grouped settings loader
```

HTTP contracts are imported from `src.interfaces.http`, the lookup from
`src.lookup`.

`src.settings.load_settings()` accepts an explicit environment mapping and
repository root, returning a frozen tree of path, Schema, and runtime groups.
Every field has a runtime reader. It reads no `.env` file and probes no
external service; the schema version is the one `data/c3-schemas/_index.json`
records.

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
    |                              |
    |                              v
    |                         lookup/service
    v                              |
domain/* <-------------------------+

Explicit maintenance path:

scripts/init.py -----> ingest/c3_fetcher.py -----> data/
```

Static boundary tests reject `lookup -> rag` and `application -> ingest`, keep
the module graph acyclic, and check that importing the service loads no model
or vector package.

## Search SOP

`SearchWorkflow` carries one `SearchCommand` through three stable stages:

| Stage | Responsibility | Data in state |
|---|---|---|
| `initialize` | Detect language and validate the query and language hint | command, language |
| `lookup` | Run deterministic structured lookup | `LookupResponse` |
| `respond` | Freeze `SearchOutcome`; the HTTP presenter maps it to DTOs | typed outcome |

Validation is part of initialization rather than a fourth public stage. The
HTTP model rejects a field or a mode it does not have instead of ignoring it;
a blank query or an unknown language hint is rejected before the lookup engine
is built.

```text
SearchRequest (Pydantic)
    -> SearchCommand (frozen dataclass)
    -> SearchExecution (request-local mutable state)
    -> SearchOutcome (transport-independent result)
    -> SearchResponse (Pydantic presenter output)
```

Debug state never lives in Pydantic private attributes or temporary response
dictionaries.

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
schema path; `LookupEngine` and `SchemaIndex` have no default.

Direct Lookup is deliberately conservative:

- a hit requires non-empty structured matches;
- exact entity spans win over substring guesses;
- tutorial, comparison, concept, and solution requests are declined: the
  response carries no `lookup` section, and reading the manual or the examples
  is the caller's;
- directed aliases are scoped, single-hop, and deterministic;
- `_common` ACEs are searched only for compatible World-like objects;
- examples, terms, script APIs, properties, and ACEs retain typed identities.

The four repositories expose public loading/iteration/search methods. Callers
do not inspect another repository's private dictionaries.

## Schema snapshot contract

`schema_layout.py` validates `_index.json` into `SchemaManifest`. A usable
snapshot must declare `en-US` and `zh-CN`, contain non-empty plugin, behavior,
and effect sections, and provide a parseable bilingual JSON file for every
manifest entry. Each locale directory also carries an `_index.json` with
display names; it must list exactly the manifest's ids, and
`schema_index.py` reads it to match effect names in queries. The runtime
reads the committed dataset, or the directory `C3_SCHEMA_DIR` names. A refresh
replaces `data/` itself, so the cache is never read at query time.

No ordinary import or query refreshes the CDN. `scripts/init.py` fetches,
exports into the cache, and replaces the `data/` directories; the update
workflow runs the same script.
