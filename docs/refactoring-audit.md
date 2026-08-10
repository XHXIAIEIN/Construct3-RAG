# Refactoring Audit

This document records structural findings that should survive individual code
changes. It distinguishes completed cleanup from work that still needs an
explicit design decision.

## Completed in the current refactor

- Repaired the data update contract. The exporter writes `en-US`/`zh-CN`, and
  automation now copies actual exported directories instead of the retired
  `en`/`zh` names.
- Restored repository-bundled bilingual r495 schemas so direct lookup and tests
  no longer depend on a developer-specific cache once these files are committed.
- Centralized schema layout validation, version selection, and counting in
  `src/schema_layout.py`.
- Removed a runtime CDN fetch from API lookup initialization. Committed data is
  usable offline; refreshing data is an explicit setup/init responsibility.
- Replaced the missing `data/examples_index.json` build artifact with an
  in-memory index over committed example metadata.
- Removed QueryExpander, Semantic Chain/HyDE/CollectionRouter, and Lookup Tier
  2/3 after production call-graph review confirmed they had no caller or
  dependency injection path. Their isolated shape tests, LLM-only dependencies,
  prompts, and configuration were removed in the same reviewable cleanup.
- Removed unused r466 plugin/behavior catalogs, stale collection counts, UI
  descriptions, event-generator validation strings, and obsolete LLM/UI config.
- Removed indexing jobs for retired `ace-reference.json`, scripting API, and
  property exports that had no data source or reachable orchestration path.
- Moved Chinese query bridges, stop words, prompts, and indexing hints into
  explicit `src/locale/` resources.
- Rewrote directory guides and public docs to match the current modules, data
  paths, workflow name, embedding default, and health response.

## Stage-zero query-system audit

The product-direction and historical-assumption review is recorded in
[`query-understanding-stage-zero-audit.md`](query-understanding-stage-zero-audit.md).
It traced the real `/search` path, compared current Direct Lookup with a literal
no-synonym/no-category-expansion baseline, audited the commit chains, and set a
72-query structured gold-set plan.

Decisions established by that review:

- Keep the versioned bilingual schema and narrow, explicit structured lookup as
  the product core.
- Simplify examples, scripting, and explicit translation lookup around real
  repository data and exact identifiers.
- Rewrite broad Direct Lookup classification and directional aliases; remove
  category-wide expansion from the default strategy.
- Remove QueryExpander, unused Lookup embedding/Ollama tiers, and Semantic
  Chain/HyDE in a separate reviewable change. They have no production caller.
- Treat Qdrant multi-collection fusion, weighted RRF, and CrossEncoder reranking
  as optional capabilities that require a current, reproducible comparison with
  a simpler retrieval baseline.
- Do not allow an empty or heuristic lookup section to suppress all semantic
  ACE results; target exact stable-ID deduplication.

No complex query module was deleted during the audit itself. Qdrant was not
running, so semantic-path implementation changes would have exceeded the
available evidence.

## Stage-one product baseline and boundary correction

[`query-understanding-stage-one-baseline.md`](query-understanding-stage-one-baseline.md)
records the 72-query r495 gold set, the pre-change current/literal reports, the
post-change comparison, evidence paths, and remaining experiment plan.

Implemented product decisions:

- lookup-only is the default; full semantic retrieval is explicitly enabled by
  `scripts/setup.py --full` / `LITE_MODE=false`;
- context-only or empty lookup formatting is not a hit, including zero-result
  translations;
- terms and examples now return structured stable identities;
- semantic ACE deduplication is exact per stable result key rather than removing
  every ACE and plugin overview after any lookup;
- translation grammar is explicit and anchored, so tutorial/localization/error
  sentences fall back;
- broad undirected synonym and whole-category expansion were removed; one
  directed, exact-topic, scoped, single-hop visibility alias remains with a
  stable rule ID;
- exact entity spans and globally ranked structural name matches prevent the
  `Array 保存` cascade, `_common` leakage, and unknown-plugin substring matches.

## SOP and module-boundary refactor

The structural split is now implemented while preserving the established
external import paths:

