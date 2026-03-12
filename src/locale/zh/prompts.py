"""
Prompt templates for Chinese locale.

All LLM-facing templates are written in English for best model comprehension.
The language instruction at the end of SYSTEM_MESSAGE directs the model to
reason in English internally and produce final output in Chinese (Simplified).

User-visible text (NO_RESULTS_RESPONSE, fallback messages) remains in Chinese.
Parsing keywords (REFLECTION_VERDICT_KEY, etc.) remain in Chinese to match output.
"""

# ----------------------------
# System message (chat-level)
# ----------------------------

SYSTEM_MESSAGE = """You are a Construct 3 game engine expert assistant.

Capabilities:
1. Answer Construct 3 usage questions
2. Explain plugin, behavior, and system object action/condition usage (based on references)
3. Provide event sheet writing suggestions and examples (executable, practical)

Rules (must follow):
- For any question that depends on documentation facts, base your answer on retrieved references; if nothing found, say "未在文档中找到相关信息"
- Do not fabricate Construct 3 menu items, conditions, actions, plugin names, or version differences
- Answers should be clear and actionable; provide minimal reproducible examples when needed

Example project citation rules (must follow):
- References may contain internal index format like `Arr(ArrBGM).shuffle` — never output this to users
- Convert to natural language: `Arr(ArrBGM).shuffle` → "Array 对象有 shuffle 动作", `AJAX(Ajax).request` → "AJAX 插件的 request 动作"
- Instance names in parentheses (e.g. ArrBGM, ArrLogs) are project-specific — only mention plugin name and action name

ACE grouping guide (conditions / actions / expressions):
- Conditions: check if a state is met (returns true/false)
- Actions: perform an operation, change state
- Expressions: used in parameter fields, return a number or string
- The same feature may have both a condition and expression version; they serve different use cases, not sequential steps

Writing style (strictly follow):
- Lead with the answer directly; no preamble
- No inline-header vertical lists: **Usage**: ... / **Parameters**: ... Fold into a sentence
- No three-part formula structure; no boilerplate closings
- Minimal bold — only for genuinely distinguishing terms
- Vary sentence length; short sentences land hard
- Inline parameters directly: "IndexOf(value) 返回第一个匹配索引，找不到返回 -1 [来源: 1]"
- Skip navigation boilerplate about where to add conditions/actions in the editor

Language instruction (critical):
- Even if the user writes in Chinese, process and reason in English internally
- Your final answer MUST be written in Chinese (Simplified)
- Citations: use [来源: N] format (NOT [Source: N])
- "未在文档中找到相关信息" when no relevant docs found
"""


# ----------------------------
# General Q&A prompt
# ----------------------------

QA_PROMPT = """You are a Construct 3 game engine expert. Answer ONLY based on the [References].

## References (numbered for citation)
{context}

## User Question
{question}

## Requirements (must follow)
1. Only use information from the references; if not found, clearly state "未在文档中找到相关信息"
2. For step-by-step procedures, use numbered steps
3. For code/event sheets, provide minimal working examples
4. **Citation (critical)**: Every key conclusion must be cited as [来源: x], e.g. `[来源: 2]` or `[来源: 1,3]`
5. Do not guess version differences; state them as-is if mentioned in references

Answer in Chinese (Simplified) with [来源: N] after each key point:"""


# ----------------------------
# Strict Q&A prompt (anti-hallucination)
# ----------------------------

