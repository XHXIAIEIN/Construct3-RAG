"""
Tests for RAG Chain module
Uses mocks so Qdrant and Ollama are not required.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag.chain import RAGChain, LLMClient, RAGResponse
from src.rag.prompts import NO_RESULTS_RESPONSE
from src.rag.retriever import SearchResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_result(text: str, score: float = 0.8, source: str = "c3_guide") -> SearchResult:
    return SearchResult(
        text=text,
        score=score,
        source=source,
        metadata={"source": f"{source}.md", "h2_heading": "Test"}
    )


def make_chain() -> RAGChain:
    """Return a RAGChain with mocked retriever and LLM."""
    with patch("src.rag.chain.HybridRetriever"):
        chain = RAGChain()

    # Mock retriever
    chain.retriever = MagicMock()
    chain.retriever.check_health.return_value = (True, "ok")
    chain.retriever.search_all_with_rerank.return_value = [
        make_result("Sprite 是一个可视对象，用于显示图片。", score=0.9),
        make_result("使用 Sprite 插件可以添加动画帧。", score=0.75),
    ]
    chain.retriever.filter_by_adaptive_threshold.side_effect = lambda r, **kw: r
    chain.retriever.reciprocal_rank_fusion.side_effect = lambda lists, **kw: lists[0] if lists else []

    # Mock LLM
    chain.llm = MagicMock()
    chain.llm.check_health.return_value = (True, "ok")
    chain.llm.generate.return_value = "Sprite 是 Construct 3 的基础可视对象。[来源: 1]"
    chain.llm.generate_stream.return_value = iter(["Sprite ", "是 ", "基础对象。"])

    return chain


# ---------------------------------------------------------------------------
# LLMClient tests
# ---------------------------------------------------------------------------

class TestLLMClient:
    def test_check_health_no_ollama(self):
        """health check returns False when ollama not importable"""
        client = LLMClient()
        client._client = None
        # Force client property to return None by setting _client to None
        with patch.object(type(client), "client", new_callable=PropertyMock, return_value=None):
            available, msg = client.check_health()
        assert available is False

    def test_generate_returns_string(self):
        """generate() returns string even when ollama fails"""
        client = LLMClient()
        mock_ollama = MagicMock()
        mock_ollama.chat.return_value = {"message": {"content": "hello"}}
        client._client = mock_ollama

        result = client.generate("test prompt")
        assert isinstance(result, str)
        assert result == "hello"

    def test_generate_handles_exception(self):
        """generate() returns error string on exception"""
        client = LLMClient()
        mock_ollama = MagicMock()
        mock_ollama.chat.side_effect = Exception("connection error")
        client._client = mock_ollama

        result = client.generate("test")
        assert "LLM error" in result


# ---------------------------------------------------------------------------
# RAGChain.classify_query tests
# ---------------------------------------------------------------------------

class TestClassifyQuery:
    def test_qa_classification(self):
        chain = make_chain()
        assert chain.classify_query("Sprite 怎么用？") == "qa"
        assert chain.classify_query("Platform 行为是什么？") == "qa"

    def test_code_classification(self):
        chain = make_chain()
        assert chain.classify_query("帮我写一个事件表") == "code"
        assert chain.classify_query("生成跳跃逻辑代码") == "code"


# ---------------------------------------------------------------------------
# RAGChain.answer_qa tests
# ---------------------------------------------------------------------------

class TestAnswerQA:
    def test_returns_rag_response(self):
        chain = make_chain()
        # Mock self-reflection to always say reliable
        chain.llm.generate.side_effect = [
            "Sprite 是基础对象。[来源: 1]",   # answer
            "可靠性：可靠\n核查发现：\n- 引用正确"  # reflection
        ]

        response = chain.answer_qa("Sprite 是什么？")

        assert isinstance(response, RAGResponse)
        assert response.answer != ""
        assert response.query_type in ("qa", "qa_low_confidence")
        assert response.confidence in ("high", "medium", "low", "none")

    def test_no_results_returns_none_confidence(self):
        chain = make_chain()
        chain.retriever.search_all_with_rerank.return_value = []
        chain.enable_query_rewrite = False

        response = chain.answer_qa("completely unrelated xyz123")

        assert response.confidence == "none"
        assert response.query_type == "qa_no_results"

    def test_query_rewrite_fallback_finds_results(self):
        """When initial retrieval is empty, query rewrite should retry and succeed."""
        chain = make_chain()
        chain.enable_query_rewrite = True

        rewrite_result = make_result("通过改写找到的内容", score=0.85)

        # First call returns empty, second (rewritten) call returns results
        chain.retriever.search_all_with_rerank.side_effect = [
            [],              # original query — empty
            [rewrite_result],  # rewritten query — found
        ]
        # LLM calls: rewrite → answer → reflection
        chain.llm.generate.side_effect = [
            "改写后的查询",                          # _rewrite_query
            "改写后找到的答案。[来源: 1]",            # answer generation
            "可靠性：可靠",                           # self-reflection
        ]

        response = chain.answer_qa("obscure query xyz")

        assert response.query_type in ("qa", "qa_low_confidence")
        assert response.answer != ""
        assert response.confidence != "none"

    def test_query_rewrite_still_no_results(self):
        """When query rewrite also finds nothing, should return no_results."""
        chain = make_chain()
        chain.enable_query_rewrite = True

        # Both original and rewritten queries return empty
        chain.retriever.search_all_with_rerank.return_value = []
        chain.llm.generate.return_value = "改写后的查询"  # _rewrite_query

        response = chain.answer_qa("impossible query xyz")

        assert response.confidence == "none"
        assert response.query_type == "qa_no_results"

    def test_sources_populated(self):
        chain = make_chain()
        chain.llm.generate.side_effect = [
            "答案。[来源: 1]",
            "可靠性：可靠"
        ]

        response = chain.answer_qa("Sprite 动画？")

        assert len(response.sources) > 0
        assert "type" in response.sources[0]
        assert "score" in response.sources[0]


# ---------------------------------------------------------------------------
# RAGChain.answer_stream tests
# ---------------------------------------------------------------------------

class TestAnswerStream:
    def test_yields_chunks(self):
        chain = make_chain()
        chunks = list(chain.answer_stream("Sprite 是什么？"))
        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)

    def test_no_results_yields_no_results_response(self):
        chain = make_chain()
        chain.retriever.search_all_with_rerank.return_value = []
        chain.enable_query_rewrite = False

        chunks = list(chain.answer_stream("xyz123 impossible query"))
        full = "".join(chunks)
        assert NO_RESULTS_RESPONSE in full


# ---------------------------------------------------------------------------
# RAGChain.answer_with_fallback tests
# ---------------------------------------------------------------------------

class TestAnswerWithFallback:
    def test_qdrant_unavailable(self):
        chain = make_chain()
        chain.retriever.check_health.return_value = (False, "connection refused")

        response = chain.answer_with_fallback("test")

        assert response.query_type == "fallback_qdrant_unavailable"
        assert response.confidence == "none"

    def test_llm_unavailable(self):
        chain = make_chain()
        chain.llm.check_health.return_value = (False, "ollama not running")

        response = chain.answer_with_fallback("Sprite 是什么？")

        assert response.query_type == "fallback_llm_unavailable"
        assert response.confidence == "low"
        # Sources should still be returned from Qdrant
        assert len(response.sources) > 0

    def test_full_answer_returned(self):
        chain = make_chain()
        chain.llm.generate.side_effect = [
            "答案内容。[来源: 1]",
            "可靠性：可靠"
        ]

        response = chain.answer_with_fallback("Sprite 是什么？")

        assert response.query_type == "qa"
        assert response.answer != ""


# ---------------------------------------------------------------------------
# RAGChain.answer_smart tests
# ---------------------------------------------------------------------------

class TestAnswerSmart:
    def test_simple_query_uses_fallback(self):
        chain = make_chain()
        chain.llm.generate.side_effect = [
            "Sprite 答案。[来源: 1]",
            "可靠性：可靠"
        ]

        response = chain.answer_smart("Sprite 是什么？")

        assert isinstance(response, RAGResponse)

    def test_complex_query_detected(self):
        chain = make_chain()
        # Patch answer_complex_workflow to track if it's called
        chain.answer_complex_workflow = MagicMock(
            return_value=RAGResponse(
                answer="complex answer",
                sources=[],
                query_type="qa_complex_workflow",
                confidence="high"
            )
        )

        complex_query = "如何实现带二段跳和墙跳以及冲刺的平台角色？"
        chain.answer_smart(complex_query)

        # Should have routed to complex workflow
        chain.answer_complex_workflow.assert_called_once_with(complex_query, include_js=False)


# ---------------------------------------------------------------------------
# RAGChain.check_services tests
# ---------------------------------------------------------------------------

class TestCheckServices:
    def test_returns_both_service_statuses(self):
        chain = make_chain()
        chain.retriever.check_health.return_value = (True, "qdrant ok")
        chain.llm.check_health.return_value = (True, "llm ok")

        status = chain.check_services()

        assert "llm" in status
        assert "qdrant" in status
        assert status["llm"][0] is True
        assert status["qdrant"][0] is True


# ---------------------------------------------------------------------------
# RAGChain._self_reflect parsing tests
# ---------------------------------------------------------------------------

class TestSelfReflect:
    """
    Verify that the "可靠" / "不可靠" substring bug is fixed.
    "不可靠" contains "可靠" as a substring, so naive string matching
    would incorrectly return is_reliable=True when the verdict is "不可靠".
    """

    def _call_self_reflect(self, chain: RAGChain, reflection_text: str):
        """Patch LLM to return given reflection, then call _self_reflect."""
        chain.llm.generate.return_value = reflection_text
        _, is_reliable = chain._self_reflect("question", "answer", "context")
        return is_reliable

    def test_reliable_verdict(self):
        chain = make_chain()
        reflection = "可靠性：可靠\n\n核查发现：\n- 引用正确"
        assert self._call_self_reflect(chain, reflection) is True

    def test_unreliable_verdict(self):
        """Critical: must return False even though "可靠" is substring of "不可靠"."""
        chain = make_chain()
        reflection = "可靠性：不可靠\n\n核查发现：\n- 存在捏造的陈述"
        assert self._call_self_reflect(chain, reflection) is False

    def test_unreliable_with_additional_reliable_mentions(self):
        """
        Even if the word "可靠" appears later in the text (in "核查发现" section),
        the verdict must still be False if the verdict line says "不可靠".
        """
        chain = make_chain()
        reflection = (
            "可靠性：不可靠\n\n"
            "核查发现：\n"
            "- [来源: 2] 引用可靠\n"       # "可靠" appears here
            "- [来源: 1] 陈述不可靠\n"     # "不可靠" also appears here
            "\n如果不可靠，给出修正版本：\n..."
        )
        assert self._call_self_reflect(chain, reflection) is False

    def test_reliable_with_notes(self):
        chain = make_chain()
        reflection = (
            "可靠性：可靠\n\n"
            "核查发现：\n"
            "- 所有来源引用正确\n"
            "- 未发现捏造内容\n"
        )
        assert self._call_self_reflect(chain, reflection) is True


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Adaptive filter integration tests
# ---------------------------------------------------------------------------

class TestAdaptiveFilter:
    """Verify filter_by_adaptive_threshold is wired into answer paths."""

    def test_answer_qa_calls_filter(self):
        chain = make_chain()
        chain.answer_qa("timer 怎么用")
        chain.retriever.filter_by_adaptive_threshold.assert_called_once()

    def test_answer_high_confidence_calls_filter(self):
        chain = make_chain()
        chain.answer_high_confidence("timer 怎么用")
        assert chain.retriever.filter_by_adaptive_threshold.call_count >= 1


# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
