# The Service Is Direct Lookup Only

Date: 2026-09-22
Schema: Construct 3 r495.2

## Problem

The service had an optional full mode: semantic retrieval over the schemas,
the manual and the example projects, which asked for Docker with Qdrant, an
embedding model, a reranker, the sibling clones and an index build. The
default path never called it. The maintainer decided that the project asks
no one for Docker or a model.

## Evidence

Cost of the full mode on the frozen r495 index: about 18.5 GB of VRAM, 777 s
to build 45 070 points, warm p95 of 0.8 to 1.7 s with the reranker. Every
strategy returned ten results for each query that has no answer.

What it bought for the question this project exists for, which ACE to use.
On the 20 gold queries with an ACE-level label, the configured full mode
(fanout, weighted RRF, reranker) put a gold ACE first 4 times; ranking the
`ace` collection's own candidates did 11 times. Mixed ranking lets manual
prose beat a terse ACE entry.

The reranker's score does not say whether an answer exists: as a gate, its
AUC for "a relevant result is in the top ten" was 0.565, and a plugin that
does not exist scored 0.669.

Without vectors: BM25 over the committed ACEs puts a gold addon in the top
five for 20 of 20. Finding the addon is lexical; choosing the ACE inside it
is a reading task. An unmodified local 8B model given the same ten
candidates as a closed list picks a gold ACE for 17 of 20, the reranker 9.
The consumers of this data are LLM agents, which are such readers.

The runs are kept on the evaluation machine under
`.local/docs/evidence/query-quality/`.

Direct Lookup itself widened a topic word through undirected synonym groups
and added whole ACE categories to a hit. The groups chained into each other:
保存 grew to about 220 words, so `Array 保存` was answered with `Load`. With
both expansions turned off, the lookup declined that query. The audit is in
`docs/decisions/query-understanding-stage-zero-audit.md` and
`query-understanding-refactor-requirements.md` of commit
`8c71768425fcf32c77009a295d328f83e1510757`, the last that holds them.

## Options

1. Keep the full mode: a GPU tier no default path calls, and the weakest of
   the measured rankings at naming the ACE.
2. Shrink it to typed retrieval over the `ace` collection: still Docker, a
   model and an index build per release, to hand an agent ten candidates.
3. Replace vectors with a local model used as a classifier: a 15 GiB model
   in a project that promises to work from its committed files.
4. Remove it. Retrieval by vectors or by a model is a consumer of `data/` and
   lives in its own repository.

## Decision

Option 4.

- Removed: `src/qdrant/`, the vector ingestion and its parsers,
  `src/domain/retrieval.py`, `src/rag/retriever.py`, the vector settings and
  their environment variables, `scripts/setup.py --full`,
  `src/requirements-full.txt`, the semantic evaluator and its gold set.
  The last commit that holds them is
  `5f39cf72ca064949ea4dca29827a833605c16364`.
- Direct Lookup has no synonym groups and no category expansion. A word
  reaches another only through a directed alias under
  `expansion.directed_aliases` in `src/locale/catalog.json`: keyed by its
  rule ID, scoped, and one hop, which `src/locale/resources.py` enforces.
  `Array 保存` is declined (`tests/test_lookup.py`).
- `POST /search`: `mode` is `auto`, `lookup` or `list`, and `auto` equals
  `lookup`. The request model forbids unknown fields, so a caller that sends
  a removed filter gets 422 with the field's name. There is no `semantic`
  section.
- `GET /health`: `status` (`ok` or `unavailable`), `schema_ready`, `message`.
- `SearchStage`: `initialize`, `lookup`, `respond`.
- A query Direct Lookup declines gets a response with no `lookup` section.
  Inside the lookup that class is the `declined` intent
  (`query-gold-in-pytest.md`).

This broke the `construct3-copilot` bridge, which sent `mode=semantic` and
filters.

## Re-evaluate when

- A consumer that is not an LLM agent needs the ACE for a free-text
  question: build it in a separate repository, from typed retrieval over ACEs
  and a choice from a closed list, not from mixed ranking.
- Agents pick the wrong addon with the offline tools: build a lexical search
  that proposes candidate addons in the core tier, and measure it on queries
  with an ACE-level label.
- A caller needs a declined query told apart from an empty lookup: add a
  typed reason to the response, with `docs/guide/api-reference.md` and its
  tests.
