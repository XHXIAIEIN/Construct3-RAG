# Query Understanding Stage-Two Semantic Evaluation

Date: 2026-08-08 to 2026-08-09
Schema: Construct 3 r495
Status: complete; dev and the single authorized heldout evaluation finished

## Decision

The default product boundary remains unchanged: `LITE_MODE=true` and Direct
Lookup stay the deterministic default. Full semantic retrieval remains an
explicit opt-in.

On the frozen r495 benchmark, the real CrossEncoder reranker is the strongest
full-mode strategy. It improves nDCG@10 from 0.277774 to 0.343207 on dev and
from 0.326824 to 0.469668 on heldout relative to raw fanout. It is not suitable
as the default path yet: warm p95 was 1,667.92 ms on dev and 812.64 ms on
heldout, the full model stack used roughly 18.5 GB allocated VRAM and peaked
near 19.8 GB, and every strategy returned noise for all four negative-only
queries.

Standalone cross-collection weighted RRF is rejected. It regressed nDCG@10
against fanout on both dev (0.179955 versus 0.277774) and heldout (0.270646
versus 0.326824). Raw fanout was also not a stable independent win: it slightly
improved dev over the limited collection set but regressed on heldout while
roughly doubling warm p95 latency.

## Safety and evidence boundary

- The repository started at commit
  `bc66955ac27436f5955007a0c7eab90bdf8acbcc` with 44 pre-existing tracked
  changes. No reset, clean, commit, or broad formatting was performed. At final
  validation the dirty worktree had 46 tracked and 20 untracked entries,
  including this stage's files; it is not represented as clean.
- The repository-local `qdrant_storage/` directory was empty. The distinct,
  unmounted Docker volume `qdrant_storage` was 12.74 GB with zero links. It was
  never mounted, read, modified, pruned, deleted, or rebuilt.
- All live work used the isolated container and volume
  `construct3-rag-stage2-r495-80564481`, bound to `127.0.0.1:6334`.
- The evaluator ran real Qdrant queries and real CUDA embedding/reranking.
  Mock tests are used only for evaluator and production contract coverage.
- The core heldout set was opened once under the frozen protocol. API fixes and
  probes occurred afterward and did not trigger a second heldout run or any
  heldout-driven parameter change.
- QueryExpander, Semantic Chain, HyDE, CollectionRouter, Lookup Tier 2/3, and
  Ollama classification remain outside this experiment.

## Frozen identities

| Component | Immutable identity |
|---|---|
| Direct gold | 72 rows, SHA-256 `80564481e0688dae7de48327aab0289a2a74eada3b28c0fa6f183c5b7ecaf3de` |
| Semantic gold | 57 rows (38 dev / 19 heldout; 4 negative-only), SHA-256 `683a0ef0dd5a5aa50174568e66b395c691abf3dcfe442fb091ea4cbb965819be` |
| Locked protocol | SHA-256 `3b944e61b7cff9ec72a2dc24dba4725a5b60e8e40510f2aa43f658280a73d188` |
| Heldout-open protocol | SHA-256 `440a430d4fc1baaf388c3ae19daf79305928f30ea701d83773069f531ee1b85d` |
| Schema index | r495 `_index.json`, SHA-256 `f4ff84ee1b12368690fe11ec3c9afb1aa4c42b3cd03f8e98b314d848691e9dea` |
| Schema tree | 375 canonical files, manifest `2320b546e5ab08e3860f311a12858d439860fa4236abcae04da0c150503a651c`; 376 including `.exported`, `0d66be1b95704ba3baeb027161e209366fd59c340d125df82d6dc11c8732729d` |
| Embedding | local Qwen3-Embedding-4B C3 merge; 5,120 dimensions; `model.safetensors` `b3228bde2685dabbb60e1afb50d942399db67891d91a0928326d7189b70b8c8c`; ten-file manifest `ccb0c1600665495e0f33287ebcafd9f0ea5345e8e0de874d2dd11da354d87954` |
| Reranker | `BAAI/bge-reranker-v2-m3` revision `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`; 13-file manifest `b9d5357d1a1228ff00e06cd3c66789943e7ba107b0d47a62bb1d491873245490` |
| BM25 | 20,589 terms, average document length 23.01113, SHA-256 `2081dfcbc06a5bb0dbb2c54334187269a13da0b4efdbe5fc4d98e7cf38961546` |
| Qdrant | 1.17.0, commit `4ab6d2ee0f6c718667e553b1055f3e944fef025f`, image digest `sha256:f1c7272cdac52b38c1a0e89313922d940ba50afd90d593a1605dbbc214e66ffb` |
| Frozen index | 11 collections / 45,070 points; payload manifest `31ed2fd6530306ae67660463048071e71f6fc7b3aa15010fbb1e0a47c9a4b090`; file SHA-256 `c59754ebd278cd579e72f56e3500b0c64f30afe8d78d132425c66b00d9103e39` |