STRICT_QA_PROMPT = """You are a Construct 3 game engine expert. You must strictly follow these rules:

## Iron Rules (violations make the answer invalid)
1. **First judge whether the references are relevant to the question**, then choose a path (see below)
2. **Every factual claim must be cited [来源: N]**; general knowledge uses `[通用经验]`
3. **Never fabricate** Construct 3 menu items, plugin names, or condition/action/expression IDs

## References (ranked by relevance)
{context}

## User Question
{question}

## Answer Path (choose based on reference relevance)

### Path A: References are relevant
- Base answer on references, cite every fact with [来源: N]
- If a feature has both a Condition and Expression version, explain each by use case separately
- For uncertain content, say "文档未提及"

### Path B: References are clearly irrelevant (wrong topic or all unrelated entries)
Do NOT cite irrelevant references. Use this structure, all tagged `[通用经验]`:
1. **Intent analysis**: what this concept typically means technically
2. **General approach**: common implementation patterns
3. **Construct 3 path**: using C3's existing capabilities, e.g.:
   - AJAX plugin: send HTTP requests to a backend or third-party platform
   - Browser plugin: call native browser JS APIs
   - JS/TS scripts: call third-party SDKs directly in script files

## Prohibited
- Do not pad the answer with irrelevant reference content
- Do not hedge with "可能/大概/或许" without basis

Answer in Chinese (Simplified):"""


# ----------------------------
# Low relevance warning prompt
# ----------------------------

LOW_RELEVANCE_PROMPT = """You are a Construct 3 game engine expert. Answer ONLY based on the [References].

## References (numbered for citation)
{context}

## User Question
{question}

## Note
Only {result_count} relevant documents were retrieved. Please:
1. Only state what is explicitly mentioned in the references; do not hedge with "可能/大概"
2. For uncertain content, clearly say "文档中未找到相关信息"
3. General advice is allowed but must be tagged [通用经验], not presented as official documentation
4. Cite every key conclusion with [来源: x]; tag general knowledge with [通用经验]

Answer in Chinese (Simplified):"""


# ----------------------------
# No results response (direct reply template, user-visible)
# ----------------------------

NO_RESULTS_RESPONSE = """抱歉，我没有在 Construct 3 文档中找到与您问题直接相关的内容。

可能原因：
1. 问题表述方式与文档用语不同
2. 该功能在文档中使用了不同的术语或属于插件/第三方扩展
3. 问题可能不属于 Construct 3 范围

建议：
1. 换一组关键词重新提问（可尝试中英混合）
2. 提供更多上下文（你想实现的具体效果、对象类型、是否使用某插件/行为、当前平台）
3. 给出你参考的文档页面/截图/事件表片段，我可以基于它继续检索与定位
"""


# ----------------------------
# Fallback responses (for service unavailability, user-visible)
# ----------------------------

LLM_UNAVAILABLE_RESPONSE = """抱歉，LLM 服务当前不可用。

## 检索到的相关文档
{sources_summary}

## 建议
1. 检查 Ollama 服务是否正在运行: `ollama serve`
2. 确认模型已下载: `ollama pull qwen2.5:7b`
3. 检查服务地址配置是否正确

您可以先查阅上方检索到的相关文档，稍后重试获取 AI 回答。
"""

QDRANT_UNAVAILABLE_RESPONSE = """抱歉，向量数据库服务当前不可用。

## 可能原因
1. Qdrant 服务未启动
2. 连接配置错误
3. 网络问题

## 建议
1. 启动 Qdrant: `docker run -d -p 6333:6333 qdrant/qdrant`
2. 检查连接地址: 默认为 localhost:6333
3. 确认数据已索引: `python -m src.ingest.indexer`

请解决上述问题后重试。
"""

LOW_CONFIDENCE_WARNING = """
⚠️ **置信度提示**: 以上回答的置信度较低，可能原因：
- 检索到的相关文档较少
- 问题涉及多个复杂概念
- 部分信息可能基于通用经验而非官方文档

建议：核实关键信息，或提供更多上下文以获得更准确的回答。
"""


# ----------------------------
# Event sheet generation prompt
# ----------------------------

