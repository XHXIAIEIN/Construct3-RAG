# Search API Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure `/search` API to return separated lookup and semantic results with structured metadata, supporting `mode` parameter for selective execution.

**Architecture:** Single `POST /search` endpoint with `mode: auto|lookup|semantic`. Response splits into `lookup` (structured intent + matches) and `semantic` (vector results) sections. Lookup returns structured ACE match objects instead of flat text. A `context` field provides compact LLM-ready text.

**Tech Stack:** FastAPI, Pydantic v2, Python 3.14

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/api.py` | Modify | New request/response models, mode routing, result assembly |
| `src/rag/lookup.py` | Modify | `LookupResponse` returns structured matches + context separately |
| `tests/test_api_models.py` | Create | Response model unit tests |
| `tests/test_lookup.py` | Modify | Update assertions for new `LookupResponse` fields |
| `playground.html` | Modify | Render structured lookup matches as cards |

## Current State

**`LookupResponse`** (lookup.py):
```python
@dataclass
class LookupResponse:
    answer: str            # flat markdown text (mixed ACE + zh translations)
    query_type: str        # "lookup_ace_list" etc.
    intent: LookupIntent
    elapsed_ms: float = 0.0
```

**`SearchResponse`** (api.py):
```python
class SearchResponse(BaseModel):
    query: str
    lang: str
    route: str
    latency_ms: float
    results: list  # mixed: LookupResult | ACEResult | DocResult | ...
    trace: list
```

Problems:
1. `LookupResponse.answer` is flat text — no structured data for Copilot to consume
2. `SearchResponse.results` mixes lookup and semantic in one flat list
3. No way to request lookup-only or semantic-only
4. Lookup result plugin/ACE info is buried in text, not queryable

## Target State

**New `LookupResponse`** (lookup.py):
```python
@dataclass
class LookupMatch:
    ace_id: str
    ace_type: str          # condition | action | expression
    name_en: str
    name_zh: str
    plugin_id: str         # which plugin this ACE belongs to
    plugin_name_zh: str
    description_en: str
    description_zh: str
    script_name: str
    category: str
    relevance: int         # keyword match score
    params: list           # param dicts
    is_trigger: bool = False
    is_async: bool = False
    return_type: str = ""

@dataclass
class LookupResponse:
    intent: LookupIntent
    matches: list[LookupMatch]   # structured ACE matches
    context: str                 # compact text for LLM consumption
    query_type: str
    elapsed_ms: float = 0.0
```

**New `SearchResponse`** (api.py):
```python
class SearchRequest(BaseModel):
    query: str
    mode: str = "auto"     # "auto" | "lookup" | "semantic"
    top_k: int = 10
    # ... existing fields ...

class LookupSection(BaseModel):
    hit: bool
    tier: int = 0
    confidence: float = 0.0
    intent: str = ""
    plugin: PluginInfo | None = None
    keywords: list[str] = []
    matches: list[LookupMatchResult] = []
    context: str = ""      # compact LLM text

class SearchResponse(BaseModel):
    query: str
    lang: str
    mode: str
    latency_ms: float
    lookup: LookupSection | None = None   # null when mode=semantic
    semantic: list = []                    # empty when mode=lookup
    trace: list = []
```

---

### Task 1: Add LookupMatch dataclass and restructure LookupResponse

**Files:**
- Modify: `src/rag/lookup.py:106-128` (data models)
- Modify: `src/rag/lookup.py:969-992` (try_lookup)
- Modify: `src/rag/lookup.py:1130-1220` (_format_ace_search)

- [ ] **Step 1: Write failing test for LookupMatch in response**

Add to `tests/test_lookup.py`:
```python
class TestLookupResponseStructure:
    def test_ace_search_returns_matches(self):
        engine = make_engine()
        resp = engine.try_lookup("Sprite 动画")
        assert resp is not None
        assert len(resp.matches) > 0
        match = resp.matches[0]
        assert hasattr(match, 'ace_id')
        assert hasattr(match, 'name_en')
        assert hasattr(match, 'name_zh')
        assert hasattr(match, 'plugin_id')
        assert hasattr(match, 'relevance')

    def test_ace_search_has_context(self):
        engine = make_engine()
        resp = engine.try_lookup("Sprite 动画")
        assert resp.context  # non-empty LLM text
        assert isinstance(resp.context, str)

    def test_ace_list_returns_matches(self):
        engine = make_engine()
        resp = engine.try_lookup("Sprite actions")
        assert resp is not None
        assert len(resp.matches) > 0
        assert all(m.ace_type == "action" for m in resp.matches)

    def test_prop_list_returns_matches(self):
        engine = make_engine()
        resp = engine.try_lookup("Platform 属性")
        assert resp is not None
        assert len(resp.matches) > 0

    def test_backward_compat_answer(self):
        """resp.answer still works (alias for context)."""
        engine = make_engine()
        resp = engine.try_lookup("Sprite actions")
        assert resp.answer == resp.context
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_lookup.py::TestLookupResponseStructure -v`
Expected: FAIL — `LookupResponse` has no `matches` / `context` attributes

- [ ] **Step 3: Add LookupMatch dataclass and update LookupResponse**

In `src/rag/lookup.py`, add after `LookupIntent`:
```python
@dataclass
class LookupMatch:
    """A single ACE/property match from lookup."""
    ace_id: str
    ace_type: str
    name_en: str
    name_zh: str
    plugin_id: str
    plugin_name_zh: str = ""
    description_en: str = ""
    description_zh: str = ""
    script_name: str = ""
    category: str = ""
    relevance: int = 0
    params: List[Dict] = field(default_factory=list)
    is_trigger: bool = False
    is_async: bool = False
    return_type: str = ""
