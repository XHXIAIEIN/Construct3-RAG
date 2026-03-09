# RAGAS Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate RAGAS evaluation framework into `src/evaluation/`, replacing `scripts/benchmark.py` with a unified evaluation system that measures generation quality across 12 metrics.

**Architecture:** Three-layer design — `HeuristicEvaluator` (format/rule-based metrics, migrated from benchmark.py) and `RagasEvaluator` (embedding + local LLM judge) both produce `List[MetricResult]`, merged by `runner.py` into `EvalResult`. CLI entry via `src/evaluation/evaluate_ragas.py` and thin wrapper `scripts/evaluate.py`.

**Tech Stack:** Python 3.14, ragas>=0.2.0, existing BAAI/bge-m3 embeddings, existing LLMClient (Qwen3.5-9B), Qdrant.

---

## Prerequisites

```bash
# Verify Python path
/c/Users/test/AppData/Local/Python/bin/python.exe --version   # Python 3.14

# Run existing tests to confirm baseline
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/ -v --tb=short
```

---

## Task 1: Data Models

**Files:**
- Create: `src/evaluation/__init__.py`
- Test: `tests/test_evaluation.py` (new file)

**Step 1: Write failing tests**

```python
# tests/test_evaluation.py
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
    # Diagnostic metrics (weight=0) must not affect composite score
    metrics = [
        MetricResult("answer_correctness", score=0.8, weight=1.0, details={}),
        MetricResult("latency_ms", score=0.0, weight=0.0, details={}),  # diagnostic
    ]
    result = EvalResult("B01", "q", "a", metrics, latency_ms=500)
    assert abs(result.composite_score - 0.8) < 0.001
```

**Step 2: Run test to verify it fails**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_evaluation.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.evaluation'`

**Step 3: Implement `src/evaluation/__init__.py`**

```python
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
        weighted = [(m.score * m.weight) for m in self.metrics if m.weight > 0]
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
```

**Step 4: Run tests to verify they pass**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_evaluation.py -v
```

Expected: 4 PASSED

**Step 5: Commit**

```bash
git add src/evaluation/__init__.py tests/test_evaluation.py
git commit -m "feat: add evaluation data models (MetricResult, EvalResult)"
```

---

## Task 2: Evaluation Dataset

**Files:**
- Create: `data/ragas_dataset.json`
- Create: `src/evaluation/dataset.py`

**Step 1: Write failing tests**

Add to `tests/test_evaluation.py`:

```python
from src.evaluation.dataset import EvalDataset, EvalCase


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
```

**Step 2: Run tests to verify they fail**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_evaluation.py::test_dataset_loads_from_json tests/test_evaluation.py::test_dataset_get_by_id -v
```

Expected: `ModuleNotFoundError: No module named 'src.evaluation.dataset'`

**Step 3: Create `data/ragas_dataset.json`**

Seed from existing BENCHMARK_CASES (no ground_truth yet — generated later):

