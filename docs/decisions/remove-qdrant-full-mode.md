# The Qdrant Full Mode Is Removed

Date: 2026-09-22
Schema: Construct 3 r495.2; the retrieval numbers are those of the frozen
r495 index of `query-understanding-stage-two-semantic-evaluation.md`

## Problem

The service had two modes. The default answered exact questions from the
committed schemas, offline. The full mode added semantic retrieval over the
schemas, the manual and the example projects, and asked the user for Docker
with Qdrant, an embedding model, a reranker, up to three sibling clones and an
index build. The maintainer's call of this date: the project no longer asks anyone
for Docker or a model, and vector retrieval, if it is wanted again, gets a
repository of its own.

Task: someone who clones this repository reads `data/` or starts the lookup
service, and nothing in the code, the configuration, the tests or the docs
points at a mode that needs more. The default path never called the full mode:
`LITE_MODE=true` returned before the retriever was built.

## Evidence

What the full mode cost, from the stage-two record of 2026-08-09: about
18.5 GB of allocated VRAM for the evaluated stack, 777 s to build the
45 070-point index, warm p95 of 813 to 1668 ms with the reranker. Every
strategy returned ten results for each of the four negative-only queries,
which is why that record kept it out of the default.

What it bought for the question this project exists for, which ACE to use.
The stage-two reports were re-read on 2026-09-22 without running anything. Of
the 57 semantic gold rows, 20 carry an ACE-level label of grade 2 or more
(15 dev, 5 heldout; 12 in Chinese). Best rank of a gold ACE in the top ten:

| Ranking | @1 | @3 | @5 | @10 |
|---------|----|----|----|-----|
| The `ace` collection's own candidates | 11 | 13 | 16 | 18 |
| limited (plugins, ace, examples) | 6 | 11 | 13 | 15 |
| fanout (ten collections) | 3 | 5 | 7 | 10 |
| fanout, weighted RRF, reranker: the configured full mode | 4 | 6 | 9 | 9 |

The first row was not a strategy of that run; it is read from the recorded
candidate batch, so this is a post-hoc slice, the heldout rows are in it and
nothing was tuned. Against the configured full mode it is better on 7 queries
and worse on none at rank 1 (two-sided sign test p = 0.016), and 9 to none at
rank 10 (p = 0.004). The strategy that stage two found strongest by nDCG over
mixed documents is the weakest at naming the ACE: a terse ACE entry loses to
manual prose in one mixed ranking.

The reranker's score does not say whether an answer exists. As a gate on its
top-1 score, the AUC for "a relevant result is in the top ten" is 0.565, and
withholding all four negative-only queries costs 22 of 40 answered queries.
Results it scores 0.8 to 1.0 are judged relevant 36% of the time (unjudged
counts as not relevant); `QuantumSprite 有哪些 actions`, a plugin that does not
exist, scores 0.669.

What is left without vectors. BM25 over all 3017 ACEs, built from the
committed schemas with the standard library alone (CJK as character bigrams,
k1 = 1.2, b = 0.75, first attempt, nothing tuned), puts a gold addon in the
top five for 20 of 20 and a gold ACE at rank 1 for 3 of 20. Finding the addon
is a lexical problem; choosing the ACE inside it is not.

Who does that choosing. The consumers of this data are LLM agents. An
unmodified local model (Qwen/Qwen3-8B, next-token logits read over the option
letters, one forward pass, no generation, prompts fixed before the single full
run) picks a gold ACE from the same ten recorded candidates for 17 of 20,
averaged over three option orders, where the recorded order gives 11 and
`bge-reranker-v2-m3` on the same candidates 9. A reader that is handed a closed
list does this step better than the reranker did, and an agent is such a
reader. The same model says an answer exists for `QuantumSprite 有哪些 actions`:
the closed-world name check stays with deterministic code.

Size of what goes: 45 files and 10 780 lines deleted outright, before the
edits to what stays, and `src/requirements-full.txt` (qdrant-client,
sentence-transformers, FlagEmbedding, numpy, pandas, tqdm, beautifulsoup4,
lxml).

One known consumer of the HTTP API, the `construct3-copilot` plugin of the
Construct3-Copilot repository: its bridge sends `mode=semantic` for its
`search` subcommand and may add `plugin`, `top_k` and `collections`. Against
the default service those requests already returned nothing, or 422 when a
filter met `mode=lookup`. It reads `/health` only for `status` as a string.

The reports, scripts and outputs are kept outside the repository at
`.local/docs/evidence/query-quality/` on the evaluation machine. The two
reports hash to what the stage-two record states.