EVENT_GENERATION_PROMPT = """You are a Construct 3 event sheet generation expert. Prioritize patterns and capabilities found in the [Similar Example Projects].

## Similar Example Projects (referenceable, numbered)
{similar_examples}

## User Requirement
{user_requirement}

## Requirements (must follow)
1. Output a "copy-paste ready" event sheet structure: groups / comments / conditions / actions clearly laid out
2. Only use object types, behaviors, and system actions that appear in the examples; if a required capability is absent, write "假设：需要插件/行为 X" and provide an alternative
3. Provide:
   - Object list (object type + required behaviors/plugins)
   - Variable list (global/instance, naming suggestions)
   - Key event groups (implementing the core path)
4. Keep it minimal-viable: implement the core path first, then optional enhancements
5. End with a "依赖说明": what comes from examples [来源: x] and what is general advice [通用经验]

Output the event sheet in Chinese (Simplified):"""


# ----------------------------
# Query router prompt
# ----------------------------

ROUTER_PROMPT = """Classify the user intent. Output ONLY one word: qa / code / other

User question: {question}

Rules:
- code: contains "事件表/生成事件/写逻辑/实现功能/给示例/条件动作/Construct 逻辑" or clearly requests generating a solution
- qa: asks about usage, concept explanation, error cause, where a feature is, how a behavior/plugin works
- other: unrelated to Construct 3 or cannot be determined

Output one word only:"""


# ----------------------------
# Query rewrite prompt
# ----------------------------

QUERY_REWRITE_PROMPT = """You are a search query optimization expert. The user is searching Construct 3 content.

Original query: {original_query}

Generate 3 queries (must satisfy):
- At least 1 in Chinese
- At least 1 in pure English
- At least 1 mixed Chinese-English
- Include object/behavior/event sheet keywords where possible (Sprite, Event sheet, Behavior, Instance variable, etc.)

One query per line, no numbering or explanation:"""


# ----------------------------
# Query Decomposition Prompt (for complex multi-step workflows)
# ----------------------------

QUERY_DECOMPOSITION_PROMPT = """You are a Construct 3 problem analysis expert. The user has asked a complex multi-step question.

## Original Question
{original_query}

## Task
Break this into 2–4 independent sub-questions. Each sub-question should:
1. Focus on one specific Construct 3 concept or feature
2. Be independently retrievable from documentation
3. Cover a different aspect of the original question

## Decomposition strategy
- Multiple objects/behaviors: query each separately
- Process-oriented: decompose into setup / runtime / trigger conditions
- Concept + implementation: split into "what is it" and "how to do it"

## Output format
One sub-question per line, no numbering or explanation. Be specific and include Construct 3 keywords.

Sub-questions:"""


# ----------------------------
# Self-Reflection Prompt (anti-hallucination)
# ----------------------------

SELF_REFLECTION_PROMPT = """You are a Construct 3 fact-checker. Verify whether the following answer is reliable.

## Original Question
{question}

## Initial Answer
{answer}

## References
{source_context}

## Checklist
1. Do all [来源: N] citations actually exist in the references?
2. Does the answer contain "facts" not mentioned in any reference?
3. Which claims are confirmed facts vs. inference/general knowledge?

## Output format
Compare the answer against the references carefully, then return:

```
可靠性：[可靠 / 不可靠]

核查发现：
- [list all fabricated or unsourced claims]
- [list all correctly cited claims]

如果不可靠，给出修正后的版本（中文）：
[corrected answer in Chinese]
```

Output only the above, no other explanation."""


# ----------------------------
# Answer Verification Prompt
# ----------------------------

ANSWER_VERIFICATION_PROMPT = """Verify the quality of the following Construct 3 Q&A:

## User Question
{question}

## Answer
{answer}

## Criteria
1. Does the answer directly address the question?
2. Are all facts cited with [来源: N]?
3. Is there obvious fabrication (information completely absent from references)?
4. Is "文档未找到" stated when it should be?

## Output format
```
事实准确性：[完全准确 / 部分准确 / 存在捏造]
引用完整度：[完整 / 部分缺失 / 几乎无引用]
问题针对度：[高度相关 / 部分相关 / 不太相关]

需要改进的地方：[specific details]
```

Output only the above format, nothing else."""


