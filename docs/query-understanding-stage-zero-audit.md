# 查询理解与术语系统：第零阶段审计

> 审计日期：2026-08-08
> 审计快照：`bc66955ac27436f5955007a0c7eab90bdf8acbcc` 加当前未提交重构工作树
> 数据快照：r495；66 个插件、32 个行为、89 个特效
> 状态：产品方向已复核；复杂查询能力尚未获准进入默认路径

本文执行《查询理解与术语系统重构要求》的“第零阶段”。结论来自真实
`/search` 调用路径、当前工作树中的双语 Schema、git 历史和对照实验，而不是
仅由现有测试反推需求。

## 1. 证据边界

- 审计开始时工作树已有一轮大规模未提交修改；本文没有回滚或覆盖这些修改。
- `data/c3-schemas/en-US` 和 `data/c3-schemas/zh-CN` 在审计快照中存在且完整，
  但仍是未跟踪文件。因此本文验证的是当前工作树，不把它误称为 clean HEAD 行为。
- Qdrant 未启动。已验证 Direct Lookup、API 编排、Schema 解析和离线基线；没有
  验证完整语义召回、多集合融合、真实 Reranker 模型收益或 Semantic Chain。
- 当前 188 个单元测试全部通过只能证明既有实现契约没有破坏，不能证明查询结果
  符合用户需要。

## 2. 产品定位判断

Construct3-RAG 当前最可信的产品形态是：**以版本化双语 Construct 3 结构化数据为
核心的纯检索服务**。它应优先为下游 Copilot、聊天界面或开发工具提供可引用的
插件、行为、ACE、属性、脚本 API 和示例元数据；它本身不负责生成最终教程。

由此得到四条产品约束：

1. Direct Lookup 只应接管具有明确实体、明确操作和可验证结构化答案的查询。
   教程、方案、比较、概念、长句和歧义主题应回退，不能为了“有结果”而高置信度
   截获。
2. 离线、确定性和可解释性是默认能力。Qdrant、Embedding、Reranker 和外部/本地
   LLM 都是可选增强，必须在同一金标集上证明净收益。
3. “查询扩展”不是产品能力本身。只有当它改善有序结果且不增加错误直查和禁止
   结果时才有保留价值。
4. 兼容性测试、历史 benchmark 数字和已有代码量都不是保留理由；需要可复现的
   当前数据、当前运行路径证据。

## 3. 当前真实调用路径

### 3.1 `/search`

```text
POST /search (默认 mode=auto)
    │
    ├─ auto / lookup / list
    │    └─ LookupEngine(schema_dir=SCHEMA_DIR)
    │         ├─ 明确 ACE/属性/翻译/示例意图
    │         ├─ ACE_SYNONYMS + ACE_CATEGORY_EXPAND
    │         ├─ ScriptingIndex fallback
    │         └─ ExamplesIndex（当前工作树从元数据内存构建）
    │
    ├─ auto / semantic
    │    └─ HybridRetriever.search_all_with_rerank()
    │         ├─ 固定十集合 fan-out
    │         ├─ weighted RRF
    │         └─ 可选 CrossEncoder Reranker
    │
    └─ 合并
         └─ 只要 lookup 命中，删除全部 semantic ACE
```

`src/api.py` 创建 `LookupEngine` 时只传 `schema_dir`。没有生产代码为它注入
Embedding 或 Ollama，因此分类器中的 Tier 2/3 在真实 API 中不会执行。
`QueryExpander` 与 `SemanticChain` 也没有生产调用者；它们只被自身测试引用。

默认 `mode=auto` 且 `LITE_MODE=false`。`scripts/setup.py` 虽把新安装描述成
lookup-only，却没有设置 `LITE_MODE=true`；当前轻量安装只是可能因为缺少 Qdrant
依赖而偶然降级。在装有 Qdrant 客户端的机器上，默认请求仍会尝试语义路径。

### 3.2 错误命中的影响

lookup 的任意 section 都会令 auto 合并逻辑删除所有 semantic ACE。这个条件还会
被“有 intent/context、无结构化 match”的翻译或示例结果触发。因此 Direct Lookup
的错误不只是多返回一段噪声；它可能压掉语义路径中原本可以补救的结果。

实测 `mode=lookup`：

