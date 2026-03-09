# Retrieval Quality Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve retrieval quality for weak benchmark cases (B08 timer=0.56, B11 collision=0.68, B12 score=0.63, B03 instance var=0.76) through four incremental, independently verifiable steps.

**Architecture:** Post-retrieval filtering (P1) removes long-tail noise before context formatting. Cross-encoder reranking (P2) reorders candidates by joint (query, document) relevance. BM25 hybrid (P3) adds exact keyword matching alongside semantic vectors. Contextual chunking (P4) prepends LLM-generated summaries to each chunk before embedding to improve embedding quality.

**Tech Stack:** Python, Qdrant (sparse vector support), `FlagEmbedding.FlagReranker` (cross-encoder), `jieba` (BM25 tokenization), existing `LLMClient` (contextual chunking generation)

**Verification command (all tasks):**
```bash
/c/Users/test/AppData/Local/Python/bin/python.exe scripts/evaluate.py --heuristic --cases B08,B11,B12,B03
```
**Baseline:** B08=0.56, B11=0.68, B12=0.63, B03=0.76

---

## Task 1: P1 — Post-Retrieval Adaptive Filtering

`filter_by_adaptive_threshold()` already exists in `HybridRetriever` (retriever.py:149–199) but is never called. Wire it into the two answer paths in `chain.py`.

**Files:**
- Modify: `src/rag/chain.py:854–855` (answer_qa, after retrieval before format)
- Modify: `src/rag/chain.py:1028–1031` (answer_high_confidence, after sort before format)
- Test: `tests/test_chain.py`

**Step 1: Write the failing test**

In `tests/test_chain.py`, add a test class `TestAdaptiveFilter`:

```python
class TestAdaptiveFilter(unittest.TestCase):
    """Verify filter_by_adaptive_threshold is called in answer paths."""

    def _make_results(self, scores):
        from src.rag.retriever import SearchResult
        return [SearchResult(text=f"doc{i}", score=s, source="c3_plugins", metadata={})
                for i, s in enumerate(scores)]

    @patch("src.rag.chain.RAGChain._format_reranked_context", return_value="ctx")
    @patch("src.rag.chain.RAGChain._self_reflect", return_value=("ok", True))
    @patch("src.rag.chain.LLMClient.generate", return_value="answer")
    @patch("src.rag.retriever.HybridRetriever.search_all_with_rerank")
    @patch("src.rag.retriever.HybridRetriever.filter_by_adaptive_threshold")
    def test_answer_qa_calls_filter(self, mock_filter, mock_search, *_):
        # Scores span: good results + one outlier low score
        mock_search.return_value = self._make_results([0.9, 0.85, 0.8, 0.3])
        mock_filter.return_value = self._make_results([0.9, 0.85, 0.8])
        chain = RAGChain.__new__(RAGChain)
        chain.retriever = HybridRetriever.__new__(HybridRetriever)
        chain.llm = MagicMock()
        chain.llm.generate.return_value = "answer"
        chain.enable_query_rewrite = False
        chain.STRICT_MODE = False
        chain._self_reflect = MagicMock(return_value=("ok", True))
        chain._format_reranked_context = MagicMock(return_value="ctx")
        chain._append_js_note = MagicMock(side_effect=lambda p, _: p)
        chain.answer_qa("timer 怎么用")
        mock_filter.assert_called_once()
```

**Step 2: Run test to verify it fails**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_chain.py::TestAdaptiveFilter -v
```
Expected: FAIL — `filter_by_adaptive_threshold` not called (assert_called_once fails)

**Step 3: Implement — add filter call in answer_qa**

In `src/rag/chain.py`, locate line ~854 (just before `context = self._format_reranked_context(results)`):

```python
        # Step 1.5: Filter noise via adaptive threshold
        results = self.retriever.filter_by_adaptive_threshold(results)

        # Step 2: Format context
        context = self._format_reranked_context(results)
