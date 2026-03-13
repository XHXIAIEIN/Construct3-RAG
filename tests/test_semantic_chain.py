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
