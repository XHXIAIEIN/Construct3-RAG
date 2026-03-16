# 查询处理全流程追踪

> 示例查询：**"怎么在数组中查找特定数字？"**
> 入口：`POST /search` (`src/api.py`)

---

## 流程总览

```
用户输入
  │
  ▼
┌─────────────────────────────────┐
│  Stage 0: Direct Lookup 快捷路径 │  ← LookupEngine.try_lookup()
│  (零 LLM 消耗，毫秒级)           │
└──────────┬──────────────────────┘
           │ 未命中
           ▼
┌─────────────────────────────────┐
│  Stage 1: 向量检索               │  ← Qdrant 跨 collection 搜索
│  HybridRetriever (weighted RRF) │     + cross-encoder reranking
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────┐
│  Stage 2: 自适应阈值过滤          │  ← filter_by_adaptive_threshold()
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────┐
│  Stage 3: 返回结果 + 诊断信息     │  ← SearchResponse + diagnostics
└─────────────────────────────────┘
```

---

## Stage 0: Direct Lookup 快捷路径

**代码入口**: `api.py` → `LookupEngine.try_lookup()`

**目的**：对于"列出 Sprite 的所有动作"、"翻译 Destroy"等精确查询，直接从本地 JSON/CSV 查找，跳过整个 RAG 流程。

**三层分类器** (`lookup.py:IntentClassifier.classify()`):

### Tier 1: 规则匹配（正则表达式）

```
查询: "怎么在数组中查找特定数字？"

_LIST_PATTERNS   → 不匹配（无 "有哪些/列出/所有" + ACE 类型词）
_TRANSLATE_PATTERNS → 不匹配（无 "翻译/中文/英文" 模式）
_DETAIL_PATTERNS → 不匹配（无 "怎么用/参数" 后缀）

结果: Tier 1 未命中
```

### Tier 1.5: 关键词推断

```
1. 跳过词检查:
   "怎么" 不在 _HOWTO_SKIP_WORDS 中 ✓（注意："如何" 会被跳过，但 "怎么" 不会）

2. 分词 + 插件名匹配:
   tokens = re.split(中文粒子模式, "怎么在数组中查找特定数字")
   → tokens ≈ ["数组", "查找", "特定", "数字"]

3. 插件解析:
   SchemaIndex.resolve_name("数组") → ("array", False)  ✓ 命中！
   （schema_dir/plugins/array.json 中 name_zh="数组", id="array"）

4. 剩余 tokens: ["查找", "特定", "数字"]

5. ACE 类型推断:
   topic_tokens = {"查找", "特定", "数字", ...2-char子串...}
   _infer_ace_types(topic_tokens):
     conditions 关键词: "查找" ∈ {"查找", "搜索", "找到", ...} → ✓
     expressions 关键词: "查找" ∈ {"查找", "搜索", "找到", ...} → ✓
   → ace_types = ["conditions", "expressions"]

6. 构建 Intent:
   LookupIntent(
     intent_type = "ace_search",
     plugin_id   = "array",
     ace_type    = "conditions,expressions",
     filter_term = "查找 特定 数字",
     is_behavior = False,
     tier        = 1,
   )

结果: Tier 1.5 命中！→ 进入 LookupEngine._execute()
```

### 执行查找

**代码**: `LookupEngine._format_ace_search()` (`lookup.py:897-970`)

```
1. 加载 Array 插件 Schema:
   schema = SchemaIndex.get_schema("array", is_behavior=False)
   → 读取 data/schemas/plugins/array.json

2. 构建过滤词集:
   raw_words = ["查找", "特定", "数字"]
   filter_words = {"查找", "特定", "数字"} + 2-char子串

3. 遍历 conditions 列表:
   对每个 condition，拼接 name_zh + name_en + description_zh
   检查是否包含任意 filter_word

   命中示例:
   - "查找值" (IndexOf) → name_zh 包含 "查找"
   - "包含值" (Contains) → description 中可能包含 "查找"

4. 遍历 expressions 列表:
   - "IndexOf" → description_zh 包含 "查找"

5. 生成 Markdown 表格:
   **数组 (Array)** 插件与"查找 特定 数字"相关的功能，共 N 项：

   **条件 (Conditions)**
   | # | 名称 | 英文名 | 说明 |
   |---|------|--------|------|
   | 1 | 查找值 | IndexOf | ... |
   ...

   **表达式 (Expressions)**
   | # | 名称 | 英文名 | 说明 |
   |---|------|--------|------|
   | 1 | IndexOf | IndexOf | ... |
   ...
```

### 格式化输出

**代码**: 格式化输出（`api.py` SearchResponse）

```html
<details class="rag-analysis">
<summary>⚡ 直接查找 · 规则匹配 · 3ms</summary>

- 分类层: Tier 1 (规则匹配)
- 插件: `array`
- ACE 类型: `conditions,expressions`
- 过滤词: `查找 特定 数字`
- 耗时: 3ms

</details>

（接上面的 Markdown 表格）
```

**至此查询完成，未调用任何 LLM，耗时约 3-10ms。**

---

## 如果 Lookup 未命中（标准 RAG 流程）