```

In `answer_high_confidence` (line ~1028, after `unique_results.sort(...)`):

```python
        # Filter noise via adaptive threshold
        unique_results = self.retriever.filter_by_adaptive_threshold(unique_results)

        # Use strict mode with expanded context
        context = self._format_reranked_context(unique_results)
```

**Step 4: Run test to verify it passes**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_chain.py::TestAdaptiveFilter -v
```
Expected: PASS

**Step 5: Run full test suite**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/ -v
```
Expected: all tests pass (no regressions)

**Step 6: Verify benchmark improvement (requires services)**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe scripts/evaluate.py --heuristic --cases B08,B11,B12,B03
```
Expected improvement: B08/B12 +0.1 to +0.2

**Step 7: Commit**

```bash
git add src/rag/chain.py tests/test_chain.py
git commit -m "feat: apply adaptive threshold filter in answer_qa and answer_high_confidence"
```

---

## Task 2: Cross-Encoder Reranking

Add `BAAI/bge-reranker-v2-m3` cross-encoder reranking at the end of `search_all_with_rerank()`. Cross-encoders score (query, document) pairs jointly — far more accurate than cosine similarity of independent embeddings.

**Files:**
- Modify: `src/config.py` (add 3 new env vars)
- Modify: `src/rag/retriever.py` (add `_rerank_with_cross_encoder()`, call in `search_all_with_rerank()`)
- Test: `tests/test_retriever.py` (new file)

**Step 1: Add config variables**

In `src/config.py`, append after existing EXPANDER vars:

```python
# =============================================================================
# Cross-Encoder Reranking
# =============================================================================
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "true").lower() == "true"
RERANKER_TOP_K   = int(os.getenv("RERANKER_TOP_K", "10"))   # candidates fed to reranker
RERANKER_MODEL   = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
```

**Step 2: Write failing tests**

Create `tests/test_retriever.py`:

```python
"""Tests for HybridRetriever cross-encoder reranking."""
import unittest
from unittest.mock import patch, MagicMock
from src.rag.retriever import HybridRetriever, SearchResult


def _make_results(texts_scores):
    return [SearchResult(text=t, score=s, source="c3_plugins", metadata={})
            for t, s in texts_scores]


class TestCrossEncoderReranker(unittest.TestCase):

    def test_rerank_changes_order(self):
        """Cross-encoder should reorder results based on query relevance."""
        retriever = HybridRetriever.__new__(HybridRetriever)
        results = _make_results([
            ("Timer: 等待 N 秒后触发事件", 0.7),
            ("Sprite 动画帧设置", 0.75),    # higher cosine but irrelevant
            ("Timer 行为使用 Wait 条件", 0.65),
        ])
        query = "如何使用 Timer 等待 3 秒"

        # Simulate cross-encoder scores: timer docs get higher scores
        mock_model = MagicMock()
        mock_model.compute_score.return_value = [0.95, 0.1, 0.88]
        retriever._reranker = mock_model

        reranked = retriever._rerank_with_cross_encoder(query, results)
        # Timer docs should now be at top
        assert reranked[0].text.startswith("Timer: 等待"), f"Expected timer doc first, got: {reranked[0].text}"
        assert reranked[1].text.startswith("Timer 行为"), f"Expected second timer doc, got: {reranked[1].text}"

    def test_rerank_disabled_passthrough(self):
        """When RERANKER_ENABLED=False, results pass through unchanged."""
        retriever = HybridRetriever.__new__(HybridRetriever)
        results = _make_results([("doc A", 0.9), ("doc B", 0.8)])
        with patch("src.rag.retriever.RERANKER_ENABLED", False):
            out = retriever._rerank_with_cross_encoder("query", results)
        assert out == results

    def test_rerank_empty_input(self):
        """Empty input returns empty output."""
        retriever = HybridRetriever.__new__(HybridRetriever)
        retriever._reranker = MagicMock()
        out = retriever._rerank_with_cross_encoder("query", [])
        assert out == []
        retriever._reranker.compute_score.assert_not_called()


if __name__ == "__main__":
    unittest.main()
```

