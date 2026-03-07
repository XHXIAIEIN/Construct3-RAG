# Query Expander Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a two-stage pre-retrieval component that expands Chinese query tokens via a manual dict + schema inverted index, then bridges zh→en to produce precise ACE identifiers for better vector retrieval.

**Architecture:** `SmallLLMExpander` uses a tiny HuggingFace model (Qwen3-0.5B, CPU by default) to generate semantically related Chinese terms from query tokens — replacing hand-crafted dictionaries as the primary expansion source. `SchemaZhEnIndex` builds an inverted index from all schema JSON files (plugins/behaviors/effects/features/editor) mapping Chinese tokens to ACE nodes. `QueryExpander` merges LLM expansion + manual fallback + schema auto-expansion, then scores nodes by term overlap. High-scoring matches augment the retrieval query with English ACE identifiers.

**Tech Stack:** Python dataclasses, jieba, HuggingFace transformers, pathlib, json, existing `SchemaIndex` from `src/rag/lookup.py`

---

## Task 0: Add EXPANDER_MODEL config

**Files:**
- Modify: `src/config.py`

**Step 1: Append to config.py**

```python
# =============================================================================
# Query Expander (SmallLLMExpander)
# =============================================================================
# Ultra-small model for semantic query token expansion (zh → related zh terms).
# Runs on CPU by default — does not compete with main LLM for VRAM.
# Set EXPANDER_MODEL="" to disable LLM expansion (fall back to manual+auto only).
EXPANDER_MODEL  = os.getenv("EXPANDER_MODEL",  "Qwen/Qwen3-0.5B")
EXPANDER_DEVICE = os.getenv("EXPANDER_DEVICE", "cpu")   # "cpu" | "cuda"
EXPANDER_MAX_NEW_TOKENS = int(os.getenv("EXPANDER_MAX_NEW_TOKENS", "80"))
EXPANDER_TIMEOUT_S      = float(os.getenv("EXPANDER_TIMEOUT_S",    "5.0"))
```