| File | SHA-256 |
|---|---|
| `stage-two/semantic-dev-all.json` | `b668da5c3c8b56095df99502f1169662c8147b02a4307cbc24539e0cba346d83` |
| `stage-two/semantic-heldout-all-final.json` | `29008ab916f0cf57e1bfb2fe5fd59ff092a68f010896bf5f98b2466afdf9baa3` |
| `ace-decision-reread/reread_stage_two_reports.txt` | `c82e96916bed738cd1fd6e5d2218436431597f65fa3c7130aef0f299086767af` |
| `ace-decision-reread/ace_lexical_baseline__bigram.txt` | `ae4a0a7684c91e08cf42cb63e38765c24a96058d1912fd92c94188e10e03f3c8` |
| `ace-decision-reread/logit_readout_experiment__qwen3-8b__all.txt` | `7afbab3db9d405ac179a571577c630d1be5e4fd10f1d1f71ca2b0e636bde93e9` |
| `ace-decision-reread/logit_readout_followup.txt` | `fbcac69ba06aa82b9871d617fd6a5511c5449ce9de3860c0240be2d05a4d1c3f` |

## Options

1. Keep the full mode. Nothing to do. The project keeps a tier that needs a
   GPU, that no default path calls, and whose configured strategy is the worst
   of four at the project's main question.
2. Keep Qdrant and shrink it to typed retrieval over the `ace` collection.
   The best retrieval measured here. It still asks for Docker, a model and an
   index build per release, to hand an agent ten candidates.
3. Replace vectors with a local model read as a classifier. 58 ms a pass and
   17 of 20, and still a 15 GiB model inside a project that promises to work
   from its committed files.
4. Remove it. The service is Direct Lookup; retrieval by vectors or by a model
   is a consumer of `data/` and lives in its own repository.

## Decision

Option 4.

- Gone: `src/qdrant/`; of `src/ingest/` everything but the CDN fetcher and the
  shared ACEs; `src/domain/retrieval.py`; `src/rag/retriever.py`; the `index`
  section of `src/locale/catalog.json`, which only fed vector text; the
  sibling-clone paths and the vector and feature settings with their
  environment variables (`LITE_MODE`,
  `QDRANT_*`, `EMBEDDING_MODEL`, `RERANKER_*`, `BM25_ENABLED`,
  `BGE_M3_NATIVE_SPARSE`, `CONTEXTUAL_CHUNKING_*`); `scripts/setup.py --full`
  and `--skip-index`; `src/requirements-full.txt`; the semantic evaluator,
  `tests/semantic_eval/`, `tests/eval_semantic_quality.py`,
  `tests/fixtures/semantic_gold.jsonl`, and the tests of the removed modules.
- `POST /search` changes, and breaks a caller that used the full mode. `mode`
  is `auto`, `lookup` or `list`; `auto` equals `lookup`. `top_k`,
  `collections`, `plugin`, `section_types` and `apply_threshold` are gone, and
  so are the `semantic` section and the semantic half of `debug`. The request
  model forbids unknown fields: a caller that sends a filter gets 422 and the
  field's name, not an unfiltered answer.
- `GET /health` is `status` (`ok` or `unavailable`), `schema_ready` and
  `message`.
- `SearchStage` is `initialize`, `lookup`, `respond`.
- Kept: the `semantic_fallback` route name inside the lookup, its gold set and
  its evaluator. It names the class of query Direct Lookup declines, and the
  72-row gold set pins 19 of them. The response to such a query has no
  `lookup` section, as the default service always answered it.
- The last commit that holds the removed code, the 57-row semantic gold set
  (SHA-256 `683a0ef0dd5a5aa50174568e66b395c691abf3dcfe442fb091ea4cbb965819be`)
  and its evaluator is `5f39cf72ca064949ea4dca29827a833605c16364`.

Not done, because this change only removes:

- A typed reason in the response for a declined query. An empty response does
  not tell an agent "unknown addon" from "needs reading".
- An entry to `lookup_ace.py` for "which addon has this", which the BM25
  result above supports and which needs the skill's own evaluation
  (`skills/AGENTS.md`).
- The Copilot bridge: `search` and `semantic` map to a mode that no longer
  exists, and its flags to fields that are rejected.

## Re-evaluate when

- A consumer that is not an LLM agent needs free-text "which ACE": that is the
  separate repository, starting from typed retrieval over ACEs only and the
  closed-list choice above, not from the mixed ranking removed here.
- Agents are seen picking the wrong addon with the offline tools: build the
  lexical proposer in the core tier and measure it on ACE-labelled queries,
  of which there are 20 today.
- A caller depends on a declined query being told apart from an empty lookup:
  add the typed reason, with `docs/guide/api-reference.md` and its tests.
