# Retrieval Quality Improvements Design

**Date**: 2026-03-09
**Status**: Approved

## Goal

Improve retrieval quality through four incremental steps, targeting the known weak cases:
B08 (timer, 0.56), B11 (collision, 0.68), B12 (score system, 0.63), B03 (instance var, 0.76).

## Implementation Order

Each step is independently verifiable via `python scripts/evaluate.py --heuristic --cases B08,B11,B12,B03`.

---

## Step 1: Post-Retrieval Filtering (P1)

**Files**: `src/rag/chain.py`
**Cost**: ~3 lines, no index rebuild

`filter_by_adaptive_threshold()` already exists in `HybridRetriever` but is not called
in the answer chain. Apply it after `search_all_with_rerank()` before context formatting.

Target methods: `_answer_qa()`, `_answer_high_confidence()`.

---

## Step 2: Cross-Encoder Reranking

**Files**: `src/rag/retriever.py`, `src/config.py`
**Cost**: Medium, no index rebuild
**Model**: `BAAI/bge-reranker-v2-m3` (same family as bge-m3)

After RRF fusion, rerank the top-k candidates using a cross-encoder before returning.
Cross-encoders score (query, document) pairs jointly — far more accurate than
cosine similarity between independent embeddings.

Config:
- `RERANKER_ENABLED` (bool, default: True)
- `RERANKER_TOP_K` (int, default: 10) — candidates fed to reranker
- `RERANKER_MODEL` (str, default: "BAAI/bge-reranker-v2-m3")

Integration point: end of `search_all_with_rerank()`, after deduplication.

---

## Step 3: BM25 Hybrid Search

**Files**: `src/ingest/indexer.py`, `src/rag/retriever.py`, `src/config.py`
**Cost**: Large, requires index rebuild (~30-60 min)

Qdrant supports sparse vectors natively. Add BM25 sparse vectors alongside
existing dense vectors. Query both paths and fuse scores.

Implementation approach:
- Use `qdrant_client` sparse vector support (no extra library needed for BM25)
- Simple BM25 via term frequency on tokenized text (jieba for Chinese)
- Sparse + dense fusion via RRF (already implemented)

Config:
- `BM25_ENABLED` (bool, default: False until index rebuilt)

---

## Step 4: Contextual Chunking

**Files**: `src/ingest/indexer.py`, `src/config.py`
**Cost**: Large, requires index rebuild (combine with Step 3)

Before embedding each chunk, prepend a LLM-generated context summary:

```
[Plugin: Platform Behavior > Movement Properties]
Max Speed: Maximum horizontal movement speed (px/s)...
```

Anthropic reports 49% retrieval accuracy improvement with this technique.

Generation: Offline batch (one LLM call per chunk, cached to JSON).
Merge with Step 3 rebuild to avoid two full re-indexing runs.

Config:
- `CONTEXTUAL_CHUNKING_ENABLED` (bool, default: False until contexts generated)
- `CONTEXTUAL_CHUNKING_CACHE` (path, default: `data/chunk_contexts.json`)

---

## Verification

After each step:
```bash
python scripts/evaluate.py --heuristic --cases B08,B11,B12,B03
```

Baseline: B08=0.56, B11=0.68, B12=0.63, B03=0.76

Expected improvements:
- Step 1: B08/B12 (+0.1 to +0.2, noise filtered)
- Step 2: B08/B11 (+0.1 to +0.15, better ranking)
- Step 3: B03/B11 (+0.1, keyword-exact matching)
- Step 4: All weak cases (+0.1 to +0.2, context-aware embeddings)
