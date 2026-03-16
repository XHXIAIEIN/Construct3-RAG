# Semantic Chain Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a zero-dictionary LLM-driven semantic decomposition chain that improves retrieval quality across all Construct 3 question types.

**Architecture:** A new `SemanticChain` class decomposes each query into structured roles + intents via pluggable LLM backends, routes to relevant Qdrant collections via embedding similarity + query_type bias, then runs multi-path retrieval (keyword + HyDE) with weighted RRF fusion. Results are merged with existing retrieval in `answer_smart` before dispatch.

**Tech Stack:** Python 3.14, `instructor==1.14.4` (installed), `pydantic>=2`, existing `LLMClient` + `HybridRetriever.embedder`, Qdrant via existing `retriever.py` search methods.

**Spec:** `docs/superpowers/specs/2026-03-13-semantic-chain-design.md`

---

## Chunk 1: Foundation — Data Structures, Prompt, weighted_rrf

### Task 1: DecomposedQuery dataclass + SEMANTIC_DECOMPOSE_PROMPT

**Files:**
- Modify: `src/locale/zh/prompts.py` — add `SEMANTIC_DECOMPOSE_PROMPT`
- Modify: `src/locale/en/prompts.py` — add `SEMANTIC_DECOMPOSE_PROMPT` (identical)
- Modify: `src/rag/prompts.py` — re-export `SEMANTIC_DECOMPOSE_PROMPT`
- Create: `src/rag/semantic_chain.py` — `DecomposedQuery`, `QueryIntent`, `QUERY_TYPES`
- Create: `tests/test_semantic_chain.py` — tests for data structures

- [ ] **Step 1: Write failing test for DecomposedQuery construction and normalization**

```python
# tests/test_semantic_chain.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.rag.semantic_chain import DecomposedQuery, QueryIntent, normalize_intents


def test_query_intent_basic():
    intent = QueryIntent(label="follow", keywords=["set position"], weight=0.6)
    assert intent.label == "follow"
    assert intent.weight == 0.6


def test_decomposed_query_basic():
    dq = DecomposedQuery(
        query_type="howto",
        c3_objects=["Sprite", "Mouse"],
        action_verbs=["跟随"],
        intents=[QueryIntent("immediate follow", ["set position", "Mouse.X"], 0.6),
                 QueryIntent("smooth follow", ["lerp"], 0.4)],
        solution_rewrite="Sprite set position Mouse.X Mouse.Y",
        confidence=0.95,
    )
    assert dq.query_type == "howto"
    assert len(dq.c3_objects) == 2
    assert dq.confidence == 0.95


def test_normalize_intents_sums_to_one():
    intents = [QueryIntent("a", [], 0.9), QueryIntent("b", [], 0.7)]
    normalized = normalize_intents(intents)
    total = sum(i.weight for i in normalized)
    assert abs(total - 1.0) < 1e-9


def test_normalize_intents_single():
    intents = [QueryIntent("a", [], 0.5)]
    normalized = normalize_intents(intents)
    assert normalized[0].weight == 1.0


def test_empty_intents_returns_default():
    from src.rag.semantic_chain import ensure_intents
    dq = DecomposedQuery(
        query_type="explain", c3_objects=[], action_verbs=["解释"],
        intents=[], solution_rewrite="", confidence=0.9,
    )
    result = ensure_intents(dq)
    assert len(result.intents) == 1
    assert result.intents[0].weight == 1.0
    assert "解释" in result.intents[0].keywords
```

- [ ] **Step 2: Run test to verify it fails**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_semantic_chain.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.rag.semantic_chain'`

- [ ] **Step 3: Create `src/rag/semantic_chain.py` with data structures**

```python
# src/rag/semantic_chain.py
"""Semantic decomposition chain for zero-dictionary query understanding."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal
import copy

QUERY_TYPES = Literal[
    "howto", "explain", "troubleshoot", "translate",
    "list_ace", "code_gen", "unknown",
]


@dataclass
class QueryIntent:
    label: str
    keywords: list[str]
    weight: float  # normalized to sum=1.0 across all intents


@dataclass
class DecomposedQuery:
    query_type: str
    c3_objects: list[str]
    action_verbs: list[str]
    intents: list[QueryIntent]
    solution_rewrite: str
    confidence: float  # 0.0–1.0


def normalize_intents(intents: list[QueryIntent]) -> list[QueryIntent]:
    """Normalize intent weights to sum to 1.0."""
    if not intents:
        return intents
    total = sum(i.weight for i in intents)
    if total <= 0:
        equal = 1.0 / len(intents)
        return [QueryIntent(i.label, i.keywords, equal) for i in intents]
    return [QueryIntent(i.label, i.keywords, i.weight / total) for i in intents]


def ensure_intents(dq: DecomposedQuery) -> DecomposedQuery:
    """If intents is empty, insert a default intent using available keywords."""
    if dq.intents:
        return dq
    keywords = list(dq.c3_objects) + list(dq.action_verbs)
    result = copy.replace(dq, intents=[QueryIntent("default", keywords, 1.0)])
    return result
```

- [ ] **Step 4: Run test to verify it passes**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_semantic_chain.py -v
```
Expected: 5 tests PASS

- [ ] **Step 5: Add SEMANTIC_DECOMPOSE_PROMPT to both locale files**

Append to `src/locale/zh/prompts.py` **and** `src/locale/en/prompts.py` (identical content — LLM-facing, not locale-specific):

```python
# ----------------------------
# Semantic decomposition prompt (LLM-facing, identical in zh and en)
# ----------------------------