```json
[
  {"id":"B01","query":"Sprite 对象是什么？它的主要用途是什么？","ground_truth":"","expected_keywords":["Sprite","图像","动画","精灵","碰撞"],"category":"概念","forbidden_phrases":[],"has_answer":true,"note":"基础插件概念"},
  {"id":"B02","query":"事件表（Event Sheet）是什么？","ground_truth":"","expected_keywords":["事件","条件","动作","表达式"],"category":"概念","forbidden_phrases":[],"has_answer":true,"note":"核心概念"},
  {"id":"B03","query":"实例变量和全局变量的区别是什么？","ground_truth":"","expected_keywords":["实例","全局","静态","作用域"],"category":"概念","forbidden_phrases":[],"has_answer":true,"note":"变量作用域"},
  {"id":"B04","query":"平台(Platform) 行为有哪些主要参数？","ground_truth":"","expected_keywords":["平台","最大移动速度","加速度","减速度","重力","跳跃高度","最大下落速度","跳跃维持","二段跳"],"category":"插件","forbidden_phrases":[],"has_answer":true,"note":"Platform 行为配置"},
  {"id":"B05","query":"补间(Tween) 行为怎么用？如何让对象移动到指定位置？","ground_truth":"","expected_keywords":["补间","两个参数","位置","过渡","时间","曲线"],"category":"插件","forbidden_phrases":[],"has_answer":true,"note":"Tween 行为用法"},
  {"id":"B06","query":"键盘(Keyboard) 插件如何检测按键？按住(on key pressed) 和按下(is key down) 的区别？","ground_truth":"","expected_keywords":["键盘","按键","按键码","按住","按下","持续","单次"],"category":"插件","forbidden_phrases":[],"has_answer":true,"note":"输入检测差异"},
  {"id":"B07","query":"系统(System) 对象的遍历(For each) 条件如何使用？","ground_truth":"","expected_keywords":["条件","循环","遍历","对象","实例","范围","跳出","loopindex"],"category":"系统","forbidden_phrases":[],"has_answer":true,"note":"循环遍历对象"},
  {"id":"B08","query":"如何在 Construct 3 中实现计时器？","ground_truth":"","expected_keywords":["计时","正在计时","计时结束","遍历"],"category":"系统","forbidden_phrases":[],"has_answer":true,"note":"计时器实现方式"},
  {"id":"B09","query":"等待信号(Wait for signal) 和 等待X秒(Wait X seconds) 有什么区别？","ground_truth":"","expected_keywords":["信号","异步","秒","时间","等待"],"category":"系统","forbidden_phrases":[],"has_answer":true,"note":"等待机制"},
  {"id":"B10","query":"如何让玩家按空格键跳跃？并且播放跳跃动画？","ground_truth":"","expected_keywords":["键盘","空格","模拟控制","跳跃","平台","条件","正在跳跃","准备起跳","动画"],"category":"工作流","forbidden_phrases":[],"has_answer":true,"note":"经典平台游戏跳跃"},
  {"id":"B11","query":"如何实现碰撞检测？Sprite 和 Sprite 碰撞时触发事件","ground_truth":"","expected_keywords":["碰撞","重叠","家族"],"category":"工作流","forbidden_phrases":[],"has_answer":true,"note":"碰撞事件"},
  {"id":"B12","query":"如何用事件表实现分数系统？包括变量定义和 UI 更新","ground_truth":"","expected_keywords":["变量","分数","设置文本","动作组"],"category":"工作流","forbidden_phrases":[],"has_answer":true,"note":"分数系统工作流"},
  {"id":"B13","query":"在 Construct 3 脚本中如何获取一个对象的实例？","ground_truth":"","expected_keywords":["runtime","objects","getInstance","getInstanceByUid","getFirstInstance","getAllInstances","getPickedInstances","getPairedInstance"],"category":"脚本","forbidden_phrases":[],"has_answer":true,"note":"脚本 API 基础"},
  {"id":"B14","query":"Construct 3 支持 WebGPU 渲染吗？有什么限制？","ground_truth":"","expected_keywords":[],"category":"边界","forbidden_phrases":["完全支持","没有限制"],"has_answer":false,"note":"边界知识，防止幻觉"},
  {"id":"B15","query":"Construct 3 r999 版本有哪些新功能？","ground_truth":"","expected_keywords":[],"category":"边界","forbidden_phrases":["r999"],"has_answer":false,"note":"不存在的版本"}
]
```

**Step 4: Implement `src/evaluation/dataset.py`**

```python
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from src.config import DATA_DIR


DEFAULT_DATASET_PATH = Path(DATA_DIR) / "ragas_dataset.json"


@dataclass
class EvalCase:
    id: str
    query: str
    ground_truth: str
    expected_keywords: List[str] = field(default_factory=list)
    category: str = "general"
    forbidden_phrases: List[str] = field(default_factory=list)
    has_answer: bool = True
    note: str = ""


@dataclass
class EvalDataset:
    cases: List[EvalCase]

    @classmethod
    def load(cls, path: Path = DEFAULT_DATASET_PATH) -> "EvalDataset":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        cases = [EvalCase(**item) for item in raw]
        return cls(cases=cases)

    def save(self, path: Path = DEFAULT_DATASET_PATH) -> None:
        data = [vars(c) for c in self.cases]
        Path(path).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get(self, case_id: str) -> Optional[EvalCase]:
        return next((c for c in self.cases if c.id == case_id), None)

    def filter_by_category(self, category: str) -> "EvalDataset":
        return EvalDataset([c for c in self.cases if c.category == category])
```

**Step 5: Run tests to verify they pass**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_evaluation.py -v
```

Expected: 6 PASSED

**Step 6: Commit**

```bash
git add src/evaluation/dataset.py data/ragas_dataset.json tests/test_evaluation.py
git commit -m "feat: add evaluation dataset model and seed data"
```

---

## Task 3: HeuristicEvaluator

**Files:**
- Create: `src/evaluation/heuristic_evaluator.py`
- Modify: `tests/test_evaluation.py`

**Step 1: Write failing tests**

Add to `tests/test_evaluation.py`:

```python
from unittest.mock import MagicMock
from src.evaluation.heuristic_evaluator import HeuristicEvaluator
from src.evaluation.dataset import EvalCase
from src.rag.chain import RAGResponse


def _mock_response(answer: str, confidence: str = "high") -> RAGResponse:
    return RAGResponse(answer=answer, sources=[], query_type="qa",
                       confidence=confidence)


def _make_case(**kwargs) -> EvalCase:
    defaults = dict(id="B01", query="q", ground_truth="", expected_keywords=[],
                    category="概念", forbidden_phrases=[], has_answer=True, note="")
    defaults.update(kwargs)
    return EvalCase(**defaults)


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
    # diagnostic metrics have weight=0
    for r in results:
        if r.name in ("latency_ms", "lookup_hit"):
            assert r.weight == 0.0