The embedding runtime dimension is 5,120, not the older 2,560 comment: the
SentenceTransformer pooling module concatenates mean-token and last-token
pooling. The repository wrapper does not explicitly normalize embeddings;
Qdrant uses cosine distance. Evaluation used CPython 3.12.10, PyTorch
2.10.0+cu128, and an RTX 5090 D v2. The shell's default Python 3.14 environment
has CPU-only PyTorch and was not used for model execution.

## Gold and index construction

Two independent, source-only adjudication rounds froze the semantic fixture
before retrieval output was opened. All 133 unique judged stable IDs resolved
against the final index; unresolved disagreements and missing judged IDs were
both zero. The four no-positive-answer cases are represented explicitly by an
empty relevance set rather than invented expected documents.

Two source-coverage defects were fixed before the isolated rebuild:

- event-example IDs now include the complete event path, preventing distinct
  nested events from overwriting each other;
- substantive Markdown introduction text now produces a stable `root` chunk,
  instead of becoming unsearchable whenever the same file also has H2 sections.

The isolated rebuild took 777.236 seconds. Every collection was green with a
named 5,120-dimensional Cosine dense vector and a named sparse vector:

| Collection | Points |
|---|---:|
| `c3_ace` | 3,017 |
| `c3_addon_sdk` | 327 |
| `c3_behaviors` | 189 |
| `c3_effects` | 89 |
| `c3_examples` | 13,129 |
| `c3_guide` | 147 |
| `c3_interface` | 174 |
| `c3_plugins` | 492 |
| `c3_project` | 177 |
| `c3_scripting` | 351 |
| `c3_terms` | 26,978 |
| **Total** | **45,070** |

The pre-heldout, post-heldout, and post-API manifests are byte-identical. This
proves that evaluation and API probes did not mutate collection contents or
schema.

## Comparison contract

The core benchmark compares four frozen strategies on one cached candidate
batch per query:

1. `limited`: `plugins`, `ace`, and `examples`, merged by raw score.
2. `fanout`: the frozen ten-collection semantic fanout, merged by raw score.
3. `rrf`: the same fanout candidates fused with
   `sum(1 / (round(60 / weight) + one_based_rank))`; examples weight 0.6,
   terms 0.5, and the other collections 1.0.
4. `rerank`: the same RRF candidate pool with the real CrossEncoder applied to
   the frozen top-20 window.

Each query is encoded once for dense and once for sparse retrieval. Qdrant's
within-collection dense/sparse `Fusion.RRF` is constant across all strategies;
the tested weighted RRF is the separate cross-collection stage.

The benchmark deliberately disables adaptive thresholding and diversity
injection, then applies exact rebuild-stable-ID deduplication, tail backfill,
and a hard top-10 budget. These controls isolate fusion quality and are not a
claim that the historical production `auto` path behaved identically. Lookup
hit/miss/bypass and post-lookup projections are recorded, but the primary
numbers below are semantic-pre-lookup metrics over positive cases.

## Results