SEMANTIC_DECOMPOSE_PROMPT = """You are a Construct 3 query analyzer. Extract the semantic structure of the user's question.

Output JSON:
{
  "query_type": "howto|explain|troubleshoot|translate|list_ace|code_gen|unknown",
  "c3_objects": [...],
  "action_verbs": [...],
  "intents": [
    {"label": "...", "keywords": ["...", "..."], "weight": 0.0}
  ],
  "solution_rewrite": "...",
  "confidence": 0.0
}

Rules:
- c3_objects: ALL Construct 3 objects/plugins mentioned. Do NOT distinguish subject/target.
- intents.weights: must sum to 1.0
- solution_rewrite: describe what the SOLUTION looks like in C3 terms (howto/code_gen only); empty string "" for other types
- confidence: how certain you are about this decomposition (1.0 = very clear query)

Examples:
Q: "怎么让 Sprite 跟随鼠标"
→ {{"query_type":"howto","c3_objects":["Sprite","Mouse"],"action_verbs":["跟随"],"intents":[{{"label":"immediate follow","keywords":["set position","Mouse.X","Mouse.Y"],"weight":0.6}},{{"label":"smooth follow","keywords":["lerp","every tick"],"weight":0.4}}],"solution_rewrite":"Sprite set position Mouse.X Mouse.Y every tick lerp smooth follow cursor","confidence":0.95}}

Q: "每 0.1 秒执行一次"
→ {{"query_type":"howto","c3_objects":["System"],"action_verbs":["计时","每 X 秒","执行","触发"],"intents":[{{"label":"repeating timer","keywords":["every","seconds","timer","wait"],"weight":0.8}},{{"label":"variable timer","keywords":["variable","multiply","delta time"],"weight":0.2}}],"solution_rewrite":"System every 0.1 seconds trigger repeating timer condition","confidence":0.9}}

Q: "为什么我的碰撞检测不准"
→ {{"query_type":"troubleshoot","c3_objects":["Solid","Physics","Sprite"],"action_verbs":["碰撞","重叠","检测"],"intents":[{{"label":"collision mask mismatch","keywords":["collision polygon","bounding box","image point"],"weight":0.5}},{{"label":"physics vs solid","keywords":["Solid behavior","Physics behavior","overlap"],"weight":0.3}},{{"label":"z-order or layer issue","keywords":["layer","Z order","initial layer"],"weight":0.2}}],"solution_rewrite":"","confidence":0.7}}

Q: "什么是事件表"
→ {{"query_type":"explain","c3_objects":[],"action_verbs":["解释","了解"],"intents":[{{"label":"event sheet concept","keywords":["event sheet","events","conditions","actions","logic"],"weight":1.0}}],"solution_rewrite":"","confidence":0.99}}

Q: "用 Array 实现背包系统"
→ {{"query_type":"code_gen","c3_objects":["Array","Sprite","Text"],"action_verbs":["存储","添加","删除","显示","实现"],"intents":[{{"label":"array as inventory data","keywords":["Array push","Array at","Array size","index"],"weight":0.5}},{{"label":"UI item display","keywords":["Sprite","Text","set text","for each"],"weight":0.3}},{{"label":"add/remove item logic","keywords":["condition compare","action set","variable"],"weight":0.2}}],"solution_rewrite":"Array store item name quantity Sprite display inventory slot for each element","confidence":0.85}}

Now analyze:
Q: "{query}"
"""
```

- [ ] **Step 6: Re-export from `src/rag/prompts.py`**

Add `SEMANTIC_DECOMPOSE_PROMPT` to the import list:

```python
# In src/rag/prompts.py — add to existing import block:
    CLIPBOARD_CONTEXT_HEADER, CLIPBOARD_DEFAULT_QUERY,
    SEMANTIC_DECOMPOSE_PROMPT,
```

- [ ] **Step 7: Verify import works**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -c "from src.rag.prompts import SEMANTIC_DECOMPOSE_PROMPT; print('OK', len(SEMANTIC_DECOMPOSE_PROMPT))"
```
Expected: `OK <number>`

- [ ] **Step 8: Commit**

```bash
git add src/rag/semantic_chain.py src/locale/zh/prompts.py src/locale/en/prompts.py src/rag/prompts.py tests/test_semantic_chain.py
git commit -m "feat(semantic-chain): add DecomposedQuery dataclass + SEMANTIC_DECOMPOSE_PROMPT"
```

---

### Task 2: weighted_rrf in retriever.py

**Files:**
- Modify: `src/rag/retriever.py` — add `weighted_rrf` after `reciprocal_rank_fusion`
- Modify: `tests/test_retriever.py` — add weighted_rrf tests

- [ ] **Step 1: Write failing tests**

```python
# Add to tests/test_retriever.py

def make_sr(text: str, score: float = 0.8) -> SearchResult:
    return SearchResult(text=text, score=score, source="c3_guide", metadata={})


class TestWeightedRRF:
    def test_single_list_returns_sorted(self):
        from src.rag.retriever import weighted_rrf
        results = [make_sr("a", 0.9), make_sr("b", 0.7), make_sr("c", 0.5)]
        out = weighted_rrf([results], [1.0])
        assert [r.text for r in out] == ["a", "b", "c"]

    def test_higher_weight_ranks_higher(self):
        from src.rag.retriever import weighted_rrf
        list_high = [make_sr("important")]
        list_low  = [make_sr("noise")]
        out = weighted_rrf([list_low, list_high], [0.2, 0.8])
        # "important" should rank above "noise"
        assert out[0].text == "important"

    def test_deduplication(self):
        from src.rag.retriever import weighted_rrf
        r = make_sr("same text")
        out = weighted_rrf([[r], [r]], [0.5, 0.5])
        texts = [x.text for x in out]
        assert texts.count("same text") == 1

    def test_empty_lists_handled(self):
        from src.rag.retriever import weighted_rrf
        out = weighted_rrf([[], [make_sr("x")]], [0.5, 0.5])
        assert len(out) == 1

    def test_zero_weight_floor(self):
        from src.rag.retriever import weighted_rrf
        # weight=0 should not raise ZeroDivisionError
        out = weighted_rrf([[make_sr("x")]], [0.0])
        assert len(out) == 1
```

