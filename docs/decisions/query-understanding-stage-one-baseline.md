# Query Understanding Stage-One Baseline

Date: 2026-08-08
Schema: Construct 3 r495
Fixture: `tests/fixtures/query_gold.jsonl`
Runner: `tests/eval_query_quality.py`

This report freezes the product-quality baseline established before the first
production behavior change, then records the narrower offline product boundary
implemented from that evidence. It is not a Qdrant quality claim: both runner
strategies execute Direct Lookup only and interpret a miss as a semantic
fallback without running semantic retrieval.

## Reproducibility and data identity

The pre-change report was written before modifying production lookup logic,
using the initial adjudication snapshot:

```bash
python tests/eval_query_quality.py --strategy all --split all \
  --output .cache/query-quality/pre-change-r495.json
```

That exact 72-line fixture is preserved at
`.cache/query-quality/query_gold-pre-review.jsonl` with SHA-256
`b64e6751156c0413c267cfbf1173c5ef9541d411e068a3a5901e5459ddbfaf7b`.
An independent second review then strengthened 24 list/property/entity/example
judgments without changing the queries, splits, route labels, or family quotas.
The final tracked fixture has SHA-256
`80564481e0688dae7de48327aab0289a2a74eada3b28c0fa6f183c5b7ecaf3de`.

The final reviewed stage-one report is reproduced with:

```bash
python tests/eval_query_quality.py --strategy all --split all \
  --output .cache/query-quality/post-change-r495.json
```

For an exact pre/post comparison under the original adjudication snapshot, run:

```bash
python tests/eval_query_quality.py --strategy all --split all \
  --fixture .cache/query-quality/query_gold-pre-review.jsonl \
  --output .cache/query-quality/post-change-r495-pre-review-gold.json
```

Every report records:

- its exact fixture path and SHA-256;
- selected schema version and resolved directory;
- route, intent, entity, ordered stable IDs, ranking judgments, expansion
  attribution, cold/warm latency, and repeat stability for every query;
- `qdrant=false`, `embedding_model=false`, `ollama=false`, and `network=false`.

The run resolved `.cache/c3-cdn/r495/schemas`. It and the current repository
`data/c3-schemas` snapshot each contain 375 JSON files and had the same aggregate
content SHA-256,
`b56321979f54705cbd68ce6b72a8982a242e74274908741abbecee600066a70c`.
This identity check does not make untracked repository data part of clean HEAD;
the working-tree status remains part of the handoff.

## Gold-set structure and adjudication

The first fixture has 72 JSONL records, 48 development and 24 held-out. Every
record includes the required query metadata, routing and intent expectations,
entity judgment, stable required/forbidden/alternative results, rank gate,
critical flag, r495 evidence path, rationale, and split.

| Family | Count |
|---|---:|
| Explicit ACE lists | 8 |
| ACE details and parameters | 6 |
| Property lists | 5 |
| Entity/plugin/behavior ambiguity | 6 |
| Unambiguous ACE topics | 8 |
| Ambiguous verbs | 14 |
| Explicit term translation | 5 |
| Translation negative cases | 4 |
| Tutorial/comparison/concept/solution fallback | 6 |
| Unknown/long/oral fallback edges | 4 |
| Exact scripting APIs | 3 |
| Examples and effects | 3 |

Language style tags comprise 32 Chinese, 20 English, 16 mixed, and 4
identifier-neutral queries; locale fields are 48 `zh-CN` and 24 `en-US`.
The split is now frozen for future work, but it is not a blind generalization
claim for this stage: stage-one diagnosis and remediation inspected the full
72-query baseline. Subsequent tuning should use only `dev` and open `heldout`
after policy changes are fixed.
The five required critical queries are present and pass under the stage-one
current strategy: `Array 保存`, `中文教程怎么做`,
`怎么在数组中查找特定数字`, `Sprite 有哪些 action`, and
`如何实现存档系统`.

Result judgments use four-part canonical keys such as
`plugins|arr|expression|indexof`, never a bare ACE ID. `_common` stays the
source identity for shared World ACEs. Scripting keys are checked against both
autocomplete data and declarations; examples and effects use their committed
metadata/schema IDs. A recursive validation pass resolved all 117 referenced
result specs against r495 and found all 79 non-null evidence-path entries. The
19 expected lookup misses received a second independent route review, with
particular attention to ambiguous verbs and semantic-only effects. The same
review replaced Schema-first-item assertions with three representative keys and
complete result-count gates for list/property/entity-list cases. Example
judgments use metadata-backed alternative groups instead of filename order.