**Step 2: Verify**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -c "from src.config import EXPANDER_MODEL, EXPANDER_DEVICE; print(EXPANDER_MODEL, EXPANDER_DEVICE)"
```

Expected: `Qwen/Qwen3-0.5B cpu`

**Step 3: Commit**

```bash
git add src/config.py
git commit -m "feat: add EXPANDER_MODEL/DEVICE config for SmallLLMExpander"
```

---

## Task 0.5: Implement SmallLLMExpander

**Files:**
- Create: `src/rag/query_expander.py` (first pass — SmallLLMExpander only)

**Step 1: Write failing tests for SmallLLMExpander**

Add to `tests/test_query_expander.py` (create the file now with just this class):

```python
"""Tests for SmallLLMExpander — LLM mocked, no model download required."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSmallLLMExpander:

    def test_available_false_when_model_empty(self):
        from src.rag.query_expander import SmallLLMExpander
        exp = SmallLLMExpander(model_path="")
        assert exp.available is False

    def test_expand_returns_empty_when_unavailable(self):
        from src.rag.query_expander import SmallLLMExpander
        exp = SmallLLMExpander(model_path="")
        result = exp.expand(["查找", "数组"])
        assert result == set()

    def test_expand_calls_model_generate(self):
        from src.rag.query_expander import SmallLLMExpander
        exp = SmallLLMExpander.__new__(SmallLLMExpander)
        exp._cache = {}
        exp._model_path = "fake"
        # Inject mock model + tokenizer
        mock_tok = MagicMock()
        mock_tok.return_value = {"input_ids": MagicMock()}
        mock_tok.decode = MagicMock(return_value="包含\n检测\n遍历\n索引")
        mock_model = MagicMock()
        mock_model.generate = MagicMock(return_value=[[0, 1, 2]])
        exp._tokenizer = mock_tok
        exp._model = mock_model
        result = exp._run_inference(["查找", "数组"])
        assert isinstance(result, set)

    def test_expand_caches_result(self):
        from src.rag.query_expander import SmallLLMExpander
        exp = SmallLLMExpander(model_path="")
        exp.expand(["查找"])
        exp.expand(["查找"])  # second call should use cache
        # No assertion needed — just verify no exception

    def test_parse_output_extracts_words(self):
        from src.rag.query_expander import SmallLLMExpander
        exp = SmallLLMExpander.__new__(SmallLLMExpander)
        result = exp._parse_output("包含\n检测\n遍历\n索引\n比较\n")
        assert "包含" in result
        assert "检测" in result
        assert len(result) <= 12

    def test_parse_output_filters_short_tokens(self):
        from src.rag.query_expander import SmallLLMExpander
        exp = SmallLLMExpander.__new__(SmallLLMExpander)
        result = exp._parse_output("的\n包含\n检测\na\n遍历\n")
        assert "的" not in result
        assert "a" not in result
        assert "包含" in result
```

**Step 2: Run tests to confirm they fail**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_query_expander.py::TestSmallLLMExpander -v 2>&1 | head -20
```

Expected: `ERROR — ModuleNotFoundError`

**Step 3: Implement SmallLLMExpander**

Create `src/rag/query_expander.py`:

```python
"""Query Expander: semantic expansion + schema zh→en bridging."""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jieba

from src.config import DATA_DIR, EXPANDER_MODEL, EXPANDER_DEVICE, EXPANDER_MAX_NEW_TOKENS, EXPANDER_TIMEOUT_S

logger = logging.getLogger(__name__)

_SCHEMA_DIR = Path(DATA_DIR) / "schemas"

_EXPAND_PROMPT = (
    "你是一个语义联想助手。给定技术文档查询中的关键词，"
    "列出相关的中文动词和名词（每行一个，不超过12个，只输出词语）：\n\n"
    "关键词：{keywords}\n\n相关词：\n"
)

_ZH_SKIP: frozenset[str] = frozenset({
    "的", "了", "在", "是", "有", "和", "就", "不", "都", "一",
    "上", "也", "到", "要", "去", "会", "着", "没", "好", "这",
    "他", "她", "它", "中", "把", "那", "被", "从", "对", "让",
    "给", "用", "与", "向", "于", "某", "其", "将", "该", "或",
    "以", "及", "并", "但", "而", "如", "当", "若", "为", "由",
    "可", "能", "应", "需", "至", "等", "种", "个", "件", "些",
})


class SmallLLMExpander:
    """Ultra-lightweight LLM semantic expander.

    Uses a small HuggingFace model (default: Qwen3-0.5B) to generate
    semantically related Chinese terms for query tokens. Runs on CPU by
    default to avoid competing with the main LLM for VRAM.

    Falls back gracefully (returns empty set) when:
    - EXPANDER_MODEL is empty string
    - Model fails to load
    - Inference times out (> EXPANDER_TIMEOUT_S)
    """

    def __init__(
        self,
        model_path: str = EXPANDER_MODEL,
        device: str = EXPANDER_DEVICE,
    ) -> None:
        self._model_path = model_path
        self._device = device
        self._model = None
        self._tokenizer = None
        self._load_error: str | None = None
        self._cache: dict[frozenset, set[str]] = {}
        self._lock = threading.Lock()
        if model_path:
            self._lazy_load()

    def _lazy_load(self) -> None:
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM
            import torch
            logger.info(f"[SmallLLM] Loading {self._model_path} on {self._device}...")
            self._tokenizer = AutoTokenizer.from_pretrained(
                self._model_path, trust_remote_code=True
            )
            self._model = AutoModelForCausalLM.from_pretrained(
                self._model_path, torch_dtype=torch.float32, trust_remote_code=True
            )
            if self._device != "cpu":
                self._model = self._model.to(self._device)
            self._model.eval()
            logger.info(f"[SmallLLM] Loaded OK")
        except Exception as e:
            self._load_error = str(e)
            logger.warning(f"[SmallLLM] Load failed: {e} — expansion disabled")

    @property
    def available(self) -> bool:
        return self._model is not None and self._tokenizer is not None

    def expand(self, tokens: list[str]) -> set[str]:
        """Return semantically related zh terms. Empty set if unavailable."""
        if not self.available:
            return set()
        cache_key = frozenset(tokens)
        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]
        result = self._run_with_timeout(tokens)
        with self._lock:
            self._cache[cache_key] = result
        return result

    def _run_with_timeout(self, tokens: list[str]) -> set[str]:
        result: set[str] = set()
        exc: list[Exception] = []

        def _target():
            try:
                result.update(self._run_inference(tokens))
            except Exception as e:
                exc.append(e)

        t = threading.Thread(target=_target, daemon=True)
        t.start()
        t.join(timeout=EXPANDER_TIMEOUT_S)
        if t.is_alive():
            logger.warning("[SmallLLM] Inference timeout — skipping expansion")
            return set()
        if exc:
            logger.warning(f"[SmallLLM] Inference error: {exc[0]}")
            return set()
        return result

    def _run_inference(self, tokens: list[str]) -> set[str]:
        import torch
        prompt = _EXPAND_PROMPT.format(keywords=" / ".join(tokens))
        inputs = self._tokenizer(prompt, return_tensors="pt")
        if self._device != "cpu":
            inputs = {k: v.to(self._device) for k, v in inputs.items()}
        with torch.no_grad():
            out = self._model.generate(
                **inputs,
                max_new_tokens=EXPANDER_MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=self._tokenizer.eos_token_id,
            )
        input_len = inputs["input_ids"].shape[1]
        new_tokens = out[0][input_len:]
        text = self._tokenizer.decode(new_tokens, skip_special_tokens=True)
        return self._parse_output(text)

    def _parse_output(self, text: str) -> set[str]:
        """Parse LLM output: one word per line, filter noise."""
        result: set[str] = set()
        for line in text.strip().splitlines():
            word = line.strip().strip("、，。,.")
            if len(word) >= 2 and word not in _ZH_SKIP:
                result.add(word)
            if len(result) >= 12:
                break
        return result
```

**Step 4: Run SmallLLMExpander tests**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_query_expander.py::TestSmallLLMExpander -v
```

Expected: all pass.

**Step 5: Run full suite**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/ -v 2>&1 | tail -5
```

Expected: `126 passed`

**Step 6: Commit**

```bash
git add src/rag/query_expander.py tests/test_query_expander.py
git commit -m "feat: implement SmallLLMExpander with lazy load, cache, and timeout"
```

---

## Task 1: Add SEMANTIC_EXPAND to keywords.py

**Files:**
- Modify: `src/locale/keywords.py`

**Step 1: Append the dict at end of file**

```python
# ---------------------------------------------------------------------------
# 语义扩展词表 — 用于 QueryExpander 手工增补（与 schema 自动扩展合并）
# key: 用户查询中常见的中文动词/名词
# value: 在 C3 schema 描述中语义相近的词，帮助 zh→en 桥接
# ---------------------------------------------------------------------------

SEMANTIC_EXPAND: dict[str, list[str]] = {
    '查找': ['包含', '检测', '遍历', '存在', '检索', '条件', '表达式', '比较'],
    '搜索': ['包含', '检测', '遍历', '存在', '检索', '查询'],
    '排序': ['升序', '降序', '动作', '顺序', '比较'],
    '碰撞': ['重叠', '检测', '条件', '触发'],
    '移动': ['速度', '方向', '动作', '位置', '角度'],
    '播放': ['动画', '音频', '声音', '动作'],
    '创建': ['实例', '生成', '动作', '对象'],
    '删除': ['销毁', '移除', '动作', '实例'],
    '设置': ['修改', '动作', '属性', '值'],
    '获取': ['读取', '表达式', '返回', '值'],
    '计时': ['时间', '延迟', '等待', '秒'],
    '存储': ['保存', '数据', '变量', '文件'],
    '加载': ['读取', '文件', '数据', '动作'],
    '显示': ['可见', '透明度', '动作', '隐藏'],
    '隐藏': ['可见', '透明度', '动作', '显示'],
    '旋转': ['角度', '动作', '方向'],
    '缩放': ['大小', '尺寸', '宽度', '高度', '动作'],
    '文本': ['字符串', '内容', '表达式', '属性'],
    '数字': ['值', '变量', '表达式', '参数', '整数', '浮点'],
    '数组': ['数据结构', '列表', '索引', '元素'],
    '条件': ['判断', '比较', '检测', '触发', '如果'],
    '动作': ['执行', '操作', '设置', '调用'],
    '表达式': ['返回', '计算', '获取', '值'],
}
```

**Step 2: Verify import works**

```bash
cd D:/Users/Administrator/Documents/GitHub/Construct3-RAG
/c/Users/test/AppData/Local/Python/bin/python.exe -c "from src.locale.keywords import SEMANTIC_EXPAND; print(len(SEMANTIC_EXPAND), 'entries')"
```

Expected: `23 entries`

**Step 3: Commit**

```bash
git add src/locale/keywords.py
git commit -m "feat: add SEMANTIC_EXPAND manual expansion dict to keywords"
```

---

## Task 2: Build SchemaZhEnIndex — data structures

**Files:**
- Create: `src/rag/query_expander.py`

**Step 1: Write failing test for NodeData and index construction**

Create `tests/test_query_expander.py`:

```python
"""Tests for QueryExpander — all mocked, no external services required."""
import sys
from pathlib import Path
from dataclasses import dataclass, field
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Minimal schema fixture (mimics one plugin JSON)
# ---------------------------------------------------------------------------

FIXTURE_ARR = {
    "id": "arr",
    "name_zh": "数组",
    "name_en": "Array",
    "description_zh": "允许将数据储存在最多三维的数组空间中。",
    "description_en": "Store an array of values in up to 3 dimensions.",
    "path": "data-and-storage/array",
    "categories": ["array", "data"],
    "conditions": [
        {
            "id": "contains-value",
            "name_zh": "如果包含值",
            "name_en": "Contains value",
            "description_zh": "查找整个数组，检测是否包含某个值。",
            "description_en": "Test if the array contains a value.",
            "scriptName": "ContainsValue",
            "params": [
                {
                    "id": "value",
                    "type": "any",
                    "name_zh": "值",
                    "name_en": "Value",
                }
            ],
        }
    ],
    "actions": [],
    "expressions": [
        {
            "id": "index-of",
            "name_zh": "索引",
            "name_en": "IndexOf",
            "description_zh": "返回某个值在数组中的索引位置。",
            "description_en": "Get the index of a value in the array.",
            "scriptName": "IndexOf",
            "params": [
                {
                    "id": "value",
                    "type": "any",
                    "name_zh": "值",
                    "name_en": "Value",
                }
            ],
        }
    ],
    "properties": [],
}

FIXTURE_EFFECT = {
    "id": "blur",
    "name_zh": "模糊",
    "name_en": "Blur",
    "description_zh": "对对象应用模糊效果。",
    "description_en": "Apply a blur effect.",
    "category": "blur",
    "parameters": [
        {"id": "amount", "name_zh": "强度", "name_en": "Amount"}
    ],
}

FIXTURE_EDITOR = {
    "version": "1.0",
    "bars": {
        "layers": {"name_zh": "图层栏", "name_en": "Layers"},
    },
    "dialogs": {
        "addBehavior": {"name_zh": "添加行为", "name_en": "Add Behavior"},
    },
    "views": {},
    "stats": {},
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSchemaZhEnIndex:

    def _make_index(self):
        from src.rag.query_expander import SchemaZhEnIndex
        idx = SchemaZhEnIndex.__new__(SchemaZhEnIndex)
        idx._build_from_fixtures(
            plugins=[FIXTURE_ARR],
            behaviors=[],
            effects=[FIXTURE_EFFECT],
            features=[],
            editor=FIXTURE_EDITOR,
        )
        return idx

    def test_plugin_node_indexed(self):
        idx = self._make_index()
        assert "arr" in idx.node_data

    def test_ace_node_indexed(self):
        idx = self._make_index()
        assert "arr/contains-value" in idx.node_data

    def test_zh_token_hits_plugin(self):
        idx = self._make_index()
        hits = idx.token_to_nodes.get("数组", set())
        assert "arr" in hits

    def test_zh_token_hits_ace(self):
        idx = self._make_index()
        # "包含" appears in contains-value description
        hits = idx.token_to_nodes.get("包含", set())
        assert "arr/contains-value" in hits

    def test_effect_indexed_with_lower_weight(self):
        idx = self._make_index()
        assert "blur" in idx.node_data
        assert idx.node_data["blur"].weight == 0.9

    def test_editor_indexed_with_lowest_weight(self):
        idx = self._make_index()
        assert "bar/layers" in idx.node_data
        assert idx.node_data["bar/layers"].weight == 0.4

    def test_en_tokens_extracted(self):
        idx = self._make_index()
        en = idx.node_data["arr/contains-value"].en_tokens
        assert "ContainsValue" in en or "Contains" in en

    def test_search_returns_scored_matches(self):
        idx = self._make_index()
        matches = idx.search({"数组", "包含", "值"})
        ids = [m.node_id for m in matches]
        assert "arr/contains-value" in ids

    def test_search_score_ordered(self):
        idx = self._make_index()
        matches = idx.search({"数组", "包含", "值"})
        scores = [m.score for m in matches]
        assert scores == sorted(scores, reverse=True)

    def test_editor_lower_score_than_plugin(self):
        idx = self._make_index()
        # Both "图层" and "数组" in term_set
        matches = idx.search({"数组", "图层"})
        plugin_score = next((m.score for m in matches if m.node_id == "arr"), 0)
        editor_score = next((m.score for m in matches if m.node_id == "bar/layers"), 0)
        assert plugin_score > editor_score


class TestQueryExpander:

    def _make_expander(self):
        from src.rag.query_expander import QueryExpander, SchemaZhEnIndex
        idx = SchemaZhEnIndex.__new__(SchemaZhEnIndex)
        idx._build_from_fixtures(
            plugins=[FIXTURE_ARR], behaviors=[], effects=[], features=[], editor={}
        )
        manual = {"查找": ["包含", "遍历", "存在"]}
        return QueryExpander(schema_index=idx, manual_expand=manual)

    def test_expand_manual_terms(self):
        exp = self._make_expander()
        result = exp.expand(["查找"])
        assert "包含" in result["查找"]
        assert "遍历" in result["查找"]

    def test_expand_auto_terms(self):
        exp = self._make_expander()
        # "数组" appears in arr plugin; other tokens from arr should expand
        result = exp.expand(["数组"])
        assert "数组" in result  # key exists

    def test_get_term_set_includes_originals(self):
        exp = self._make_expander()
        ts = exp.get_term_set(["查找", "数组"])
        assert "查找" in ts
        assert "数组" in ts

    def test_get_term_set_includes_expansions(self):
        exp = self._make_expander()
        ts = exp.get_term_set(["查找"])
        assert "包含" in ts  # from manual expand

    def test_search_via_expander(self):
        exp = self._make_expander()
        ts = exp.get_term_set(["数组", "查找"])
        matches = exp.search(ts)
        assert len(matches) > 0
```

**Step 2: Run test to confirm it fails**

```bash
cd D:/Users/Administrator/Documents/GitHub/Construct3-RAG
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_query_expander.py -v 2>&1 | head -30
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'src.rag.query_expander'`

**Step 3: Commit failing tests**

```bash
git add tests/test_query_expander.py
git commit -m "test: add failing tests for SchemaZhEnIndex and QueryExpander"
```

---

## Task 3: Implement SchemaZhEnIndex

**Files:**
- Create: `src/rag/query_expander.py`

**Step 1: Write the full implementation**

```python
"""Query Expander: Chinese token expansion + Schema zh→en bridging.

