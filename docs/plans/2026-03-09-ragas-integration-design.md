# RAGAS Integration Design

**Date**: 2026-03-09
**Status**: Approved

## Goal

Long-term integration of RAGAS evaluation framework into the project, replacing heuristic-only scoring with a hybrid evaluation system focused on generation quality.

## Directory Structure

```
src/evaluation/
├── __init__.py
├── dataset.py               # Ground truth dataset management
├── heuristic_evaluator.py   # Migrated from scripts/benchmark.py
├── ragas_evaluator.py       # RAGAS metrics (embedding + local LLM)
└── evaluate_ragas.py        # Standalone entry point (__main__ block)

data/
└── ragas_dataset.json       # Evaluation dataset (query + ground_truth + metadata)

scripts/
└── evaluate.py              # Thin entry: --heuristic / --ragas / --all
                             # (benchmark.py deprecated → thin wrapper)

tests/
└── test_evaluation.py       # Unit tests (fully mocked)
```

## Metrics Matrix

| # | Metric | Layer | Weight | Module | ground_truth | LLM |
|---|--------|-------|:------:|--------|:---:|:---:|
| 1 | Faithfulness | Generation | 20% | ragas | No | Yes (Qwen) |
| 2 | Answer Relevance | Generation | 20% | ragas | No | Yes (Qwen) |
| 3 | Answer Correctness | Generation | 20% | ragas | **Yes** | No (embedding) |
| 4 | Context Precision | Retrieval | 15% | ragas | No | No (embedding) |
| 5 | Context Recall | Retrieval | 10% | ragas | **Yes** | No (embedding) |
| 6 | Instruction Following | Format | 10% | heuristic | No | No |
| 7 | Citation Rate | Format | 3% | heuristic | No | No |
| 8 | Confidence Quality | Format | 2% | heuristic | No | No |
| 9 | Answer Completeness | Generation | — | ragas | Yes | No (embedding) |
| 10 | LookupEngine Hit Rate | Retrieval | — | heuristic | No | No |
| 11 | Collection Contribution | Retrieval | — | heuristic | No | No |
| 12 | End-to-End Latency | Performance | — | heuristic | No | No |

> `—` weight = diagnostic only, excluded from composite score

**Composite score**: 20+20+20+15+10+10+3+2 = 100%

## Data Model

```python
@dataclass
class MetricResult:
    name: str
    score: float          # 0.0 - 1.0
    weight: float         # 0 = diagnostic only
    details: dict         # raw data for debugging

@dataclass
class EvalResult:
    query_id: str
    query: str
    answer: str
    metrics: List[MetricResult]
    composite_score: float    # weighted composite
    grade: str                # A/B/C/D
    latency_ms: float
```

## Evaluator Interfaces

```python
class HeuristicEvaluator:
    def evaluate(self, query: str, response: RAGResponse,
                 case: dict) -> List[MetricResult]: ...

class RagasEvaluator:
    def evaluate(self, query: str, response: RAGResponse,
                 contexts: List[str], ground_truth: str) -> List[MetricResult]: ...
```

## Dataset Format (`data/ragas_dataset.json`)

```json
[
  {
    "id": "B01",
    "query": "...",
    "ground_truth": "...",
    "expected_keywords": [...],
    "category": "workflow"
  }
]
```

## Ground Truth Generation Workflow

```bash
# Step 1: LLM generates draft ground truth for all 15 cases
python scripts/evaluate.py --generate-ground-truth

# Step 2: Human review and edit data/ragas_dataset.json

# Step 3: Run full evaluation
python scripts/evaluate.py --all
```

## CLI Usage

```bash
python scripts/evaluate.py --heuristic    # Original benchmark behavior
python scripts/evaluate.py --ragas        # RAGAS evaluation only
python scripts/evaluate.py --all          # Both, with comparison output
python scripts/evaluate.py --generate-ground-truth  # Bootstrap dataset

python -m src.evaluation.evaluate_ragas   # Direct module run
```

## Migration Path

1. `scripts/benchmark.py` → deprecated, becomes thin wrapper calling `src/evaluation/runner.py`
2. Keyword coverage metric → replaced by Answer Relevance (semantic)
3. Hallucination penalty → replaced by Faithfulness
4. Citation rate & Confidence quality → retained (no RAGAS equivalent)

## Dependencies to Add

```
ragas>=0.1.0
```

LLM judge: local Qwen3.5-9B via existing `LLMClient`.
Embedding judge: existing `BAAI/bge-m3` via `EmbeddingModel`.