`膨胀特效有哪些参数` is explicitly a stage-one boundary decision, not a claim
that r495 lacks a structured answer: the Bulge schema contains `radius` and
`scale`, and deterministic Effect Lookup should be reconsidered next.

## Pre-change current versus literal

`current` was the then-production Direct Lookup. `literal` kept entity parsing,
jieba, schema, script, and example indexes but disabled `ACE_SYNONYMS` and
`ACE_CATEGORY_EXPAND` in the evaluation process.

| Metric | Pre current | Pre literal |
|---|---:|---:|
| Fully passing queries | 25/72 | 26/72 |
| Critical queries | 2/5 | 3/5 |
| Route accuracy | 79.17% | 80.56% |
| Intent accuracy | 59.72% | 61.11% |
| Entity accuracy | 76.39% | 76.39% |
| Hit@1 / Hit@3 / Hit@5 | 30.19% / 37.74% / 41.51% | 33.96% / 39.62% / 41.51% |
| MRR | 0.355 | 0.380 |
| nDCG@5 | 0.359 | 0.378 |
| False Direct Lookup | 47.37% (9/19) | 42.11% (8/19) |
| Correct fallback | 52.63% (10/19) | 57.89% (11/19) |
| Forbidden-result violations | 4.17% | 2.78% |
| Context-only “hits” | 9 | 9 |
| Duplicate result rate | 0% | 0% |
| Warm mean / p95 | 0.356 / 0.689 ms | 0.340 / 0.680 ms |
| Warm repeat stability | 100% | 100% |
| Expansion mean / p95 / max | 2.36 / 21 / 54 | 0 / 0 / 0 |

Literal improved routing, ranking, and false-direct behavior without adding a
dependency. This was the evidence to remove broad expansion before attempting a
more complex query layer.

On the same original fixture, the final implementation reaches 72/72 for
current and 71/72 for literal; current has 100% route/intent/entity accuracy,
zero false directs, 100% correct fallback, and no context-only hits. Thus the
behavior delta is directly comparable even though the final tracked fixture was
subsequently strengthened.

## Stage-one current versus literal

After the boundary correction, `literal` additionally disables the remaining
directed aliases. `current` retains only a scoped one-hop
`world.action.show-to-visible` rule.

| Metric | Post current | Post literal |
|---|---:|---:|
| Fully passing queries | 72/72 | 71/72 |
| Critical queries | 5/5 | 5/5 |
| Route / intent / entity accuracy | 100% / 100% / 100% | 98.61% / 98.61% / 100% |
| Hit@1 / Hit@3 / Hit@5 | 62.26% / 66.04% / 66.04% | 60.38% / 64.15% / 64.15% |
| MRR | 0.991 | 0.972 |
| nDCG@5 | 0.823 | 0.804 |
| False Direct Lookup | 0% (0/19) | 0% (0/19) |
| Correct fallback | 100% (19/19) | 100% (19/19) |
| Forbidden-result violations | 0% | 0% |
| Context-only “hits” | 0 | 0 |
| Duplicate result rate | 0% | 0% |
| Warm mean / p95 | 0.107 / 0.541 ms | 0.111 / 0.593 ms |
| Warm repeat stability | 100% | 100% |
| Expansion mean / max | 0.014 / 1 | 0 / 0 |

The strict Hit@K definition requires every representative key for a case to be
inside K. Complete-list cases deliberately sample the beginning, middle, and
end of lists containing up to 83 items, so they can pass their evidence-based
full-list `max_rank` and count gates while failing Hit@5. This makes the lower
reviewed Hit@K/nDCG values an honest completeness/ranking distinction, not a
regression from the pre-review scores.

The one literal failure is `精灵显示`: it intentionally cannot bridge the
user verb “显示” to r495 `_common` action “设置可见性”. Current adds exactly one
term under one source/type scope and returns
`plugins|_common|action|set-visible`. The rule is observed once in the full run,
never cascades, and reports its stable rule ID. Its exact-topic guard prevents
the more specific `Text 显示中文文本` query from gaining unrelated visibility
results. This is the measured justification for retaining it.

The post-change first-pass maximum still reflects lazy jieba initialization;
warm results are the comparable per-query latency. Engine construction remained
about 65–69 ms and both strategies were route/intent/order stable on every repeat.

## Product boundary changes

1. `LITE_MODE=true` is the configuration default. Normal setup explicitly
   launches lookup-only; `scripts/setup.py --full` explicitly passes
   `LITE_MODE=false` after full prerequisites are prepared.
   Normal setup uses an existing local Schema and only `--refresh-data`,
   `--version`, or `--full` accesses the Construct CDN.
