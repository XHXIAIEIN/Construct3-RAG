"""Tests for HybridRetriever cross-encoder reranking and BM25Vectorizer."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag.retriever import HybridRetriever, SearchResult


def _make_results(texts_scores):
    return [SearchResult(text=t, score=s, source="c3_plugins", metadata={})
            for t, s in texts_scores]


# ---------------------------------------------------------------------------
# Cross-encoder reranker tests
# ---------------------------------------------------------------------------

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
        mock_model.predict.return_value = np.array([0.95, 0.1, 0.88])
        retriever._reranker = mock_model

        with patch("src.rag.retriever.RERANKER_ENABLED", True):
            reranked = retriever._rerank_with_cross_encoder(query, results)
        # Timer docs should now be at top
        assert reranked[0].text.startswith("Timer: 等待"), \
            f"Expected timer doc first, got: {reranked[0].text}"
        assert reranked[1].text.startswith("Timer 行为"), \
            f"Expected second timer doc, got: {reranked[1].text}"

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
        retriever._reranker.predict.assert_not_called()

    def test_rerank_preserves_metadata(self):
        """Reranked results should carry original_score in metadata."""
        retriever = HybridRetriever.__new__(HybridRetriever)
        results = _make_results([("doc A", 0.9), ("doc B", 0.7)])
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.5, 0.95])
        retriever._reranker = mock_model

        with patch("src.rag.retriever.RERANKER_ENABLED", True):
            reranked = retriever._rerank_with_cross_encoder("query", results)
        assert "original_score" in reranked[0].metadata
        assert "reranker_score" in reranked[0].metadata


# ---------------------------------------------------------------------------
# BM25Vectorizer tests
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Contextual chunking tests (Indexer helpers)
# ---------------------------------------------------------------------------

class TestContextualChunking(unittest.TestCase):

    def test_load_context_cache(self):
        """Indexer should load chunk_contexts.json and prepend to chunk text."""
        import json
        import tempfile
        import os
        from src.ingest.indexer import Indexer

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


class TestWeightedRRF(unittest.TestCase):
    def make_sr(self, text: str, score: float = 0.8) -> SearchResult:
        return SearchResult(text=text, score=score, source="c3_guide", metadata={})

    def test_single_list_returns_sorted(self):
        from src.rag.retriever import weighted_rrf
        results = [self.make_sr("a", 0.9), self.make_sr("b", 0.7), self.make_sr("c", 0.5)]
        out = weighted_rrf([results], [1.0])
        assert [r.text for r in out] == ["a", "b", "c"]

    def test_higher_weight_ranks_higher(self):
        from src.rag.retriever import weighted_rrf
        list_high = [self.make_sr("important")]
        list_low  = [self.make_sr("noise")]
        out = weighted_rrf([list_low, list_high], [0.2, 0.8])
        assert out[0].text == "important"

    def test_deduplication(self):
        from src.rag.retriever import weighted_rrf
        r = self.make_sr("same text")
        out = weighted_rrf([[r], [r]], [0.5, 0.5])
        texts = [x.text for x in out]
        assert texts.count("same text") == 1

    def test_empty_lists_handled(self):
        from src.rag.retriever import weighted_rrf
        out = weighted_rrf([[], [self.make_sr("x")]], [0.5, 0.5])
        assert len(out) == 1

    def test_zero_weight_floor(self):
        from src.rag.retriever import weighted_rrf
        out = weighted_rrf([[self.make_sr("x")]], [0.0])
        assert len(out) == 1


# ---------------------------------------------------------------------------
# Query complexity routing tests
# ---------------------------------------------------------------------------

class TestQueryComplexity(unittest.TestCase):

    def test_short_query_is_simple(self):
        from src.rag.retriever import estimate_query_complexity
        preset = estimate_query_complexity("Sprite动画")
        self.assertEqual(preset.complexity, "simple")
        self.assertEqual(preset.top_k_per_collection, 3)
        self.assertEqual(preset.final_top_k, 5)

    def test_normal_query_is_moderate(self):
        from src.rag.retriever import estimate_query_complexity
        preset = estimate_query_complexity("如何使用 Timer 行为设置倒计时")
        self.assertEqual(preset.complexity, "moderate")
        self.assertEqual(preset.top_k_per_collection, 5)

    def test_multi_question_is_complex(self):
        from src.rag.retriever import estimate_query_complexity
        preset = estimate_query_complexity("Sprite 有哪些碰撞条件？Platform 行为怎么设置跳跃高度？")
        self.assertEqual(preset.complexity, "complex")
        self.assertEqual(preset.top_k_per_collection, 8)
        self.assertEqual(preset.final_top_k, 15)

    def test_long_with_splitters_is_complex(self):
        from src.rag.retriever import estimate_query_complexity
        preset = estimate_query_complexity("实现平台跳跃游戏、支持物理碰撞、带存档功能、还有多人联机")
        self.assertEqual(preset.complexity, "complex")

    def test_empty_query_is_simple(self):
        from src.rag.retriever import estimate_query_complexity
        preset = estimate_query_complexity("")
        self.assertEqual(preset.complexity, "simple")

    def test_medium_with_one_splitter_is_complex(self):
        from src.rag.retriever import estimate_query_complexity
        # 40+ chars with 1 splitter → complex
        preset = estimate_query_complexity("如何让 Sprite 在碰到 Solid 对象时停下来；同时播放动画")
        self.assertEqual(preset.complexity, "complex")


# ---------------------------------------------------------------------------
# Context tier assignment tests
# ---------------------------------------------------------------------------

class TestContextTier(unittest.TestCase):

    def test_top_result_gets_full(self):
        from src.rag.retriever import assign_context_tiers
        results = [
            {"score": 0.95, "text": "A"},
            {"score": 0.60, "text": "B"},
            {"score": 0.20, "text": "C"},
        ]
        assign_context_tiers(results)
        self.assertEqual(results[0]["context_tier"], "full")
        self.assertEqual(results[1]["context_tier"], "normal")
        self.assertEqual(results[2]["context_tier"], "brief")

    def test_low_top_score_still_works(self):
        """RRF scores are tiny (0.01-0.03) — ratios still apply."""
        from src.rag.retriever import assign_context_tiers
        results = [
            {"score": 0.016, "text": "A"},
            {"score": 0.014, "text": "B"},
            {"score": 0.003, "text": "C"},
        ]
        assign_context_tiers(results)
        self.assertEqual(results[0]["context_tier"], "full")
        self.assertEqual(results[1]["context_tier"], "normal")  # 0.014/0.016 = 0.875
        self.assertEqual(results[2]["context_tier"], "brief")   # 0.003/0.016 = 0.19

    def test_empty_results(self):
        from src.rag.retriever import assign_context_tiers
        self.assertEqual(assign_context_tiers([]), [])

    def test_single_result_is_full(self):
        from src.rag.retriever import assign_context_tiers
        results = [{"score": 0.5, "text": "only"}]
        assign_context_tiers(results)
        self.assertEqual(results[0]["context_tier"], "full")

    def test_all_same_score(self):
        from src.rag.retriever import assign_context_tiers
        results = [{"score": 0.7, "text": f"r{i}"} for i in range(5)]
        assign_context_tiers(results)
        # First is full (rank 0, ratio=1.0), rest are normal (ratio=1.0 >= 0.5)
        self.assertEqual(results[0]["context_tier"], "full")
        for r in results[1:]:
            self.assertEqual(r["context_tier"], "normal")


if __name__ == "__main__":
    unittest.main()