```

Update `LookupResponse`:
```python
@dataclass
class LookupResponse:
    """Result from a direct lookup."""
    intent: LookupIntent
    matches: List[LookupMatch] = field(default_factory=list)
    context: str = ""          # compact LLM text
    query_type: str = ""
    elapsed_ms: float = 0.0

    @property
    def answer(self) -> str:
        """Backward compat alias for context."""
        return self.context
```

- [ ] **Step 4: Update _format_ace_search to return (context, matches) tuple**

Refactor `_format_ace_search` to build both `lines` (text) and `matches` (structured).
For each matched item in the scoring loop, append a `LookupMatch` to a list.
Return both the formatted text string and the matches list.

Update `_execute()` to handle the new return format — each `_format_*` method
returns `(context_str, matches_list)` instead of just a string.

Update `try_lookup()` to populate `LookupResponse.matches` and `.context`.

- [ ] **Step 5: Update remaining _format_* methods**

Each `_format_ace_list`, `_format_prop_list`, `_format_ace_detail` should also
return `(context, matches)`. For `_format_term_translate` and `_format_example_find`,
matches can be empty (these don't return ACE matches).

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_lookup.py -v`
Expected: ALL PASS (56 existing + 5 new)

- [ ] **Step 7: Commit**

```bash
git add src/rag/lookup.py tests/test_lookup.py
git commit -m "refactor: LookupResponse returns structured matches + context"
```

---

### Task 2: Add `mode` parameter and restructure SearchResponse

**Files:**
- Modify: `src/api.py` (request/response models, search endpoint)
- Create: `tests/test_api_models.py`

- [ ] **Step 1: Write failing test for new response structure**

Create `tests/test_api_models.py`:
```python
"""Tests for API response models — no external services required."""
import pytest
from unittest.mock import MagicMock, patch
from src.api import SearchRequest, SearchResponse, LookupSection


def test_search_request_mode_default():
    req = SearchRequest(query="test")
    assert req.mode == "auto"


def test_search_request_mode_lookup():
    req = SearchRequest(query="test", mode="lookup")
    assert req.mode == "lookup"


def test_search_request_mode_validation():
    with pytest.raises(Exception):
        SearchRequest(query="test", mode="invalid")


def test_lookup_section_model():
    section = LookupSection(
        hit=True, tier=1, confidence=0.85,
        intent="ace_search",
        keywords=["碰撞"],
    )
    assert section.hit is True
    assert section.tier == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api_models.py -v`
Expected: FAIL — `LookupSection` not defined, `mode` not in `SearchRequest`

- [ ] **Step 3: Add mode to SearchRequest, define LookupSection and new SearchResponse**

In `src/api.py`, add `mode` field to `SearchRequest`:
```python
class SearchRequest(BaseModel):
    query: str = Field(..., max_length=500)
    mode: str = Field("auto", pattern="^(auto|lookup|semantic)$")
    top_k: int = Field(10, ge=1, le=50)
    # ... keep existing fields ...
```

Add `LookupMatchResult` and `LookupSection`:
```python
class LookupMatchResult(BaseModel):
    ace_id: str
    ace_type: str
    name_en: str
    name_zh: str = ""
    plugin_id: str
    plugin_name_zh: str = ""
    description_en: str = ""
    description_zh: str = ""
    script_name: str = ""
    category: str = ""
    relevance: int = 0
    params: List[ACEParam] = []
    is_trigger: bool = False
    is_async: bool = False
    return_type: Optional[str] = None

class LookupSection(BaseModel):
    hit: bool
    tier: int = 0
    confidence: float = 0.0
    intent: str = ""
    plugin: Optional[PluginInfo] = None
    keywords: list[str] = []
    matches: List[LookupMatchResult] = []
    context: str = ""
```

