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
    │   Output: DecomposedQuery {c3_objects, action_verbs, intents[], solution_rewrite}
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
    weight: float        # 0.0–1.0 (normalized to sum=1.0 across all intents at runtime)

QUERY_TYPES = Literal[
    "howto",       # 操作步骤: 怎么让 Sprite 跟随鼠标
    "explain",     # 概念解释: 什么是事件表
    "troubleshoot",# 排错诊断: 为什么碰撞检测不准
    "translate",   # 术语翻译: Tween 是什么
    "list_ace",    # ACE 列表: Sprite 有哪些动作
    "code_gen",    # 代码生成: 帮我写一个计分系统
    "unknown",     # fallback
]

@dataclass
class DecomposedQuery:
    query_type: str           # one of QUERY_TYPES — drives collection routing bias
    c3_objects: list[str]     # all C3 objects/plugins mentioned (may be empty for
                              # pure concept queries like "什么是事件表")
    action_verbs: list[str]   # ["跟随", "每 X 秒"]
    intents: list[QueryIntent] # 1–3 intents; weights normalized to sum=1.0
                               # if empty (e.g. simple translation), a single
                               # default intent {label:"default", keywords:[], weight:1.0}
                               # is inserted at runtime
    solution_rewrite: str     # HyDE: hypothetical answer text — embedded directly
                              # for vector search AND used as keyword fallback
                              # empty string for non-howto queries (translate/list_ace)
    confidence: float         # 0.0–1.0 — LLM self-assessed decomposition confidence
                              # low confidence → reduce SemanticChain blend weight
                              # in final weighted_rrf call
```

### Edge case handling

| Condition | Runtime behavior |
|-----------|-----------------|
| `c3_objects` empty | Use `action_verbs` only for retrieval keywords; skip object-based routing bias |
| `intents` empty | Insert `{label:"default", keywords: c3_objects + action_verbs, weight:1.0}` |
| `intents` weights don't sum to 1.0 | Normalize: `w_i = w_i / sum(weights)` |
| `solution_rewrite` empty | Skip HyDE path entirely; use keyword path only |
| `confidence < 0.4` | Set SemanticChain blend weight to 0.2 (vs default 0.5); rely more on existing path |
| All backends fail | `SemanticChain.run()` returns `None`; `answer_smart` falls back to `pre_fetched=None` |

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
  "query_type": "howto|explain|troubleshoot|translate|list_ace|code_gen|unknown",
  "c3_objects": [...],
  "action_verbs": [...],
  "intents": [
    {"label": "...", "keywords": ["...", "..."], "weight": 0.0–1.0}
  ],
  "solution_rewrite": "...",
  "confidence": 0.0–1.0
}

Rules:
- c3_objects: ALL Construct 3 objects/plugins mentioned. Do NOT distinguish subject/target.
- intents.weights: must sum to 1.0
- solution_rewrite: describe what the SOLUTION looks like in C3 terms (for howto/code_gen);
  leave empty string "" for translate/list_ace queries
- confidence: how certain you are about the decomposition (1.0 = very clear query)

Examples:
Q: "怎么让 Sprite 跟随鼠标"
→ {"query_type":"howto",
   "c3_objects":["Sprite","Mouse"],
   "action_verbs":["跟随"],
   "intents":[
     {"label":"immediate follow","keywords":["set position","Mouse.X","Mouse.Y"],"weight":0.6},
     {"label":"smooth follow","keywords":["lerp","every tick"],"weight":0.4}
   ],
   "solution_rewrite":"Sprite set position Mouse.X Mouse.Y every tick lerp smooth follow cursor",
   "confidence":0.95}

Q: "每 0.1 秒执行一次"
→ {"query_type":"howto",
   "c3_objects":["System"],
   "action_verbs":["计时","每 X 秒","执行","触发"],
   "intents":[
     {"label":"repeating timer","keywords":["every","seconds","timer","wait"],"weight":0.8},
     {"label":"variable timer","keywords":["variable","multiply","delta time"],"weight":0.2}
   ],
   "solution_rewrite":"System every 0.1 seconds trigger repeating timer condition",
   "confidence":0.9}

Q: "为什么我的碰撞检测不准"
→ {"query_type":"troubleshoot",
   "c3_objects":["Solid","Physics","Sprite"],
   "action_verbs":["碰撞","重叠","检测"],
   "intents":[
     {"label":"collision mask mismatch","keywords":["collision polygon","bounding box","image point"],"weight":0.5},
     {"label":"physics vs solid collision","keywords":["Solid behavior","Physics behavior","overlap"],"weight":0.3},
     {"label":"z-order or layer issue","keywords":["layer","Z order","initial layer"],"weight":0.2}
   ],
   "solution_rewrite":"",
   "confidence":0.7}

Q: "什么是事件表"
→ {"query_type":"explain",
   "c3_objects":[],
   "action_verbs":["解释","了解"],
   "intents":[
     {"label":"event sheet concept","keywords":["event sheet","events","conditions","actions","logic"],"weight":1.0}
   ],
   "solution_rewrite":"",
   "confidence":0.99}

Q: "用 Array 实现背包系统"
→ {"query_type":"code_gen",
   "c3_objects":["Array","Sprite","Text"],
   "action_verbs":["存储","添加","删除","显示","实现"],
   "intents":[
     {"label":"array as inventory data","keywords":["Array push","Array at","Array size","index"],"weight":0.5},
     {"label":"UI item display","keywords":["Sprite","Text","set text","for each"],"weight":0.3},
     {"label":"add/remove item logic","keywords":["condition compare","action set","variable"],"weight":0.2}
   ],
   "solution_rewrite":"Array store item name quantity Sprite display inventory slot for each element",
   "confidence":0.85}

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

**Routing logic**: two-signal fusion:

1. **Embedding similarity**: embed query → cosine similarity with each descriptor
2. **`query_type` bias** (additive): hard-boost collections that match the query type

```python
QUERY_TYPE_BIAS: dict[str, dict[str, float]] = {
    "howto":        {"c3_ace": +0.3, "c3_guide": +0.2},
    "explain":      {"c3_guide": +0.3, "c3_project": +0.2},
    "troubleshoot": {"c3_guide": +0.2, "c3_examples": +0.3},
    "translate":    {"c3_terms": +0.6},
    "list_ace":     {"c3_ace": +0.5},
    "code_gen":     {"c3_scripting": +0.3, "c3_examples": +0.3},
    "unknown":      {},   # no bias; rely on embedding only
}
# Final weight = cosine_similarity + query_type_bias (clamped to [0, 1])
```

Collections with final weight below `weight_threshold` (default 0.2) are skipped.

---

## Component 3: Multi-Path Retrieval + RRF

### Retrieval

Three parallel search paths:

```
Path A — Intent keyword search (1 per intent):
  intent[i] (weight w_i) × top-2 collections → search(keywords, top_k=5)

