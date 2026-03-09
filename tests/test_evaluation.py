from src.evaluation import MetricResult, EvalResult
from src.evaluation.dataset import EvalDataset, EvalCase
from unittest.mock import MagicMock
from src.evaluation.heuristic_evaluator import HeuristicEvaluator
from src.evaluation.ragas_evaluator import RagasEvaluator
from src.evaluation.runner import EvaluationRunner
from src.rag.chain import RAGResponse


def _mock_response(answer: str, confidence: str = "high") -> RAGResponse:
    return RAGResponse(answer=answer, sources=[], query_type="qa",
                       confidence=confidence)


def _make_case(**kwargs) -> EvalCase:
    defaults = dict(id="B01", query="q", ground_truth="", expected_keywords=[],
                    category="概念", forbidden_phrases=[], has_answer=True, note="")
    defaults.update(kwargs)
    return EvalCase(**defaults)


def test_metric_result_fields():
    m = MetricResult(name="faithfulness", score=0.8, weight=0.2, details={})
    assert m.name == "faithfulness"
    assert m.score == 0.8
    assert m.weight == 0.2


def test_eval_result_composite_score():
    metrics = [
        MetricResult("faithfulness", score=0.9, weight=0.2, details={}),
        MetricResult("answer_relevance", score=0.7, weight=0.2, details={}),
        MetricResult("answer_correctness", score=0.8, weight=0.2, details={}),
        MetricResult("context_precision", score=0.6, weight=0.15, details={}),
        MetricResult("context_recall", score=0.5, weight=0.10, details={}),
        MetricResult("instruction_following", score=1.0, weight=0.10, details={}),
        MetricResult("citation_rate", score=0.8, weight=0.03, details={}),
        MetricResult("confidence_quality", score=1.0, weight=0.02, details={}),
    ]
    result = EvalResult(query_id="B01", query="q", answer="a",
                        metrics=metrics, latency_ms=1000.0)
    # 0.9*0.2 + 0.7*0.2 + 0.8*0.2 + 0.6*0.15 + 0.5*0.10 + 1.0*0.10 + 0.8*0.03 + 1.0*0.02
    # = 0.18 + 0.14 + 0.16 + 0.09 + 0.05 + 0.10 + 0.024 + 0.02 = 0.764
    assert abs(result.composite_score - 0.764) < 0.001


def test_eval_result_grade():
    def make_result(score):
        m = MetricResult("x", score=score, weight=1.0, details={})
        return EvalResult("B01", "q", "a", [m], latency_ms=0)

    assert make_result(0.85).grade == "A"
    assert make_result(0.75).grade == "B"
    assert make_result(0.55).grade == "C"
    assert make_result(0.30).grade == "D"


def test_diagnostic_metrics_excluded_from_composite():
    metrics = [
        MetricResult("answer_correctness", score=0.8, weight=1.0, details={}),
        MetricResult("latency_ms", score=0.0, weight=0.0, details={}),
    ]
    result = EvalResult("B01", "q", "a", metrics, latency_ms=500)
    assert abs(result.composite_score - 0.8) < 0.001


# ── Task 2: Dataset ───────────────────────────────────────────────────────────

def test_dataset_loads_from_json(tmp_path):
    import json
    data = [{"id": "B01", "query": "q1", "ground_truth": "",
             "expected_keywords": ["kw1"], "category": "概念",
             "forbidden_phrases": [], "has_answer": True, "note": ""}]
    f = tmp_path / "dataset.json"
    f.write_text(json.dumps(data), encoding="utf-8")

    ds = EvalDataset.load(f)
    assert len(ds.cases) == 1
    assert ds.cases[0].id == "B01"
    assert ds.cases[0].query == "q1"


def test_dataset_get_by_id(tmp_path):
    import json
    data = [{"id": "B01", "query": "q1", "ground_truth": "",
             "expected_keywords": [], "category": "概念",
             "forbidden_phrases": [], "has_answer": True, "note": ""}]
    f = tmp_path / "dataset.json"
    f.write_text(json.dumps(data), encoding="utf-8")

    ds = EvalDataset.load(f)
    case = ds.get("B01")
    assert case is not None
    assert case.query == "q1"
    assert ds.get("B99") is None


# ── Task 3: HeuristicEvaluator ────────────────────────────────────────────────

def test_heuristic_keyword_hit():
    ev = HeuristicEvaluator()
    case = _make_case(expected_keywords=["Sprite", "动画"])
    resp = _mock_response("Sprite 是一种支持动画的对象。[来源: 1]")
    results = ev.evaluate("q", resp, case)
    kw = next(r for r in results if r.name == "keyword_coverage")
    assert kw.score == 1.0