| 查询 | 当前结果 | 判断 |
|---|---|---|
| `Sprite 有哪些 action` | 返回 16 个 Sprite actions | 符合明确结构化查询 |
| `Array 保存` | 0.85 命中，返回 `load`、`set-from-json` | 错误直查；保存/加载同义词级联 |
| `中文教程怎么做` | 0.95 判为 `term_translate`，API 中 lookup 为空 | 过宽意图规则和空命中截获 |
| `怎么在数组中查找特定数字` | 命中 `IndexOf`，同时混入 `pick-by-unique-id` | 有用结果与通用噪声并存 |
| `如何实现存档系统` | 回退 | 正确边界 |

`/health` 实测约 9 秒后返回 `status=unavailable`、`qdrant=false`、
`schema_ready=true`；这不是完整语义检索验证。

## 4. 能力审计表

“核心/可选/实验/未调用/残留”描述当前产品地位；“结论”是下一阶段动作，不等同于
立即在本次审计中删除代码。

| 能力 | 用户问题 | 当前真实调用与历史假设 | 成本/风险与更简单替代 | 分类 | 结论 |
|---|---|---|---|---|---|
| 双语版本化 Schema 与结构化结果 | 精确获得插件、行为、ACE、属性及中英字段 | Direct Lookup 和索引管线共同依赖；数据可指向原始路径 | 主要成本是数据更新与版本一致性；没有更简单且同等可靠的替代 | 核心 | **保留** |
| 明确 ACE list/detail/property | “Sprite 有哪些 action”“某 ACE 参数是什么” | 真实 API 使用，确定性强 | 现分类器把明确查询和主题检索混在一起；改成窄语法和精确实体解析 | 核心 | **简化并重写边界** |
| 主题型 Direct Lookup | “Array 保存”“Sprite 动画” | 由关键词、描述、同义词和类别扩展组成；假设宽召回可直接作为答案 | 高置信度错误会压掉 semantic ACE；更简单替代是只直查高精度意图，其余回退 | 当前核心中的高风险部分 | **重写** |
| ACE 手工同义词 | 处理中英别名、碰撞/重叠等表达差异 | 当前 API 使用；多个重叠词组按遍历顺序原地扩张 | 有一定召回贡献，但产生保存→加载级联；替代为有方向、实体/字段限定、带来源的别名 | 可选 | **重写；默认先收窄** |
| ACE 类别整组扩展 | 主题词命中时补全整个 category | 当前 API 使用；旧 eval 明确固化它 | 结果多、排序靠后，类别并不等于用户意图；替代为精确结果加显式“查看同类” | 实验性默认能力 | **从默认路径删除** |
| 明确术语翻译 | 查询 Construct 3 术语中英文 | 当前 API 使用，但宽泛正则会把“中文教程”当翻译；零 match 仍命中 | 直接查询双语 Schema 即可；只接受锚定句式，零结果必须回退 | 核心的窄能力 | **简化** |
| ExamplesIndex | 按示例标签或元数据查找项目 | 当前工作树真实调用；历史派生 JSON 删除后曾静默失效 | 直接从版本化元数据内存建反向索引，避免 15 万行派生产物 | 可选 | **保留并简化** |
| ScriptingIndex | 精确查找脚本类/方法 | 当前作为 lookup fallback 调用 | 通用描述匹配会污染；更简单替代是类限定、规范化标识符和精确/前缀检索 | 可选 | **保留并简化** |
| `QueryExpander` Schema 共现/手工/LLM 并集 | 假设通过扩词改善召回 | 自 2026-03-14 起无生产调用者；真实 r495 单词可扩成 55–367 项 | 共现无权重、无上限、不可解释，模型后端增加依赖；默认零扩展是更好基线 | 未调用实验代码 | **删除当前实现** |
| Tier 2 Embedding 分类 | 模糊识别 intent/plugin | 从引入起 API 就未注入 embedder | 无金标、无生产调用、增加模型；先用确定性实体别名和 fallback | 未调用代码 | **删除当前实现** |
| Tier 3 Ollama 分类 | 复杂意图判别 | 从引入起 API 就未注入 Ollama；配置和提示仍在 | 延迟、服务和不可复现输出均无收益证据；复杂查询直接进入检索更简单 | 未调用实验代码 | **删除当前实现** |
| Semantic Chain / Router / HyDE | 假设复杂查询需改写、多路召回和动态集合路由 | 唯一生产调用者上线次日即被删除；当前只有 mock 测试 | 组件多、依赖多，集合路由还被最低权重补丁弱化；简单单查询基线优先 | 历史残留 | **删除当前实现** |
| 多集合 Qdrant 固定 fan-out | 从不同资料类型召回相关内容 | auto 真实语义路径固定搜索十集合，不使用 Semantic Chain 路由 | 维护权重、集合一致性和融合；`addon_sdk` 已索引却不在默认表 | 可选、尚未验证 | **继续调研，倾向简化** |
| weighted RRF | 融合多个集合排名 | 默认语义路径真实调用 | 旧 benchmark 有正向数字，但数据集、报告和脚本已删除且索引已变化；应与单一统一检索比较 | 可选 | **继续调研** |
| CrossEncoder Reranker | 改善语义结果前排顺序 | 完整依赖安装且启用时真实调用 | 模型下载、延迟和资源较高；现测试只证明 mock 分数能重排 | 可选 | **改为显式可选；当前收益待复测** |