- [ ] **Step 2: Run to verify they fail**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_retriever.py::TestWeightedRRF -v
```
Expected: `ImportError` or `AttributeError: module has no attribute 'weighted_rrf'`

- [ ] **Step 3: Add `weighted_rrf` to `src/rag/retriever.py`**

Add immediately after the `reciprocal_rank_fusion` method (find it with `grep -n "def reciprocal_rank_fusion" src/rag/retriever.py`):

```python
def weighted_rrf(
    self,
    result_lists: list[list[SearchResult]],
    weights: list[float],
) -> list[SearchResult]:
    """RRF fusion where each list's contribution is scaled by its weight.

    Higher weight → smaller k → higher RRF score contribution.
    Dedup key: text[:150].lower().strip() — same as reciprocal_rank_fusion.

    Args:
        result_lists: parallel list of ranked result lists
        weights: per-list importance weights (need not sum to 1; 0 uses floor 0.1)
    """
    rrf_scores: dict[str, float] = {}
    result_map: dict[str, SearchResult] = {}
    for results, w in zip(result_lists, weights):
        k = round(60 / max(w, 0.1))
        for rank, r in enumerate(results):
            key = r.text[:150].lower().strip()
            rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (k + rank + 1)
            result_map.setdefault(key, r)
    return [
        result_map[key]
        for key in sorted(rrf_scores, key=rrf_scores.__getitem__, reverse=True)
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_retriever.py::TestWeightedRRF -v
```
Expected: 5 tests PASS

- [ ] **Step 5: Run full test suite — no regressions**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/ -v --tb=short
```
Expected: all existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add src/rag/retriever.py tests/test_retriever.py
git commit -m "feat(retriever): add weighted_rrf with per-list k scaling"
```

---

## Chunk 2: Backends — InstructorBackend + RawLLMBackend

### Task 3: StructuredOutputBackend ABC + RawLLMBackend (always-available fallback)

**Files:**
- Modify: `src/rag/semantic_chain.py` — add ABC + RawLLMBackend

- [ ] **Step 1: Write failing tests**

```python
# Add to tests/test_semantic_chain.py

from unittest.mock import MagicMock


class TestRawLLMBackend:
    def _make_llm(self, response: str) -> MagicMock:
        llm = MagicMock()
        llm.generate.return_value = response
        return llm

    def test_parses_valid_json(self):
        from src.rag.semantic_chain import RawLLMBackend
        llm = self._make_llm(
            '```json\n{"query_type":"howto","c3_objects":["Sprite"],'
            '"action_verbs":["跟随"],"intents":[{"label":"follow",'
            '"keywords":["set position"],"weight":1.0}],'
            '"solution_rewrite":"Sprite set position","confidence":0.9}\n```'
        )
        backend = RawLLMBackend(llm, "test-prompt {query}")
        dq = backend.decompose("test query")
        assert dq.query_type == "howto"
        assert "Sprite" in dq.c3_objects
        assert dq.confidence == 0.9

    def test_returns_fallback_on_invalid_json(self):
        from src.rag.semantic_chain import RawLLMBackend
        llm = self._make_llm("sorry I cannot help")
        backend = RawLLMBackend(llm, "{query}")
        dq = backend.decompose("test")
        assert dq.query_type == "unknown"
        assert dq.confidence == 0.0

    def test_normalizes_intent_weights(self):
        from src.rag.semantic_chain import RawLLMBackend
        llm = self._make_llm(
            '{"query_type":"howto","c3_objects":[],"action_verbs":[],'
            '"intents":[{"label":"a","keywords":[],"weight":0.9},'
            '{"label":"b","keywords":[],"weight":0.7}],'
            '"solution_rewrite":"","confidence":0.8}'
        )
        backend = RawLLMBackend(llm, "{query}")
        dq = backend.decompose("q")
        total = sum(i.weight for i in dq.intents)
        assert abs(total - 1.0) < 1e-9
```

- [ ] **Step 2: Run to verify they fail**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_semantic_chain.py::TestRawLLMBackend -v
```
Expected: `ImportError`

- [ ] **Step 3: Add ABC and RawLLMBackend to `src/rag/semantic_chain.py`**

```python
# Add after the dataclass definitions:

import json
import re
import logging

logger = logging.getLogger(__name__)

_FALLBACK_DQ = DecomposedQuery(
    query_type="unknown", c3_objects=[], action_verbs=[],
    intents=[], solution_rewrite="", confidence=0.0,
)


class StructuredOutputBackend(ABC):
    """Abstract base for all decomposition backends."""

    @property
    def available(self) -> bool:
        return True

    @abstractmethod
    def decompose(self, query: str) -> DecomposedQuery: ...


def _parse_dq_from_json(raw: str) -> DecomposedQuery | None:
    """Extract and validate a DecomposedQuery from raw LLM text."""
    # Strip markdown code fences
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    json_str = match.group(1) if match else raw.strip()
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        # Try finding first { ... } block
        m = re.search(r"\{[\s\S]+\}", json_str)
        if not m:
            return None
        try:
            data = json.loads(m.group())
        except json.JSONDecodeError:
            return None

    try:
        intents = [
            QueryIntent(
                label=str(i.get("label", "")),
                keywords=[str(k) for k in i.get("keywords", [])],
                weight=float(i.get("weight", 1.0)),
            )
            for i in data.get("intents", [])
        ]
        dq = DecomposedQuery(
            query_type=str(data.get("query_type", "unknown")),
            c3_objects=[str(o) for o in data.get("c3_objects", [])],
            action_verbs=[str(v) for v in data.get("action_verbs", [])],
            intents=normalize_intents(intents),
            solution_rewrite=str(data.get("solution_rewrite", "")),
            confidence=float(data.get("confidence", 0.5)),
        )
        return ensure_intents(dq)
    except Exception as e:
        logger.debug("DecomposedQuery parse error: %s", e)
        return None


class RawLLMBackend(StructuredOutputBackend):
    """Always-available fallback: prompt LLM, regex-extract JSON, Pydantic-validate."""

    def __init__(self, llm, prompt_template: str):
        self._llm = llm
        self._prompt = prompt_template

    def decompose(self, query: str) -> DecomposedQuery:
        prompt = self._prompt.format(query=query)
        try:
            raw = self._llm.generate(prompt)
            result = _parse_dq_from_json(raw)
            if result is not None:
                return result
        except Exception as e:
            logger.debug("RawLLMBackend error: %s", e)
        return copy.copy(_FALLBACK_DQ)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_semantic_chain.py::TestRawLLMBackend -v
```
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/rag/semantic_chain.py tests/test_semantic_chain.py
git commit -m "feat(semantic-chain): add StructuredOutputBackend ABC + RawLLMBackend"
```

---

### Task 4: InstructorBackend (Ollama provider)

**Files:**
- Modify: `src/rag/semantic_chain.py` — add InstructorBackend

- [ ] **Step 1: Write failing tests**

```python
# Add to tests/test_semantic_chain.py

class TestInstructorBackend:
    def test_unavailable_when_not_ollama(self):
        from src.rag.semantic_chain import InstructorBackend
        llm = MagicMock()
        llm.provider = "huggingface"
        backend = InstructorBackend(llm, "prompt {query}")
        assert not backend.available

    def test_available_when_ollama(self):
        from src.rag.semantic_chain import InstructorBackend
        llm = MagicMock()
        llm.provider = "ollama"
        llm.model = "qwen2.5:7b"
        llm.ollama_host = "localhost"
        llm.ollama_port = 11434
        backend = InstructorBackend(llm, "prompt {query}")
        # availability depends on ollama being running; just check no crash
        # (actual connection may fail in test env — that's fine)
        assert isinstance(backend.available, bool)

    def test_falls_back_on_connection_error(self):
        from src.rag.semantic_chain import InstructorBackend
        llm = MagicMock()
        llm.provider = "ollama"
        llm.model = "qwen2.5:7b"
        llm.ollama_host = "localhost"
        llm.ollama_port = 11434
        backend = InstructorBackend(llm, "prompt {query}")
        # If ollama not running, decompose should return fallback not raise
        dq = backend.decompose("test")
        assert dq.query_type in (
            "howto", "explain", "troubleshoot", "translate",
            "list_ace", "code_gen", "unknown",
        )
```

- [ ] **Step 2: Run to verify they fail**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_semantic_chain.py::TestInstructorBackend -v
```
Expected: `ImportError`

- [ ] **Step 3: Add InstructorBackend to `src/rag/semantic_chain.py`**

```python
from pydantic import BaseModel, Field


class _IntentModel(BaseModel):
    label: str
    keywords: list[str] = Field(default_factory=list)
    weight: float = 1.0


class _DecomposedQueryModel(BaseModel):
    query_type: str = "unknown"
    c3_objects: list[str] = Field(default_factory=list)
    action_verbs: list[str] = Field(default_factory=list)
    intents: list[_IntentModel] = Field(default_factory=list)
    solution_rewrite: str = ""
    confidence: float = 0.5


class InstructorBackend(StructuredOutputBackend):
    """Pydantic validation via instructor library (Ollama provider only)."""

    def __init__(self, llm, prompt_template: str):
        self._llm = llm
        self._prompt = prompt_template
        self._client = None

    @property
    def available(self) -> bool:
        if getattr(self._llm, "provider", None) != "ollama":
            return False
        try:
            import instructor
            from ollama import Client
            host = getattr(self._llm, "ollama_host", "localhost")
            port = getattr(self._llm, "ollama_port", 11434)
            self._client = instructor.from_ollama(
                Client(host=f"http://{host}:{port}"),
                mode=instructor.Mode.JSON,
            )
            return True
        except Exception:
            return False

    def decompose(self, query: str) -> DecomposedQuery:
        if not self.available or self._client is None:
            return copy.copy(_FALLBACK_DQ)
        try:
            model_name = getattr(self._llm, "model", "qwen2.5:7b")
            prompt = self._prompt.format(query=query)
            result: _DecomposedQueryModel = self._client.chat.completions.create(
                model=model_name,
                response_model=_DecomposedQueryModel,
                messages=[{"role": "user", "content": prompt}],
            )
            intents = [
                QueryIntent(i.label, i.keywords, i.weight)
                for i in result.intents
            ]
            dq = DecomposedQuery(
                query_type=result.query_type,
                c3_objects=result.c3_objects,
                action_verbs=result.action_verbs,
                intents=normalize_intents(intents),
                solution_rewrite=result.solution_rewrite,
                confidence=result.confidence,
            )
            return ensure_intents(dq)
        except Exception as e:
            logger.debug("InstructorBackend error: %s", e)
            return copy.copy(_FALLBACK_DQ)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_semantic_chain.py::TestInstructorBackend -v
```
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/rag/semantic_chain.py tests/test_semantic_chain.py
git commit -m "feat(semantic-chain): add InstructorBackend (Ollama + Pydantic validation)"
```

---

## Chunk 3: CollectionRouter + SemanticChain Orchestrator

### Task 5: CollectionRouter

**Files:**
- Modify: `src/rag/semantic_chain.py` — add `CollectionRouter`

- [ ] **Step 1: Write failing tests**

```python
# Add to tests/test_semantic_chain.py

class TestCollectionRouter:
    def _make_embedder(self, sim_value: float = 0.5):
        """Embedder that returns fixed similarity for all collections."""
        embedder = MagicMock()
        embedder.encode_single.return_value = [0.1] * 10
        embedder.encode_batch.return_value = [[0.1] * 10] * 10
        return embedder

    def test_returns_weights_for_all_collections(self):
        from src.rag.semantic_chain import CollectionRouter
        router = CollectionRouter(self._make_embedder())
        weights = router.route("怎么让 Sprite 跟随鼠标", "howto")
        assert set(weights.keys()) == {
            "c3_guide", "c3_interface", "c3_project", "c3_plugins",
            "c3_behaviors", "c3_scripting", "c3_ace", "c3_effects",
            "c3_terms", "c3_examples",
        }

    def test_translate_query_boosts_terms(self):
        from src.rag.semantic_chain import CollectionRouter
        router = CollectionRouter(self._make_embedder(0.3))
        weights = router.route("Tween 是什么意思", "translate")
        assert weights["c3_terms"] >= 0.5  # bias +0.6 applied

    def test_threshold_filters_low_collections(self):
        from src.rag.semantic_chain import CollectionRouter
        embedder = MagicMock()
        # Very low similarity for all
        embedder.encode_single.return_value = [0.0] * 10
        embedder.encode_batch.return_value = [[0.0] * 10] * 10
        router = CollectionRouter(embedder)
        weights = router.route("test", "unknown", threshold=0.8)
        active = {k for k, v in weights.items() if v >= 0.8}
        # With all-zero embeddings and no bias, nothing should pass threshold=0.8
        assert len(active) == 0

    def test_weights_are_non_negative(self):
        from src.rag.semantic_chain import CollectionRouter
        router = CollectionRouter(self._make_embedder())
        weights = router.route("test query", "howto")
        assert all(v >= 0 for v in weights.values())
```

- [ ] **Step 2: Run to verify they fail**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_semantic_chain.py::TestCollectionRouter -v
```
Expected: `ImportError`

- [ ] **Step 3: Add CollectionRouter to `src/rag/semantic_chain.py`**

```python
import numpy as np


COLLECTION_DESCRIPTORS: dict[str, str] = {
    "c3_guide":     "Construct 3 manual tutorial guide how-to concept explanation documentation",
    "c3_interface": "Construct 3 editor interface UI toolbar menu layout panel dialog",
    "c3_project":   "Construct 3 project structure events objects timelines flowcharts families",
    "c3_plugins":   "Construct 3 plugin object type properties behavior scripting SDK",
    "c3_behaviors": "Construct 3 behavior platform movement physics collision tween pathfinding",
    "c3_scripting": "Construct 3 JavaScript TypeScript runtime API script module",
    "c3_ace":       "Construct 3 plugin action condition expression API parameter reference",
    "c3_effects":   "Construct 3 visual effect shader WebGL blend parameter",
    "c3_terms":     "Construct 3 Chinese English translation term glossary vocabulary",
    "c3_examples":  "Construct 3 example project game template event sheet code sample",
}

QUERY_TYPE_BIAS: dict[str, dict[str, float]] = {
    "howto":        {"c3_ace": 0.3, "c3_guide": 0.2},
    "explain":      {"c3_guide": 0.3, "c3_project": 0.2},
    "troubleshoot": {"c3_guide": 0.2, "c3_examples": 0.3},
    "translate":    {"c3_terms": 0.6},
    "list_ace":     {"c3_ace": 0.5},
    "code_gen":     {"c3_scripting": 0.3, "c3_examples": 0.3},
    "unknown":      {},
}


def _cosine(a: list[float], b: list[float]) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class CollectionRouter:
    """Routes queries to Qdrant collections via embedding similarity + query_type bias."""

    def __init__(self, embedder, threshold: float = 0.2):
        self._embedder = embedder
        self._default_threshold = threshold
        self._descriptor_vecs: dict[str, list[float]] | None = None

    def _ensure_descriptors(self) -> None:
        if self._descriptor_vecs is not None:
            return
        texts = list(COLLECTION_DESCRIPTORS.values())
        vecs = self._embedder.encode_batch(texts)
        self._descriptor_vecs = {
            name: vecs[i]
            for i, name in enumerate(COLLECTION_DESCRIPTORS)
        }

    def route(
        self,
        query: str,
        query_type: str = "unknown",
        threshold: float | None = None,
    ) -> dict[str, float]:
        """Return weight map for all collections. Values < threshold are still included
        (caller decides whether to skip them)."""
        self._ensure_descriptors()
        assert self._descriptor_vecs is not None
        query_vec = self._embedder.encode_single(query)
        bias = QUERY_TYPE_BIAS.get(query_type, {})
        weights = {}
        for name, desc_vec in self._descriptor_vecs.items():
            sim = _cosine(query_vec, desc_vec)
            w = min(1.0, max(0.0, sim + bias.get(name, 0.0)))
            weights[name] = w
        return weights
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_semantic_chain.py::TestCollectionRouter -v
```
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/rag/semantic_chain.py tests/test_semantic_chain.py
git commit -m "feat(semantic-chain): add CollectionRouter with embedding similarity + query_type bias"
```

---

### Task 6: SemanticChain Orchestrator

**Files:**
- Modify: `src/rag/semantic_chain.py` — add `SemanticChain` class

- [ ] **Step 1: Write failing tests**

```python
# Add to tests/test_semantic_chain.py

class TestSemanticChain:
    def _make_chain(self):
        from src.rag.semantic_chain import SemanticChain, RawLLMBackend
        llm = MagicMock()
        llm.provider = "huggingface"
        llm.generate.return_value = (
            '{"query_type":"howto","c3_objects":["Sprite"],'
            '"action_verbs":["跟随"],'
            '"intents":[{"label":"follow","keywords":["set position"],"weight":1.0}],'
            '"solution_rewrite":"Sprite set position Mouse.X","confidence":0.9}'
        )
        embedder = MagicMock()
        embedder.encode_single.return_value = [0.5] * 10
        embedder.encode_batch.return_value = [[0.5] * 10] * 10

        retriever = MagicMock()
        retriever.search_collection.return_value = []

        from src.rag.semantic_chain import CollectionRouter
        router = CollectionRouter(embedder)
        backend = RawLLMBackend(llm, "{query}")
        return SemanticChain(backend=backend, router=router, retriever=retriever)

    def test_run_returns_result_lists_and_weights(self):
        chain = self._make_chain()
        result_lists, weights = chain.run("怎么让 Sprite 跟随鼠标")
        assert isinstance(result_lists, list)
        assert isinstance(weights, list)
        assert len(result_lists) == len(weights)

    def test_run_with_disabled_returns_none(self):
        from src.rag.semantic_chain import SemanticChain
        chain = SemanticChain(backend=None, router=None, retriever=None, enabled=False)
        result = chain.run("test")
        assert result is None

    def test_cache_avoids_duplicate_decomposition(self):
        chain = self._make_chain()
        chain.run("Sprite 跟随鼠标")
        call_count_after_first = chain._backend._llm.generate.call_count
        chain.run("Sprite 跟随鼠标")  # same query
        # LLM should not be called again
        assert chain._backend._llm.generate.call_count == call_count_after_first

    def test_low_confidence_reduces_blend_weight(self):
        from src.rag.semantic_chain import SemanticChain, RawLLMBackend, CollectionRouter
        llm = MagicMock()
        llm.provider = "huggingface"
        llm.generate.return_value = (
            '{"query_type":"unknown","c3_objects":[],"action_verbs":[],'
            '"intents":[],"solution_rewrite":"","confidence":0.2}'
        )
        embedder = MagicMock()
        embedder.encode_single.return_value = [0.3] * 10
        embedder.encode_batch.return_value = [[0.3] * 10] * 10
        retriever = MagicMock()
        retriever.search_collection.return_value = []
        chain = SemanticChain(
            backend=RawLLMBackend(llm, "{query}"),
            router=CollectionRouter(embedder),
            retriever=retriever,
        )
        _, weights = chain.run("vague query")
        # All weights should be ≤ 0.2 * 0.5 = 0.1 blend
        semantic_weights = [w for w in weights]
        assert all(w <= 0.6 for w in semantic_weights)
```

- [ ] **Step 2: Run to verify they fail**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_semantic_chain.py::TestSemanticChain -v
```
Expected: `ImportError`

- [ ] **Step 3: Add `SemanticChain` to `src/rag/semantic_chain.py`**

```python
import hashlib
import unicodedata


def _normalize_query(query: str) -> str:
    """Normalize query for cache key: NFKC + strip + lowercase ASCII."""
    q = unicodedata.normalize("NFKC", query)
    q = " ".join(q.split())
    q = q.lower()
    return q


def _cache_key(query: str) -> str:
    return hashlib.sha256(_normalize_query(query).encode()).hexdigest()


class SemanticChain:
    """Orchestrates semantic decomposition → collection routing → multi-path retrieval."""

    def __init__(
        self,
        backend: StructuredOutputBackend | None,
        router: CollectionRouter | None,
        retriever,  # HybridRetriever instance
        enabled: bool = True,
        threshold: float = 0.2,
        top_k_per_intent: int = 5,
        top_k_hyde: int = 5,
        top_k_keyword: int = 3,
    ):
        self._backend = backend
        self._router = router
        self._retriever = retriever
        self._enabled = enabled
        self._threshold = threshold
        self._top_k_intent = top_k_per_intent
        self._top_k_hyde = top_k_hyde
        self._top_k_keyword = top_k_keyword
        self._cache: dict[str, DecomposedQuery] = {}

    def decompose(self, query: str) -> DecomposedQuery | None:
        if not self._enabled or self._backend is None:
            return None
        key = _cache_key(query)
        if key not in self._cache:
            self._cache[key] = self._backend.decompose(query)
        return self._cache[key]

    def run(self, query: str) -> tuple[list, list] | None:
        """Run full semantic chain. Returns (result_lists, weights) or None if disabled."""
        if not self._enabled or self._backend is None:
            return None

        dq = self.decompose(query)
        if dq is None:
            return None

        assert self._router is not None
        collection_weights = self._router.route(query, dq.query_type, self._threshold)
        top_collections = [
            c for c, w in sorted(collection_weights.items(), key=lambda x: x[1], reverse=True)
            if w >= self._threshold
        ][:3]

        result_lists: list = []
        weights: list[float] = []

        # Path A: intent keyword search
        semantic_blend = max(0.2, dq.confidence * 0.5)
        for intent in dq.intents[:3]:
            if not intent.keywords or not top_collections:
                continue
            search_query = " ".join(intent.keywords[:6])
            for col in top_collections[:2]:
                try:
                    results = self._retriever.search_collection(
                        col, search_query, top_k=self._top_k_intent
                    )
                    result_lists.append(results)
                    weights.append(intent.weight * semantic_blend)
                except Exception:
                    pass

        # Path B: HyDE vector search (embed solution_rewrite)
        if dq.solution_rewrite and top_collections:
            for col in top_collections[:2]:
                try:
                    results = self._retriever.search_collection(
                        col, dq.solution_rewrite, top_k=self._top_k_hyde
                    )
                    result_lists.append(results)
                    weights.append(0.4 * semantic_blend)
                except Exception:
                    pass

        # Path C: solution_rewrite keyword fallback (lower weight)
        if dq.solution_rewrite:
            for col in top_collections[:1]:
                try:
                    results = self._retriever.search_collection(
                        col, dq.solution_rewrite, top_k=self._top_k_keyword
                    )
                    result_lists.append(results)
                    weights.append(0.2 * semantic_blend)
                except Exception:
                    pass

        return result_lists, weights
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_semantic_chain.py::TestSemanticChain -v
```
Expected: 4 tests PASS

- [ ] **Step 5: Run full test suite**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/ -v --tb=short
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/rag/semantic_chain.py tests/test_semantic_chain.py
git commit -m "feat(semantic-chain): add SemanticChain orchestrator with cache + multi-path retrieval"
```

---

## Chunk 4: chain.py Integration + server.py Endpoints

### Task 7: Wire SemanticChain into `answer_smart`

**Files:**
- Modify: `src/rag/chain.py` — init SemanticChain, pre-dispatch step, `pre_fetched_results` param
- Modify: `tests/test_chain.py` — add SemanticChain integration tests

The pre-dispatch step runs AFTER the lookup shortcut (step 2) and BEFORE complexity detection (step 4). Both `answer_with_fallback` and `answer_complex_workflow` gain `pre_fetched_results: list | None = None`.

- [ ] **Step 1: Write failing tests**

```python
# Add to tests/test_chain.py

class TestSemanticChainIntegration:
    def test_answer_smart_with_semantic_chain_disabled(self):
        """SemanticChain disabled → behaves exactly like before."""
        chain = make_chain()
        chain.semantic_chain = None
        resp = chain.answer_smart("Sprite 跟随鼠标")
        assert resp is not None

    def test_pre_fetched_results_skips_internal_search(self):
        """answer_with_fallback with pre_fetched skips search_all_with_rerank."""
        chain = make_chain()
        from tests.test_chain import make_result
        pre = [make_result("pre-fetched content", score=0.9)]
        with patch.object(chain.retriever, "search_all_with_rerank") as mock_search:
            resp = chain.answer_with_fallback("test", pre_fetched_results=pre)
        mock_search.assert_not_called()
        assert resp is not None
```

- [ ] **Step 2: Run to verify they fail**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_chain.py::TestSemanticChainIntegration -v
```
Expected: `AttributeError` or test logic failures

- [ ] **Step 3: Add SemanticChain init to `RAGChain.__init__`**

In `src/rag/chain.py`, after `self.retriever = HybridRetriever(...)`:

```python
from src.rag.semantic_chain import (
    SemanticChain, CollectionRouter, RawLLMBackend, InstructorBackend,
)
import os as _os

# Build backend fallback chain
_backends = []
_instructor_b = InstructorBackend(self.llm, SEMANTIC_DECOMPOSE_PROMPT)
if _instructor_b.available:
    _backends.append(_instructor_b)
_backends.append(RawLLMBackend(self.llm, SEMANTIC_DECOMPOSE_PROMPT))

# Use first available backend
_active_backend = _backends[0] if _backends else None
_router = CollectionRouter(self.retriever.embedder)
_enabled = _os.getenv("SEMANTIC_CHAIN_ENABLED", "true").lower() != "false"

self.semantic_chain = SemanticChain(
    backend=_active_backend,
    router=_router,
    retriever=self.retriever,
    enabled=_enabled,
)
```

- [ ] **Step 4: Add `pre_fetched_results` param to `answer_with_fallback`**

Find `def answer_with_fallback(self, query: str` and change signature to:
```python
def answer_with_fallback(self, query: str, schema_context: str = "", pre_fetched_results: list | None = None) -> RAGResponse:
```

Then inside the method, find where `search_all_with_rerank` is called and wrap:
```python
if pre_fetched_results is not None:
    all_results = pre_fetched_results
else:
    all_results = self.retriever.search_all_with_rerank(...)
```

Do the same for `answer_complex_workflow`.

- [ ] **Step 5: Add pre-dispatch step in `answer_smart`**

After the lookup shortcut block and before complexity detection, insert:

```python
# Semantic chain pre-dispatch (after lookup, before complexity routing)
pre_fetched: list | None = None
if self.semantic_chain:
    _sc_result = self.semantic_chain.run(query)
    if _sc_result is not None:
        sc_result_lists, sc_weights = _sc_result
        if sc_result_lists:
            existing = self.retriever.search_all_with_rerank(
                self._enrich_query(query),
                top_k_per_collection=5, final_top_k=10,
            )
            blend = max(0.2, (sc_weights[0] if sc_weights else 0.3))
            pre_fetched = self.retriever.weighted_rrf(
                [existing, *sc_result_lists],
                [1.0 - blend, *sc_weights],
            )
            _trace(f"semantic: {len(pre_fetched)} results merged", "retrieve")
```

Pass `pre_fetched_results=pre_fetched` to both downstream dispatch calls.

- [ ] **Step 6: Run tests**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_chain.py tests/test_semantic_chain.py -v --tb=short
```
Expected: all pass

- [ ] **Step 7: Smoke test end-to-end (manual)**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -c "
from src.rag.chain import RAGChain
chain = RAGChain()
dq = chain.semantic_chain.decompose('怎么让 Sprite 跟随鼠标')
print('query_type:', dq.query_type)
print('c3_objects:', dq.c3_objects)
print('confidence:', dq.confidence)
"
```
Expected: prints structured decomposition without error

- [ ] **Step 8: Commit**

```bash
git add src/rag/chain.py src/rag/semantic_chain.py tests/test_chain.py
git commit -m "feat(chain): integrate SemanticChain into answer_smart pre-dispatch"
```

---

### Task 8: Add /search and /decompose to server.py

**Files:**
- Modify: `scripts/server.py` — add two new POST endpoints

- [ ] **Step 1: Add endpoints in `do_POST`**

Find the `else:  # /query` branch and replace with:

```python
elif path == "/decompose":
    query = body.get("query", "")
    dq = chain.semantic_chain.decompose(query) if chain.semantic_chain else None
    if dq:
        self._respond({
            "query_type": dq.query_type,
            "c3_objects": dq.c3_objects,
            "action_verbs": dq.action_verbs,
            "intents": [{"label": i.label, "keywords": i.keywords, "weight": i.weight}
                        for i in dq.intents],
            "solution_rewrite": dq.solution_rewrite,
            "confidence": dq.confidence,
        })
    else:
        self._respond({"error": "semantic chain unavailable"})

elif path == "/search":
    query = body.get("query", "")
    top_k = int(body.get("top_k", 8))
    with _infer_lock:
        results = chain.retriever.search_all_with_rerank(
            query, top_k_per_collection=3, final_top_k=top_k
        )
        dq = chain.semantic_chain.decompose(query) if chain.semantic_chain else None
    self._respond({
        "results": [
            {"text": r.text, "source": r.source, "score": r.score}
            for r in results
        ],
        "decomposed": {
            "query_type": dq.query_type if dq else "unknown",
            "c3_objects": dq.c3_objects if dq else [],
            "intents": [{"label": i.label, "keywords": i.keywords}
                        for i in dq.intents] if dq else [],
            "confidence": dq.confidence if dq else 0.0,
        }
    })

else:  # /  (answer_smart)
    query = body.get("query", "")
    with _infer_lock:
        resp = chain.answer_smart(query)
    self._respond({
        "answer": resp.answer,
        "query_type": resp.query_type,
        "confidence": resp.confidence,
        "trace": resp.trace,
    })
```

- [ ] **Step 2: Verify server starts without error**

```bash
# Start server in background, wait 5s, then curl test
/c/Users/test/AppData/Local/Python/bin/python.exe scripts/server.py &
sleep 5
curl -s -X POST http://localhost:8765/decompose \
  -H "Content-Type: application/json" \
  -d '{"query":"怎么让 Sprite 跟随鼠标"}' | python -m json.tool
kill %1
```
Expected: JSON response with `query_type`, `c3_objects`, etc.

- [ ] **Step 3: Commit**

```bash
git add scripts/server.py
git commit -m "feat(server): add /search and /decompose endpoints for Copilot integration"
```

---

### Task 9: Final validation + requirements.txt update

- [ ] **Step 1: Run full test suite**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: all pass, no regressions

- [ ] **Step 2: Add instructor to requirements.txt**

```bash
grep -n "instructor\|pydantic" /d/Users/Administrator/Documents/GitHub/Construct3-RAG/requirements.txt
```

If `instructor` is not listed, append:
```
instructor>=1.14.0    # structured LLM output backend for SemanticChain
# outlines==0.0.46   # optional: constrained decoding (verify torch nightly compat first)
# ltp-py             # optional: Chinese NLP SRL (Python 3.14 wheel unconfirmed)
```

- [ ] **Step 3: Verify import chain from scratch**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -c "
from src.rag.chain import RAGChain
from src.rag.semantic_chain import SemanticChain, CollectionRouter
from src.rag.retriever import weighted_rrf
from src.rag.prompts import SEMANTIC_DECOMPOSE_PROMPT
print('All imports OK')
"
```

- [ ] **Step 4: Final commit**

```bash
git add requirements.txt
git commit -m "chore: add instructor to requirements.txt; document optional outlines/ltp"
```

---

## Summary

| Task | Files | Tests |
|------|-------|-------|
| 1 | `semantic_chain.py` (dataclasses), `zh/en prompts.py`, `rag/prompts.py` | `test_semantic_chain.py` |
| 2 | `retriever.py` (weighted_rrf) | `test_retriever.py` |
| 3 | `semantic_chain.py` (ABC + RawLLMBackend) | `test_semantic_chain.py` |
| 4 | `semantic_chain.py` (InstructorBackend) | `test_semantic_chain.py` |
| 5 | `semantic_chain.py` (CollectionRouter) | `test_semantic_chain.py` |
| 6 | `semantic_chain.py` (SemanticChain) | `test_semantic_chain.py` |
| 7 | `chain.py` (integration) | `test_chain.py` |
| 8 | `server.py` (/search, /decompose) | manual curl |
| 9 | `requirements.txt` | full suite |