def test_heuristic_keyword_miss():
    ev = HeuristicEvaluator()
    case = _make_case(expected_keywords=["Sprite", "动画", "碰撞"])
    resp = _mock_response("Sprite 是基础对象。[来源: 1]")
    results = ev.evaluate("q", resp, case)
    kw = next(r for r in results if r.name == "keyword_coverage")
    assert abs(kw.score - 1/3) < 0.01


def test_heuristic_citation_full():
    ev = HeuristicEvaluator()
    case = _make_case()
    resp = _mock_response("[来源: 1] 说明A。[来源: 2] 说明B。[来源: 3] 说明C。")
    results = ev.evaluate("q", resp, case)
    cite = next(r for r in results if r.name == "citation_rate")
    assert cite.score == 1.0


def test_heuristic_confidence_mapping():
    ev = HeuristicEvaluator()
    case = _make_case()
    for conf, expected in [("high", 1.0), ("medium", 0.6), ("low", 0.3), ("none", 0.0)]:
        resp = _mock_response("answer", confidence=conf)
        results = ev.evaluate("q", resp, case)
        conf_m = next(r for r in results if r.name == "confidence_quality")
        assert conf_m.score == expected, f"failed for {conf}"


def test_heuristic_instruction_following_with_citation():
    ev = HeuristicEvaluator()
    case = _make_case()
    resp = _mock_response("答案内容。[来源: 1][来源: 2][来源: 3]", confidence="high")
    results = ev.evaluate("q", resp, case)
    instr = next(r for r in results if r.name == "instruction_following")
    assert instr.score == 1.0


def test_heuristic_diagnostic_metrics_present():
    ev = HeuristicEvaluator()
    case = _make_case()
    resp = _mock_response("answer [来源: 1]", confidence="high")
    results = ev.evaluate("q", resp, case)
    names = {r.name for r in results}
    assert "latency_ms" in names
    assert "lookup_hit" in names
    for r in results:
        if r.name in ("latency_ms", "lookup_hit"):
            assert r.weight == 0.0


# ── Task 5: RagasEvaluator ────────────────────────────────────────────────────

def test_ragas_returns_expected_metric_names():
    import numpy as np
    ev = RagasEvaluator.__new__(RagasEvaluator)
    ev._embedder = None
    ev._llm = None

    resp = _mock_response("答案。[来源: 1]", confidence="high")

    # Patch all compute methods
    from unittest.mock import patch
    with patch.object(ev, '_compute_context_precision', return_value=0.8), \
         patch.object(ev, '_compute_context_recall', return_value=0.6), \
         patch.object(ev, '_compute_answer_correctness', return_value=0.7), \
         patch.object(ev, '_compute_answer_completeness', return_value=0.7), \
         patch.object(ev, '_compute_faithfulness', return_value=0.9), \
         patch.object(ev, '_compute_answer_relevance', return_value=0.85):
        results = ev.evaluate("q", resp, contexts=["ctx"], ground_truth="gt")

    names = {r.name for r in results}
    assert "context_precision" in names
    assert "context_recall" in names
    assert "faithfulness" in names
    assert "answer_relevance" in names
    assert "answer_correctness" in names
    assert "answer_completeness" in names


def test_ragas_metric_weights():
    ev = RagasEvaluator.__new__(RagasEvaluator)
    assert ev._metric_weight("faithfulness") == 0.20
    assert ev._metric_weight("answer_relevance") == 0.20
    assert ev._metric_weight("answer_correctness") == 0.20
    assert ev._metric_weight("context_precision") == 0.15
    assert ev._metric_weight("context_recall") == 0.10
    assert ev._metric_weight("answer_completeness") == 0.0  # diagnostic


def test_ragas_context_precision_perfect():
    import numpy as np
    ev = RagasEvaluator.__new__(RagasEvaluator)

    class MockEmbedder:
        def encode(self, texts):
            # Return identical vectors → cosine sim = 1.0
            return np.ones((len(texts), 3))

    ev._embedder = MockEmbedder()
    score = ev._compute_context_precision("q", ["ctx1", "ctx2"], threshold=0.5)
    assert score == 1.0


def test_ragas_context_precision_none_relevant():
    import numpy as np
    ev = RagasEvaluator.__new__(RagasEvaluator)

    call_count = [0]

    class MockEmbedder:
        def encode(self, texts):
            call_count[0] += 1
            if call_count[0] == 1:
                return np.array([[1.0, 0.0, 0.0]])   # query
            return np.zeros((len(texts), 3))           # contexts → sim=0

    ev._embedder = MockEmbedder()
    score = ev._compute_context_precision("q", ["ctx1", "ctx2"], threshold=0.5)
    assert score == 0.0