| Split | Strategy | nDCG@10 | Recall@10 | Hit@5 | MRR | Warm p95 |
|---|---|---:|---:|---:|---:|---:|
| dev | limited | 0.253809 | 0.290278 | 0.5556 | 0.363426 | 152.61 ms |
| dev | fanout | 0.277774 | 0.344444 | 0.5000 | 0.390421 | 358.52 ms |
| dev | RRF | 0.179955 | 0.313426 | 0.4167 | 0.173578 | 358.74 ms |
| dev | rerank | **0.343207** | **0.382870** | **0.6389** | **0.488272** | 1,667.92 ms |
| heldout | limited | 0.358220 | 0.451961 | 0.5294 | 0.345588 | 180.72 ms |
| heldout | fanout | 0.326824 | 0.471569 | 0.4706 | 0.325000 | 368.75 ms |
| heldout | RRF | 0.270646 | 0.332353 | 0.5294 | 0.299020 | 369.05 ms |
| heldout | rerank | **0.469668** | **0.513725** | **0.8235** | **0.593137** | 812.64 ms |

All final strategy runs had zero query, collection, filter, contract, and
final-budget errors.

Direct rerank-versus-fanout paired analysis is mixed but positive in aggregate:

| Split | Improved / regressed / tied | Mean nDCG@10 delta | Mean Recall@10 delta | Mean MRR delta |
|---|---:|---:|---:|---:|
| dev | 16 / 9 / 13 | +0.061989 | +0.036404 | +0.092701 |
| heldout | 10 / 2 / 7 | +0.127808 | +0.037719 | +0.239912 |

The two heldout regressions against fanout were
`semantic-filter-effects-pixel-en-49` and
`semantic-workflow-leaderboard-en-29`. Three heldout cases still had zero
rerank nDCG: events-versus-script, colloquial Array save, and Addon SDK
TypeScript setup. The TypeScript case scored zero under all four strategies,
and all three unfiltered Addon SDK dev cases also scored zero. Therefore the
Addon SDK collection is available for explicit filtering but is not added to
default fanout.

Every strategy returned ten results for each of the four negative-only gold
queries. This is a real no-result/noise weakness and blocks default semantic
enablement. Limited heldout also had one forbidden-result violation on
`semantic-legacy-animation-editor-en-05`, where an animation action appeared
for an editor-location question.

Heldout infrastructure history is preserved accurately. The first attempt
failed before query 1 with a CUDA `cudaGetDeviceCount` invalid-argument error
and produced no report. Retry 1 failed its Qdrant preflight with WinError 10061;
`semantic-heldout-all.json` has `queries=[]` and is not a quality report. Only
`semantic-heldout-all-final.json` executed the 19 heldout queries, and heldout
was not run again.

## Evidence-backed production fixes

The pre-fix full API probe captured six concrete defects: named-vector plugin
search returned empty; explicit `addon_sdk` raised HTTP 500; standalone
`section_types` was silently ignored; effective result budgets were exceeded;
example slugs were duplicated; and the same lookup/semantic ACE survived
deduplication.

The minimal production changes were:

- use exact stable identities for ACEs, Markdown sections, examples, effects,
  terms, and Addon SDK documents across fusion and post-rerank deduplication;
  payloads without enough identity fields remain unique rather than being
  wrongly merged by source or text;
- query the named dense vector, use exact canonical plugin filtering, and make
  section filters mandatory;
- make `addon_sdk` explicitly searchable without adding it to the default
  fanout;
- rerank only the top-20 window, append the untouched tail, exact-deduplicate,
  backfill, and hard-cap the effective budget;
- keep diversity within the same collection namespace, forbid duplicate
  injection, and enforce the final cap;
- cache a confirmed Qdrant outage for two seconds so Direct Lookup survives
  while repeated semantic fallbacks fail fast, then permit recovery probing.

The weighted-RRF arithmetic was not tuned from heldout. The production change
is identity correctness: one stable ID contributes at most once per list, and
distinct stable documents no longer collapse through an overly broad key.

## Real API and degradation probes

| Checkpoint | Result |
|---|---|
| Baseline full | Six reproduced contract defects, including one HTTP 500 |
| Final healthy full | 12/12 probes passed; health `healthy`, Qdrant true, 11 collections, 45,070 documents |
| Recovery full | 12/12 passed after Qdrant recovery |
| Post-degradation full | 12/12 passed, proving semantic recovery |
| Degraded | Health `unavailable`, Qdrant false; Direct hit survived; lookup miss and semantic-only request fabricated no results |
| Final LITE | 5/5 probes passed; health `lite`, Qdrant false, schema ready, zero semantic sections, RSS 122,200,064 bytes |