```

**Step 2: Run tests to verify they fail**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_evaluation.py -k "heuristic" -v
```

Expected: `ModuleNotFoundError: No module named 'src.evaluation.heuristic_evaluator'`

**Step 3: Implement `src/evaluation/heuristic_evaluator.py`**

```python
from __future__ import annotations
import re
from typing import List

from src.evaluation import MetricResult
from src.evaluation.dataset import EvalCase
from src.rag.chain import RAGResponse

# Metric weights (must sum to 1.0 across all weighted metrics)
_WEIGHTS = {
    "instruction_following": 0.10,
    "citation_rate":         0.03,
    "confidence_quality":    0.02,
    # diagnostic only (weight=0):
    "keyword_coverage":      0.0,   # replaced by Answer Relevance (RAGAS)
    "latency_ms":            0.0,
    "lookup_hit":            0.0,
    "collection_contribution": 0.0,
}

_NO_ANSWER_SIGNALS = ["未找到", "未提及", "文档", "没有", "无法"]
_CITATION_PATTERN = re.compile(
    r'\[来源[:：]\s*[\d,\s]+\]'
    r'|来源[:：]\s*\[\d+\]'
    r'|\[来源[:：]\s*\d+'
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
    """Combined format compliance: citations present + confidence declared."""
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
            # Diagnostic only
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
```

**Step 4: Run tests to verify they pass**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_evaluation.py -k "heuristic" -v
```

Expected: 7 PASSED

**Step 5: Commit**

```bash
git add src/evaluation/heuristic_evaluator.py tests/test_evaluation.py
git commit -m "feat: add HeuristicEvaluator (migrated from benchmark.py)"
```

---

## Task 4: Install RAGAS

**Files:**
- Modify: `requirements.txt`

**Step 1: Add dependency**

```
# Evaluation
ragas>=0.2.0
```

**Step 2: Install**

```bash
/c/Users/test/AppData/Local/Python/bin/pip install ragas>=0.2.0
```

**Step 3: Verify install**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -c "import ragas; print(ragas.__version__)"
```

Expected: prints version like `0.2.x`

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add ragas>=0.2.0 dependency"
```

---

## Task 5: RagasEvaluator

**Files:**
- Create: `src/evaluation/ragas_evaluator.py`
- Modify: `tests/test_evaluation.py`

**Step 1: Write failing tests**

Add to `tests/test_evaluation.py`:

```python
from unittest.mock import MagicMock, patch
from src.evaluation.ragas_evaluator import RagasEvaluator
from src.rag.chain import RAGResponse


def test_ragas_evaluator_embedding_metrics_no_ground_truth():
    """Context Precision should work without ground_truth."""
    ev = RagasEvaluator.__new__(RagasEvaluator)
    ev._embedder = MagicMock()
    ev._embedder.encode.return_value = [[0.1, 0.2, 0.3]]
    ev._llm = None

    resp = _mock_response("答案。[来源: 1]", confidence="high")
    contexts = ["相关文档内容A", "相关文档内容B"]

    with patch.object(ev, '_compute_context_precision', return_value=0.8), \
         patch.object(ev, '_compute_context_recall', return_value=0.0), \
         patch.object(ev, '_compute_answer_correctness', return_value=0.0), \
         patch.object(ev, '_compute_answer_completeness', return_value=0.0), \
         patch.object(ev, '_compute_faithfulness', return_value=0.9), \
         patch.object(ev, '_compute_answer_relevance', return_value=0.85):
        results = ev.evaluate("q", resp, contexts=contexts, ground_truth="")

    names = {r.name for r in results}
    assert "context_precision" in names
    assert "faithfulness" in names
    assert "answer_relevance" in names


def test_ragas_metrics_have_correct_weights():
    """Verify metric weights sum to RAGAS portion (0.85 total with heuristic 0.15)."""
    ev = RagasEvaluator.__new__(RagasEvaluator)
    # All 8 weighted RAGAS metrics
    expected_weights = {
        "faithfulness": 0.20,
        "answer_relevance": 0.20,
        "answer_correctness": 0.20,
        "context_precision": 0.15,
        "context_recall": 0.10,
    }
    for name, weight in expected_weights.items():
        assert ev._metric_weight(name) == weight


def test_ragas_context_precision_perfect():
    """All contexts relevant → precision = 1.0."""
    ev = RagasEvaluator.__new__(RagasEvaluator)
    ev._embedder = MagicMock()
    # Simulate high similarity: query embedding ≈ context embeddings
    import numpy as np
    query_vec = np.array([1.0, 0.0, 0.0])
    context_vecs = np.array([[1.0, 0.0, 0.0], [0.99, 0.1, 0.0]])
    ev._embedder.encode.side_effect = [
        query_vec.reshape(1, -1),
        context_vecs,
    ]
    score = ev._compute_context_precision("q", ["ctx1", "ctx2"], threshold=0.5)
    assert score >= 0.9