**Step 3: Run tests to verify they fail**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_retriever.py -v
```
Expected: FAIL — `_rerank_with_cross_encoder` not defined

**Step 4: Implement cross-encoder in retriever.py**

Add to `src/rag/retriever.py` imports at top:

```python
from src.config import RERANKER_ENABLED, RERANKER_TOP_K, RERANKER_MODEL
```

Add new method and lazy-loaded reranker to `HybridRetriever`:

```python
    @property
    def reranker(self):
        """Lazy-load cross-encoder reranker model."""
        if not hasattr(self, "_reranker") or self._reranker is None:
            import os
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            from FlagEmbedding import FlagReranker
            logger.info(f"[Load] Reranker: {RERANKER_MODEL} ...")
            self._reranker = FlagReranker(RERANKER_MODEL, use_fp16=True)
        return self._reranker

    def _rerank_with_cross_encoder(
        self,
        query: str,
        results: List[SearchResult]
    ) -> List[SearchResult]:
        """
        Rerank results using cross-encoder (joint query-document scoring).

        Cross-encoders are far more accurate than cosine similarity because
        they see both query and document together and can model interactions.

        Args:
            query: Original user query
            results: Candidates to rerank (typically top-k from RRF)

        Returns:
            Results reordered by cross-encoder relevance score
        """
        if not RERANKER_ENABLED or not results:
            return results

        pairs = [[query, r.text] for r in results]
        scores = self.reranker.compute_score(pairs)

        reranked = sorted(
            zip(results, scores),
            key=lambda x: x[1],
            reverse=True
        )
        return [SearchResult(
            text=r.text,
            score=float(score),
            source=r.source,
            metadata={**r.metadata, "reranker_score": float(score),
                      "original_score": r.score}
        ) for r, score in reranked]
```

**Step 5: Call reranker in `search_all_with_rerank()`**

In `retriever.py:482`, after `final_results = reranked[:final_top_k]`, add:

```python
        # Cross-encoder reranking for more accurate relevance ordering
        if RERANKER_ENABLED:
            candidates = reranked[:RERANKER_TOP_K]
            final_results = self._rerank_with_cross_encoder(query, candidates)
        else:
            final_results = reranked[:final_top_k]
```

**Step 6: Run tests**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_retriever.py tests/test_chain.py -v
```
Expected: all PASS

**Step 7: Verify benchmark improvement (requires services)**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe scripts/evaluate.py --heuristic --cases B08,B11,B12,B03
```
Expected: B08/B11 +0.1 to +0.15

**Step 8: Commit**

```bash
git add src/config.py src/rag/retriever.py tests/test_retriever.py
git commit -m "feat: add cross-encoder reranking (bge-reranker-v2-m3) to search_all_with_rerank"
```

---

## Task 3: BM25 Hybrid Search

Add sparse BM25 vectors to Qdrant alongside existing dense vectors. BM25 excels at exact keyword matching — critical for technical terms like "实例变量" (instance variable) that semantic search may miss.

**⚠ Requires full index rebuild (~30–60 min)**

**Files:**
- Modify: `src/config.py` (add BM25_ENABLED)
- Modify: `src/ingest/indexer.py` (BM25Vectorizer class, sparse vector indexing)
- Modify: `src/rag/retriever.py` (sparse search path, fusion)
- Test: `tests/test_retriever.py` (new BM25 test class)

**Step 1: Add config variable**

In `src/config.py`, after reranker vars:

```python
# =============================================================================
# BM25 Hybrid Search
# =============================================================================
# Set to True after rebuilding index with sparse vectors
BM25_ENABLED = os.getenv("BM25_ENABLED", "false").lower() == "true"
```

**Step 2: Write failing test for BM25Vectorizer**

In `tests/test_retriever.py`, add:

```python
class TestBM25Vectorizer(unittest.TestCase):

    def test_fit_and_encode_returns_sparse(self):
        """BM25Vectorizer.encode() should return {index: value} sparse dict."""
        from src.ingest.indexer import BM25Vectorizer
        vect = BM25Vectorizer()
        corpus = ["Timer 行为 等待 条件", "Sprite 动画 帧 速度", "实例变量 数值 文本"]
        vect.fit(corpus)
        vec = vect.encode("Timer 等待 多少秒")
        assert isinstance(vec, dict), "Expected sparse dict"
        assert len(vec) > 0, "Expected non-empty sparse vector"
        assert all(isinstance(k, int) for k in vec), "Keys must be int (term index)"
        assert all(v > 0 for v in vec.values()), "Values must be positive"

    def test_encode_unknown_term_ignored(self):
        """Terms not in vocabulary should be silently ignored."""
        from src.ingest.indexer import BM25Vectorizer
        vect = BM25Vectorizer()
        vect.fit(["hello world"])
        vec = vect.encode("completely unknown term xyz")
        assert vec == {}, "Unknown terms should produce empty sparse vector"