2. A Direct Lookup hit requires structured matches. Empty translation results
   and context-only formatting fall back and cannot suppress semantic results.
3. Translation and example lookup now return stable structured matches.
4. Lookup/semantic deduplication compares exact four-part ACE identities.
   Unrelated semantic ACEs and plugin overview documents remain.
5. Translation grammar is anchored to explicit phrases; tutorial,
   localization, and English-error negative cases fall back.
6. Entity parsing uses longest exact schema spans and identifier boundaries.
   Unknown `QuantumSprite` cannot resolve to Sprite, and `File system` cannot
   collapse to System.
7. Topic lookup requires structural ACE-name evidence, ranks candidates
   globally, restricts `_common` to World-like plugins, and preserves the true
   source collection/entity.
8. Broad undirected synonyms, chained groups, description-only matches, and
   whole-category additions are no longer default behavior.
9. Scripting lookup accepts exact qualified or standalone identifiers, avoiding
   natural-language false directs while preserving the committed API index.
10. Effects remain semantic-only, but versioned effect-name parsing records the
    entity on fallback.
11. Importing the minimal lookup package no longer imports the Qdrant-backed
    Retriever as a side effect; the historical package export is lazy.
12. Semantic-only API filters bypass Direct Lookup instead of being silently
    ignored, and the production Playground/OpenAPI documentation render the
    actual nested response contract.

## Test requirements corrected

The historical evaluator and unit tests had encoded implementation mechanisms
as requirements. Assertions that required collision/overlap synonym closure,
animation category-wide stop/start results, or a whole collision category were
replaced with stable must/forbidden/rank product outcomes. API tests no longer
assume default `auto` constructs the Retriever; semantic orchestration is tested
only with explicit full mode. Context-only translations/examples were changed
to require actual structured identities. List/property tests now assert breadth
and representative identities rather than a Schema-first-item Top1. The directed
display alias has a negative test preventing specific text queries from being
expanded. `tests/eval_lookup.py` remains a clearly labeled historical bare-ID
diagnostic, not the product gold set.

## Removed, retained, and deferred modules

Removed as a separate dead-code cleanup after production call-graph review:

- QueryExpander and its isolated tests/config/locale expansion table;
- Semantic Chain, HyDE, CollectionRouter, and isolated tests;
- Lookup embedding intent templates and Ollama classification branches;
- their unused prompt plus `ollama`/`openai` full requirements.

Retained:

- deterministic Schema, term, scripting, and in-memory example indexes;
- optional `HybridRetriever`, Qdrant collections, current weighted RRF and
  reranker implementation, because the full API still has a real opt-in path.

Deferred unchanged because Qdrant was not running:

- fixed multi-collection fan-out and collection defaults;
- weighted RRF and CrossEncoder reranking;
- addon SDK routing/indexing behavior.

## Final validation record

- `python -m pytest -q`: 160 passed; three warnings are third-party
  `jieba/pkg_resources` and FAISS SWIG deprecations.
- final reviewed `current`/`literal` quality run: 72/72 and 71/72, with a full
  per-query JSON report at `.cache/query-quality/post-change-r495.json`;
- `python tests/eval_lookup.py -v`: 22/22 historical diagnostics passed;
- `python -m compileall -q src scripts tests`: passed;
- production Playground inline JavaScript syntax check: passed;
- `git diff --check`: passed; Git only reported existing LF-to-CRLF notices;
- `scripts/setup.py --help`, local-schema reporting, and setup boundary tests:
  passed; ordinary setup made no CDN request in the test contract;
- Direct API probe used r495 from `.cache/c3-cdn/r495/schemas`,
  `LITE_MODE=true`, no Retriever construction, no embedding, no Qdrant, and no
  network. The five required critical queries routed as adjudicated; translation
  returned seven structured matches and the Tween example query returned five;
- TCP probing found `127.0.0.1:6333` unreachable. No live Qdrant index, semantic
  retrieval quality, multi-collection fan-out, RRF, reranker, or addon SDK route
  was validated in this stage.

## Required live semantic experiment

Start one Qdrant instance and use the same index snapshot, schema version,
fixture, and candidate budget. Compare in order:

1. a single or small evidence-selected collection baseline;
2. current fixed multi-collection fan-out;
3. fan-out plus weighted RRF;
4. fan-out/RRF plus Reranker.

Report the same per-query stable results and rank metrics, plus timeouts,
collection misses, model/device, warm/cold latency, and deployment cost. Do not
rewrite multi-collection routing or promote the addon SDK collection before this
experiment demonstrates a reproducible benefit.
