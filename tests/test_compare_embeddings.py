"""Tests for embedding comparison script (no external services needed)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.compare_embeddings import (
    CaseScore,
    ModelReport,
    cosine_similarity,
    generate_comparison_report,
)


def test_cosine_similarity_identical():
    v = [1.0, 0.0, 0.0]
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(cosine_similarity(a, b)) < 1e-6


def test_cosine_similarity_opposite():
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    assert abs(cosine_similarity(a, b) - (-1.0)) < 1e-6


def test_model_report_avg():
    report = ModelReport(
        model_name="test", dimension=128, load_time_s=1.0, encode_time_s=0.5,
        scores=[
            CaseScore("A", "q1", "cat1", "easy", 0.8),
            CaseScore("B", "q2", "cat1", "hard", 0.6),
        ],
    )
    assert abs(report.avg_similarity - 0.7) < 1e-6
    assert abs(report.median_similarity - 0.7) < 1e-6


def test_model_report_by_category():
    report = ModelReport(
        model_name="test", dimension=128, load_time_s=0, encode_time_s=0,
        scores=[
            CaseScore("A", "q1", "lookup", "easy", 0.9),
            CaseScore("B", "q2", "lookup", "easy", 0.7),
            CaseScore("C", "q3", "general", "medium", 0.5),
        ],
    )
    by_cat = report.avg_by_category()
    assert abs(by_cat["lookup"] - 0.8) < 1e-6
    assert abs(by_cat["general"] - 0.5) < 1e-6


def test_model_report_by_difficulty():
    report = ModelReport(
        model_name="test", dimension=128, load_time_s=0, encode_time_s=0,
        scores=[
            CaseScore("A", "q1", "cat", "easy", 0.9),
            CaseScore("B", "q2", "cat", "hard", 0.3),
        ],
    )
    by_diff = report.avg_by_difficulty()
    assert abs(by_diff["easy"] - 0.9) < 1e-6
    assert abs(by_diff["hard"] - 0.3) < 1e-6


def test_generate_comparison_report_two_models():
    scores_a = [CaseScore("L001", "q1", "lookup", "easy", 0.80)]
    scores_b = [CaseScore("L001", "q1", "lookup", "easy", 0.85)]
    reports = [
        ModelReport("BAAI/bge-m3", 1024, 2.0, 1.0, scores_a),
        ModelReport("Qwen/Qwen3-Embedding-0.6B", 1024, 3.0, 1.5, scores_b),
    ]
    md = generate_comparison_report(reports)
    assert "Embedding Model Comparison" in md
    assert "bge-m3" in md
    assert "Qwen3-Embedding-0.6B" in md
    assert "Delta" in md
    assert "Per-Case" in md


def test_generate_comparison_report_single_model():
    scores = [CaseScore("L001", "q", "cat", "easy", 0.75)]
    reports = [ModelReport("BAAI/bge-m3", 1024, 1.0, 0.5, scores)]
    md = generate_comparison_report(reports)
    assert "bge-m3" in md
    # No Delta section for single model
    assert "Delta" not in md