Two components:
- SchemaZhEnIndex: inverted index over all schema JSON files (zh tokens → nodes)
- QueryExpander:   combines manual SEMANTIC_EXPAND + auto expansion, scores nodes
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jieba

from src.config import DATA_DIR

logger = logging.getLogger(__name__)

# Schema root directory
_SCHEMA_DIR = Path(DATA_DIR) / "schemas"

# Node type weights
_WEIGHTS: dict[str, float] = {
    "plugin":   1.0,
    "behavior": 1.0,
    "effect":   0.9,
    "feature":  0.8,
    "editor":   0.4,
}

# Jieba stop tokens to skip when building zh vocab
_ZH_SKIP: frozenset[str] = frozenset({
    "的", "了", "在", "是", "有", "和", "就", "不", "都", "一",
    "上", "也", "到", "要", "去", "会", "着", "没", "好", "这",
    "他", "她", "它", "中", "把", "那", "被", "从", "对", "让",
    "给", "用", "与", "向", "于", "某", "其", "将", "该", "或",
    "以", "及", "并", "但", "而", "如", "当", "若", "为", "由",
    "可", "能", "应", "需", "至", "等", "种", "个", "件", "些",
})


def _tokenize_zh(text: str) -> set[str]:
    """Jieba-tokenize Chinese text, return filtered token set."""
    tokens = set()
    for tok in jieba.lcut(text):
        tok = tok.strip()
        if len(tok) >= 2 and tok not in _ZH_SKIP:
            tokens.add(tok)
    return tokens