```

**Step 3: Run tests to verify they fail**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_retriever.py::TestBM25Vectorizer -v
```
Expected: FAIL — `BM25Vectorizer` not defined

**Step 4: Implement BM25Vectorizer in indexer.py**

Add after the `EmbeddingModel` class (line ~50):

```python
class BM25Vectorizer:
    """
    Simple BM25 vectorizer for sparse vector indexing.
    Produces {term_index: bm25_score} dicts compatible with Qdrant sparse vectors.

    k1=1.5, b=0.75 (standard BM25 parameters)
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.vocab: dict[str, int] = {}        # term → index
        self.idf: dict[int, float] = {}        # index → IDF score
        self._avg_dl: float = 0.0
        self._fitted = False

    def _tokenize(self, text: str) -> list[str]:
        import jieba
        return [t for t in jieba.cut(text) if len(t.strip()) > 1]

    def fit(self, corpus: list[str]) -> "BM25Vectorizer":
        """Build vocabulary and IDF from corpus."""
        import math
        tokenized = [self._tokenize(doc) for doc in corpus]
        N = len(tokenized)
        self._avg_dl = sum(len(d) for d in tokenized) / max(N, 1)

        # Build vocabulary
        all_terms: set[str] = set()
        for doc in tokenized:
            all_terms.update(doc)
        self.vocab = {t: i for i, t in enumerate(sorted(all_terms))}

        # Compute IDF
        df: dict[int, int] = {}
        for doc in tokenized:
            seen = set()
            for t in doc:
                idx = self.vocab[t]
                if idx not in seen:
                    df[idx] = df.get(idx, 0) + 1
                    seen.add(idx)

        self.idf = {
            idx: math.log(1 + (N - freq + 0.5) / (freq + 0.5))
            for idx, freq in df.items()
        }
        self._fitted = True
        return self

    def encode(self, text: str) -> dict[int, float]:
        """Encode text to BM25 sparse vector."""
        if not self._fitted:
            return {}
        tokens = self._tokenize(text)
        dl = len(tokens)
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1

        vec: dict[int, float] = {}
        for term, freq in tf.items():
            if term not in self.vocab:
                continue
            idx = self.vocab[term]
            idf = self.idf.get(idx, 0.0)
            # BM25 TF normalization
            tf_norm = (freq * (self.k1 + 1)) / (
                freq + self.k1 * (1 - self.b + self.b * dl / max(self._avg_dl, 1))
            )
            score = idf * tf_norm
            if score > 0:
                vec[idx] = round(score, 6)
        return vec
```

**Step 5: Run BM25 tests**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_retriever.py::TestBM25Vectorizer -v
```
Expected: PASS

**Step 6: Update Indexer to support sparse vectors**

In `src/ingest/indexer.py`, import BM25_ENABLED from config and update `create_collection()` and the indexing loop. This is the larger change — add a `_create_collection_with_sparse()` helper and update the upsert calls to include sparse vectors when enabled.

Key change in `Indexer.index_documents()` — add sparse vector alongside dense:

```python
from src.config import BM25_ENABLED

# In index_documents(), after encoding dense vectors:
if BM25_ENABLED and self._bm25 is not None:
    sparse_vec = self._bm25.encode(chunk["text"])
    point = PointStruct(
        id=point_id,
        vector={"dense": dense_vector, "sparse": sparse_vec},
        payload=payload
    )
