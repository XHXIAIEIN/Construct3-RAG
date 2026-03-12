# Semantic Chain Design

**Date**: 2026-03-13
**Status**: Approved
**Topic**: Embedding-guided semantic reasoning chain for zero-dictionary query understanding

---

## Problem

The current RAG pipeline routes queries using manually-maintained keyword dictionaries (`SEMANTIC_EXPAND`, `ACE_INTENT_KEYWORDS`). These are:

- Inherently incomplete (C3 has hundreds of plugins and thousands of ACEs)
- Unable to handle colloquial phrasing ("每 0.1 秒执行一次")
- Single-intent — one enriched query per retrieval round
- Rule-based collection routing (doesn't adapt to query semantics)

## Goal

A zero-dictionary, LLM-driven semantic chain that:

1. Decomposes any query into structured semantic roles and multiple intents
2. Routes to Qdrant collections via embedding similarity (no manual rules)
3. Generates intent-specific sub-queries per collection
4. Merges results via weighted RRF
5. Works robustly across all C3 question types (operation, explanation, code, ambiguous)

---

## Architecture

### Overview

```
User Query
    │
    ▼
[Step 1] Semantic Decomposer  (Qwen3.5-9B + pluggable backend)
    │   Output: DecomposedQuery {roles, intents[], solution_rewrite}
    ▼
[Step 2] Collection Router  (reuses HybridRetriever.embedder, cosine similarity)
    │   Output: {collection → weight} map
    ▼
[Step 3] Multi-Path Retrieval  (parallel, intent × top-weighted collections)
    │   + solution_rewrite path (lower-weight)
    ▼
[Step 4] RRF Fusion (intent-weight-aware k parameter)
    │
    ▼
[Step 5] Pre-dispatch merge in answer_smart
    │   final_results = RRF([existing_results, semantic_results])
    ▼
answer_complex_workflow / answer_with_fallback  (unchanged)
```

### Integration with existing pipeline

`answer_smart` gains a pre-dispatch step that runs `SemanticChain` in parallel with the
existing `_enrich_query → search_all_with_rerank` path, then merges via RRF **before**
dispatching to `answer_complex_workflow` or `answer_with_fallback`. Neither downstream
method is modified.

---

## Data Structures

```python
@dataclass
class QueryIntent:
    label: str           # "immediate follow" / "smooth follow (lerp)"
    keywords: list[str]  # ["set position", "Mouse.X", "Mouse.Y"]
    weight: float        # 0.0–1.0

@dataclass
class DecomposedQuery:
    subject_objects: list[str]         # ["Sprite"]
    action_verbs: list[str]            # ["跟随"]
    target_objects: list[str]          # ["鼠标"]
    intents: list[QueryIntent]         # 1–3 intents
    solution_rewrite: str              # solution-perspective rewrite
```

---

## Component 1: Structured Output Layer (Pluggable Backends)

Four backends share the same `StructuredOutputBackend` interface. The chain auto-selects
the best available backend at startup and falls back on failure.

```python
class StructuredOutputBackend(ABC):
    @abstractmethod
    def decompose(self, query: str) -> DecomposedQuery: ...

class ToolCallingBackend(StructuredOutputBackend):
    """Function calling (Claude API / Qwen2.5+ tool-use). Best quality."""

class InstructorBackend(StructuredOutputBackend):
    """Pydantic validation + automatic retry on schema violation."""

class OutlinesBackend(StructuredOutputBackend):
    """Constrained decoding — forces JSON schema compliance at token level.
    Requires: pip install outlines==0.0.46  (pinned; must not conflict with
    torch nightly build already in requirements.txt — verify before enabling)."""

class LTPBackend(StructuredOutputBackend):
    """Harbin LTP semantic role labeling.
    Note: ltp-py has no confirmed Python 3.14 / Windows wheel. Mark as
    unavailable if import fails; skip in fallback chain silently."""
```

**Fallback chain**: `ToolCalling → Instructor → Outlines → LTP → raw LLM + regex`

Each backend is treated as unavailable (not an error) if its dependency is missing or
import fails. The chain proceeds to the next backend.

### Decomposition Cache

Results are cached by **normalized query hash** to avoid repeated LLM calls.

Normalization scheme (applied before hashing):
1. Unicode NFKC normalization (full-width → half-width, traditional → simplified variants)
2. Strip leading/trailing whitespace; collapse internal whitespace to single space
3. Lowercase ASCII characters
4. SHA-256 hex digest of the resulting string

Cache is an in-memory `dict[str, DecomposedQuery]` on the `SemanticChain` instance (no
persistence across restarts; acceptable given startup LLM warmup already occurs).

### Step 1 Prompt (`SEMANTIC_DECOMPOSE_PROMPT`)

Stored in `src/locale/zh/prompts.py` and `src/locale/en/prompts.py` with identical
content — this is an LLM-facing prompt, not locale-specific UI text. Both locales keep
the same Chinese few-shot examples because Qwen3.5-9B is multilingual and the examples
teach output format, not language matching.

```
You are a Construct 3 query analyzer. Extract the semantic structure of the user's question.

Output JSON:
{
  "subject_objects": [...],
  "action_verbs": [...],
  "target_objects": [...],
  "intents": [
    {"label": "...", "keywords": ["...", "..."], "weight": 0.0–1.0}
  ],
  "solution_rewrite": "..."
}

Examples:
Q: "怎么让 Sprite 跟随鼠标"
→ {"subject_objects":["Sprite"], "action_verbs":["跟随"], "target_objects":["鼠标"],
   "intents":[
     {"label":"immediate follow","keywords":["set position","Mouse.X","Mouse.Y"],"weight":0.6},
     {"label":"smooth follow","keywords":["lerp","every tick"],"weight":0.4}
   ],
   "solution_rewrite":"Sprite set position Mouse.X Mouse.Y every tick lerp smooth"}

Q: "每 0.1 秒执行一次"
→ {"subject_objects":["System"], "action_verbs":["计时","执行"], "target_objects":["事件"],
   "intents":[
     {"label":"repeating timer","keywords":["every","seconds","timer","wait"],"weight":0.8},
     {"label":"variable timer","keywords":["variable","multiply","delta time"],"weight":0.2}
   ],
   "solution_rewrite":"System every 0.1 seconds trigger repeating timer condition"}

Now analyze:
Q: "{query}"
```

---

## Component 2: Collection Router

Collection descriptors are embedded **once at startup** by reusing the existing
`HybridRetriever.embedder` instance (passed in as constructor argument — no second model
load, no additional VRAM cost). At query time, only cosine similarity is computed.

All 10 Qdrant collections are included:

```python
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
```

**Routing logic**: embed query → cosine similarity with each descriptor → weight map.
Collections below `weight_threshold` (default 0.2) are skipped (dynamic pruning).

---

## Component 3: Multi-Path Retrieval + RRF

### Retrieval

```
intent[0] (weight w0) × top-2 collections → search(keywords, top_k=5)
intent[1] (weight w1) × top-2 collections → search(keywords, top_k=5)
solution_rewrite (fixed weight=0.3)        → all collections, top_k=3
```

### Intent-weight-aware RRF

The existing `reciprocal_rank_fusion(result_lists, k=60)` is called once per result list
with a **per-list k value** derived from the intent weight:

```
k_for_list = round(60 / max(weight, 0.1))   # higher weight → smaller k → higher RRF score
```

Examples: weight=0.8 → k=75; weight=0.5 → k=120; solution_rewrite weight=0.3 → k=200.
Floor of 0.1 prevents ZeroDivisionError for zero-weight lists.

A new helper `weighted_rrf(result_lists, weights)` is added to `retriever.py`,
co-located with the existing `reciprocal_rank_fusion`. It is imported by `chain.py`
for the final merge step. `SemanticChain` does **not** call it directly — it returns
raw per-intent result lists; the caller (`answer_smart`) performs the final merge.
The existing `reciprocal_rank_fusion` signature is not modified.

```python
def weighted_rrf(
    result_lists: list[list[SearchResult]],
    weights: list[float],
) -> list[SearchResult]:
    """RRF fusion where each list's k is derived from its weight.
    Higher weight → smaller k → higher score contribution.
    Dedup key matches reciprocal_rank_fusion: text[:150].lower().strip().
    """
    rrf_scores: dict[str, float] = {}
    result_map: dict[str, SearchResult] = {}
    for results, w in zip(result_lists, weights):
        k = round(60 / max(w, 0.1))   # floor guard prevents ZeroDivisionError
        for rank, r in enumerate(results):
            key = r.text[:150].lower().strip()   # same as reciprocal_rank_fusion
            rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (k + rank + 1)
            result_map.setdefault(key, r)
    return [result_map[k] for k in sorted(rrf_scores, key=rrf_scores.__getitem__, reverse=True)]
```

---

## Integration in `answer_smart`

**Ordering within `answer_smart`** (relative to existing steps):

1. Clipboard detection (unchanged — must run first)
2. Lookup shortcut (unchanged — builds `schema_context`)
3. ← **SemanticChain runs here**, after `schema_context` is available
4. Complexity detection + dispatch (unchanged)

```python
# After lookup step, before complexity detection:
if self.semantic_chain:
    dq = self.semantic_chain.decompose(query)               # Step 1
    collection_weights = self.semantic_chain.route(query)   # Step 2
    semantic_results = self.semantic_chain.retrieve(dq, collection_weights)  # Steps 3–4

    existing_results = self.retriever.search_all_with_rerank(
        self._enrich_query(query), top_k_per_collection=5, final_top_k=10
    )
    pre_fetched = weighted_rrf(                             # from retriever.py
        [existing_results, semantic_results],
        [0.5, 0.5],   # equal blend; tunable via SEMANTIC_CHAIN_BLEND env var
    )
else:
    pre_fetched = None   # downstream methods fall back to their own search call

# Dispatch (unchanged): passes pre_fetched into answer_with_fallback /
# answer_complex_workflow which skip their internal search_all_with_rerank
# when pre_fetched is not None.
```

Both `answer_with_fallback` and `answer_complex_workflow` receive `pre_fetched_results`
as an optional parameter (new parameter with default `None` — backward-compatible).
When provided, they skip their internal `search_all_with_rerank` call.

---

## Files

| File | Change |
|------|--------|
| `src/rag/semantic_chain.py` | New — `SemanticChain`, `CollectionRouter`, 4 backends |
| `src/rag/retriever.py` | Add `weighted_rrf` helper (authoritative location; imported by `chain.py`) |
| `src/rag/chain.py` | Add pre-dispatch step in `answer_smart`; add `pre_fetched_results` param to `answer_with_fallback` and `answer_complex_workflow` |
| `src/locale/zh/prompts.py` | Add `SEMANTIC_DECOMPOSE_PROMPT` |
| `src/locale/en/prompts.py` | Add `SEMANTIC_DECOMPOSE_PROMPT` (identical) |
| `requirements.txt` | Add `instructor`; `outlines==0.0.46` and `ltp-py` as optional comments |

### Unchanged

- `answer_complex_workflow`, `answer_with_fallback` internal logic — only signature gains optional `pre_fetched_results`
- `QueryExpander`, `_enrich_query()`, `filter_by_adaptive_threshold()` — kept as-is
- `SEMANTIC_EXPAND`, `ACE_INTENT_KEYWORDS` — deprecated but not deleted until validated

---

## Non-goals

- No LangChain dependency (Pydantic v1/v2 conflict with Python 3.14)
- No fine-tuning of any model
- No manual dictionary maintenance going forward
- No breaking changes to existing `answer_smart` public signature

---

## Risks

| Risk | Mitigation |
|------|------------|
| `outlines` conflicts with torch nightly | Pin to `0.0.46`; verify in isolated env before enabling |
| `ltp-py` no Python 3.14 wheel | Silently skip if import fails; not in default fallback path |
| Semantic decomposition adds 1–3s latency | Cache by normalized query hash; optional `SEMANTIC_CHAIN_ENABLED` env flag |
| Decomposition quality varies by backend | Backend auto-selection + fallback chain; degradation to existing path if all fail |

---

## Success Criteria

- `DecomposedQuery` produced for ≥ 14/15 evaluation cases (validated by manual inspection of trace output)
- Multi-path retrieval improves or matches context recall on existing 15-case evaluation suite
- No regression: aggregate score remains ≥ 0.96
- At least 2 of 4 backends operational on first deployment
- `SEMANTIC_CHAIN_ENABLED=false` disables the feature entirely with zero behavior change