```

**Step 2: Run tests to verify they fail**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_evaluation.py -k "ragas" -v
```

Expected: `ModuleNotFoundError: No module named 'src.evaluation.ragas_evaluator'`

**Step 3: Implement `src/evaluation/ragas_evaluator.py`**

```python
"""
RAGAS-based evaluation metrics.

Embedding metrics (no LLM needed):
  - context_precision    (embedding cosine similarity)
  - context_recall       (embedding coverage vs ground_truth)
  - answer_correctness   (embedding similarity answer vs ground_truth)
  - answer_completeness  (diagnostic, embedding coverage)

LLM-judge metrics (uses local Qwen3.5-9B):
  - faithfulness         (answer grounded in contexts?)
  - answer_relevance     (answer addresses the question?)
"""
from __future__ import annotations
import logging
from typing import List, Optional

import numpy as np

from src.evaluation import MetricResult
from src.rag.chain import RAGResponse

logger = logging.getLogger(__name__)

_METRIC_WEIGHTS = {
    "faithfulness":          0.20,
    "answer_relevance":      0.20,
    "answer_correctness":    0.20,
    "context_precision":     0.15,
    "context_recall":        0.10,
    "answer_completeness":   0.0,   # diagnostic only
}

_FAITHFULNESS_PROMPT = """你是一个评估助手。判断以下回答是否完全基于给定的参考文档，没有编造文档中没有的信息。

参考文档：
{contexts}

回答：
{answer}

请只回答：1（完全基于文档）或 0（包含文档外的信息）。"""

_RELEVANCE_PROMPT = """你是一个评估助手。判断以下回答是否针对了给定的问题（没有跑题或答非所问）。

问题：{query}
回答：{answer}

请给出 0.0 到 1.0 的评分（1.0=完全针对问题，0.0=完全跑题）。只输出数字。"""


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class RagasEvaluator:
    def __init__(self, embedder=None, llm=None):
        self._embedder = embedder
        self._llm = llm

    def _metric_weight(self, name: str) -> float:
        return _METRIC_WEIGHTS.get(name, 0.0)

    def _embed(self, texts: list[str]) -> np.ndarray:
        vecs = self._embedder.encode(texts)
        return np.array(vecs)

    def _compute_context_precision(
        self, query: str, contexts: list[str], threshold: float = 0.4
    ) -> float:
        if not contexts:
            return 0.0
        q_vec = self._embed([query])[0]
        c_vecs = self._embed(contexts)
        sims = [_cosine_similarity(q_vec, cv) for cv in c_vecs]
        relevant = sum(1 for s in sims if s >= threshold)
        return relevant / len(contexts)

    def _compute_context_recall(
        self, contexts: list[str], ground_truth: str
    ) -> float:
        if not ground_truth or not contexts:
            return 0.0
        gt_vec = self._embed([ground_truth])[0]
        c_vecs = self._embed(contexts)
        sims = [_cosine_similarity(gt_vec, cv) for cv in c_vecs]
        return min(1.0, max(sims))

    def _compute_answer_correctness(
        self, answer: str, ground_truth: str
    ) -> float:
        if not ground_truth:
            return 0.0
        a_vec = self._embed([answer])[0]
        gt_vec = self._embed([ground_truth])[0]
        return max(0.0, _cosine_similarity(a_vec, gt_vec))

    def _compute_answer_completeness(
        self, answer: str, ground_truth: str
    ) -> float:
        return self._compute_answer_correctness(answer, ground_truth)

    def _compute_faithfulness(
        self, answer: str, contexts: list[str]
    ) -> float:
        if not self._llm or not contexts:
            return 0.0
        ctx_text = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(contexts[:5]))
        prompt = _FAITHFULNESS_PROMPT.format(contexts=ctx_text, answer=answer[:800])
        try:
            out = self._llm.generate(prompt, max_tokens=10).strip()
            return 1.0 if out.startswith("1") else 0.0
        except Exception:
            logger.warning("Faithfulness LLM call failed", exc_info=True)
            return 0.0

    def _compute_answer_relevance(
        self, query: str, answer: str
    ) -> float:
        if not self._llm:
            return 0.0
        prompt = _RELEVANCE_PROMPT.format(query=query, answer=answer[:800])
        try:
            out = self._llm.generate(prompt, max_tokens=10).strip()
            return min(1.0, max(0.0, float(out)))
        except (ValueError, Exception):
            logger.warning("Answer relevance LLM call failed", exc_info=True)
            return 0.0

    def evaluate(
        self,
        query: str,
        response: RAGResponse,
        contexts: list[str],
        ground_truth: str = "",
    ) -> List[MetricResult]:
        answer = response.answer

        return [
            MetricResult(
                name="faithfulness",
                score=self._compute_faithfulness(answer, contexts),
                weight=self._metric_weight("faithfulness"),
            ),
            MetricResult(
                name="answer_relevance",
                score=self._compute_answer_relevance(query, answer),
                weight=self._metric_weight("answer_relevance"),
            ),
            MetricResult(
                name="answer_correctness",
                score=self._compute_answer_correctness(answer, ground_truth),
                weight=self._metric_weight("answer_correctness"),
            ),
            MetricResult(
                name="context_precision",
                score=self._compute_context_precision(query, contexts),
                weight=self._metric_weight("context_precision"),
            ),
            MetricResult(
                name="context_recall",
                score=self._compute_context_recall(contexts, ground_truth),
                weight=self._metric_weight("context_recall"),
            ),
            MetricResult(
                name="answer_completeness",
                score=self._compute_answer_completeness(answer, ground_truth),
                weight=0.0,  # diagnostic
            ),
        ]
```

