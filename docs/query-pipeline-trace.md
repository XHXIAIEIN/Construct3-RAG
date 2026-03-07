# 查询处理全流程追踪

> 示例查询：**"怎么在数组中查找特定数字？"**
> 入口：`RAGChain.answer_smart()` (`src/rag/chain.py`)

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
│  Stage 1: 查询分析               │  ← 语言检测 + 术语映射
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────┐
│  Stage 2: 向量检索               │  ← Qdrant 跨 collection 搜索
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────┐
│  Stage 3: 插件精确检索（可选）    │  ← 术语命中插件时触发
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────┐
│  Stage 4: LLM 生成回答           │  ← Qwen3.5-9B 推理
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────┐
│  Stage 5: 格式化输出              │  ← 分析面板 + 回答
└─────────────────────────────────┘
```

---

## Stage 0: Direct Lookup 快捷路径

**代码入口**: `chain.py` → `LookupEngine.try_lookup()`

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

**代码**: 格式化输出（原 `formatters.py`，已迁入 `chain.py`）

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

### Stage 1: 查询分析

**代码**: `chain.py` — 查询增强逻辑

```
1. 语言检测:
   _is_chinese("怎么在数组中实现排序后的二分查找？")
   → 中文字符占比 > 15% → query_is_zh = True

2. 搜索查询:
   模型非英文 → search_query = 原始查询（不翻译）

3. 术语映射 _extract_term_keywords():
   a. jieba 分词:
      _split_zh_segments("怎么在数组中实现排序后的二分查找")
      → ["数组", "实现", "排序", "二分", "查找"]
      （过滤停用词 "怎么/在/中/后/的"）

   b. 逐词搜索 terms 集合 (Qdrant c3_terms collection):

      "数组" → search_terms("数组", top_k=3):
        结果: [{zh: "数组", en: "Array", score: 0.92}]  ✅ 采用

      "实现" → search_terms("实现", top_k=3):
        结果: [{zh: "实现", en: "Implement", score: 0.41}]  ❌ 低于阈值 0.50

      "排序" → search_terms("排序", top_k=3):
        结果: [{zh: "排序", en: "Sort", score: 0.88}]  ✅ 采用

      "二分" → search_terms("二分", top_k=3):
        结果: []  ❌ 无匹配

      "查找" → search_terms("查找", top_k=3):
        结果: [{zh: "查找", en: "Find", score: 0.85}]  ✅ 采用

   c. 最终采用的关键词:
      term_keywords = [
        {zh: "数组", en: "Array", score: 0.92},
        {zh: "排序", en: "Sort",  score: 0.88},
        {zh: "查找", en: "Find",  score: 0.85},
      ]

   d. 增强搜索查询:
      search_query = "怎么在数组中实现排序后的二分查找？ Array Sort Find"

4. ACE 意图分类 _classify_ace_intent():
   jieba 词集 ∩ 关键词集:
     "查找" ∈ conditions关键词 → ✓
     "查找" ∈ expressions关键词 → ✓
     "排序" ∈ actions关键词 → ✓
   → ace_intents = ["conditions", "actions", "expressions", "properties"]
   （expressions 命中自动关联 properties）
```

### Stage 2: 向量检索

**代码**: `chain.py` → `HybridRetriever.search_all_with_rerank()`

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

### Stage 3: 插件精确检索

**代码**: `chain.py` — 插件精确检索

```
因为 term_keywords 命中了 Array/Sort/Find，触发 search_plugin_by_name():

对每个关键词的英文术语:
  retriever.search_plugin_by_name(
    query="怎么在数组中实现排序后的二分查找？",
    plugin_en="Array",
    section_types=["conditions", "actions", "expressions", "properties"]
  )
  → 在 c3_plugins 中用 Qdrant Filter:
    must: [source contains "array"]
    should: [section_type = "conditions" | "actions" | "expressions" | "properties"]
  → 返回 Array 插件中与查询最相关的 5 条

  去重后将新结果追加到 results 末尾
```

### Stage 4: LLM 生成回答

**代码**: `chain.py` — LLM 调用

```
1. 格式化上下文:
   chain._format_reranked_context(results)
   →
   ## 参考资料（共 12 条）

   [1] plugin-reference > array > 查找值
   Array 插件的 IndexOf 条件...
   来源: plugin-reference/array.md

   [2] scripting > IArrayInstance
   indexOf(value) 方法：返回值在数组中的索引...
   来源: scripting/iarrayinstance.md

   [3] ...

2. 构建消息:
   messages = [
     {role: "system", content: SYSTEM_MESSAGE + "\n\n" + context},
     ...历史消息...,
     {role: "user", content: "怎么在数组中实现排序后的二分查找？"}
   ]

3. LLM 推理 (Qwen3.5-9B, bf16, GPU):
   a. apply_chat_template(messages, enable_thinking=False)
   b. tokenize → input_ids → GPU
   c. model.generate(max_new_tokens=2048, temperature=0.7, top_p=0.8)
   d. decode → 回答文本

   模型输出示例:
   """
   在 Construct 3 的 Array 插件中，可以使用以下方式查找特定数字：

   **方法 1：使用 IndexOf 条件**
   Array 对象的「查找值」(IndexOf) 条件可以检查某个值是否存在于数组中 [来源: 1]。

   **方法 2：使用 Contains 条件**
   使用「包含值」(Contains) 条件直接判断数组中是否包含指定值 [来源: 3]。

   **方法 3：脚本方式**
   在 JavaScript 脚本中，可以使用 `IArrayInstance.indexOf(value)` 方法 [来源: 2]。
   返回值为该数字在数组中的索引，-1 表示未找到。

   > 注意：Array 插件本身不提供原生二分查找，如需排序后查找，
   > 需先使用「排序」(Sort) 动作排序数组 [来源: 4]，
   > 然后结合 For each / While 循环自行实现二分逻辑。
   """
