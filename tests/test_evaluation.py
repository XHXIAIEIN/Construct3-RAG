from src.evaluation import MetricResult, EvalResult
from src.evaluation.dataset import EvalDataset, EvalCase
from src.evaluation.heuristic_evaluator import HeuristicEvaluator
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