def test_ragas_answer_correctness_no_ground_truth():
    ev = RagasEvaluator.__new__(RagasEvaluator)
    ev._embedder = None
    score = ev._compute_answer_correctness("answer", "")
    assert score == 0.0


def test_ragas_faithfulness_no_llm():
    ev = RagasEvaluator.__new__(RagasEvaluator)
    ev._llm = None
    score = ev._compute_faithfulness("answer", ["ctx"])
    assert score == 0.0


def test_ragas_answer_completeness_is_diagnostic():
    import numpy as np
    ev = RagasEvaluator.__new__(RagasEvaluator)

    class MockEmbedder:
        def encode(self, texts):
            return np.ones((len(texts), 3))

    ev._embedder = MockEmbedder()
    resp = _mock_response("答案")
    from unittest.mock import patch
    with patch.object(ev, '_compute_context_precision', return_value=0.8), \
         patch.object(ev, '_compute_context_recall', return_value=0.6), \
         patch.object(ev, '_compute_answer_correctness', return_value=0.7), \
         patch.object(ev, '_compute_answer_completeness', return_value=0.5), \
         patch.object(ev, '_compute_faithfulness', return_value=0.0), \
         patch.object(ev, '_compute_answer_relevance', return_value=0.0):
        results = ev.evaluate("q", resp, contexts=["ctx"], ground_truth="gt")

    completeness = next(r for r in results if r.name == "answer_completeness")
    assert completeness.weight == 0.0


# ── Task 6: EvaluationRunner ──────────────────────────────────────────────────

def _make_mock_chain(answer="答案。[来源: 1][来源: 2][来源: 3]", confidence="high"):
    chain = MagicMock()
    chain.answer_smart.return_value = MagicMock(
        answer=answer, sources=["doc1"], query_type="qa", confidence=confidence,
    )
    chain.retriever = MagicMock()
    chain.retriever.search_all_with_rerank.return_value = []
    return chain


def test_runner_heuristic_mode(tmp_path):
    import json
    data = [{"id": "B01", "query": "Sprite 是什么？", "ground_truth": "",
             "expected_keywords": ["Sprite"], "category": "概念",
             "forbidden_phrases": [], "has_answer": True, "note": ""}]
    ds_path = tmp_path / "dataset.json"
    ds_path.write_text(json.dumps(data), encoding="utf-8")

    runner = EvaluationRunner(chain=_make_mock_chain(), dataset_path=ds_path)
    results = runner.run(mode="heuristic")
    assert len(results) == 1
    assert results[0].query_id == "B01"
    assert results[0].composite_score > 0


def test_runner_filters_by_ids(tmp_path):
    import json
    data = [
        {"id": "B01", "query": "q1", "ground_truth": "", "expected_keywords": [],
         "category": "概念", "forbidden_phrases": [], "has_answer": True, "note": ""},
        {"id": "B02", "query": "q2", "ground_truth": "", "expected_keywords": [],
         "category": "概念", "forbidden_phrases": [], "has_answer": True, "note": ""},
    ]
    ds_path = tmp_path / "dataset.json"
    ds_path.write_text(json.dumps(data), encoding="utf-8")

    runner = EvaluationRunner(chain=_make_mock_chain(), dataset_path=ds_path)
    results = runner.run(mode="heuristic", case_ids=["B01"])
    assert len(results) == 1
    assert results[0].query_id == "B01"


def test_runner_all_mode_merges_both_evaluators(tmp_path):
    import json
    data = [{"id": "B01", "query": "q", "ground_truth": "gt",
             "expected_keywords": [], "category": "概念",
             "forbidden_phrases": [], "has_answer": True, "note": ""}]
    ds_path = tmp_path / "dataset.json"
    ds_path.write_text(json.dumps(data), encoding="utf-8")

    mock_ragas = MagicMock()
    mock_ragas.evaluate.return_value = [
        MetricResult("faithfulness", 0.9, 0.20),
        MetricResult("answer_relevance", 0.8, 0.20),
        MetricResult("answer_correctness", 0.7, 0.20),
        MetricResult("context_precision", 0.6, 0.15),
        MetricResult("context_recall", 0.5, 0.10),
        MetricResult("answer_completeness", 0.7, 0.0),
    ]

    runner = EvaluationRunner(chain=_make_mock_chain(), dataset_path=ds_path,
                              ragas_evaluator=mock_ragas)
    results = runner.run(mode="all")
    assert len(results) == 1
    names = {r.name for r in results[0].metrics}
    assert "faithfulness" in names
    assert "instruction_following" in names  # from heuristic
    assert results[0].composite_score > 0