```

### Stage 5: 格式化输出

**代码**: 格式化输出 + 拼接回答

最终用户看到的完整输出：

```html
<details class="rag-analysis">
<summary>🔍 分析过程 · 检索到 12 篇文档 · 最高相关度 0.82</summary>

**查询分析**
- 查询语言: 中文
- 搜索查询: `怎么在数组中实现排序后的二分查找？ Array Sort Find`

**关键词映射**
| 中文 | 英文术语 |
|------|---------|
| 数组 | Array |
| 排序 | Sort |
| 查找 | Find |

**术语映射过程**（阈值 ≥ 0.50）
| # | 查询词 | 匹配术语 | 英文 | 相关度 | 状态 |
|---|--------|----------|------|--------|------|
| 1 | 数组   | 数组     | Array | 0.92  | ✅ 采用 |
| 2 | 实现   | 实现     | Implement | 0.41 | ❌ 低于阈值 |
| 3 | 排序   | 排序     | Sort  | 0.88  | ✅ 采用 |
| 4 | 二分   | -        | -     | 0.00  | ❌ 无匹配 |
| 5 | 查找   | 查找     | Find  | 0.85  | ✅ 采用 |

共 5 个词段，采用 3 个术语
- ACE 意图: 条件(Conditions) · 动作(Actions) · 表达式(Expressions) · 属性(Properties)

**文档检索**
- 共检索到 12 篇相关文档
- 相关度范围: 0.52 ~ 0.82

**参考来源**
| # | 来源 | 相关度 |
|---|------|--------|
| 1 | plugin-reference > array > 查找值 | 0.82 |
| 2 | scripting > iarrayinstance | 0.78 |
| 3 | plugin-reference > array > 包含值 | 0.75 |
| ... | ... | ... |

</details>

在 Construct 3 的 Array 插件中，可以使用以下方式查找特定数字：
...（LLM 生成的回答）
```

---

## 不同入口的差异

| 入口方法 | 路径 | 特点 |
|----------|------|------|
| `answer_smart()` | Lookup → 复杂度检测 → fallback/decompose | 生产推荐，自动路由 |
| `answer_stream()` | 检索 → 流式 LLM | 实时输出，无 Self-Reflection |
| `answer_high_confidence()` | 多查询检索 → LLM → Self-Reflection | 最慢最准 |
| `answer_with_fallback()` | 健康检查 → 检索 → LLM → Self-Reflection | 服务降级 |

### answer_smart() 的路由逻辑

```
query = "怎么在数组中查找特定数字？"

1. LookupEngine.try_lookup(query)
   → Tier 1.5 命中 → 返回 LookupResponse → 直接返回（不走 LLM）

如果 Lookup 未命中:
2. _is_complex_query(query):
   complexity_indicators 匹配数 = 0（无 "步骤/流程/实现/和/然后"）
   word_count = 9（< 15）
   → False → 走 answer_with_fallback()

3. answer_with_fallback():
   a. check Qdrant → OK
   b. search_all_with_rerank() → 10 条结果
   c. filter_by_adaptive_threshold() → 保留 8 条
   d. check LLM → OK
   e. STRICT_QA_PROMPT + context → LLM.generate()
   f. _self_reflect() → 验证回答可靠性
   g. 返回 RAGResponse(confidence="high"/"medium")
```

---

## 关键组件职责

| 组件 | 文件 | 职责 |
|------|------|------|
| `LookupEngine` | `src/rag/lookup.py` | 三层意图分类 + 本地 JSON/CSV 直接查找 |
| `HybridRetriever` | `src/rag/retriever.py` | Qdrant 向量检索 + 跨 collection 重排 + RRF 融合 |
| `RAGChain` | `src/rag/chain.py` | 查询路由 + LLM 调用 + Self-Reflection |
| `LLMClient` | `src/rag/chain.py` | 多 provider 推理（HuggingFace/Ollama/OpenAI） |

## 数据流向

```
用户查询
  ↓
RAGChain.answer_smart()
  ├─→ LookupEngine ──→ SchemaIndex (data/schemas/*.json)
  │                 └─→ TermIndex   (data/source/zh_r475.csv)
  │
  ├─→ jieba 分词 → _extract_term_keywords()
  │     └─→ Qdrant c3_terms collection (向量搜索术语)
  │
  ├─→ HybridRetriever.search_all_with_rerank()
  │     ├─→ EmbeddingModel (BAAI/bge-m3) 编码查询
  │     └─→ Qdrant 9 个 collection 并行搜索
  │
  ├─→ search_plugin_by_name() (术语命中插件时)
  │     └─→ Qdrant c3_plugins (带 Filter)
  │
  └─→ LLMClient.chat()
        └─→ Qwen3.5-9B (GPU, bf16)
              ↓
        格式化回答（Markdown）
              ↓
         返回给用户
```
