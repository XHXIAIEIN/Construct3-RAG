# Compatibility Facades and the Request Trace Are Removed

Date: 2026-09-26

## Problem

`src/` kept import paths from before the lookup was split out of `src/rag/`:
`src/rag/` (lookup, trace and message facades), `src/domain/api.py`,
`src/lookup/indexes.py` and re-exports in `src/api.py`. Only the tests and
`tests/eval_query_quality.py` imported them. Importing `src.rag.lookup` also
bound module-level defaults, a schema directory and a trace sink, so
`LookupEngine()` without arguments worked only after that import.

The request trace had no reader. `src.api` reset the event list per request,
but no response field returned it, and the `/search` path never imported the
facade that bound the sink, so the classifier's trace calls went to a no-op.
The playground's trace panel styles and the phase colours of the old
retrieval pipeline had no element that used them.

## Decision

- Each type has one import path: `src.lookup`, `src.domain.lookup`,
  `src.interfaces.http.models`.
- `LookupEngine` and `SchemaIndex` require the schema directory;
  `configure_lookup_defaults()` and `configure_schema_default()` are gone.
- `src/observability/`, the `trace` parameters and every `_trace()` call are
  gone; `logger.info` in the classifier stays.
- The evaluator binds its own alias table and passes it to `LookupEngine` as
  the directed-alias provider. Its report is unchanged: `current` 72/72,
  `literal` 71/72, before and after.
- The playground keeps only the confidence badge styles.

## Re-evaluate when

A caller needs to see how a query was classified: add a field to the response,
documented in `docs/guide/api-reference.md`, rather than a side channel.