else:
    point = PointStruct(id=point_id, vector=dense_vector, payload=payload)
```

> **Note:** Full implementation details depend on your Qdrant collection setup. If collections use named vectors, update `VectorParams` to `{"dense": VectorParams(...), "sparse": SparseVectorParams(...)}`. If using unnamed vectors, the sparse path requires collection recreation. See Qdrant sparse vector docs for exact API.

**Step 7: Update HybridRetriever to search sparse vectors**

Add `_search_sparse()` helper in `HybridRetriever` and merge sparse + dense results in `search_collection()`:

```python
from src.config import BM25_ENABLED

def _search_sparse(
    self,
    collection_name: str,
    query: str,
    top_k: int
) -> List[SearchResult]:
    """BM25 sparse vector search for a single collection."""
    if not BM25_ENABLED or not hasattr(self, "_bm25") or self._bm25 is None:
        return []
    from qdrant_client.models import SparseVector, NamedSparseVector
    sparse_vec = self._bm25.encode(query)
    if not sparse_vec:
        return []
    indices = list(sparse_vec.keys())
    values = list(sparse_vec.values())
    try:
        response = self.client.query_points(
            collection_name=collection_name,
            query=NamedSparseVector(name="sparse", vector=SparseVector(
                indices=indices, values=values
            )),
            limit=top_k,
        )
        return [SearchResult(
            text=r.payload.get("text", ""),
            score=r.score,
            source=collection_name,
            metadata={k: v for k, v in r.payload.items() if k != "text"}
        ) for r in response.points]
    except Exception as e:
        logger.warning(f"[BM25] Sparse search failed in {collection_name}: {e}")
        return []
```

Then in `search_all_with_rerank()`, after dense collection results, add sparse results and fuse via existing `reciprocal_rank_fusion()`.

**Step 8: Rebuild index with BM25_ENABLED=true**

```bash
BM25_ENABLED=true /c/Users/test/AppData/Local/Python/bin/python.exe -m src.ingest.indexer --rebuild
```

⚠ This takes 30–60 min. Monitor with `docker logs qdrant`.

**Step 9: Run tests**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/ -v
```

**Step 10: Verify benchmark**

```bash
BM25_ENABLED=true /c/Users/test/AppData/Local/Python/bin/python.exe scripts/evaluate.py --heuristic --cases B08,B11,B12,B03
```
Expected: B03/B11 +0.1

**Step 11: Commit**

```bash
git add src/config.py src/ingest/indexer.py src/rag/retriever.py tests/test_retriever.py
git commit -m "feat: add BM25 sparse vector hybrid search (requires index rebuild)"
```

---

## Task 4: Contextual Chunking

Before embedding each chunk during indexing, prepend an LLM-generated context summary. Anthropic reports 49% retrieval accuracy improvement. Generation is done offline in batch (once per chunk, cached to JSON), so query latency is unaffected.

**⚠ Requires LLM + full index rebuild (combine with Task 3 rebuild)**

**Files:**
- Create: `scripts/generate_chunk_contexts.py` (batch generation script)
- Modify: `src/config.py` (add 2 new vars)
- Modify: `src/ingest/indexer.py` (load context cache, prepend to chunk text)
- Test: `tests/test_retriever.py` (contextual chunking test)

**Step 1: Add config variables**

In `src/config.py`, after BM25 vars:

```python
# =============================================================================
# Contextual Chunking
# =============================================================================
# Set to True after generating contexts via scripts/generate_chunk_contexts.py
CONTEXTUAL_CHUNKING_ENABLED = os.getenv("CONTEXTUAL_CHUNKING_ENABLED", "false").lower() == "true"
CONTEXTUAL_CHUNKING_CACHE   = Path(os.getenv("CONTEXTUAL_CHUNKING_CACHE",
                                              str(BASE_DIR / "data" / "chunk_contexts.json")))
```

**Step 2: Write failing test for context loading**

In `tests/test_retriever.py`, add:

