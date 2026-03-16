# tests/test_semantic_chain.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.rag.semantic_chain import DecomposedQuery, QueryIntent, normalize_intents


def test_query_intent_basic():
    intent = QueryIntent(label="follow", keywords=["set position"], weight=0.6)
    assert intent.label == "follow"
    assert intent.weight == 0.6


def test_decomposed_query_basic():
    dq = DecomposedQuery(
        query_type="howto",
        c3_objects=["Sprite", "Mouse"],
        action_verbs=["跟随"],
        intents=[QueryIntent("immediate follow", ["set position", "Mouse.X"], 0.6),
                 QueryIntent("smooth follow", ["lerp"], 0.4)],
        solution_rewrite="Sprite set position Mouse.X Mouse.Y",
        confidence=0.95,
    )
    assert dq.query_type == "howto"
    assert len(dq.c3_objects) == 2
    assert dq.confidence == 0.95


def test_normalize_intents_sums_to_one():
    intents = [QueryIntent("a", [], 0.9), QueryIntent("b", [], 0.7)]
    normalized = normalize_intents(intents)
    total = sum(i.weight for i in normalized)
    assert abs(total - 1.0) < 1e-9


def test_normalize_intents_single():
    intents = [QueryIntent("a", [], 0.5)]
    normalized = normalize_intents(intents)
    assert normalized[0].weight == 1.0


def test_empty_intents_returns_default():
    from src.rag.semantic_chain import ensure_intents
    dq = DecomposedQuery(
        query_type="explain", c3_objects=[], action_verbs=["解释"],
        intents=[], solution_rewrite="", confidence=0.9,
    )
    result = ensure_intents(dq)
    assert len(result.intents) == 1
    assert result.intents[0].weight == 1.0
    assert "解释" in result.intents[0].keywords


def test_ensure_intents_non_empty_unchanged():
    from src.rag.semantic_chain import ensure_intents
    intents = [QueryIntent("follow", ["set position"], 1.0)]
    dq = DecomposedQuery(
        query_type="howto", c3_objects=["Sprite"], action_verbs=["跟随"],
        intents=intents, solution_rewrite="", confidence=0.8,
    )
    result = ensure_intents(dq)
    assert result is dq  # fast-path: returns original unchanged


def test_normalize_intents_zero_total():
    intents = [QueryIntent("a", [], 0.0), QueryIntent("b", [], 0.0)]
    normalized = normalize_intents(intents)
    total = sum(i.weight for i in normalized)
    assert abs(total - 1.0) < 1e-9
    # Equal weights when all are zero
    assert abs(normalized[0].weight - 0.5) < 1e-9


from unittest.mock import MagicMock


class TestRawLLMBackend:
    def _make_llm(self, response: str) -> MagicMock:
        llm = MagicMock()
        llm.generate.return_value = response
        return llm

    def test_parses_valid_json(self):
        from src.rag.semantic_chain import RawLLMBackend
        llm = self._make_llm(
            '```json\n{"query_type":"howto","c3_objects":["Sprite"],'
            '"action_verbs":["跟随"],"intents":[{"label":"follow",'
            '"keywords":["set position"],"weight":1.0}],'
            '"solution_rewrite":"Sprite set position","confidence":0.9}\n```'
        )
        backend = RawLLMBackend(llm, "test-prompt {query}")
        dq = backend.decompose("test query")
        assert dq.query_type == "howto"
        assert "Sprite" in dq.c3_objects
        assert dq.confidence == 0.9

    def test_returns_fallback_on_invalid_json(self):
        from src.rag.semantic_chain import RawLLMBackend
        llm = self._make_llm("sorry I cannot help")
        backend = RawLLMBackend(llm, "{query}")
        dq = backend.decompose("test")
        assert dq.query_type == "unknown"
        assert dq.confidence == 0.0

    def test_normalizes_intent_weights(self):
        from src.rag.semantic_chain import RawLLMBackend
        llm = self._make_llm(
            '{"query_type":"howto","c3_objects":[],"action_verbs":[],'
            '"intents":[{"label":"a","keywords":[],"weight":0.9},'
            '{"label":"b","keywords":[],"weight":0.7}],'
            '"solution_rewrite":"","confidence":0.8}'
        )
        backend = RawLLMBackend(llm, "{query}")
        dq = backend.decompose("q")
        total = sum(i.weight for i in dq.intents)
        assert abs(total - 1.0) < 1e-9


class TestInstructorBackend:
    def test_unavailable_when_not_ollama(self):
        from src.rag.semantic_chain import InstructorBackend
        llm = MagicMock()
        llm.provider = "huggingface"
        backend = InstructorBackend(llm, "prompt {query}")
        assert not backend.available

    def test_available_when_ollama(self):
        from src.rag.semantic_chain import InstructorBackend
        llm = MagicMock()
        llm.provider = "ollama"
        llm.model = "qwen2.5:7b"
        llm.ollama_host = "localhost"
        llm.ollama_port = 11434
        backend = InstructorBackend(llm, "prompt {query}")
        # availability depends on ollama being running; just check no crash
        assert isinstance(backend.available, bool)

    def test_falls_back_on_connection_error(self):
        from src.rag.semantic_chain import InstructorBackend
        llm = MagicMock()
        llm.provider = "ollama"
        llm.model = "qwen2.5:7b"
        llm.ollama_host = "localhost"
        llm.ollama_port = 11434
        backend = InstructorBackend(llm, "prompt {query}")
        # If ollama not running, available returns False and decompose returns fallback
        dq = backend.decompose("test")
        # When not available (_client is None), fallback DQ is returned
        assert dq.query_type == "unknown"
        assert dq.confidence == 0.0