### 4.1 语义路径的已知实现缺口

- 集合注册表包含 `addon_sdk`，默认 `_COLLECTION_DEFAULTS` 不包含它；显式请求该
  集合还会访问缺失默认配置。这证明“已索引”不等于“可检索”。
- 多集合 diversity 注入用真实集合名判断是否已表示，却用短名记录候选，可能把每个
  集合都再次注入并使结果超过 `top_k`。
- 英文查询在 API 中排除 `terms`，其余集合仍固定全搜；不存在架构文档此前描述的
  动态 Semantic Chain 路由。

以上问题需要 Qdrant 环境和当前金标作对照。第零阶段不应在没有质量基线时继续给
现有融合逻辑打补丁。

## 5. “不使用查询扩展”基线

### 5.1 定义

`QueryExpander` 本来就不在 API 调用图中，所以单纯“关闭 QueryExpander”与当前
路径完全相同。为形成有意义的简单基线，本次使用 **Literal Direct Lookup**：

- 保留相同 `LookupEngine`、IntentClassifier、实体解析、r495 Schema、jieba、字段
  匹配、`_common` ACE、ScriptingIndex 和 ExamplesIndex；
- 仅在评测进程中将 `ACE_SYNONYMS=[]`、`ACE_CATEGORY_EXPAND=frozenset()`；
- 不修改生产文件，不调用 Qdrant、模型或网络。

### 5.2 结果

现有 `tests/eval_lookup.py` 的 22 条 case：当前路径 22/22，Literal 19/22。但旧
evaluator 只要求必须 ID 出现在**整个无序结果集合的任意位置**，并把同义词/类别
扩展本身写成预期，因此 22/22 不能直接解释为产品胜出。

在 13 条定义了必须 ID 的 case 上，采用“该 case 的全部必须 ID 都进入前 K”口径：

| 指标 | 当前 | Literal |
|---|---:|---:|
| Hit@1 | 46.2% | 46.2% |
| Hit@3 | 53.8% | 61.5% |
| Hit@5 | 76.9% | 61.5% |
| Hit@10 | 84.6% | 76.9% |
| 任意位置命中 | 100% | 76.9% |

当前扩展提高了深层召回，但牺牲了部分前排精度。例如 `Sprite 动画` 三个必需结果
位于第 10–12 位；Literal 缺少 stop/start，却把 set-animation 从第 12 提升到第 5。
`Sprite 重叠` 的精确结果由第 4 提升到第 2。更关键的是，Literal 令 `Array 保存`
从错误高置信度直查变为回退。

因此当前证据只支持“某些有方向的别名可能有价值”，不支持无约束同义词并集或类别
整组扩展进入默认路径。

当前孤立 `QueryExpander` 在真实 r495 数据上构建 3,589 个节点、2,776 个 token；
单词 `保存`、`加载`、`移动`、`查找` 的 Schema/合并扩展分别达到 220、259、367、
55 项。这一规模不适合作为默认查询改写。

## 6. 历史污染和错误假设

### 6.1 Direct Lookup 的补丁链

- `2dd65d8`（2026-03-04）整体引入 Direct Lookup，最初假设“命中即跳过 RAG”。
- `71e4c7c`（03-16）因 lookup 结果不完整改为 lookup + semantic。
- `10e3f2f`（03-21）又改成 lookup 命中时删除全部 semantic ACE，当前仍如此。
- `1307ceb` 在最后一次实现修改后几分钟把“Lookup instant and precise”写入架构；
  `5900c97` 次日才加入小型 eval，存在实现后合理化风险。
- `ff6aaa6`、`434fa5b`、`d0affe6`、`3554a20`、`cf31880`、`77e651c`、
  `90fdf62`、`089e17d` 连续以多数词匹配、短窗口、common ACE、CJK 切分、歧义词表、
  同义词和类别扩展修补同一抽象。当前 `Array 保存` 正是重叠词组级联的结果。