**Step 4: Run tests to verify they pass**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_evaluation.py -k "ragas" -v
```

Expected: 3 PASSED

**Step 5: Commit**

```bash
git add src/evaluation/ragas_evaluator.py tests/test_evaluation.py
git commit -m "feat: add RagasEvaluator with embedding + LLM-judge metrics"
```

---

## Task 6: Runner

**Files:**
- Create: `src/evaluation/runner.py`
- Modify: `tests/test_evaluation.py`

**Step 1: Write failing tests**

Add to `tests/test_evaluation.py`:

```python
from unittest.mock import MagicMock, patch
from src.evaluation.runner import EvaluationRunner


def test_runner_heuristic_mode(tmp_path):
    import json
    data = [{"id": "B01", "query": "Sprite 是什么？", "ground_truth": "",
             "expected_keywords": ["Sprite"], "category": "概念",
             "forbidden_phrases": [], "has_answer": True, "note": ""}]
    ds_path = tmp_path / "dataset.json"
    ds_path.write_text(json.dumps(data), encoding="utf-8")

    mock_chain = MagicMock()
    mock_chain.answer_smart.return_value = MagicMock(
        answer="Sprite 是基础对象。[来源: 1][来源: 2][来源: 3]",
        sources=["doc1"],
        query_type="qa",
        confidence="high",
    )
    mock_chain.retriever = MagicMock()
    mock_chain.retriever.search_all_with_rerank.return_value = []

    runner = EvaluationRunner(chain=mock_chain, dataset_path=ds_path)
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

    mock_chain = MagicMock()
    mock_chain.answer_smart.return_value = MagicMock(
        answer="答案。[来源: 1]", sources=[], query_type="qa", confidence="high")
    mock_chain.retriever = MagicMock()
    mock_chain.retriever.search_all_with_rerank.return_value = []

    runner = EvaluationRunner(chain=mock_chain, dataset_path=ds_path)
    results = runner.run(mode="heuristic", case_ids=["B01"])
    assert len(results) == 1
    assert results[0].query_id == "B01"
```

**Step 2: Run tests to verify they fail**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_evaluation.py -k "runner" -v
```

Expected: `ModuleNotFoundError: No module named 'src.evaluation.runner'`

**Step 3: Implement `src/evaluation/runner.py`**