class TestCollectionRouter:
    def _make_embedder(self, sim_value: float = 0.5):
        """Embedder that returns fixed similarity for all collections."""
        embedder = MagicMock()
        embedder.encode_single.return_value = [0.1] * 10
        embedder.encode.return_value = [[0.1] * 10] * 10
        return embedder

    def test_returns_weights_for_all_collections(self):
        from src.rag.semantic_chain import CollectionRouter
        router = CollectionRouter(self._make_embedder())
        weights = router.route("怎么让 Sprite 跟随鼠标", "howto")
        assert set(weights.keys()) == {
            "c3_guide", "c3_interface", "c3_project", "c3_plugins",
            "c3_behaviors", "c3_scripting", "c3_ace", "c3_effects",
            "c3_terms", "c3_examples",
        }

    def test_translate_query_boosts_terms(self):
        from src.rag.semantic_chain import CollectionRouter
        router = CollectionRouter(self._make_embedder(0.3))
        weights = router.route("Tween 是什么意思", "translate")
        assert weights["c3_terms"] >= 0.5  # bias +0.6 applied

    def test_threshold_filters_low_collections(self):
        from src.rag.semantic_chain import CollectionRouter, _DOC_COLLECTION_SET
        embedder = MagicMock()
        # Non-zero embeddings produce non-zero cosine similarity (~1.0 for identical vecs)
        embedder.encode_single.return_value = [1.0] * 10
        embedder.encode.return_value = [[1.0] * 10] * 10
        router = CollectionRouter(embedder)
        # With threshold=1.1 (above max possible weight of 1.0), non-doc collections
        # are zeroed out; doc collections get floor weight (0.05)
        weights = router.route("test", "unknown", threshold=1.1)
        non_doc_active = {k for k, v in weights.items() if v > 0 and k not in _DOC_COLLECTION_SET}
        assert len(non_doc_active) == 0
        # Doc collections should have floor weight
        for k, v in weights.items():
            if k in _DOC_COLLECTION_SET:
                assert v == pytest.approx(0.05)

    def test_threshold_allows_above_threshold(self):
        from src.rag.semantic_chain import CollectionRouter
        embedder = MagicMock()
        embedder.encode_single.return_value = [1.0] * 10
        embedder.encode.return_value = [[1.0] * 10] * 10
        router = CollectionRouter(embedder)
        # With threshold=0.0, all collections with any weight are kept
        weights = router.route("test", "unknown", threshold=0.0)
        active = {k for k, v in weights.items() if v > 0}
        assert len(active) > 0

    def test_weights_are_non_negative(self):
        from src.rag.semantic_chain import CollectionRouter
        router = CollectionRouter(self._make_embedder())
        weights = router.route("test query", "howto")
        assert all(v >= 0 for v in weights.values())


class TestSemanticChain:
    def _make_chain(self):
        from src.rag.semantic_chain import SemanticChain, RawLLMBackend, CollectionRouter
        llm = MagicMock()
        llm.provider = "huggingface"
        llm.generate.return_value = (
            '{"query_type":"howto","c3_objects":["Sprite"],'
            '"action_verbs":["跟随"],'
            '"intents":[{"label":"follow","keywords":["set position"],"weight":1.0}],'
            '"solution_rewrite":"Sprite set position Mouse.X","confidence":0.9}'
        )
        embedder = MagicMock()
        embedder.encode_single.return_value = [0.5] * 10
        embedder.encode.return_value = [[0.5] * 10] * 10

        retriever = MagicMock()
        retriever.search_collection.return_value = []

        router = CollectionRouter(embedder)
        backend = RawLLMBackend(llm, "{query}")
        return SemanticChain(backend=backend, router=router, retriever=retriever)

    def test_run_returns_result_lists_and_weights(self):
        chain = self._make_chain()
        result_lists, weights = chain.run("怎么让 Sprite 跟随鼠标")
        assert isinstance(result_lists, list)
        assert isinstance(weights, list)
        assert len(result_lists) == len(weights)

    def test_run_with_disabled_returns_none(self):
        from src.rag.semantic_chain import SemanticChain
        chain = SemanticChain(backend=None, router=None, retriever=None, enabled=False)
        result = chain.run("test")
        assert result is None

    def test_cache_avoids_duplicate_decomposition(self):
        chain = self._make_chain()
        chain.run("Sprite 跟随鼠标")
        call_count_after_first = chain._backend._llm.generate.call_count
        chain.run("Sprite 跟随鼠标")  # same query
        # LLM should not be called again
        assert chain._backend._llm.generate.call_count == call_count_after_first

    def test_low_confidence_reduces_blend_weight(self):
        from src.rag.semantic_chain import SemanticChain, RawLLMBackend, CollectionRouter
        llm = MagicMock()
        llm.provider = "huggingface"
        llm.generate.return_value = (
            '{"query_type":"unknown","c3_objects":[],"action_verbs":[],'
            '"intents":[],"solution_rewrite":"","confidence":0.2}'
        )
        embedder = MagicMock()
        embedder.encode_single.return_value = [0.3] * 10
        embedder.encode.return_value = [[0.3] * 10] * 10
        retriever = MagicMock()
        retriever.search_collection.return_value = []
        chain = SemanticChain(
            backend=RawLLMBackend(llm, "{query}"),
            router=CollectionRouter(embedder),
            retriever=retriever,
        )
        _, weights = chain.run("vague query")
        # All weights should be ≤ max(0.2, 0.2*0.5) * some_factor — just assert <= 0.6
        assert all(w <= 0.6 for w in weights)
