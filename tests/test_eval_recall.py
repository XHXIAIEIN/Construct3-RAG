"""Tests for recall@K evaluation script (no external services needed)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.eval_recall import (
    RecallScore,
    RecallReport,
    _build_corpus_index,
    _search_topk,
    generate_recall_report,
)


def test_corpus_index_normalization():
    vecs = np.array([[3.0, 4.0], [0.0, 1.0]])
    normed = _build_corpus_index(vecs)
    norms = np.linalg.norm(normed, axis=1)
    np.testing.assert_allclose(norms, [1.0, 1.0], atol=1e-6)


def test_search_topk_identity():
    """Query identical to doc 0 should rank doc 0 first."""
    docs = np.array([[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]])
    normed = _build_corpus_index(docs)
    query = np.array([1.0, 0.0])
    result = _search_topk(query, normed, k=3)
    assert result[0] == 0


def test_search_topk_k_larger_than_corpus():
    docs = np.array([[1.0, 0.0], [0.0, 1.0]])
    normed = _build_corpus_index(docs)
    query = np.array([1.0, 0.0])
    result = _search_topk(query, normed, k=10)
    assert len(result) == 2
    assert result[0] == 0


def test_recall_at_k():
    scores = [
        RecallScore("A", "q1", "cat", "easy", rank=1),
        RecallScore("B", "q2", "cat", "easy", rank=3),
        RecallScore("C", "q3", "cat", "medium", rank=0),  # miss
        RecallScore("D", "q4", "cat", "medium", rank=8),
    ]
    report = RecallReport(
        model_name="test", dimension=128,
        load_time_s=0, encode_time_s=0,
        num_cases=4, num_documents=4,
        scores=scores, ks=[1, 3, 5, 10],
    )
    assert report.recall_at_k(1) == 0.25   # only A
    assert report.recall_at_k(3) == 0.50   # A + B
    assert report.recall_at_k(5) == 0.50   # A + B (D is rank 8)
    assert report.recall_at_k(10) == 0.75  # A + B + D (C is miss)


def test_mrr():
    scores = [
        RecallScore("A", "q1", "cat", "easy", rank=1),   # 1/1 = 1.0
        RecallScore("B", "q2", "cat", "easy", rank=2),   # 1/2 = 0.5
        RecallScore("C", "q3", "cat", "easy", rank=0),   # miss = 0.0
    ]
    report = RecallReport(
        model_name="test", dimension=128,
        load_time_s=0, encode_time_s=0,
        num_cases=3, num_documents=3,
        scores=scores, ks=[1, 5, 10],
    )
    assert abs(report.mrr() - 0.5) < 1e-6  # (1.0 + 0.5 + 0.0) / 3


def test_keyword_hit_rate():
    scores = [
        RecallScore("A", "q1", "cat", "easy", rank=1, keyword_hits=2, keyword_total=3),
        RecallScore("B", "q2", "cat", "easy", rank=2, keyword_hits=1, keyword_total=2),
    ]
    report = RecallReport(
        model_name="test", dimension=128,
        load_time_s=0, encode_time_s=0,
        num_cases=2, num_documents=2,
        scores=scores, ks=[10],
    )
    assert abs(report.keyword_hit_rate() - 0.6) < 1e-6  # 3/5


def test_recall_by_category():
    scores = [
        RecallScore("A", "q1", "lookup", "easy", rank=1),
        RecallScore("B", "q2", "lookup", "easy", rank=15),  # > 10
        RecallScore("C", "q3", "general", "medium", rank=5),
    ]
    report = RecallReport(
        model_name="test", dimension=128,
        load_time_s=0, encode_time_s=0,
        num_cases=3, num_documents=3,
        scores=scores, ks=[10],
    )
    by_cat = report.recall_at_k_by_category(10)
    assert abs(by_cat["lookup"] - 0.5) < 1e-6   # 1/2
    assert abs(by_cat["general"] - 1.0) < 1e-6   # 1/1


def test_generate_report_two_models():
    scores_a = [RecallScore("L001", "q1", "lookup", "easy", rank=3)]
    scores_b = [RecallScore("L001", "q1", "lookup", "easy", rank=1)]
    reports = [
        RecallReport("BAAI/bge-m3", 1024, 2.0, 1.0, 1, 1, scores_a, [1, 5, 10]),
        RecallReport("Qwen/Qwen3-Embedding-0.6B", 1024, 3.0, 1.5, 1, 1, scores_b, [1, 5, 10]),
    ]
    md = generate_recall_report(reports)
    assert "Recall@K" in md
    assert "bge-m3" in md
    assert "Qwen3-Embedding-0.6B" in md
    assert "Delta" in md
    assert "Per-Case" in md


def test_generate_report_single_model():
    scores = [RecallScore("L001", "q", "cat", "easy", rank=2)]
    reports = [RecallReport("BAAI/bge-m3", 1024, 1.0, 0.5, 1, 1, scores, [1, 5, 10])]
    md = generate_recall_report(reports)
    assert "bge-m3" in md
    assert "Delta" not in md