Path B — HyDE vector search (solution_rewrite as hypothetical document):
  embed(solution_rewrite) → vector search across top-weighted collections (top_k=5)
  weight = 0.4 (only when solution_rewrite is non-empty, i.e. howto/code_gen)
  This is more powerful than keyword path for semantic matches.

Path C — solution_rewrite keyword fallback (weight=0.2):
  solution_rewrite text → keyword search, all collections, top_k=3
  Provides lexical coverage when HyDE embedding doesn't match exact terms.
```

`SemanticChain.retrieve()` returns `(result_lists, weights)` for all active paths.
The caller (`answer_smart`) passes these to `weighted_rrf` along with the existing
search results.

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

### Confidence-adaptive blending

The `confidence` field from `DecomposedQuery` adjusts how much the semantic path
contributes to the final merge:

```python
semantic_blend = max(0.2, dq.confidence * 0.5)   # 0.2–0.5 range
existing_blend = 1.0 - semantic_blend

pre_fetched = weighted_rrf(
    [existing_results, *semantic_result_lists],
    [existing_blend, *[w * semantic_blend for w in semantic_weights]],
)
```

Low-confidence decomposition (e.g. ambiguous colloquial query) → existing path
dominates. High-confidence decomposition → equal blend.

---

## Trace Integration

All semantic chain steps emit `_trace()` events visible in chat.py's trace display:

| Phase key | Group | Example message |
|-----------|-------|-----------------|
| `semantic_decompose` | 查询分析 | `type=howto objects=[Sprite,Mouse] verbs=[跟随] conf=0.95` |
| `semantic_intents` | 查询分析 | `intent[0] immediate_follow(0.6): set position Mouse.X` |
| `semantic_route` | 向量检索 | `c3_ace=0.82 c3_guide=0.71 c3_terms=0.18(skipped)` |
| `semantic_hyde` | 向量检索 | `HyDE: "Sprite set position Mouse.X..." → 5 results` |
| `semantic_blend` | 结果过滤 | `blend: existing=0.5 semantic=0.5 (conf=0.95)` |

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

## Integration Point: RAG as Service for Construct3-Copilot

RAG 对外暴露两个新 HTTP 端点，供 Copilot 调用。现有 `POST /`（answer_smart）保持不变。

### 新增端点

**`POST /search`** — 原始检索，不生成答案

```json
// 请求
{"query": "平台跳跃角色控制", "top_k": 8, "collections": ["c3_ace","c3_examples"]}

// 响应
{
  "results": [{"text": "...", "source": "c3_ace", "score": 0.87}],
  "decomposed": {
    "query_type": "howto",
    "c3_objects": ["Sprite"],
    "intents": [...],
    "confidence": 0.91
  }
}
```

**`POST /decompose`** — 仅语义分解，无检索无生成

```json
// 请求
{"query": "怎么让 Array 存储玩家背包"}

// 响应
{
  "query_type": "code_gen",
  "c3_objects": ["Array","Sprite"],
  "action_verbs": ["存储","实现"],
  "intents": [...],
  "solution_rewrite": "Array push item name quantity slot...",
  "confidence": 0.88
}
```

### Copilot 调用时机

| 场景 | 端点 | 用途 |
|------|------|------|
| 用户描述游戏需求 | `POST /decompose` | 理解意图，辅助生成 Clarification 问题 |
| 生成 JSON 之前 | `POST /search` | 拉取相关 ACE 文档 + 示例项目作为生成上下文 |
| 答疑 / 解释错误 | `POST /` | 完整 Q&A，直接给用户展示 |

随着 RAG 语义链进化（检索更准），Copilot 拿到的上下文质量自动提升——无需修改 Copilot 代码。

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
