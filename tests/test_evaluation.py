from src.evaluation import MetricResult, EvalResult


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