```python
class TestContextualChunking(unittest.TestCase):

    def test_load_context_cache(self):
        """Indexer should load chunk_contexts.json and prepend to chunk text."""
        import json, tempfile, os
        from src.ingest.indexer import Indexer

        # Create mock cache
        cache = {"abc123": "[Plugin: Timer > Wait 条件]\n"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                        delete=False, encoding="utf-8") as f:
            json.dump(cache, f)
            cache_path = f.name

        try:
            indexer = Indexer.__new__(Indexer)
            indexer._load_chunk_contexts(cache_path)
            assert hasattr(indexer, "_chunk_contexts")
            assert indexer._chunk_contexts.get("abc123") == "[Plugin: Timer > Wait 条件]\n"
        finally:
            os.unlink(cache_path)

    def test_prepend_context_to_chunk(self):
        """_prepend_context() should prepend cached summary to chunk text."""
        from src.ingest.indexer import Indexer
        indexer = Indexer.__new__(Indexer)
        indexer._chunk_contexts = {"key1": "[Plugin: Sprite > 动画]\n"}
        result = indexer._prepend_context("key1", "帧速率设置为每秒 N 帧。")
        assert result.startswith("[Plugin: Sprite > 动画]"), f"Got: {result}"
        assert "帧速率设置" in result
```

**Step 3: Run tests to verify they fail**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_retriever.py::TestContextualChunking -v
```
Expected: FAIL

**Step 4: Create batch generation script**

Create `scripts/generate_chunk_contexts.py`:

```python
#!/usr/bin/env python3
"""
Generate contextual chunk summaries for improved embedding quality.
Anthropic technique: prepend "[Collection: Section > Subsection]" style
context to each chunk before embedding.

Usage:
    python scripts/generate_chunk_contexts.py --output data/chunk_contexts.json
    python scripts/generate_chunk_contexts.py --resume  # skip already done
"""
import sys, json, hashlib, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

CONTEXT_PROMPT = """以下是一段来自 Construct 3 文档的片段：

<document>
{document}
</document>

请用一句话描述这段内容所属的模块和主题，格式如下：
[插件/行为/文档: 功能名 > 子主题]

只输出这一行，不要解释。"""