```python
"""Evaluation runner: orchestrates heuristic + RAGAS evaluation."""
from __future__ import annotations
import logging
import time
from pathlib import Path
from typing import List, Optional

from src.evaluation import EvalResult, MetricResult
from src.evaluation.dataset import EvalDataset, EvalCase, DEFAULT_DATASET_PATH
from src.evaluation.heuristic_evaluator import HeuristicEvaluator
from src.evaluation.ragas_evaluator import RagasEvaluator
from src.rag.chain import RAGChain, RAGResponse

logger = logging.getLogger(__name__)


class EvaluationRunner:
    def __init__(
        self,
        chain: RAGChain,
        dataset_path: Path = DEFAULT_DATASET_PATH,
        ragas_evaluator: Optional[RagasEvaluator] = None,
    ):
        self._chain = chain
        self._dataset = EvalDataset.load(dataset_path)
        self._heuristic = HeuristicEvaluator()
        self._ragas = ragas_evaluator

    def run(
        self,
        mode: str = "all",          # "heuristic" | "ragas" | "all"
        case_ids: Optional[List[str]] = None,
        answer_mode: str = "smart", # "smart" | "high" | "stream"
    ) -> List[EvalResult]:
        cases = self._dataset.cases
        if case_ids:
            wanted = set(case_ids)
            cases = [c for c in cases if c.id in wanted]

        results = []
        for case in cases:
            logger.info("Evaluating %s: %s", case.id, case.query[:50])
            result = self._eval_case(case, mode, answer_mode)
            results.append(result)
        return results

    def _eval_case(
        self, case: EvalCase, mode: str, answer_mode: str
    ) -> EvalResult:
        t0 = time.time()
        response, contexts = self._get_response_and_contexts(case, answer_mode)
        latency_ms = (time.time() - t0) * 1000

        metrics: List[MetricResult] = []

        if mode in ("heuristic", "all"):
            metrics += self._heuristic.evaluate(
                case.query, response, case,
                latency_ms=latency_ms,
            )

        if mode in ("ragas", "all") and self._ragas is not None:
            metrics += self._ragas.evaluate(
                case.query, response,
                contexts=contexts,
                ground_truth=case.ground_truth,
            )

        return EvalResult(
            query_id=case.id,
            query=case.query,
            answer=response.answer,
            metrics=metrics,
            latency_ms=latency_ms,
        )

    def _get_response_and_contexts(
        self, case: EvalCase, answer_mode: str
    ) -> tuple[RAGResponse, list[str]]:
        # Retrieve raw contexts for RAGAS metrics
        search_results = self._chain.retriever.search_all_with_rerank(case.query)
        contexts = [r.text for r in search_results]

        try:
            if answer_mode == "high":
                response = self._chain.answer_high_confidence(case.query)
            elif answer_mode == "stream":
                chunks = list(self._chain.answer_stream(case.query))
                response = RAGResponse(
                    answer="".join(chunks),
                    sources=[], query_type="stream", confidence="unknown",
                )
            else:
                response = self._chain.answer_smart(case.query)
        except Exception as e:
            response = RAGResponse(
                answer=f"[ERROR] {e}",
                sources=[], query_type="error", confidence="none",
            )

        return response, contexts

    def generate_ground_truth(self, save: bool = True) -> EvalDataset:
        """Use LLM to draft ground truth for cases with empty ground_truth."""
        from src.rag.chain import RAGChain

        prompt_tpl = (
            "请根据你的知识，用1-3句话简洁回答以下关于 Construct 3 的问题。"
            "只输出答案，不要解释。\n\n问题：{query}"
        )

        for case in self._dataset.cases:
            if case.ground_truth:
                continue
            try:
                prompt = prompt_tpl.format(query=case.query)
                answer = self._chain.llm.generate(prompt, max_tokens=200)
                case.ground_truth = answer.strip()
                logger.info("Generated ground truth for %s", case.id)
            except Exception:
                logger.warning("Failed to generate ground truth for %s", case.id)

        if save:
            self._dataset.save()
        return self._dataset
```

**Step 4: Run tests to verify they pass**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_evaluation.py -k "runner" -v
```

Expected: 2 PASSED

**Step 5: Commit**

```bash
git add src/evaluation/runner.py tests/test_evaluation.py
git commit -m "feat: add EvaluationRunner with heuristic/ragas/all modes"
```

---

## Task 7: Report Generator

**Files:**
- Create: `src/evaluation/report.py`

**Step 1: Write failing test**

Add to `tests/test_evaluation.py`:

```python
from src.evaluation.report import generate_report


def test_report_contains_summary():
    metrics = [
        MetricResult("faithfulness", 0.9, 0.20),
        MetricResult("answer_relevance", 0.8, 0.20),
        MetricResult("answer_correctness", 0.7, 0.20),
        MetricResult("context_precision", 0.6, 0.15),
        MetricResult("context_recall", 0.5, 0.10),
        MetricResult("instruction_following", 1.0, 0.10),
        MetricResult("citation_rate", 0.8, 0.03),
        MetricResult("confidence_quality", 1.0, 0.02),
    ]
    results = [EvalResult("B01", "q1", "answer1", metrics, latency_ms=1200)]
    report = generate_report(results, mode="all")
    assert "综合得分" in report
    assert "B01" in report
    assert "faithfulness" in report
```

**Step 2: Run test to verify it fails**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_evaluation.py::test_report_contains_summary -v
```

**Step 3: Implement `src/evaluation/report.py`**

```python
"""Markdown report generation for evaluation results."""
from __future__ import annotations
from typing import List
from src.evaluation import EvalResult


def generate_report(results: List[EvalResult], mode: str = "all") -> str:
    if not results:
        return "# 无评估结果\n"

    total = len(results)
    avg_composite = sum(r.composite_score for r in results) / total
    avg_latency = sum(r.latency_ms for r in results) / total

    grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for r in results:
        grade_counts[r.grade] += 1

    # Collect all metric names (weighted only)
    all_metric_names = []
    seen = set()
    for r in results:
        for m in r.metrics:
            if m.weight > 0 and m.name not in seen:
                all_metric_names.append(m.name)
                seen.add(m.name)

    lines = [
        "# Construct 3 RAG 评估报告",
        "",
        f"**模式**: `{mode}` | **题数**: {total} | "
        f"**平均耗时**: {avg_latency:.0f}ms",
        "",
        "## 总体评分",
        "",
        "| 指标 | 平均分 | 权重 |",
        "|------|--------|------|",
    ]

    for name in all_metric_names:
        scores = []
        weight = 0.0
        for r in results:
            m = next((m for m in r.metrics if m.name == name), None)
            if m:
                scores.append(m.score)
                weight = m.weight
        if scores:
            avg = sum(scores) / len(scores)
            lines.append(f"| {name} | {avg:.2f} | {weight:.0%} |")

    lines += [
        f"| **综合得分** | **{avg_composite:.2f}** | — |",
        "",
        f"等级分布: A={grade_counts['A']} B={grade_counts['B']} "
        f"C={grade_counts['C']} D={grade_counts['D']}",
        "",
        "## 逐题结果",
        "",
        "| ID | 分类 | 综合 | 等级 | 耗时(ms) |",
        "|----|------|------|------|----------|",
    ]

    for r in results:
        lines.append(
            f"| {r.query_id} | — "
            f"| {r.composite_score:.2f} | {r.grade} "
            f"| {r.latency_ms:.0f} |"
        )

    lines += ["", "## 详细结果", ""]
    for r in results:
        lines += [
            f"### {r.query_id} [{r.grade}] {r.query}",
            "",
            f"**综合**: {r.composite_score:.2f} | **耗时**: {r.latency_ms:.0f}ms",
            "",
            "**指标明细**:",
            "",
        ]
        for m in sorted(r.metrics, key=lambda x: -x.weight):
            tag = "" if m.weight > 0 else " _(诊断)_"
            lines.append(f"- {m.name}: {m.score:.2f}{tag}")
        lines += ["", f"**回答**: {r.answer[:400]}", ""]

    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_evaluation.py::test_report_contains_summary -v
```