`怎么在数组中查找特定数字` 的测试预期也在“必须回退”和“必须直查 IndexOf”间
多次反转；其中一次理由是把结果注入已删除的生成型 LLM。该测试不能继续充当未经
复核的产品需求。

### 6.2 QueryExpander 与 Semantic Chain

- `793b584`（03-07）把 QueryExpander 接入后来删除的 `chain.py`；`8426ea2` 和
  `ae51c48` 随后用 stopwords 修补共现噪声。
- `ad61864`（03-14）删除生成 chain 后，QueryExpander 失去生产调用者；
  `089e17d`（03-24）仍继续大幅扩词。其构建脚本和约 10 MB 向量后来被删除，
  模块、配置与测试却保留至今。
- Semantic Chain 在 03-13 一天内从 spec 到默认启用并加入 Router、HyDE、RRF，
  没有同批真实效果提交；`6fe7334` 随即为避免漏搜给所有文档集合最低权重，削弱了
  路由意义；`ad61864` 次日删除唯一调用者。

这是典型的历史残留：测试证明孤立模块能运行，不证明产品仍调用或需要它。

### 6.3 数据索引与集合

- `examples_index.json` 曾是约 15 万行派生文件。`7807f8a` 宣称不再需要并删除数据，
  却未改 runtime loader；构建器随后也被删除，测试因缺文件而 skip，功能长期静默
  失效。当前从真实元数据内存构建的修改修复了这条历史断裂，方向正确。
- 多集合从 `db27aa6` 按目录直接拆分，没有留下统一集合基线。`effects` 加入后曾长期
  未被默认搜索；`addon_sdk` 目前再次出现同类断裂。
- weighted RRF 和 Reranker 曾在 2026-03 的旧 benchmark 中报告正向收益，但相关
  数据集、报告和 runner 后来以 stale 为由删除，数据、模型和索引也已变化。它们是
  “需要当前复测”，而不是“从未有证据”或“应无条件保留”。

### 6.4 安装模式回归

提交 `31ca140` 删除了 setup 中原有的 `LITE_MODE=true` 设置，而帮助文案仍声称
默认 lookup-only。当前默认行为依赖安装了哪些包，属于环境偶然性，不是明确产品
配置。第一阶段应把 lookup-only 变为可验证的显式默认。

## 7. 现有测试能证明什么

| 测试 | 能证明 | 不能证明/固化的错误方向 |
|---|---|---|
| `tests/test_api.py` | 编排和响应字段在 mock 下工作 | Retriever 与 Lookup 同时 mock，未发现真实误分类、空 lookup 或语义抑制 |
| `tests/test_lookup.py` | 规则和格式契约 | 部分断言把当前 heuristic 当需求；翻译测试不检查提取词和实际 match |
| `tests/eval_lookup.py` | 22 个内联例子满足宽松集合断言 | 不检查大多数排名、重复、实体限定和额外噪声；仅 1 条禁止项；七个高歧义动词均无系统覆盖 |
| `tests/test_query_expander.py` | mock 后端接口和结果形状 | 不限制真实扩展规模、精度、排序或来源；`disabled` 也未证明最终零扩展 |
| `tests/test_retriever.py` | 人工分数可触发重排、稀疏向量形状 | 不证明真实 Reranker 或 BM25 质量 |
| `tests/test_semantic_chain.py` | fake LLM/向量下的数据结构、缓存和权重约束 | 不证明 Router、HyDE 或多路召回收益，也未覆盖 API |

应保留结构化 Schema 解析、明确实体和 ACE list/detail/property、精确脚本方法、示例
元数据以及已裁决 fallback 的测试。固定同义词表、类别扩展方式、集合权重和复杂度阈值
应从产品断言中移除。

## 8. 结构化金标查询集

### 8.1 第一版规模与分层

建立 `tests/fixtures/query_gold.jsonl`，首版 72 条，建议按以下分层人工裁决：

| 分层 | 数量 |
|---|---:|
| 明确 ACE 列表 | 8 |
| ACE 详情与参数 | 6 |
| 属性列表 | 5 |
| 中英混合实体、插件/行为重名与歧义 | 6 |
| 无歧义主题 ACE 搜索 | 8 |
| 易歧义动词（保存、加载、显示、移动、获取、查找、请求） | 14 |
| 明确术语翻译句式 | 5 |
| 翻译误判负例 | 4 |
| 教程、比较、概念、原理、完整方案回退 | 6 |
| 缺失实体、未知插件、长句、口语化回退 | 4 |
| 精确脚本 API | 3 |
| 示例项目与特效 | 3 |
| **合计** | **72** |