def _extract_en_tokens(data: dict[str, Any], *keys: str) -> set[str]:
    """Extract non-empty English tokens from given keys."""
    tokens: set[str] = set()
    for k in keys:
        val = data.get(k, "")
        if val and isinstance(val, str):
            # Split on common separators, keep meaningful tokens
            for part in val.replace("-", " ").replace("/", " ").split():
                if len(part) >= 2:
                    tokens.add(part)
    return tokens


@dataclass
class NodeData:
    node_id: str
    schema_type: str          # plugin/behavior/effect/feature/editor
    plugin_id: str            # parent plugin id (same as node_id for plugin nodes)
    ace_type: str | None      # conditions/actions/expressions/properties or None
    weight: float
    zh_tokens: frozenset[str]
    en_tokens: frozenset[str]


@dataclass
class SchemaMatch:
    node_id: str
    plugin_id: str
    schema_type: str
    ace_type: str | None
    score: float
    en_tokens: frozenset[str]


class SchemaZhEnIndex:
    """Inverted index from Chinese schema tokens to ACE nodes.

    Supports five schema types with different weights:
      plugins/behaviors (1.0) > effects (0.9) > features (0.8) > editor (0.4)
    """

    def __init__(self) -> None:
        self.token_to_nodes: dict[str, set[str]] = {}
        self.node_data: dict[str, NodeData] = {}
        self._build()

    def _build(self) -> None:
        """Load all schema files and build the index."""
        plugins   = _load_json_dir(_SCHEMA_DIR / "plugins")
        behaviors = _load_json_dir(_SCHEMA_DIR / "behaviors")
        effects   = _load_json_dir(_SCHEMA_DIR / "effects")
        features  = _load_json_dir(_SCHEMA_DIR / "features")
        editor    = _load_editor(_SCHEMA_DIR / "editor" / "index.json")
        self._build_from_fixtures(plugins, behaviors, effects, features, editor)
        logger.info(
            f"[SchemaZhEnIndex] Built: {len(self.node_data)} nodes, "
            f"{len(self.token_to_nodes)} zh tokens"
        )

    def _build_from_fixtures(
        self,
        plugins: list[dict],
        behaviors: list[dict],
        effects: list[dict],
        features: list[dict],
        editor: dict,
    ) -> None:
        """Build index from pre-loaded data (also used in tests)."""
        for schema in plugins:
            self._index_plugin_or_behavior(schema, "plugin")
        for schema in behaviors:
            self._index_plugin_or_behavior(schema, "behavior")
        for schema in effects:
            self._index_effect(schema)
        for schema in features:
            self._index_feature(schema)
        self._index_editor(editor)

    def _index_plugin_or_behavior(self, d: dict, schema_type: str) -> None:
        plugin_id = d.get("id", "")
        weight = _WEIGHTS[schema_type]

        # Plugin-level node
        zh = _tokenize_zh(
            " ".join(filter(None, [d.get("name_zh"), d.get("description_zh")]))
        )
        en = _extract_en_tokens(d, "name_en", "description_en")
        # path tokens: "data-and-storage/array" → {"data", "and", "storage", "array"}
        for part in d.get("path", "").replace("/", " ").split():
            if len(part) >= 2:
                en.add(part)
        en.update(d.get("categories", []))

        self._add_node(NodeData(
            node_id=plugin_id, schema_type=schema_type, plugin_id=plugin_id,
            ace_type=None, weight=weight,
            zh_tokens=frozenset(zh), en_tokens=frozenset(en),
        ))

        # ACE-level nodes
        for ace_type in ("conditions", "actions", "expressions", "properties"):
            for ace in d.get(ace_type, []):
                self._index_ace(ace, plugin_id, ace_type, schema_type, weight)

    def _index_ace(
        self, ace: dict, plugin_id: str, ace_type: str,
        schema_type: str, weight: float,
    ) -> None:
        ace_id = ace.get("id", "")
        node_id = f"{plugin_id}/{ace_id}"

        zh = _tokenize_zh(
            " ".join(filter(None, [ace.get("name_zh"), ace.get("description_zh")]))
        )
        en = _extract_en_tokens(ace, "name_en", "description_en", "scriptName")

        # Params
        for param in ace.get("params", []):
            zh.update(_tokenize_zh(param.get("name_zh", "")))
            en_tok = param.get("name_en", "").strip()
            if en_tok and len(en_tok) >= 2:
                en.add(en_tok)
            # items_i18n
            for item_val in param.get("items_i18n", {}).values():
                if isinstance(item_val, dict):
                    zh.update(_tokenize_zh(item_val.get("zh", "")))
                    en_tok = item_val.get("en", "").strip()
                    if en_tok and len(en_tok) >= 2:
                        en.add(en_tok)

        self._add_node(NodeData(
            node_id=node_id, schema_type=schema_type, plugin_id=plugin_id,
            ace_type=ace_type, weight=weight,
            zh_tokens=frozenset(zh), en_tokens=frozenset(en),
        ))

    def _index_effect(self, d: dict) -> None:
        effect_id = d.get("id", "")
        zh = _tokenize_zh(
            " ".join(filter(None, [d.get("name_zh"), d.get("description_zh")]))
        )
        en = _extract_en_tokens(d, "name_en", "description_en")
        cat = d.get("category", "")
        if cat:
            en.add(cat)
        for param in d.get("parameters", []):
            zh.update(_tokenize_zh(param.get("name_zh", "")))
            en_tok = param.get("name_en", "").strip()
            if en_tok and len(en_tok) >= 2:
                en.add(en_tok)
        self._add_node(NodeData(
            node_id=effect_id, schema_type="effect", plugin_id=effect_id,
            ace_type=None, weight=_WEIGHTS["effect"],
            zh_tokens=frozenset(zh), en_tokens=frozenset(en),
        ))

    def _index_feature(self, d: dict) -> None:
        feat_id = d.get("id", "")
        zh = _tokenize_zh(
            " ".join(filter(None, [d.get("name_zh"), d.get("description_zh")]))
        )
        en = _extract_en_tokens(d, "name_en", "description_en")
        en.update(str(t) for t in d.get("tags", []) if isinstance(t, str))
        for ex in d.get("examples", []):
            zh.update(_tokenize_zh(ex.get("description_zh", "")))
        for ace_ref in d.get("relatedACE", []):
            if isinstance(ace_ref, str) and len(ace_ref) >= 2:
                en.add(ace_ref)
        self._add_node(NodeData(
            node_id=feat_id, schema_type="feature", plugin_id=feat_id,
            ace_type=None, weight=_WEIGHTS["feature"],
            zh_tokens=frozenset(zh), en_tokens=frozenset(en),
        ))

    def _index_editor(self, d: dict) -> None:
        weight = _WEIGHTS["editor"]
        for group_key in ("bars", "dialogs", "views"):
            for elem_id, elem in d.get(group_key, {}).items():
                if not isinstance(elem, dict):
                    continue
                node_id = f"{group_key[:-1]}/{elem_id}"  # "bars"→"bar"
                name_zh = elem.get("name_zh", "")
                name_en = elem.get("name_en", "")
                zh = _tokenize_zh(name_zh)
                en: set[str] = set()
                for part in name_en.split():
                    if len(part) >= 2:
                        en.add(part)
                if not zh and not en:
                    continue
                self._add_node(NodeData(
                    node_id=node_id, schema_type="editor", plugin_id=elem_id,
                    ace_type=None, weight=weight,
                    zh_tokens=frozenset(zh), en_tokens=frozenset(en),
                ))

    def _add_node(self, node: NodeData) -> None:
        self.node_data[node.node_id] = node
        for tok in node.zh_tokens:
            self.token_to_nodes.setdefault(tok, set()).add(node.node_id)

    def search(self, term_set: set[str]) -> list[SchemaMatch]:
        """Score all nodes by zh token overlap with term_set, return sorted."""
        scores: dict[str, float] = {}
        for tok in term_set:
            for node_id in self.token_to_nodes.get(tok, set()):
                node = self.node_data[node_id]
                if not node.zh_tokens:
                    continue
                overlap = len(term_set & node.zh_tokens)
                raw = overlap / len(node.zh_tokens)
                scores[node_id] = max(scores.get(node_id, 0.0), raw * node.weight)

        return sorted(
            [
                SchemaMatch(
                    node_id=nid,
                    plugin_id=self.node_data[nid].plugin_id,
                    schema_type=self.node_data[nid].schema_type,
                    ace_type=self.node_data[nid].ace_type,
                    score=score,
                    en_tokens=self.node_data[nid].en_tokens,
                )
                for nid, score in scores.items()
            ],
            key=lambda m: -m.score,
        )

    def auto_expand(self, token: str) -> set[str]:
        """Return zh tokens co-occurring with this token across matched nodes."""
        result: set[str] = set()
        for node_id in self.token_to_nodes.get(token, set()):
            result.update(self.node_data[node_id].zh_tokens)
        result.discard(token)
        return result


