# Query Expander Design

**Date:** 2026-03-07
**Status:** Approved

## Problem

Current retrieval pipeline tokenizes user queries with jieba and maps Chinese terms to English via a translation glossary (Qdrant `terms` collection). This misses the semantic gap between natural language verbs ("查找") and the actual ACE vocabulary ("IndexOf", "Contains", "Find"). The result is imprecise vector retrieval and missed ACE matches.

## Solution: SchemaZhEnIndex + QueryExpander

A two-stage pre-retrieval component that:
1. Expands each query token into a larger Chinese term set (manual + auto)
2. Uses that term set to bridge zh → en via the schema files, producing English ACE identifiers for precise matching

---

## Data Flow

```
用户查询: "怎么在数组中查找特定数字"
    ↓ jieba
['数组', '查找', '数字']
    ↓ QueryExpander.expand()  (manual SEMANTIC_EXPAND + auto from schema zh index)
{
  '数组': {'数据结构', ...},
  '查找': {'条件', '表达式', '包含', '遍历', '存在', '检索', ...},
  '数字': {'变量', '值', '参数', '字符串', ...}
}
    ↓ 合并为大词集 term_set
{'数组', '数据结构', '查找', '条件', '表达式', '包含', '遍历', '存在', '数字', '值', ...}
    ↓ SchemaZhEnIndex.search(term_set)
[
  SchemaMatch(ace="arr/contains-value", score=0.82, en_tokens={"Array","Contains","value"}),
  SchemaMatch(ace="arr/index-of",       score=0.75, en_tokens={"Array","IndexOf","value"}),
  SchemaMatch(ace="arr/find",           score=0.61, en_tokens={"Array","Find","condition"}),
  ...
]
    ↓ 按分数分流
  score > 0.7  →  Tier C: 直接返回 ACE schema context（跳过向量检索）
  0.3~0.7      →  提取 en_tokens，拼入向量检索 query 增强精度
  < 0.3        →  跳过，走原有流程
```

---

## Component: SchemaZhEnIndex

### 索引范围（五类，含权重）

| 类型 | 权重 | 索引字段 |
|------|------|---------|
| plugins / behaviors | 1.0 | 对象级: name_zh/en, description_zh/en, path (分割), categories<br>ACE 级: name_zh/en, description_zh/en, scriptName<br>参数级: params[].name_zh/en, items_i18n[*].zh/en |
| effects | 0.9 | 对象级: name_zh/en, description_zh/en, category<br>参数级: parameters[].name_zh/en |
| features | 0.8 | 对象级: name_zh/en, description_zh/en, tags<br>examples[].description_zh/en, relatedACE |
| editor | 0.4 | bars/dialogs/views 的 name_zh/en（UI 术语桥接，权重低）|

### 内部结构

```python
# 倒排索引（zh token → 命中的节点 ID 集合）
token_to_nodes: dict[str, set[str]]

# 正向索引（节点 ID → 元数据）
node_data: dict[str, NodeData]
# NodeData: {zh_tokens, en_tokens, schema_type, plugin_id, ace_type, weight}
```

节点粒度：
- plugins/behaviors → 两种节点：plugin 节点 + ACE 节点（ace_full_id = "arr/contains-value"）
- effects → effect 节点
- features → feature 节点
- editor → UI 元素节点（"bar/layers", "dialog/addBehavior"）

### 评分公式

```
score = (命中 zh token 数 / 该节点 zh 词表大小) × weight
```

### 构建时机

启动时懒加载（首次调用时构建），结果缓存在内存中。与 SchemaIndex 共用同一批 JSON 文件，不重复读磁盘（接受 SchemaIndex 实例作为数据源）。

---

## Component: SmallLLMExpander

手工词表覆盖率有限，人工维护不可持续。引入极小 LLM 做通用语义联想，替代手工词表成为主要扩展源。

### 职责

输入：查询 token 列表 → 输出：这些词在技术文档中的语义近义词集（中文）

**不需要** C3 领域知识——只做通用汉语语义联想（"查找"→包含/检测/遍历/索引），C3 专有术语映射由 SchemaZhEnIndex 负责。

### 模型选型

| 模型 | VRAM | 速度（CPU） | 备注 |
|------|------|------------|------|
| Qwen3-0.5B | ~0.5GB | ~1-3s | 推荐，足够做词义联想 |
| Qwen3-1.5B | ~1.5GB | ~3-6s | 质量略好，适合 GPU |

默认 CPU 推理——不与主模型竞争 VRAM；结果缓存后重复查询极快。

### Prompt 设计

```
你是一个语义联想助手。给定技术文档查询中的关键词，
列出相关的中文动词和名词（每行一个，不超过12个，只输出词语）：

关键词：数组 / 查找 / 数字

相关词：
```

