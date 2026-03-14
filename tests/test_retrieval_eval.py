"""Tests for retrieval evaluation logic (no external services needed)."""
import math
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation.dataset import EvalCase, EvalDataset


# ── Dataset loading ─────────────────────────────────────────────────────────

def test_eval_case_new_fields():
    """EvalCase accepts the new retrieval evaluation fields."""
    case = EvalCase(
        id="B01", query="test", ground_truth="",
        expected_sources=["plugin-reference/sprite.md"],
        expected_collections=["plugins"],
        retrieval_difficulty="easy",
    )
    assert case.expected_sources == ["plugin-reference/sprite.md"]
    assert case.expected_collections == ["plugins"]
    assert case.retrieval_difficulty == "easy"


def test_eval_case_defaults():
    """New fields default to empty when not provided."""
    case = EvalCase(id="X", query="q", ground_truth="")
    assert case.expected_sources == []
    assert case.expected_collections == []
    assert case.retrieval_difficulty == ""


def test_dataset_load_with_new_fields():
    """EvalDataset.load() handles files with new retrieval fields."""
    ds = EvalDataset.load()
    b01 = ds.get("B01")
    assert b01 is not None
    assert "plugin-reference/sprite.md" in b01.expected_sources
    assert "plugins" in b01.expected_collections
    assert b01.retrieval_difficulty == "easy"


def test_dataset_boundary_cases_no_sources():
    """Boundary cases (B14, B15) have empty expected_sources."""
    ds = EvalDataset.load()
    b14 = ds.get("B14")
    b15 = ds.get("B15")
    assert b14.expected_sources == []
    assert b15.expected_sources == []


# ── Source matching ─────────────────────────────────────────────────────────

from scripts.evaluate_retrieval import source_matches


def test_source_matches_exact():
    assert source_matches("plugin-reference/sprite.md", "plugin-reference/sprite.md")


def test_source_matches_backslash():
    assert source_matches("plugin-reference\\sprite.md", "plugin-reference/sprite.md")


def test_source_matches_case_insensitive():
    assert source_matches("Plugin-Reference/Sprite.md", "plugin-reference/sprite.md")


def test_source_matches_prefix():
    """Directory-level expected source matches deeper actual path."""
    assert source_matches(
        "scripting/scripting-reference/object-types.md",
        "scripting/scripting-reference",
    )


def test_source_no_match():
    assert not source_matches("behavior-reference/tween.md", "plugin-reference/sprite.md")


# ── Evaluation logic ────────────────────────────────────────────────────────

from scripts.evaluate_retrieval import evaluate_single, RetrievalResult
from src.rag.retriever import SearchResult


def _mock_retriever(results: list[SearchResult]):
    """Create a mock retriever returning fixed results."""
    retriever = MagicMock()
    retriever.search_all_with_rerank.return_value = results
    return retriever


def test_evaluate_perfect_recall():
    """All expected sources found -> recall=1.0, mrr=1.0, hit=True."""
    results = [
        SearchResult(
            text="Sprite is...",
            score=0.95,
            source="c3_plugins",
            metadata={"source": "plugin-reference/sprite.md"},
        ),
    ]
    case = EvalCase(
        id="B01", query="Sprite 是什么", ground_truth="",
        expected_sources=["plugin-reference/sprite.md"],
        expected_collections=["plugins"],
        retrieval_difficulty="easy",
    )
    r = evaluate_single(_mock_retriever(results), case)
    assert r.recall == 1.0
    assert r.mrr == 1.0
    assert r.hit is True
    assert r.sources_found == ["plugin-reference/sprite.md"]
    assert r.sources_missed == []


def test_evaluate_partial_recall():
    """Only 1 of 2 expected sources found -> recall=0.5."""
    results = [
        SearchResult(
            text="Keyboard...",
            score=0.9,
            source="c3_plugins",
            metadata={"source": "plugin-reference/keyboard.md"},
        ),
    ]
    case = EvalCase(
        id="B10", query="跳跃", ground_truth="",
        expected_sources=["plugin-reference/keyboard.md", "behavior-reference/platform.md"],
        expected_collections=["plugins", "behaviors"],
        retrieval_difficulty="hard",
    )
    r = evaluate_single(_mock_retriever(results), case)
    assert r.recall == 0.5
    assert r.hit is True
    assert "plugin-reference/keyboard.md" in r.sources_found
    assert "behavior-reference/platform.md" in r.sources_missed


def test_evaluate_zero_recall():
    """No expected sources found -> recall=0.0, hit=False."""
    results = [
        SearchResult(
            text="unrelated",
            score=0.7,
            source="c3_guide",
            metadata={"source": "getting-started/intro.md"},
        ),
    ]
    case = EvalCase(
        id="B01", query="Sprite", ground_truth="",
        expected_sources=["plugin-reference/sprite.md"],
        expected_collections=["plugins"],
        retrieval_difficulty="easy",
    )
    r = evaluate_single(_mock_retriever(results), case)
    assert r.recall == 0.0
    assert r.mrr == 0.0
    assert r.hit is False


def test_evaluate_no_expected_sources():
    """Boundary case with no expected sources -> recall=NaN."""
    results = [
        SearchResult(text="x", score=0.5, source="c3_guide", metadata={"source": "a.md"}),
    ]
    case = EvalCase(
        id="B15", query="r999", ground_truth="",
        expected_sources=[],
        retrieval_difficulty="hard",
    )
    r = evaluate_single(_mock_retriever(results), case)
    assert math.isnan(r.recall)
    assert math.isnan(r.mrr)


def test_mrr_second_rank():
    """Expected source at rank 2 -> MRR=0.5."""
    results = [
        SearchResult(text="other", score=0.95, source="c3_guide",
                     metadata={"source": "getting-started/intro.md"}),
        SearchResult(text="Sprite", score=0.9, source="c3_plugins",
                     metadata={"source": "plugin-reference/sprite.md"}),
    ]
    case = EvalCase(
        id="B01", query="Sprite", ground_truth="",
        expected_sources=["plugin-reference/sprite.md"],
        retrieval_difficulty="easy",
    )
    r = evaluate_single(_mock_retriever(results), case)
    assert r.mrr == 0.5
    assert r.hit is True


# ── Report generation ───────────────────────────────────────────────────────

from scripts.evaluate_retrieval import generate_report


def test_report_contains_summary():
    results = [
        RetrievalResult(
            case_id="B01", query="test", recall=1.0, mrr=1.0, hit=True,
            sources_found=["a.md"], difficulty="easy", latency_ms=100,
        ),
    ]
    report = generate_report(results, top_k=10)
    assert "Recall@10" in report
    assert "100%" in report
    assert "B01" in report