Expected: PASSED

**Step 5: Commit**

```bash
git add src/evaluation/report.py tests/test_evaluation.py
git commit -m "feat: add evaluation report generator"
```

---

## Task 8: CLI Entry Point

**Files:**
- Create: `src/evaluation/evaluate_ragas.py`
- Create: `scripts/evaluate.py`

**Step 1: Implement `src/evaluation/evaluate_ragas.py`**

```python
#!/usr/bin/env python3
"""
Construct 3 RAG Evaluation — unified entry point.

Usage:
    python -m src.evaluation.evaluate_ragas --heuristic
    python -m src.evaluation.evaluate_ragas --ragas
    python -m src.evaluation.evaluate_ragas --all
    python -m src.evaluation.evaluate_ragas --generate-ground-truth
    python -m src.evaluation.evaluate_ragas --cases B01,B08
    python -m src.evaluation.evaluate_ragas --output report.md
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import (QDRANT_HOST, QDRANT_PORT,
                        LLM_MODEL, LLM_BASE_URL, LLM_API_KEY, LLM_PROVIDER)
from src.rag.chain import RAGChain
from src.evaluation.runner import EvaluationRunner
from src.evaluation.ragas_evaluator import RagasEvaluator
from src.evaluation.report import generate_report


def build_ragas_evaluator(chain: RAGChain) -> RagasEvaluator:
    embedder = chain.retriever.embedder
    llm = chain.llm
    return RagasEvaluator(embedder=embedder, llm=llm)


def main():
    parser = argparse.ArgumentParser(description="Construct 3 RAG Evaluation")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--heuristic", action="store_true",
                       help="Run heuristic evaluation only (fast, no LLM judge)")
    group.add_argument("--ragas", action="store_true",
                       help="Run RAGAS evaluation only")
    group.add_argument("--all", action="store_true",
                       help="Run both heuristic + RAGAS (default)")
    group.add_argument("--generate-ground-truth", action="store_true",
                       help="Generate ground truth drafts using LLM")

    parser.add_argument("--mode", default="smart",
                        choices=["smart", "high", "stream"],
                        help="Answer mode: smart/high/stream (default: smart)")
    parser.add_argument("--cases", default="",
                        help="Comma-separated case IDs to run (e.g. B01,B08)")
    parser.add_argument("--output", default="",
                        help="Save report to file (default: print to stdout)")
    args = parser.parse_args()

    print("初始化 RAG 系统...")
    chain = RAGChain(
        qdrant_host=QDRANT_HOST, qdrant_port=QDRANT_PORT,
        llm_model=LLM_MODEL, llm_base_url=LLM_BASE_URL,
        llm_api_key=LLM_API_KEY, llm_provider=LLM_PROVIDER,
    )

    ragas_ev = None
    if args.ragas or args.all:
        ragas_ev = build_ragas_evaluator(chain)

    runner = EvaluationRunner(chain=chain, ragas_evaluator=ragas_ev)

    # Handle --generate-ground-truth
    if args.generate_ground_truth:
        print("生成 ground truth 草稿...")
        runner.generate_ground_truth(save=True)
        print("已保存到 data/ragas_dataset.json，请人工审核后修改。")
        return

    # Determine mode string
    if args.heuristic:
        mode = "heuristic"
    elif args.ragas:
        mode = "ragas"
    else:
        mode = "all"

    case_ids = [c.strip().upper() for c in args.cases.split(",") if c.strip()]

    print(f"评估模式: {mode} | 回答模式: {args.mode}")
    print("-" * 60)

    results = runner.run(mode=mode, case_ids=case_ids or None, answer_mode=args.mode)

    report = generate_report(results, mode=mode)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"报告已保存到: {args.output}")
    else:
        print(report)

    avg = sum(r.composite_score for r in results) / len(results) if results else 0
    print(f"\n综合得分: {avg:.2f}/1.00")


if __name__ == "__main__":
    main()
```