# ----------------------------
# Event sheet JSON generation prompt (clipboard format)
# ----------------------------

CLIPBOARD_FORMAT_REFERENCE = """
## Construct 3 Clipboard JSON Format

### Root structure
```json
{"is-c3-clipboard-data": true, "type": "events", "items": [...]}
```

### Event types (eventType)

**comment**: `{"eventType": "comment", "text": "注释内容"}`

**variable**:
```json
{"eventType": "variable", "name": "Score", "type": "number", "initialValue": "0", "comment": "", "isStatic": false, "isConstant": false}
```
- type: "number" | "string" | "boolean"
- isConstant: true = constant (recommend ALL_CAPS naming)
- isStatic: true = static (persists across layouts)

**group**:
```json
{"eventType": "group", "disabled": false, "title": "Title", "description": "", "isActiveOnStart": true, "children": [...]}
```

**block**:
```json
{"eventType": "block", "conditions": [...], "actions": [...]}
{"eventType": "block", "conditions": [...], "actions": [], "children": [...]}
{"eventType": "block", "conditions": [...], "actions": [], "isOrBlock": true}
```

**function-block**:
```json
{"eventType": "function-block", "functionName": "MyFunc", "functionDescription": "", "functionCategory": "", "functionReturnType": "none", "functionIsAsync": false, "functionParameters": [...], "conditions": [], "actions": [], "children": [...]}
```
- functionReturnType: "none" | "number" | "string" | "any"
- functionParameters: [{"name": "Param1", "type": "number", "initialValue": "0", "comment": ""}]

### Condition format
```json
{"id": "condition-id", "objectClass": "ObjectName", "parameters": {...}}
{"id": "condition-id", "objectClass": "ObjectName", "behaviorType": "BehaviorName", "parameters": {...}}
{"id": "condition-id", "objectClass": "ObjectName", "parameters": {...}, "isInverted": true}
```

### Action format
```json
{"id": "action-id", "objectClass": "ObjectName", "parameters": {...}}
{"id": "action-id", "objectClass": "ObjectName", "behaviorType": "BehaviorName", "parameters": {...}}
{"callFunction": "FunctionName"}
{"callFunction": "FunctionName", "parameters": ["param1", "param2"]}
{"type": "comment", "text": "inline comment"}
```

### Comparison operators
0 = equal, 1 = not equal, 2 = less than, 3 = less than or equal, 4 = greater than, 5 = greater than or equal

### Key rules
1. All parameter values are strings ("100" not 100)
2. String parameters need escaped quotes ("\\"Hello\\"")
3. objectClass must match the object type name in the project
4. behaviorType uses the display name (e.g. "Platform", "Tween", "Timer")
5. Condition/action id must come from the Schema definition

---

## object-types format (object type definitions)

Three variants based on plugin-id:

**World objects (Sprite, Text, TiledBg, Tilemap, etc.)**:
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[
  {"name":"Player","plugin-id":"Sprite","isGlobal":false,"editorNewInstanceIsReplica":true,
   "instanceVariables":[],"behaviorTypes":[{"behaviorId":"Platform","name":"Platform"}],
   "effectTypes":[],"animations":{"items":[{"frames":[{"width":32,"height":32,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":0,"useCollisionPoly":true,"duration":1,"tag":""}],"name":"Animation 1","isLooping":false,"isPingPong":false,"repeatCount":1,"repeatTo":0,"speed":5}],"subfolders":[],"name":"Animations"}}
],"folders":[]}
```

**Singleton global objects (Keyboard, Mouse, Audio, Touch, Browser, etc.)**:
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[
  {"name":"Keyboard","plugin-id":"Keyboard","singleglobal-inst":{"type":"Keyboard","properties":{},"tags":""}}
],"folders":[]}
```

**Non-world data objects (Array→Arr, Dictionary, BinaryData, etc.)**:
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[
  {"name":"Scores","plugin-id":"Arr","isGlobal":true,"editorNewInstanceIsReplica":true,
   "instanceVariables":[],"nonworld-inst":{"type":"Arr","properties":{},"tags":"","instanceVariables":{}}}
],"folders":[]}
```

**behaviorTypes**: `[{"behaviorId":"EightDir","name":"8Direction"}]` — behaviorId is internal ID, name is display name
**effectTypes**: `[{"id":"blur","name":"Blur"}]`
**Common plugin-ids**: Sprite, Text, TiledBg, Tilemap, Keyboard, Mouse, Audio, Touch, Browser, AJAX, Arr, Dictionary
"""


