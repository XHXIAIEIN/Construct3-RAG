from __future__ import annotations
import re
from typing import List

from src.evaluation import MetricResult
from src.evaluation.dataset import EvalCase
from src.rag.chain import RAGResponse

# Metric weights (weighted metrics must sum to 0.15 — heuristic portion)
_WEIGHTS = {
    "instruction_following": 0.10,
    "citation_rate":         0.03,
    "confidence_quality":    0.02,
    # diagnostic only (weight=0):
    "keyword_coverage":      0.0,
    "latency_ms":            0.0,
    "lookup_hit":            0.0,
    "collection_contribution": 0.0,
}

_NO_ANSWER_SIGNALS = ["未找到", "未提及", "文档", "没有", "无法"]
_CITATION_PATTERN = re.compile(
    r'\[来源[:：]\s*[\d,\s]+\]'    # [来源: 1] or [来源: 1,2]
    r'|来源[:：]\s*\[\d+\]'         # 来源: [1]
    r'|\[来源[:：]\s*\d+'           # [来源: 1 (unclosed)
    r'|参考资料\s*[\[【]\s*\d+'     # 参考资料 [1] or 参考资料【1】
    r'|\[资料[:：]?\s*\d+'          # [资料: 1] or [资料1]
)


def _score_keywords(answer: str, case: EvalCase) -> float:
    if not case.expected_keywords:
        if not case.has_answer:
            hits = sum(1 for s in _NO_ANSWER_SIGNALS if s in answer)
            return min(1.0, hits / 2)
        return 0.5
    lower = answer.lower()
    hits = sum(1 for kw in case.expected_keywords if kw.lower() in lower)
    return hits / len(case.expected_keywords)


def _score_citations(answer: str, case: EvalCase) -> float:
    if not case.has_answer:
        return 1.0 if any(s in answer for s in _NO_ANSWER_SIGNALS) else 0.3
    citations = _CITATION_PATTERN.findall(answer)
    if len(citations) >= 3:
        return 1.0
    elif len(citations) >= 1:
        return 0.6
    elif "[通用经验]" in answer:
        return 0.3
    return 0.0


def _score_confidence(confidence: str) -> float:
    return {"high": 1.0, "medium": 0.6, "low": 0.3,
            "none": 0.0, "unknown": 0.0}.get(confidence, 0.0)


def _score_instruction_following(answer: str, confidence: str, case: EvalCase) -> float:
    citation_ok = _score_citations(answer, case) >= 0.6
    confidence_ok = confidence in ("high", "medium", "low")
    return (0.7 if citation_ok else 0.0) + (0.3 if confidence_ok else 0.0)


class HeuristicEvaluator:
    def evaluate(
        self,
        query: str,
        response: RAGResponse,
        case: EvalCase,
        latency_ms: float = 0.0,
        lookup_hit: bool = False,
        collection_counts: dict | None = None,
    ) -> List[MetricResult]:
        answer = response.answer
        confidence = response.confidence

        return [
            MetricResult(
                name="instruction_following",
                score=_score_instruction_following(answer, confidence, case),
                weight=_WEIGHTS["instruction_following"],
            ),
            MetricResult(
                name="citation_rate",
                score=_score_citations(answer, case),
                weight=_WEIGHTS["citation_rate"],
            ),
            MetricResult(
                name="confidence_quality",
                score=_score_confidence(confidence),
                weight=_WEIGHTS["confidence_quality"],
            ),
            MetricResult(
                name="keyword_coverage",
                score=_score_keywords(answer, case),
                weight=0.0,
                details={"expected": case.expected_keywords},
            ),
            MetricResult(
                name="latency_ms",
                score=0.0,
                weight=0.0,
                details={"ms": latency_ms},
            ),
            MetricResult(
                name="lookup_hit",
                score=1.0 if lookup_hit else 0.0,
                weight=0.0,
            ),
            MetricResult(
                name="collection_contribution",
                score=0.0,
                weight=0.0,
                details={"counts": collection_counts or {}},
            ),
        ]