Update `SearchResponse`:
```python
class SearchResponse(BaseModel):
    query: str
    lang: str
    mode: str              # "auto" | "lookup" | "semantic"
    latency_ms: float
    lookup: Optional[LookupSection] = None
    semantic: list = []    # ACEResult | DocResult | ...
    trace: List[TraceStep] = []

    # DEPRECATED — backward compat
    @property
    def results(self) -> list:
        items = []
        if self.lookup and self.lookup.hit:
            items.append(LookupResult(
                intent=self.lookup.intent,
                plugin=self.lookup.plugin.id if self.lookup.plugin else "",
                content=self.lookup.context,
                confidence=self.lookup.confidence,
                tier=self.lookup.tier,
            ).model_dump())
        items.extend(self.semantic)
        return items

    @property
    def route(self) -> str:
        if self.lookup and self.lookup.hit and self.semantic:
            return "lookup+semantic"
        if self.lookup and self.lookup.hit:
            return "lookup"
        return "semantic"
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_api_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api.py tests/test_api_models.py
git commit -m "feat: add mode param, LookupSection, restructure SearchResponse"
```

---

### Task 3: Rewire search endpoint to use mode and new response structure

**Files:**
- Modify: `src/api.py:322-448` (search endpoint)

- [ ] **Step 1: Refactor search() to respect mode parameter**

The endpoint logic becomes:
```python
@app.post("/search")
def search(req: SearchRequest):
    t0 = time.time()
    # ... trace init ...

    lookup_section = None
    semantic_results = []

    # Lookup phase (skip if mode=semantic)
    if req.mode in ("auto", "lookup"):
        lookup_section = _do_lookup(req)

    # Semantic phase (skip if mode=lookup)
    if req.mode in ("auto", "semantic"):
        semantic_results = _do_semantic(req)

    return SearchResponse(
        query=req.query,
        lang=detected_lang,
        mode=req.mode,
        latency_ms=...,
        lookup=lookup_section,
        semantic=semantic_results,
        trace=...,
    )
```

Extract `_do_lookup(req) -> LookupSection | None` and `_do_semantic(req) -> list`.
These are refactors of existing code, not new logic.

- [ ] **Step 2: Convert LookupResponse.matches to LookupSection.matches**

In `_do_lookup()`, map `LookupMatch` → `LookupMatchResult` (Pydantic model),
populate `LookupSection.keywords` from `intent.filter_term` (jieba split),
populate `LookupSection.plugin` from schema resolution.

- [ ] **Step 3: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 4: Manual verification**

```bash
# Lookup only — fast, no embedding load
curl -X POST localhost:8765/search -H "Content-Type: application/json" \
  -d '{"query": "Sprite actions", "mode": "lookup"}'

# Semantic only
curl -X POST localhost:8765/search -H "Content-Type: application/json" \
  -d '{"query": "如何实现碰撞检测", "mode": "semantic"}'

# Auto (default) — both
curl -X POST localhost:8765/search -H "Content-Type: application/json" \
  -d '{"query": "Sprite 碰撞检测"}'
```

Verify:
- `mode=lookup` → `lookup` populated, `semantic` empty, fast (<100ms)
- `mode=semantic` → `lookup` null, `semantic` populated
- `mode=auto` → both populated

- [ ] **Step 5: Commit**

```bash
git add src/api.py
git commit -m "feat: search endpoint respects mode param, returns separated sections"
```

---

### Task 4: Update playground.html for new response structure

**Files:**
- Modify: `playground.html`

- [ ] **Step 1: Update result rendering**

Read from `data.lookup` and `data.semantic` instead of `data.results`.
Render lookup matches as structured cards (plugin badge + ACE name + params).
Keep semantic results rendering as-is but source from `data.semantic`.

- [ ] **Step 2: Add mode selector UI**

Add a toggle or dropdown: Auto / Lookup Only / Semantic Only.
Default: Auto.

- [ ] **Step 3: Manual test in browser**

Open `http://localhost:8765/playground`, test all three modes.

- [ ] **Step 4: Commit**

```bash
git add playground.html
git commit -m "feat: playground renders structured lookup matches, add mode selector"
```

---

### Task 5: Backward compatibility and cleanup

**Files:**
- Modify: `src/api.py` — remove deprecated `LookupResult` model after transition
- Modify: `tests/test_lookup.py` — ensure old `.answer` property still works

- [ ] **Step 1: Verify backward compat**

The old `results` flat list format should still work via the `results` property
on `SearchResponse`. Test that existing Copilot consumers don't break.

- [ ] **Step 2: Update tests/CLAUDE.md**

Add `test_api_models.py` to the test file table.

- [ ] **Step 3: Final commit**

```bash
git add tests/CLAUDE.md
git commit -m "docs: update test directory documentation"
```