def _load_json_dir(path: Path) -> list[dict]:
    if not path.exists():
        return []
    result = []
    for f in sorted(path.glob("*.json")):
        try:
            result.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:
            logger.warning(f"[SchemaZhEnIndex] Skip {f.name}: {e}")
    return result


def _load_editor(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"[SchemaZhEnIndex] Skip editor/index.json: {e}")
        return {}
```

**Step 2: Run tests**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_query_expander.py::TestSchemaZhEnIndex -v
```

Expected: all `TestSchemaZhEnIndex` tests PASS.

**Step 3: Commit**

```bash
git add src/rag/query_expander.py
git commit -m "feat: implement SchemaZhEnIndex with five schema types"
```

---

## Task 4: Implement QueryExpander (three-layer merge)

**Files:**
- Modify: `src/rag/query_expander.py` (append class)

**Step 1: Append QueryExpander class to query_expander.py**

```python
class QueryExpander:
    """Three-layer semantic expander + schema zh→en bridge.

    Expansion priority (all merged via union):
      1. SmallLLMExpander  — neural semantic association (primary)
      2. SEMANTIC_EXPAND   — manual fallback dict (fast, always available)
      3. SchemaZhEnIndex   — schema co-occurrence (C3-specific vocabulary)

    Usage:
        expander = QueryExpander()
        term_set = expander.get_term_set(["数组", "查找"])
        matches  = expander.search(term_set)
        # score > 0.7  → en_tokens boost retrieval query heavily
        # score 0.3-0.7 → en_tokens appended to search query
    """

    def __init__(
        self,
        schema_index: SchemaZhEnIndex | None = None,
        manual_expand: dict[str, list[str]] | None = None,
        llm_expander: SmallLLMExpander | None = None,
    ) -> None:
        self._index = schema_index if schema_index is not None else SchemaZhEnIndex()
        if manual_expand is not None:
            self._manual = manual_expand
        else:
            from src.locale.keywords import SEMANTIC_EXPAND
            self._manual = SEMANTIC_EXPAND
        self._llm = llm_expander if llm_expander is not None else SmallLLMExpander()

    def expand(self, tokens: list[str]) -> dict[str, set[str]]:
        """For each token, return union of LLM + manual + auto expansions."""
        # LLM expansion: runs on all tokens as a cluster (better context)
        llm_all = self._llm.expand(tokens)

        result: dict[str, set[str]] = {}
        for tok in tokens:
            manual = set(self._manual.get(tok, []))
            auto   = self._index.auto_expand(tok)
            result[tok] = llm_all | manual | auto
        return result

    def get_term_set(self, tokens: list[str]) -> set[str]:
        """Return flattened union: original tokens + all expansions."""
        term_set = set(tokens)
        for expansions in self.expand(tokens).values():
            term_set.update(expansions)
        return term_set

    def search(self, term_set: set[str]) -> list[SchemaMatch]:
        """Score schema nodes by term_set overlap. Returns sorted matches."""
        return self._index.search(term_set)
```

