from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass
class MetricResult:
    name: str
    score: float        # 0.0 – 1.0
    weight: float       # 0.0 = diagnostic only (excluded from composite)
    details: dict = field(default_factory=dict)


@dataclass
class EvalResult:
    query_id: str
    query: str
    answer: str
    metrics: List[MetricResult]
    latency_ms: float

    @property
    def composite_score(self) -> float:
        weighted = [m.score * m.weight for m in self.metrics if m.weight > 0]
        total_weight = sum(m.weight for m in self.metrics if m.weight > 0)
        if total_weight == 0:
            return 0.0
        return sum(weighted) / total_weight

    @property
    def grade(self) -> str:
        s = self.composite_score
        if s >= 0.8:
            return "A"
        elif s >= 0.6:
            return "B"
        elif s >= 0.4:
            return "C"
        return "D"