期望输出：
```
包含
检测
索引
遍历
比较
存在
返回
位置
查询
元素
值
筛选
```

### 配置

```python
# config.py 新增
EXPANDER_MODEL  = os.getenv("EXPANDER_MODEL", "Qwen/Qwen3-0.5B")
EXPANDER_DEVICE = os.getenv("EXPANDER_DEVICE", "cpu")   # "cpu" | "cuda"
```

### 接口

```python
class SmallLLMExpander:
    def expand(self, tokens: list[str]) -> set[str]   # 返回扩展词集，失败返回 set()
    @property
    def available(self) -> bool                        # 模型是否已成功加载
```

- 懒加载：首次调用时加载模型
- 结果缓存：`frozenset(tokens)` 为 key，避免重复推理
- 超时保护：推理超过 5s 则跳过，返回空集
- 失败降级：加载失败不抛异常，`available=False`，QueryExpander 静默跳过

---

## Component: QueryExpander

### 扩展词来源（三层，按优先级合并）

| 来源 | 类型 | 优先级 | 说明 |
|------|------|--------|------|
| `SmallLLMExpander` | 神经网络语义联想 | 主 | 通用中文词义扩展，不依赖 C3 知识 |
| `SEMANTIC_EXPAND` 手工词表 | 规则 | 补充 | 快速路径 + LLM 不可用时兜底 |
| `SchemaZhEnIndex.auto_expand` | 共现统计 | 补充 | schema 词汇共现，贴近 C3 文档用词 |

三者取并集，无优先级覆盖关系。

**B. 自动扩展（从 SchemaZhEnIndex）**

对每个 token，找到命中的节点，取这些节点的 zh_tokens 作为扩展词（去掉 token 本身）。

### 接口

```python
class QueryExpander:
    def expand(self, tokens: list[str]) -> dict[str, set[str]]
    def get_term_set(self, tokens: list[str]) -> set[str]
    def search(self, term_set: set[str]) -> list[SchemaMatch]
```

```python
@dataclass
class SchemaMatch:
    node_id: str          # e.g. "arr/contains-value"
    plugin_id: str        # e.g. "arr"
    schema_type: str      # "plugin"/"behavior"/"effect"/"feature"/"editor"
    ace_type: str | None  # "conditions"/"actions"/"expressions"/None
    score: float
    en_tokens: set[str]   # en 词集，用于增强向量 query
```

---

## Integration in chain.py

在 `answer_with_fallback()` 的 jieba 分词之后，插入 QueryExpander：

```python
# 现有流程
segments = self._split_zh_segments(query)
term_keywords = self._extract_term_keywords(query)

# 新增
matches = self.query_expander.search(self.query_expander.get_term_set(segments))
high = [m for m in matches if m.score > 0.7]
mid  = [m for m in matches if 0.3 <= m.score <= 0.7]

if high:
    # Tier C: 直接构建 schema context，跳过向量检索
    ...
elif mid:
    # 提取 en_tokens 增强 retrieval query
    en_boost = " ".join(t for m in mid for t in m.en_tokens)
    enhanced_query = f"{query} {en_boost}"
    ...
```

Trace 插桩：在 `"expand"` 阶段后新增 `"schema_match"` phase，输出 top-3 命中及分数。

---

## File Changes

| 操作 | 文件 | 内容 |
|------|------|------|
| 新建 | `src/rag/query_expander.py` | `SmallLLMExpander` + `SchemaZhEnIndex` + `QueryExpander` + `SchemaMatch` |
| 修改 | `src/config.py` | 新增 `EXPANDER_MODEL` / `EXPANDER_DEVICE` |
| 修改 | `src/locale/keywords.py` | 新增 `SEMANTIC_EXPAND` 手工词表（兜底用） |
| 修改 | `src/rag/chain.py` | 初始化 `QueryExpander`，接入 `answer_with_fallback()` |
| 修改 | `scripts/chat.py` | `_TRACE_LABEL`/`_TRACE_GROUP` 添加 `"schema_match"` phase |
| 新建 | `tests/test_query_expander.py` | 单元测试（SmallLLMExpander mock + SchemaZhEnIndex + QueryExpander）|

---

## Test Plan

- `SchemaZhEnIndex` 构建后，给定 "数组" 能命中 arr plugin 节点
- `QueryExpander.expand(["查找"])` 返回手工词表 + 自动扩展的并集
- `search({"数组", "查找", "值"})` 返回 arr/contains-value score > arr/sort（分数合理）
- editor 节点权重 0.4，同等命中时分数低于 plugin 节点
- Tier C 路径：高分命中时 `answer_with_fallback` 跳过向量检索
- 中分路径：enhanced_query 包含 en_tokens
- 无命中时走原有流程，行为不变
- 全部现有 126 个测试通过