**Step 2: Implement `scripts/evaluate.py`** (thin wrapper)

```python
#!/usr/bin/env python3
"""Thin wrapper — delegates to src.evaluation.evaluate_ragas."""
import runpy, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
runpy.run_module("src.evaluation.evaluate_ragas", run_name="__main__", alter_sys=True)
```

**Step 3: Verify CLI runs (dry-run with --help)**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe scripts/evaluate.py --help
```

Expected: prints help with `--heuristic / --ragas / --all / --generate-ground-truth`

**Step 4: Commit**

```bash
git add src/evaluation/evaluate_ragas.py scripts/evaluate.py
git commit -m "feat: add CLI entry points (evaluate_ragas + scripts/evaluate.py)"
```

---

## Task 9: Deprecate benchmark.py

**Files:**
- Modify: `scripts/benchmark.py`
- Modify: `scripts/CLAUDE.md`

**Step 1: Replace `scripts/benchmark.py` with deprecation wrapper**

Replace the entire content of `scripts/benchmark.py` with:

```python
#!/usr/bin/env python3
"""
DEPRECATED: Use scripts/evaluate.py instead.

  python scripts/evaluate.py --heuristic --mode smart
  python scripts/evaluate.py --heuristic --mode smart --output report.md

This file is kept for backwards compatibility and delegates to the new
src/evaluation system.
"""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
warnings.warn(
    "benchmark.py is deprecated. Use: python scripts/evaluate.py --heuristic",
    DeprecationWarning, stacklevel=1,
)

# Translate legacy --mode flag into new CLI
args = sys.argv[1:]
new_args = ["--heuristic"]
for i, a in enumerate(args):
    if a == "--mode" and i + 1 < len(args):
        new_args += ["--mode", args[i + 1]]
    elif a == "--output" and i + 1 < len(args):
        new_args += ["--output", args[i + 1]]
    elif a == "--cases" and i + 1 < len(args):
        new_args += ["--cases", args[i + 1]]

sys.argv = [sys.argv[0]] + new_args

import runpy
runpy.run_module("src.evaluation.evaluate_ragas", run_name="__main__", alter_sys=True)
```

**Step 2: Update `scripts/CLAUDE.md`**

In the "Evaluation & Analysis" table, update the benchmark.py row:

```
| `benchmark.py` | **DEPRECATED** — use `evaluate.py`. Thin wrapper that calls `src/evaluation/` | `python scripts/benchmark.py --mode smart` |
| `evaluate.py` | Unified evaluation (heuristic + RAGAS). Replaces benchmark.py | `python scripts/evaluate.py --all` |
```

**Step 3: Commit**

```bash
git add scripts/benchmark.py scripts/CLAUDE.md
git commit -m "chore: deprecate benchmark.py, delegate to src/evaluation"
```

---

## Task 10: Run Full Test Suite

**Step 1: Run all tests**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/ -v --tb=short
```

Expected: all tests pass (including pre-existing test_chain.py, test_lookup.py)

**Step 2: Verify evaluation module summary**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_evaluation.py -v
```

Expected: ≥15 PASSED

**Step 3: Final commit**

```bash
git add .
git commit -m "test: verify full test suite passes after RAGAS integration"
```

---

## Post-Integration: Ground Truth Bootstrap

After integration is complete, generate and review ground truth:

```bash
# 1. Start services (Qdrant + LLM must be running)
./scripts/start-services.sh

# 2. Generate draft ground truth
/c/Users/test/AppData/Local/Python/bin/python.exe scripts/evaluate.py --generate-ground-truth

# 3. Review and edit data/ragas_dataset.json (fill in ground_truth fields)

# 4. Run full evaluation
/c/Users/test/AppData/Local/Python/bin/python.exe scripts/evaluate.py --all --output report.md
```

---

## Metric Weight Reference

| Metric | Weight | Module | Needs ground_truth | Needs LLM |
|--------|:------:|--------|:-----------------:|:---------:|
| faithfulness | 20% | ragas | No | Yes (Qwen) |
| answer_relevance | 20% | ragas | No | Yes (Qwen) |
| answer_correctness | 20% | ragas | **Yes** | No (embed) |
| context_precision | 15% | ragas | No | No (embed) |
| context_recall | 10% | ragas | **Yes** | No (embed) |
| instruction_following | 10% | heuristic | No | No |
| citation_rate | 3% | heuristic | No | No |
| confidence_quality | 2% | heuristic | No | No |
| answer_completeness | diag | ragas | Yes | No (embed) |
| keyword_coverage | diag | heuristic | No | No |
| latency_ms | diag | heuristic | No | No |
| lookup_hit | diag | heuristic | No | No |