Before the outage cache, the three degraded requests each took about 21
seconds. With the two-second confirmed-outage TTL their recorded client times
were 2.901 ms, 2.010 ms, and 1.232 ms. This optimization does not turn an
outage into a normal empty result: `/health` remains explicitly unavailable in
full mode, while the LITE service reports its separate lookup-only state.

At final validation the LITE Playground was served at
`http://127.0.0.1:8765/playground` with HTTP 200. Its single 25,427-character
inline script passed `node --check`; a live HTTP search for
`Sprite 有哪些 actions` returned the Sprite lookup with 16 actions and no
semantic section. The in-app Browser surface exposed no browser instance, so
visual rendering and click interaction could not be honestly verified; this
is recorded as an environment limitation rather than a browser pass.

## Final validation

- CPython 3.12.10: `python -m pytest -q` — **192 passed**, three third-party
  deprecation warnings.
- `python tests/eval_lookup.py` — **22/22 passed**.
- `python -m compileall -q src scripts tests` — passed.
- Direct quality, current strategy — **72/72 passed**, 19/19 correct semantic
  fallbacks, zero duplicate or forbidden violations; literal control 71/72.
- `git diff --check` — passed; only line-ending warnings were emitted.
- Playground HTTP/JavaScript fallback — passed; in-app visual browser check
  unavailable as described above.

The machine-readable final command, hash, runtime, worktree, and browser-status
record is `.cache/query-quality/stage-two/final-validation.json`.

## Primary artifacts

| Artifact | SHA-256 |
|---|---|
| `.cache/query-quality/stage-two/semantic-dev-all.json` | `b668da5c3c8b56095df99502f1169662c8147b02a4307cbc24539e0cba346d83` |
| `.cache/query-quality/stage-two/semantic-heldout-all-final.json` | `29008ab916f0cf57e1bfb2fe5fd59ff092a68f010896bf5f98b2466afdf9baa3` |
| `.cache/query-quality/stage-two/index-manifest.json` | `c59754ebd278cd579e72f56e3500b0c64f30afe8d78d132425c66b00d9103e39` |
| `.cache/query-quality/stage-two/index-manifest-post-heldout-final.json` | `c59754ebd278cd579e72f56e3500b0c64f30afe8d78d132425c66b00d9103e39` |
| `.cache/query-quality/stage-two/index-manifest-post-api-final.json` | `c59754ebd278cd579e72f56e3500b0c64f30afe8d78d132425c66b00d9103e39` |
| `.cache/query-quality/stage-two/api-full-probes-before.json` | `f1251b366d7945775e439fe49c44c7b02accdb9071693594b73886dba93eb168` |
| `.cache/query-quality/stage-two/api-full-probes-final.json` | `72ba3d5f77e3c9d01223a7997245dc4a8be8cbb32f7aa8464fa0b6968df2f247` |
| `.cache/query-quality/stage-two/api-full-probes-post-degradation.json` | `ddba1f3ffcca66fa865cfa3ab1f4cf14ca3fa0995558d7eee26fcde37f52441b` |
| `.cache/query-quality/stage-two/api-degraded-probes-optimized.json` | `9f66d93427d0eedb632f071c10ce19e0ebf108d36eede676f25a11b07fd4211c` |
| `.cache/query-quality/stage-two/api-lite-probes-final.json` | `1c5e7d75c78319d68343dd634a3f05e5be759b4f67fddeae333439cd770e42b8` |
| `.cache/query-quality/stage-two/api-runtime-audit.json` | `8ee80e4b7f6973f5c8c8f23aff753b08fef7677df217bdb5e510e3111902f102` |
| `.cache/query-quality/stage-two/direct-quality-final.json` | `5916459604d647688db15666f39920adce777bfa136d5195c41e0f1afa78bb2f` |

The isolated Qdrant container and the final LITE API process remain running for
local inspection. Neither is attached to the historical volume.