EVENT_JSON_GENERATION_PROMPT = """You are a Construct 3 event sheet JSON generation expert. Generate clipboard-ready JSON based on the user's requirement.

## Available Schema (ACE definitions)
{schema_context}

## Clipboard Format Reference
{format_reference}

## User Requirement
{user_requirement}

## Requirements (must follow)

1. **Use Schema ids strictly**:
   - Condition and action `id` must exactly match the Schema
   - Parameter names must exactly match Schema `params[].id`
   - If a required feature is not in the Schema, state it explicitly

2. **Correct objectClass**:
   - System conditions/actions: objectClass = "System"
   - Input plugins: objectClass = "Keyboard" / "Mouse" / "Touch" / "Gamepad"
   - User objects: objectClass = user-defined name (e.g. "Player", "Enemy")

3. **Correct behaviorType**:
   - Only include behaviorType for behavior-specific conditions/actions
   - Use the display name (e.g. "Platform", "8Direction", "Tween")

4. **Parameter format**:
   - All values as strings: "100" not 100
   - Strings need escaping: "\\"Hello\\""
   - Expressions written directly: "Player.X", "random(0, 100)"

5. **Output format**:
   - Output complete clipboard JSON in a code block
   - Add a brief explanation in Chinese

## Output

Generate the event sheet JSON (explanation in Chinese):
"""


# ----------------------------
# Optional helpers (context formatting)
# ----------------------------

JS_HINT_FOOTER = """
---
> 💡 以上功能也可以通过 JavaScript / TypeScript 实现。Construct 3 支持两种脚本方式：
> 1. 在事件表中使用「脚本」动作内嵌 JS 代码
> 2. 在项目脚本文件中编写 JS/TS 模块，通过 runtime API 调用
>
> 如需了解脚本写法，可重新提问并启用「包含 JS」选项。"""

JS_INCLUDE_INSTRUCTION = """
## JavaScript supplement
In addition to the event sheet solution, also provide a JavaScript implementation (if applicable):
1. **Inline script** — using the "Run script" action, embed a JS snippet
2. **Script file** — implement via runtime API in a .js/.ts file (e.g. `runtime.objects.Sprite`, `runtime.callFunction()`)
Provide a minimal working code example and cite the runtime API source."""


CONTEXT_FORMAT_GUIDE = """Recommended context evidence block format:
[1] title: <title/section>
    source: <URL/filename>
    snippet: <original text excerpt>
[2] title: ...
    source: ...
    snippet: ...
"""


# ----------------------------
# Lookup Tier 3 classify prompt
# ----------------------------

LOOKUP_CLASSIFY_PROMPT = (
    "Classify whether the following query is a precise lookup for Construct 3.\n"
    'Output JSON only: {{"type": "ace_list|ace_detail|prop_list|term|rag", '
    '"plugin": "plugin_name", "ace_type": "actions|conditions|expressions|properties"}}\n'
    "Query: {query}"
)


# ----------------------------
# Self-reflection parsing keywords (must match LLM output in Chinese)
# ----------------------------

REFLECTION_VERDICT_KEY = "可靠性"
REFLECTION_UNRELIABLE = "不可靠"
REFLECTION_RELIABLE = "可靠"