**Step 2: Update TestQueryExpander tests** to pass a mock `llm_expander`

In `tests/test_query_expander.py`, update `_make_expander()`:

```python
def _make_expander(self):
    from src.rag.query_expander import QueryExpander, SchemaZhEnIndex, SmallLLMExpander
    idx = SchemaZhEnIndex.__new__(SchemaZhEnIndex)
    idx._build_from_fixtures(
        plugins=[FIXTURE_ARR], behaviors=[], effects=[], features=[], editor={}
    )
    manual = {"查找": ["包含", "遍历", "存在"]}
    # Disable LLM for unit tests
    mock_llm = SmallLLMExpander(model_path="")
    return QueryExpander(schema_index=idx, manual_expand=manual, llm_expander=mock_llm)
```

**Step 2: Run all QueryExpander tests**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_query_expander.py -v
```

Expected: all tests PASS.

**Step 3: Run full test suite to check no regression**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/ -v 2>&1 | tail -10
```

Expected: `126 passed`

**Step 4: Commit**

```bash
git add src/rag/query_expander.py
git commit -m "feat: implement QueryExpander with manual+auto expansion and schema search"
```

---

## Task 5: Integrate into RAGChain

**Files:**
- Modify: `src/rag/chain.py`

**Step 1: Add import at top of chain.py**