1. HTTP Pydantic contracts and presentation mapping live under
   `src/interfaces/http/`. `src/domain/` now contains transport-independent
   lookup, retrieval, and health records only; `src.domain.api` is a facade.
2. `SearchWorkflow` consumes typed `SearchCommand` and port Protocols. Its
   request state contains `LookupResponse` and `SearchResult`, not response DTOs,
   Pydantic private attributes, or `_type`/`_result_id` sentinel dictionaries.
3. Input validation runs before LITE/backend checks. Invalid collections can no
   longer become a misleading HTTP 200 merely because Qdrant is disabled.
4. Canonical Lookup lives under `src/lookup/`: service, handlers, formatting,
   intent classification, and four repositories are separate. `src.rag.lookup`
   is a small compatibility facade that injects historical defaults.
5. `src/retrieval/semantic.py` is the optional adapter; identity and ranking
   policy remain pure modules. Application code uses public port methods and
   never reads `_qdrant_available` or calls `_search()`.
6. Dense and sparse vector adapters live under `src/vector/`, shared by runtime
   retrieval and ingest without a runtime-to-maintenance dependency.
7. `VectorDocument`, `VectorMode`, and pipeline reports make the ingest boundary
   explicit. `index_all_data()` is a facade over the named
   prepare → validate → publish → verify workflow. The canonical Qdrant writer
   lives in `src.ingest.qdrant_adapter`, so orchestration no longer forms an
   import cycle with its historical `src.ingest.indexer` facade.
8. Collection routing/taxonomy moved to a validated JSON registry, and Schema
   selection now validates a typed bilingual manifest rather than accepting
   empty directories.
9. Configuration parsing moved into immutable grouped settings. `src.config`
   is now the explicit dotenv and historical-constant compatibility boundary;
   importing `src.settings` neither loads dotenv nor probes network/model
   services. Retired LLM/expander names remain facade-only for compatibility.
10. The uncalled `src/evaluation` module pointing at a missing RAGAS fixture was
   removed. Current query and semantic evaluation tools remain explicit under
   `tests/`.

Remaining boundaries and deliberate limits:

- Qdrant access, embedding/reranker lifecycle, and full-mode fusion still share
  `HybridRetriever`. They form one optional adapter today; split them further
  only for a concrete second lifecycle/backend or an independently testable
  product need.
- Pipeline preparation is all-or-nothing, but publication is still sequential
  per collection. It does not yet use temporary collections plus atomic alias
  swaps, so a mid-publish infrastructure failure requires a rerun.
- CDN export, vector normalization, and Lookup bilingual projection still have
  separate representations. Unify them only with golden output parity across
  committed Schema, Direct Lookup, and the frozen semantic corpus.
- Runtime Schema may use a version-matched cache while example lookup reads the
  bundled example dataset. A future dataset-snapshot manifest should make that
  cross-source version choice explicit.
- Lookup compatibility context remains a rendered English/Chinese string beside
  typed matches. Remove or version it only with an API contract decision.

## Language policy

- CDN-translated content stays in generated JSON.
- Query vocabulary, grammar, aliases, and indexing hints live in one
  `src/locale/catalog.json`, keyed by stable concepts with colocated locale
  values. Locale-neutral Python loads and validates it; language-independent
  rule metadata is not duplicated across locale files. Every resource records
  its purpose, provenance, production consumers, and regression tests; gold
  provenance is validated against the committed query fixture.
- API response fields remain language-neutral; localized values are returned as
  structured `en`/`zh` objects.
- Human-readable vector text may be bilingual, but its templates must not be
  embedded in parser or transport control flow.
- English and Chinese READMEs describe the same behavior; volatile counts come
  from `_index.json` rather than prose.

## Compatibility and experiments scheduled for later review

- The lookup context formatter still returns an English Markdown compatibility
  string alongside structured matches. Remove it only with an API version bump.
- `requirements-full.txt` still groups Qdrant, embedding, and reranking packages;
  extras or lock files would make the optional installation boundary clearer.
- Qdrant fixed multi-collection fan-out, weighted RRF, Reranker, and addon SDK
  routing remain unchanged until the same live index can compare limited/single
  collection, fixed fan-out, +RRF, and +Reranker on the gold set.