> 假设查询改为 **"怎么在数组中实现排序后的二分查找？"**
> 这种问题 Lookup 可能不会命中（或命中后结果为空 fallback 到 RAG）

### Stage 1: 向量检索

**代码**: `api.py` → `HybridRetriever.search_all_with_rerank()`

```
1. 健康检查:
   retriever.check_health() → Qdrant 连接正常 ✓

2. 编码查询向量:
   embedder.encode_single("怎么在数组中实现排序后的二分查找？ Array Sort Find")
   → [0.023, -0.118, 0.045, ...] (1024 维向量)

3. 搜索 9 个 collection（每个 top_k=5）:

   c3_guide      → search(query_vector, limit=5) → 2 条（score > 0.5）
   c3_interface   → search(...) → 0 条
   c3_project     → search(...) → 1 条
   c3_plugins     → search(...) → 4 条（Array 插件文档高分命中）
   c3_behaviors   → search(...) → 0 条
   c3_scripting   → search(...) → 3 条（IArrayInstance API 命中）
   c3_ace         → search(...) → 3 条（Array ACE 条目命中）
   c3_terms       → search(...) → 5 条
   c3_examples    → search(...) → 2 条

   原始结果共 ~20 条

4. 跨 collection 重排序:
   a. 去重: 基于前 100 字符去除重复文档
   b. 按 cosine similarity 分数排序
   c. 取 top 10

   最终结果示例:
   | # | collection  | score | 内容摘要                              |
   |---|------------|-------|---------------------------------------|
   | 1 | c3_plugins | 0.82  | Array 插件：查找值(IndexOf)条件...      |
   | 2 | c3_scripting| 0.78  | IArrayInstance: indexOf(), includes()... |
   | 3 | c3_ace     | 0.75  | Array 条件: Contains, IndexOf...       |
   | 4 | c3_plugins | 0.73  | Array 插件：排序(Sort)动作...           |
   | 5 | c3_examples| 0.68  | 示例项目: Array search demo...          |
   | ... | ...      | ...   | ...                                    |
```

### Stage 2: 自适应阈值过滤

**代码**: `retriever.py` → `filter_by_adaptive_threshold()`

```
输入: 10 条 RRF 融合后的结果
计算: mean - 0.5 * std_dev 作为阈值（下限 MIN_SCORE_THRESHOLD=0.005）
输出: 过滤后保留 8 条结果（至少保留 min_results=2）
```

### Stage 3: 返回结果

**代码**: `api.py` → `SearchResponse`

API 返回 JSON：
```json
{
  "results": [
    {"text": "...", "score": 0.82, "collection": "plugins", "source": "...", "metadata": {}},
    ...
  ],
  "diagnostics": {
    "route": "semantic",
    "total_candidates": 20,
    "after_rerank": 10,
    "after_threshold": 8,
    "latency_ms": 245.3
  }
}
```

---

## API 路由逻辑

`POST /search` 端点处理流程（`api.py`）：

```
request = SearchRequest(query="怎么在数组中查找特定数字？")

1. 如果 skip_lookup=false 且无 plugin/collections 过滤:
   LookupEngine.try_lookup(query)
   → Tier 1.5 命中 → 返回 LookupResponse → route="lookup"

2. 如果指定 plugin 过滤:
   retriever.search_plugin_by_name(query, plugin_en, section_types)
   → route="plugin_filter"

3. 如果指定 collections 过滤:
   逐 collection 搜索 → 去重排序
   → route="collection_filter"

4. 默认（Lookup 未命中，无过滤）:
   retriever.search_all_with_rerank(query)
   → weighted RRF 融合 → cross-encoder reranking
   → filter_by_adaptive_threshold()
   → route="semantic"
```

---

## 关键组件职责

| 组件 | 文件 | 职责 |
|------|------|------|
| `FastAPI app` | `src/api.py` | REST API 端点（/health, /search）、查询路由 |
| `LookupEngine` | `src/rag/lookup.py` | 三层意图分类 + 本地 JSON/CSV 直接查找 |
| `HybridRetriever` | `src/rag/retriever.py` | Qdrant 向量检索 + 跨 collection weighted RRF + cross-encoder reranking |
| `SemanticChain` | `src/rag/semantic_chain.py` | 查询分解 + 集合路由 + 多路径检索 |

## 数据流向

```
POST /search (api.py)
  ↓
  ├─→ LookupEngine.try_lookup() ──→ SchemaIndex (CDN cache / data/schemas/)
  │                              └─→ TermIndex   (data/source/zh_r475.csv)
  │     命中 → 直接返回 route="lookup"
  │
  ├─→ HybridRetriever.search_all_with_rerank()
  │     ├─→ EmbeddingModel (Qwen3-Embedding-0.6B) 编码查询
  │     ├─→ Qdrant 9+ 个 collection 搜索
  │     ├─→ weighted RRF 融合（按 collection 重要性加权）
  │     └─→ cross-encoder reranking（可选）
  │
  ├─→ filter_by_adaptive_threshold()
  │     └─→ 自适应阈值过滤低分结果
  │
  └─→ SearchResponse (JSON)
        ├─→ results: [{text, score, collection, source, metadata}]
        └─→ diagnostics: {route, latency_ms, ...}
```