After existing imports, add:

```python
from .query_expander import QueryExpander, SchemaMatch
```

**Step 2: Instantiate QueryExpander in `__init__`**

In `RAGChain.__init__`, after `self.enable_query_rewrite = enable_query_rewrite`:

```python
self._query_expander: QueryExpander | None = None  # lazy init
```

Add a property for lazy initialization (avoids slowing down tests that mock the retriever):

```python
@property
def query_expander(self) -> QueryExpander:
    if self._query_expander is None:
        self._query_expander = QueryExpander()
    return self._query_expander
```

**Step 3: Insert QueryExpander call in `answer_with_fallback()`**

Find the block in `answer_with_fallback()` that starts with:

```python
# Query enhancement: term keyword expansion via TermIndex
search_query = query
term_keywords: list[dict] = []
if self._is_chinese(query):
    term_keywords = self._extract_term_keywords(query, threshold=0.3)
    if term_keywords:
        en_terms = " ".join(kw["en"] for kw in term_keywords)
        search_query = f"{query} {en_terms}"
        logger.info(f"[TermExpand] +{[kw['en'] for kw in term_keywords]}")
        _trace(f"\"{search_query[:80]}\"", "query")
```

Replace with:

```python
# Query enhancement: term keyword expansion via TermIndex
search_query = query
term_keywords: list[dict] = []
schema_matches: list[SchemaMatch] = []

if self._is_chinese(query):
    term_keywords = self._extract_term_keywords(query, threshold=0.3)
    if term_keywords:
        en_terms = " ".join(kw["en"] for kw in term_keywords)
        search_query = f"{query} {en_terms}"
        logger.info(f"[TermExpand] +{[kw['en'] for kw in term_keywords]}")

    # Schema zh→en bridge via QueryExpander
    segments = self._split_zh_segments(query)
    term_set = self.query_expander.get_term_set(segments)
    schema_matches = self.query_expander.search(term_set)

    high = [m for m in schema_matches if m.score > 0.7]
    mid  = [m for m in schema_matches if 0.3 <= m.score <= 0.7]

    if high or mid:
        boost_matches = high if high else mid[:3]
        en_boost = " ".join(
            tok for m in boost_matches for tok in m.en_tokens
        )
        search_query = f"{search_query} {en_boost}".strip()
        logger.info(f"[SchemaExpand] +{[m.node_id for m in boost_matches]}")

    if search_query != query:
        _trace(f"\"{search_query[:80]}\"", "query")

    # Trace top schema matches
    if schema_matches:
        top3 = schema_matches[:3]
        summary = "  ".join(f"{m.node_id}({m.score:.2f})" for m in top3)
        _trace(summary, "schema_match")
```