def generate_context(llm, chunk_text: str) -> str:
    prompt = CONTEXT_PROMPT.format(document=chunk_text[:1000])
    try:
        return llm.generate(prompt, system="") + "\n"
    except Exception as e:
        return f"[Context generation failed: {e}]\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/chunk_contexts.json")
    parser.add_argument("--resume", action="store_true",
                        help="Skip chunks already in output file")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of chunks to process (0=all)")
    args = parser.parse_args()

    from src.config import QDRANT_HOST, QDRANT_PORT
    from src.rag.chain import LLMClient
    from src.config import LLM_PROVIDER, LLM_MODEL, LLM_BASE_URL, LLM_API_KEY
    from qdrant_client import QdrantClient

    output_path = Path(args.output)
    contexts: dict[str, str] = {}
    if args.resume and output_path.exists():
        contexts = json.loads(output_path.read_text(encoding="utf-8"))
        print(f"Resuming: {len(contexts)} chunks already done")

    llm = LLMClient(model=LLM_MODEL, base_url=LLM_BASE_URL,
                    api_key=LLM_API_KEY, provider=LLM_PROVIDER)
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    collections = [c.name for c in client.get_collections().collections]
    processed = 0

    for coll in collections:
        print(f"\n[{coll}] Processing...")
        offset = None
        while True:
            result = client.scroll(coll, limit=50, offset=offset, with_payload=True)
            points, offset = result
            if not points:
                break
            for pt in points:
                text = pt.payload.get("text", "")
                if not text:
                    continue
                key = hashlib.md5(text[:500].encode()).hexdigest()
                if key in contexts:
                    continue
                contexts[key] = generate_context(llm, text)
                processed += 1
                if processed % 10 == 0:
                    output_path.write_text(json.dumps(contexts, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
                    print(f"  Saved {processed} chunks...")
                if args.limit and processed >= args.limit:
                    break
            if args.limit and processed >= args.limit:
                break

    output_path.write_text(json.dumps(contexts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDone. Generated {processed} new contexts → {output_path}")


if __name__ == "__main__":
    main()
```

**Step 5: Implement _load_chunk_contexts and _prepend_context in indexer.py**

Add to `Indexer` class in `src/ingest/indexer.py`:

```python
    def _load_chunk_contexts(self, cache_path: str | Path | None = None) -> None:
        """Load pre-generated contextual chunk summaries from JSON cache."""
        from src.config import CONTEXTUAL_CHUNKING_CACHE
        path = Path(cache_path or CONTEXTUAL_CHUNKING_CACHE)
        if path.exists():
            import json
            self._chunk_contexts = json.loads(path.read_text(encoding="utf-8"))
            print(f"[ContextualChunking] Loaded {len(self._chunk_contexts)} contexts from {path}")
        else:
            self._chunk_contexts = {}
            print(f"[ContextualChunking] Cache not found at {path}, using raw chunks")

    def _prepend_context(self, chunk_key: str, chunk_text: str) -> str:
        """Prepend cached context summary to chunk text for embedding."""
        ctx = getattr(self, "_chunk_contexts", {}).get(chunk_key, "")
        return ctx + chunk_text if ctx else chunk_text
```

Then in `index_documents()`, compute chunk key and call `_prepend_context()` before encoding:

```python
from src.config import CONTEXTUAL_CHUNKING_ENABLED
import hashlib

# In index_documents(), before embedding:
embed_text = chunk["text"]
if CONTEXTUAL_CHUNKING_ENABLED:
    key = hashlib.md5(embed_text[:500].encode()).hexdigest()
    embed_text = self._prepend_context(key, embed_text)
# Use embed_text for encoding, store original chunk["text"] in payload
```

**Step 6: Load context cache in Indexer.__init__()**

```python
    def __init__(self, ...):
        ...
        from src.config import CONTEXTUAL_CHUNKING_ENABLED
        if CONTEXTUAL_CHUNKING_ENABLED:
            self._load_chunk_contexts()
```

**Step 7: Run tests**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_retriever.py::TestContextualChunking -v
```
Expected: PASS

**Step 8: Generate contexts (requires LLM running)**

```bash
# First, generate context summaries (slow — one LLM call per chunk)
/c/Users/test/AppData/Local/Python/bin/python.exe scripts/generate_chunk_contexts.py \
    --output data/chunk_contexts.json --resume

# Then rebuild index with both BM25 + contextual chunking
BM25_ENABLED=true CONTEXTUAL_CHUNKING_ENABLED=true \
    /c/Users/test/AppData/Local/Python/bin/python.exe -m src.ingest.indexer --rebuild
```

**Step 9: Verify benchmark**

```bash
BM25_ENABLED=true CONTEXTUAL_CHUNKING_ENABLED=true \
    /c/Users/test/AppData/Local/Python/bin/python.exe scripts/evaluate.py --heuristic --cases B08,B11,B12,B03
```
Expected: all weak cases +0.1 to +0.2

**Step 10: Commit**

```bash
git add src/config.py src/ingest/indexer.py scripts/generate_chunk_contexts.py tests/test_retriever.py
git commit -m "feat: add contextual chunking (offline LLM context prepend before embedding)"
```

---

## Summary

| Task | Files Changed | Index Rebuild | Expected Gain |
|------|---------------|---------------|---------------|
| P1: Adaptive filter | `chain.py` | No | B08/B12 +0.1–0.2 |
| P2: Cross-encoder | `retriever.py`, `config.py` | No | B08/B11 +0.1–0.15 |
| P3: BM25 hybrid | `indexer.py`, `retriever.py`, `config.py` | Yes (30–60min) | B03/B11 +0.1 |
| P4: Contextual chunking | `indexer.py`, `config.py` | Yes (with P3) | All +0.1–0.2 |

Run P1 and P2 first (no rebuild needed). Combine P3 + P4 into one rebuild run.