语言建议覆盖中文 32、英文 20、中英混合 16、脚本标识/语言中立 4；其中 48 条用于
开发，24 条保持隐藏或只在发布门禁运行。五个本轮强制案例必须进入金标且标为关键。

### 8.2 每条记录

```json
{
  "id": "ambiguous-array-save-zh-01",
  "query": "Array 保存",
  "locale": "zh-CN",
  "style_tags": ["short", "mixed-language", "ambiguous-verb"],
  "task_family": "topic_or_fallback",
  "expected_lookup": "miss",
  "expected_semantic": "required",
  "expected_intent": null,
  "expected_entity": {"kind": "plugin", "id": "array"},
  "expected_ace_types": [],
  "must_results": [],
  "forbidden_results": [
    {"plugin_id": "array", "ace_id": "load", "within_top_k": 5}
  ],
  "allowed_alternatives": [],
  "min_results": 0,
  "max_results": 0,
  "critical": true,
  "evidence": {
    "schema_version": "r495",
    "source_path": null,
    "rationale": "保存不是加载；无明确保存 ACE 时必须回退"
  }
}
```

每个 must/forbidden 项使用 `(collection, plugin_id, ace_type, ace_id)` 规范键，避免
不同插件或类的同名 ID 被错误视为命中。Schema 可回答的期望必须附源文件路径；
需要产品判断的 fallback 由两人裁决并记录理由。

### 8.3 产品质量指标与建议门禁

以下是待团队确认的首轮门槛，不伪装成已经由真实流量证明的 SLA：

- Route/intent：意图准确率至少 69/72；关键查询 100%；所有应回退 case 的错误
  Direct Lookup 为 0。
- Entity：实体解析准确率至少 98%，关键项 100%。
- Ranking：case-level all-required Hit@3 ≥85%、Hit@5 ≥95%，同时报告 MRR、
  nDCG@5 和各 task family 分层结果。
- Noise：关键项 Forbidden@5=0；全体最多 1/72；高置信度错误命中为 0；规范键
  重复为 0。
- Stability：相同数据连续 10 次的 intent 与结果顺序一致率 100%。
- Expansion：默认路径扩展数为 0。实验策略平均 ≤6、p95 ≤12、硬上限 ≤15，且每项
  保存来源和得分。
- Performance：Direct Lookup 预热 p95 ≤50 ms、冷启动 ≤750 ms；默认零网络、
  零模型下载、零外部服务。
- Complexity：记录安装包、模型体积、内存、冷/热延迟、外部服务数和更新维护步骤。
- Promotion gate：QueryExpander、Reranker、Semantic Chain 或多集合策略进入默认
  路径前，必须在同一金标上至少提升 5 个百分点 Hit@5 或 nDCG@5，且错误直查、
  Forbidden@5 和关键查询不退化。

评测 runner 应支持 `literal`、`current` 和候选策略，输出逐 query 的有序结果、意图、
实体、扩展来源、延迟及失败原因；不能只打印一个 passed 数字。

## 9. 第零阶段决策与第一阶段范围

本轮只固化方向和证据，不删除复杂模块。原因不是兼容性优先，而是：用户工作树已有
重构，完整语义路径又因 Qdrant 不可用而未验证；把多个删除和行为重写混入审计会
降低可审查性。

下一阶段建议按顺序进行：

1. 先提交结构化 72 条金标和策略无关 runner，复现 current/literal 基线。
2. 修正默认产品契约：显式 lookup-only/offline 默认；语义检索须显式启用；空 match
   不算 lookup 命中，也不能抑制 semantic ACE。
3. 收窄 Direct Lookup：明确 list/detail/property/translation/script/example 才直查；
   删除类别整组扩展，改写有方向别名，修复 `Array 保存` 和教程误判。
4. 在独立变更中删除无生产调用者的 QueryExpander、Tier 2/3 和 Semantic Chain 及其
   专属配置、测试与依赖。
5. 启动 Qdrant 后，在相同索引上比较单一/统一检索、固定多集合 fan-out、weighted
   RRF 和 Reranker；修复 addon_sdk/diversity 前先用失败 case 证明期望。

任何更复杂方案若未通过 promotion gate，应继续作为实验或删除，而不是以新
heuristic 给历史 abstraction 续补丁。