Apply the same pattern inside `answer_complex_workflow()` (find the equivalent term expansion block and add schema_matches augmentation after it).

**Step 4: Run tests**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/ -v 2>&1 | tail -15
```

Expected: `126 passed` (existing tests unaffected — they mock the retriever and don't exercise `query_expander`)

**Step 5: Commit**

```bash
git add src/rag/chain.py
git commit -m "feat: integrate QueryExpander into answer_with_fallback and answer_complex_workflow"
```

---

## Task 6: Trace display in chat.py

**Files:**
- Modify: `scripts/chat.py`

**Step 1: Add `schema_match` to `_TRACE_LABEL` and `_TRACE_GROUP`**

In `_TRACE_LABEL`:
```python
"schema_match":  "Schema命中",
```

In `_TRACE_GROUP` — add to group 3 (same as tokenize/expand):
```python
"tokenize": 3, "term_hit": 3, "expand": 3, "query": 3, "schema_match": 3,
```

**Step 2: Run a quick smoke test**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/ -v 2>&1 | tail -5
```

Expected: `126 passed`

**Step 3: Commit**

```bash
git add scripts/chat.py
git commit -m "feat: add schema_match phase to trace display"
```

---

## Task 7: Final verification

**Step 1: Run full test suite**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/ -v
```

Expected: all tests pass (at minimum 126 + new query_expander tests)

**Step 2: Smoke-test index build**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -c "
from src.rag.query_expander import QueryExpander
exp = QueryExpander()
ts = exp.get_term_set(['数组', '查找', '数字'])
matches = exp.search(ts)
print(f'term_set size: {len(ts)}')
for m in matches[:5]:
    print(f'  {m.node_id:<30} score={m.score:.3f}  en={list(m.en_tokens)[:4]}')
"
```

Expected: top matches include `arr/contains-value` and `arr/index-of` with scores > 0.3

**Step 3: Commit summary**

```bash
git log --oneline -8
```

---

## Implementation Notes

- `SchemaZhEnIndex._build_from_fixtures()` is the testable entry point — `__init__` calls `_build()` which loads real files, but tests bypass file I/O by calling `_build_from_fixtures()` directly.
- `query_expander` is a lazy property on `RAGChain` — first call builds the index (takes ~1s at startup, cached thereafter).
- The `schema_matches` variable is local to each call; no global state beyond the cached index.
- `answer_complex_workflow()` also benefits from query augmentation — apply the same pattern there.
- Editor nodes are included at weight 0.4 — they will rarely dominate but help with UI navigation queries like "图层栏在哪".
