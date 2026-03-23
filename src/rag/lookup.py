"""
Query Routing & Direct Lookup System for Construct 3 RAG

Three-tier intent classification + direct JSON lookup:
- Tier 1: Rule-based regex matching (instant, 0 cost)
- Tier 2: bge-m3 embedding similarity (~50ms)
- Tier 3: Ollama small model classification (~1-2s, optional)

If all tiers miss → fallback to standard RAG pipeline.
"""
import re
import json
import logging
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

import jieba

from ._trace import _trace

from src.config import SCHEMA_DIR
from src.locale.keywords import (
    ACE_TYPE_ALIASES, ACE_INTENT_KEYWORDS, HOWTO_SKIP_WORDS,
    ZH_PARTICLES, INTENT_TEMPLATES,
)
from src.rag.messages import (
    ACE_SECTION_LABELS, ACE_SECTION_LABELS_SHORT, PLUGIN_KIND_LABELS,
    ACE_LIST_HEADER, ACE_TABLE_HEADER, ACE_TABLE_SEPARATOR,
    ACE_DETAIL_HEADER, ACE_DESCRIPTION_LABEL, ACE_SCRIPT_NAME,
    ACE_TRIGGER_TYPE, ACE_PARAMS_HEADER, ACE_PARAM_TABLE_HEADER,
    ACE_PARAM_TABLE_SEPARATOR, ACE_NO_PARAMS,
    ACE_SEARCH_HEADER, TERM_TRANSLATE_HEADER, TERM_TABLE_HEADER,
    TERM_TABLE_SEPARATOR, LOOKUP_CLASSIFY_PROMPT,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Compact format helpers (ACE lines for LLM context)
# =============================================================================

_ACE_PREFIX: dict[str, str] = {
    "conditions": "C",
    "actions": "A",
    "expressions": "E",
}

_ACE_SORT_ORDER: dict[str, int] = {
    "conditions": 0,
    "actions": 1,
    "expressions": 2,
}

# Param types where the name carries no semantic value (drop from signature)
_GENERIC_PARAM_TYPES = frozenset({"cmp"})

# Plugin/behavior names that are common English words. When the query is
# purely English and the remaining tokens are also generic (action, event, etc.),
# skip lookup to avoid false matches like "custom action" → Custom behavior.
_AMBIGUOUS_PLUGIN_NAMES = frozenset({
    "custom", "system", "audio", "text", "video", "browser", "touch",
    "mouse", "list", "button", "timer", "json", "array",
})
_GENERIC_QUERY_WORDS = frozenset({
    "action", "actions", "condition", "conditions", "expression", "expressions",
    "event", "events", "function", "functions", "property", "properties",
    "variable", "variables", "how", "what", "use", "create", "add", "make",
})

# Synonym sets for ace_search keyword expansion.
# If any word in a set appears in the query, all words in that set are added
# to the filter. This captures semantic relationships that keyword matching
# misses (e.g. "碰撞" and "重叠" are both collision-detection concepts).
_ACE_SYNONYMS: list[frozenset[str]] = [
    frozenset({"碰撞", "重叠", "collision", "overlap", "collisions"}),
    frozenset({"动画", "animation", "animations", "播放", "帧"}),
    frozenset({"移动", "位置", "坐标", "position", "move"}),
    frozenset({"销毁", "删除", "destroy", "remove"}),
    frozenset({"可见", "显示", "隐藏", "visible", "show", "hide"}),
    frozenset({"计时", "timer", "wait", "等待", "延迟", "delay"}),
    frozenset({"保存", "存储", "存档", "store", "save", "set item", "设置词条"}),
    frozenset({"读取", "加载", "获取", "load", "get item", "获取词条"}),
    frozenset({"速度", "speed", "velocity", "加速"}),
    frozenset({"角度", "旋转", "rotation", "angle", "rotate"}),
    frozenset({"大小", "尺寸", "宽度", "高度", "size", "width", "height", "scale"}),
    frozenset({"按键", "键盘", "key", "keyboard", "pressed"}),
    frozenset({"点击", "触摸", "tap", "click", "touch"}),
    frozenset({"声音", "音效", "音乐", "audio", "sound", "music"}),
]

# Category expansion: when an ACE in one of these categories is matched,
# also include all ACEs sharing the same category (even if they don't
# match the keyword). E.g. matching "碰撞" in category "collisions"
# should also pull in poly-point expressions from the same category.
_CATEGORY_EXPAND = frozenset({"collisions", "animations", "size-position"})


def _format_params(params: list) -> str:
    """Build param signature for actions/expressions: empty for 0–1 params, 'p1,p2' for 2+.

    Single params produce empty string (just `()` in caller).
    Multi-params list their English names, skipping comparison operators.
    """
    semantic = [p for p in params if p.get("type", "") not in _GENERIC_PARAM_TYPES]
    if len(semantic) <= 1:
        return ""
    return ",".join(p.get("name_en", "").strip() for p in semantic if p.get("name_en", "").strip())


def _format_condition_sig(name_en: str, params: list) -> str:
    """Build condition signature: show params when present so LLM knows the call signature.

    Conditions without params → 'Name' (no parens)
    Conditions with params    → 'Name(p1,p2)' (parens with param names, skipping cmp type)
    """
    semantic = [p for p in params if p.get("type", "") not in _GENERIC_PARAM_TYPES]
    if not semantic:
        return name_en
    param_str = ",".join(p.get("name_en", "").strip() for p in semantic if p.get("name_en", "").strip())
    return f"{name_en}({param_str})" if param_str else name_en


def _build_zh_line(plugin_en: str, plugin_zh: str, zh_pairs: list[tuple[str, str]]) -> str:
    """Build 'zh: PluginEn=PluginZh,AceEn=AceZh,...' mapping line.

    Returns empty string if there are no mappings.
    """
    parts: list[str] = []
    if plugin_zh and plugin_zh != plugin_en:
        parts.append(f"{plugin_en}={plugin_zh}")
    seen: set[str] = set()
    for en, zh in zh_pairs:
        if en and en not in seen:
            seen.add(en)
            parts.append(f"{en}={zh}")
    return f"zh: {','.join(parts)}" if parts else ""


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class LookupIntent:
    """Classified intent from a user query."""
    intent_type: str       # ace_list | ace_detail | prop_list | term_translate | ace_search | example_find
    plugin_id: str = ""    # matched plugin/behavior id (e.g. "sprite")
    ace_type: str = ""     # actions | conditions | expressions (or comma-sep for ace_search)
    ace_name: str = ""     # specific ACE name for detail queries
    term: str = ""         # search term for translation queries
    filter_term: str = ""  # topic keyword for ace_search filtering
    tier: int = 0          # which tier matched (1/2/3)
    is_behavior: bool = False  # True if matched a behavior, not plugin
    matched_tags: List[str] = field(default_factory=list)  # tags for example_find intent
    confidence: float = 0.0  # 0.0–1.0 confidence score based on tier + match quality


@dataclass
class ACELocale:
    """Localized text for an ACE entry."""
    name: str = ""
    desc: str = ""
    display: str = ""       # editor display template, e.g. "设置动画为{0}(从{1}播放)"

@dataclass
class LookupMatch:
    """A single ACE/property match from lookup."""
    ace_id: str
    ace_type: str           # condition | action | expression | property
    plugin_id: str
    en: ACELocale = field(default_factory=ACELocale)
    zh: ACELocale = field(default_factory=ACELocale)
    plugin_name_zh: str = ""
    script_name: str = ""
    category: str = ""
    relevance: int = 0      # keyword match score
    params: List[Dict] = field(default_factory=list)
    is_trigger: bool = False
    is_async: bool = False
    return_type: str = ""


def _match_from_item(
    item: dict, ace_type: str, plugin_id: str, plugin_zh: str,
    name_en: str = "", name_zh: str = "", params: list | None = None,
) -> LookupMatch:
    """Build a LookupMatch from a schema item dict."""
    name_en = name_en or item.get("name_en", "")
    name_zh = name_zh or item.get("name_zh", "")
    return LookupMatch(
        ace_id=item.get("id", name_en),
        ace_type=ace_type,
        plugin_id=plugin_id,
        en=ACELocale(
            name=name_en,
            desc=item.get("description_en", ""),
            display=item.get("display_en", ""),
        ),
        zh=ACELocale(
            name=name_zh,
            desc=item.get("description_zh", ""),
            display=item.get("display_zh", ""),
        ),
        plugin_name_zh=plugin_zh,
        script_name=item.get("scriptName", item.get("script_name", "")),
        category=item.get("category", ""),
        params=params if params is not None else item.get("params", []),
        is_trigger=item.get("isTrigger", False),
        is_async=item.get("isAsync", False),
        return_type=item.get("returnType", ""),
    )


@dataclass
class LookupResponse:
    """Result from a direct lookup."""
    intent: LookupIntent
    matches: List[LookupMatch] = field(default_factory=list)
    context: str = ""          # compact LLM text (what was previously `answer`)
    query_type: str = ""
    elapsed_ms: float = 0.0


# =============================================================================
# SchemaIndex — lazy-loaded plugin/behavior JSON schemas
# =============================================================================

class SchemaIndex:
    """
    Index of all plugin and behavior JSON schemas.
    Supports fuzzy name resolution: id / zh / en / case-insensitive / partial.
    """

    def __init__(self, schema_dir: Optional[Path] = None):
        self._schema_dir = schema_dir or SCHEMA_DIR
        self._plugins: Dict[str, dict] = {}      # id -> full schema
        self._behaviors: Dict[str, dict] = {}     # id -> full schema
        self._name_map: Dict[str, tuple[str, bool]] = {}  # normalized_name -> (id, is_behavior)
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        self._loaded = True

        plugin_dir = self._schema_dir / "plugins"
        behavior_dir = self._schema_dir / "behaviors"

        # Load plugins
        if plugin_dir.exists():
            for fp in sorted(plugin_dir.glob("*.json")):
                try:
                    data = json.loads(fp.read_text(encoding="utf-8"))
                    pid = data.get("id", fp.stem)
                    self._plugins[pid] = data
                    self._register_names(data, pid, is_behavior=False)
                except Exception as e:
                    logger.warning(f"[SchemaIndex] Failed to load: {fp.name}: {e}")

        # Load behaviors
        if behavior_dir.exists():
            for fp in sorted(behavior_dir.glob("*.json")):
                if fp.stem == "index":
                    continue
                try:
                    data = json.loads(fp.read_text(encoding="utf-8"))
                    bid = data.get("id", fp.stem)
                    self._behaviors[bid] = data
                    self._register_names(data, bid, is_behavior=True)
                except Exception as e:
                    logger.warning(f"[SchemaIndex] Failed to load: {fp.name}: {e}")

        logger.info(
            f"[SchemaIndex] Loaded {len(self._plugins)} plugins, "
            f"{len(self._behaviors)} behaviors, {len(self._name_map)} name mappings"
        )

    def _register_names(self, data: dict, item_id: str, is_behavior: bool):
        """Register all name variants for fuzzy matching."""
        entry = (item_id, is_behavior)
        # Exact id
        self._name_map[item_id.lower()] = entry
        # originalId (e.g. "Sprite")
        orig = data.get("originalId", "")
        if orig:
            self._name_map[orig.lower()] = entry
        # name_zh / name_en
        for key in ("name_zh", "name_en"):
            name = data.get(key, "")
            if name:
                self._name_map[name.lower()] = entry

    def resolve_name(self, name: str) -> Optional[tuple[str, bool]]:
        """
        Resolve a plugin/behavior name to (id, is_behavior).
        Supports: id, zh name, en name, case-insensitive, partial match.

        Returns None if no match found.
        """
        self._load()
        query = name.strip().lower()
        if not query:
            return None

        # 1. Exact match
        if query in self._name_map:
            return self._name_map[query]

        # 2. Partial match (query is substring of a registered name)
        candidates = []
        for registered, entry in self._name_map.items():
            if query in registered or registered in query:
                candidates.append((registered, entry))

        if candidates:
            # Prefer shortest match (most specific)
            candidates.sort(key=lambda x: len(x[0]))
            return candidates[0][1]

        return None

    def get_schema(self, item_id: str, is_behavior: bool = False) -> Optional[dict]:
        """Get full schema by id."""
        self._load()
        if is_behavior:
            return self._behaviors.get(item_id)
        return self._plugins.get(item_id)

    def get_ace_list(
        self, item_id: str, ace_type: str, is_behavior: bool = False
    ) -> List[dict]:
        """Get list of actions/conditions/expressions/properties for a plugin/behavior."""
        schema = self.get_schema(item_id, is_behavior)
        if not schema:
            return []
        return schema.get(ace_type, [])

    def get_all_ids(self) -> tuple[List[str], List[str]]:
        """Return (plugin_ids, behavior_ids)."""
        self._load()
        return list(self._plugins.keys()), list(self._behaviors.keys())


# =============================================================================
# ScriptingIndex — TypeScript API method search
# =============================================================================

class ScriptingIndex:
    """Search scripting API methods from autocomplete-data.json."""

    def __init__(self, data_dir: Optional[Path] = None):
        self._data: dict[str, list[str]] = {}  # class → methods
        self._loaded = False
        self._data_dir = data_dir or (Path(__file__).parent.parent.parent / "data" / "c3-ts-defs")

    def _load(self):
        if self._loaded:
            return
        self._loaded = True
        ac_path = self._data_dir / "autocomplete-data.json"
        if not ac_path.exists():
            logger.warning(f"[ScriptingIndex] Not found: {ac_path}")
            return
        data = json.loads(ac_path.read_text(encoding="utf-8"))
        self._data = data.get("properties", {})
        logger.info(f"[ScriptingIndex] Loaded {len(self._data)} classes")

    @staticmethod
    def _extract_api_tokens(query: str) -> list[str]:
        """Extract probable API identifiers from a mixed-language query.

        Matches camelCase, PascalCase, snake_case, and dot-separated tokens
        that look like code (e.g. 'getAllInstances', 'IObjectClass.x').
        """
        return re.findall(r"[A-Za-z_][A-Za-z0-9_.]*[A-Za-z0-9]", query)

    def search(self, query: str, max_results: int = 20) -> list[dict]:
        """Search for classes and methods matching query.

        Class-name hits return all members of that class (capped by max_results).
        Method-name hits return individual {class, method} dicts.
        Automatically extracts API tokens from mixed-language queries.
        """
        self._load()
        q_lower = query.lower()

        # Extract API tokens for matching (e.g. "getAllInstances 怎么用" → ["getAllInstances"])
        tokens = self._extract_api_tokens(query)
        token_lowers = [t.lower() for t in tokens]

        # Phase 1: class name match
        # Require the class name to appear IN the query or a token, not the reverse.
        # This prevents short tokens like "Sprite" from matching "ISpriteInstance".
        class_hits = []
        for cls, methods in self._data.items():
            cls_lower = cls.lower()
            if cls_lower in q_lower:
                class_hits.append((cls, methods))
            elif any(cls_lower == t for t in token_lowers):
                # Exact token match (e.g. query token "IRuntime" == class "IRuntime")
                class_hits.append((cls, methods))

        if class_hits:
            results = []
            for cls, methods in class_hits:
                for method in methods:
                    results.append({"class": cls, "method": method})
                    if len(results) >= max_results:
                        return results
            return results

        # Phase 2: method name match
        # Only use tokens that start with lowercase (camelCase method names)
        # and are long enough to be specific API identifiers.
        method_tokens = [
            t.lower() for t in tokens
            if t[0].islower() and len(t) >= 8
        ] if tokens else []
        results = []
        search_terms = [q_lower] + method_tokens
        for cls, methods in self._data.items():
            for method in methods:
                method_lower = method.lower()
                if any(t in method_lower for t in search_terms):
                    results.append({
                        "class": cls,
                        "method": method,
                    })
                    if len(results) >= max_results:
                        return results
        return results


# =============================================================================
# TermIndex — CSV translation terms
# =============================================================================

class TermIndex:
    """
    Index of translation terms from CDN lang data.
    Accepts pre-loaded terms (from C3Fetcher.export_terms()).
    """

    def __init__(self, terms: Optional[List[Dict]] = None):
        self._terms: List[Dict[str, str]] = []  # [{"key": ..., "zh": ..., "en": ...}]
        self._loaded = False
        if terms is not None:
            self._ingest(terms)

    def _ingest(self, terms: List[Dict]):
        """Load terms from CDN export_terms() format into internal index."""
        self._loaded = True
        for t in terms:
            zh = t.get("zh", "").strip()
            en = t.get("en", "").strip()
            key = t.get("term_key", "")
            if zh and en:
                self._terms.append({"key": key, "zh": zh, "en": en})
        logger.info(f"[TermIndex] Loaded {len(self._terms)} terms")

    def search(self, query: str, max_results: int = 20) -> List[Dict[str, str]]:
        """
        Search terms by substring match. Exact matches first, then partial.

        Args:
            query: search string (zh or en)
            max_results: max number of results

        Returns:
            List of {"key", "zh", "en"} dicts
        """
        query_lower = query.strip().lower()
        if not query_lower:
            return []

        exact = []
        partial = []

        for term in self._terms:
            zh_lower = term["zh"].lower()
            en_lower = term["en"].lower()

            # Exact match on zh or en value
            if zh_lower == query_lower or en_lower == query_lower:
                exact.append(term)
            # Partial match
            elif query_lower in zh_lower or query_lower in en_lower:
                partial.append(term)

        results = exact + partial
        return results[:max_results]


# =============================================================================
# ExamplesIndex — inverted tag index for example browser entries
# =============================================================================

class ExamplesIndex:
    """
    Inverted index: data-tag -> example records.
    Loaded from data/examples_index.json (built by scripts/build_examples_index.py).
    """

    _INDEX_PATH = Path(__file__).parent.parent.parent / "data" / "examples_index.json"

    def __init__(self, index_path: Optional[Path] = None):
        path = index_path or self._INDEX_PATH
        self._index: Dict[str, List[Dict]] = {}
        if path.exists():
            try:
                self._index = json.loads(path.read_text(encoding="utf-8"))
                logger.info(f"[ExamplesIndex] Loaded {len(self._index)} tags")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"[ExamplesIndex] Failed to load: {e}")
        else:
            logger.warning(f"[ExamplesIndex] Index not found: {path}")

    def search(self, tags: List[str], max_results: int = 5) -> List[Dict]:
        """Find examples matching any of the given tags, ranked by overlap count."""
        if not tags:
            return []
        scores: Dict[str, Dict] = {}
        for tag in tags:
            for record in self._index.get(tag, []):
                slug = record.get("slug", "")
                if not slug:
                    continue
                if slug not in scores:
                    scores[slug] = {"record": record, "score": 0}
                scores[slug]["score"] += 1
        ranked = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
        return [r["record"] for r in ranked[:max_results]]

    @staticmethod
    def format_for_ace(records: List[Dict]) -> str:
        """Compact format for appending to ACE query results (no tags)."""
        if not records:
            return ""
        parts = [f"{r['title']} ({r['slug']})" for r in records if r.get("slug")]
        if not parts:
            return ""
        return "Related examples: " + ", ".join(parts)

    @staticmethod
    def format_for_find(records: List[Dict]) -> str:
        """Format for example_find intent results (with genre/behavior tags)."""
        if not records:
            return ""
        parts = []
        for r in records:
            if not r.get("slug"):
                continue
            tag_parts = r.get("genres", []) + r.get("behaviors", [])
            tag_str = f" [{', '.join(tag_parts[:3])}]" if tag_parts else ""
            parts.append(f"{r['title']} ({r['slug']}){tag_str}")
        if not parts:
            return ""
        return "Related examples: " + ", ".join(parts)


# =============================================================================
# IntentClassifier — three-tier classification
# =============================================================================

# Tier 1: Regex patterns for intent matching

# List-query patterns: "{plugin} 有哪些 action"
_LIST_PATTERNS = [
    # "Sprite 有哪些 action" / "Sprite 的所有动作" / "Platform 有哪些参数"
    re.compile(
        r"(?P<plugin>.+?)\s*(?:有哪些|列出|所有|列举|的)\s*(?:主要\s*)?(?P<ace_type>action|actions|condition|conditions|"
        r"expression|expressions|属性|property|properties|参数|动作|条件|表达式)",
        re.IGNORECASE,
    ),
    # "列出 Sprite 的 action"
    re.compile(
        r"(?:列出|列举|查看|显示|有哪些)\s*(?P<plugin>.+?)\s*(?:的|中的)?\s*"
        r"(?P<ace_type>action|actions|condition|conditions|expression|expressions|"
        r"属性|property|properties|参数|动作|条件|表达式)",
        re.IGNORECASE,
    ),
    # "Sprite action 列表" / "Sprite 动作列表"
    re.compile(
        r"(?P<plugin>.+?)\s*(?:的)?\s*(?P<ace_type>action|actions|condition|conditions|"
        r"expression|expressions|属性|property|properties|参数|动作|条件|表达式)\s*(?:列表|有哪些|一览)",
        re.IGNORECASE,
    ),
]

# Detail-query patterns: "{plugin} 的 Set animation 怎么用"
_DETAIL_PATTERNS = [
    re.compile(
        r"(?P<plugin>.+?)\s*(?:的|中的)\s*(?P<ace_name>.+?)\s*"
        r"(?:怎么用|参数|用法|怎么使用|有什么参数|参数是什么)",
        re.IGNORECASE,
    ),
]

# Translation patterns
_TRANSLATE_PATTERNS = [
    # "Destroy 中文是什么" / "翻译 Destroy"
    re.compile(
        r"(?:翻译|中文|英文|怎么说|怎么翻译)\s*(?P<term>.+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<term>.+?)\s*(?:中文是什么|英文是什么|怎么翻译|的中文|的英文|翻译成中文|翻译成英文)",
        re.IGNORECASE,
    ),
]

# Tier 1.5: Keyword-based ACE type inference
# ACE_INTENT_KEYWORDS imported from src.locale.keywords
# Only use the ACE-relevant subset (without "scripting")
_ACE_INFER_KEYWORDS = {
    k: v for k, v in ACE_INTENT_KEYWORDS.items()
    if k in ("conditions", "actions", "expressions", "properties")
}


# Words that always block Tier 1.5, even when a plugin name is found.
# Conceptual/comparison words have no ACE target. Compound how-to forms imply
# step-by-step intent. Bare "怎么"/"怎样" are moved to SOFT_SKIP so that
# "怎么在数组中查找" (plugin name present) can still reach Schema search.
_HOWTO_HARD_SKIP: frozenset[str] = frozenset({
    "区别", "对比", "是什么", "什么是", "概念", "原理", "介绍",
    "怎么做", "怎么实现", "步骤", "流程", "教程",
})

# Words that only block when no plugin name is found.
# "如何" queries about a specific plugin (e.g. "如何实现计时器") can still surface relevant ACEs.
_HOWTO_SOFT_SKIP: frozenset[str] = frozenset(HOWTO_SKIP_WORDS - _HOWTO_HARD_SKIP)

# Combined noise word set (lower-cased) for useful-token filtering
_HOWTO_NOISE_LOWER: frozenset[str] = frozenset(
    w.lower() for w in (_HOWTO_HARD_SKIP | _HOWTO_SOFT_SKIP)
)


def _infer_ace_types(query_tokens: set[str]) -> list[str]:
    """Infer ACE types from query tokens using keyword mapping.

    Returns list of matched ACE types (e.g. ["conditions", "actions"]).
    """
    matched = []
    for ace_type, keywords in _ACE_INFER_KEYWORDS.items():
        if query_tokens & keywords:
            matched.append(ace_type)
    return matched


class IntentClassifier:
    """
    Three-tier intent classifier:
    - Tier 1: Rule-based regex (instant)
    - Tier 2: Embedding similarity (~50ms)
    - Tier 3: Ollama small model (~1-2s, optional)
    """

    def __init__(
        self,
        schema_index: SchemaIndex,
        embedder=None,
        ollama_model: str = "",
        ollama_url: str = "",
    ):
        self.schema = schema_index
        self._embedder = embedder
        self._ollama_model = ollama_model
        self._ollama_url = ollama_url
        self._template_vectors: Optional[Dict[str, Any]] = None

    def _display_name(self, plugin_id: str, is_behavior: bool) -> str:
        """Return human-readable name_en for a plugin/behavior ID."""
        data = self.schema.get_schema(plugin_id, is_behavior)
        if data:
            return data.get("name_en", plugin_id)
        return plugin_id

    def classify(self, query: str) -> Optional[LookupIntent]:
        """
        Classify query through three tiers.
        Returns LookupIntent if matched, None if should go to RAG.
        """
        # Pre-Tier: Example-find detection
        intent = self._detect_example_find(query)
        if intent:
            logger.info(f"[Lookup] example_find hit: tags={intent.matched_tags}")
            _trace(f"示例查找: tags={intent.matched_tags} conf={intent.confidence:.2f}", "lookup")
            return intent

        # Tier 1: Rule-based
        intent = self._rule_based(query)
        if intent:
            logger.info(f"[Lookup] Tier 1 hit: {intent.intent_type} plugin={intent.plugin_id}")
            name = self._display_name(intent.plugin_id, intent.is_behavior)
            _trace(f"精确匹配: {intent.intent_type} · {name} conf={intent.confidence:.2f}", "lookup")
            return intent
        _trace("精确匹配: 未命中", "lookup")

        # Tier 1.5: Keyword inference (plugin + topic → ace_search)
        intent = self._keyword_infer(query)
        if intent:
            logger.info(
                f"[Lookup] Tier 1.5 hit: ace_search plugin={intent.plugin_id} "
                f"ace_type={intent.ace_type} filter={intent.filter_term}"
            )
            name = self._display_name(intent.plugin_id, intent.is_behavior)
            _trace(f"字典搜索: {name} conf={intent.confidence:.2f}", "lookup")
            if intent.filter_term:
                _trace(f"关键词: {intent.filter_term}", "lookup")
            return intent
        _trace("字典搜索: 未命中", "lookup")

        # Tier 2: Embedding similarity
        intent = self._embedding_match(query)
        if intent:
            logger.info(f"[Lookup] Tier 2 hit: {intent.intent_type} plugin={intent.plugin_id}")
            name = self._display_name(intent.plugin_id, intent.is_behavior)
            _trace(f"语义模板: {intent.intent_type} · {name} conf={intent.confidence:.2f}", "lookup")
            return intent
        _trace("语义模板: 未命中", "lookup")

        # Tier 3: Ollama small model
        intent = self._ollama_classify(query)
        if intent:
            logger.info(f"[Lookup] Tier 3 hit: {intent.intent_type} plugin={intent.plugin_id}")
            name = self._display_name(intent.plugin_id, intent.is_behavior)
            _trace(f"LLM分类: {intent.intent_type} · {name} conf={intent.confidence:.2f}", "lookup")
            return intent
        _trace("LLM分类: 跳过(未配置)" if not self._ollama_model else "LLM分类: 未命中", "lookup")

        return None

    # -- Pre-Tier: Example-find detection ---------------------------------

    def _detect_example_find(self, query: str) -> Optional[LookupIntent]:
        """Detect example-seeking queries like '有没有Tween的示例'."""
        q_lower = query.lower()
        example_kws = ("示例", "example", "案例", "样例", "模板", "template")
        if not any(kw in q_lower for kw in example_kws):
            return None
        # Match plugin/behavior names from schema
        self.schema._load()
        matched_tags: List[str] = []
        for plugin_id, _ in self.schema._plugins.items():
            if plugin_id.lower() in q_lower:
                matched_tags.append(f"plugin-{plugin_id}")
        for behavior_id, _ in self.schema._behaviors.items():
            if behavior_id.lower() in q_lower:
                matched_tags.append(f"behavior-{behavior_id}")
        return LookupIntent(
            intent_type="example_find",
            plugin_id="",
            filter_term=query,
            matched_tags=matched_tags,
            confidence=0.7 if matched_tags else 0.5,
        )

    # -- Tier 1: Rule-based -----------------------------------------------

    def _rule_based(self, query: str) -> Optional[LookupIntent]:
        """Match query against known regex patterns."""

        # Try list patterns
        for pat in _LIST_PATTERNS:
            m = pat.search(query)
            if m:
                plugin_name = m.group("plugin").strip()
                ace_type_raw = m.group("ace_type").strip().lower()
                ace_type = ACE_TYPE_ALIASES.get(ace_type_raw, "")
                if not ace_type:
                    continue

                resolved = self.schema.resolve_name(plugin_name)
                if resolved:
                    pid, is_beh = resolved
                    return LookupIntent(
                        intent_type="ace_list" if ace_type != "properties" else "prop_list",
                        plugin_id=pid,
                        ace_type=ace_type,
                        is_behavior=is_beh,
                        tier=1,
                        confidence=0.95,
                    )

        # Try translation patterns
        for pat in _TRANSLATE_PATTERNS:
            m = pat.search(query)
            if m:
                term = m.group("term").strip()
                if term and len(term) < 50:  # sanity check
                    return LookupIntent(
                        intent_type="term_translate",
                        term=term,
                        tier=1,
                        confidence=0.95,
                    )

        # Try detail patterns (last, as they're most greedy)
        for pat in _DETAIL_PATTERNS:
            m = pat.search(query)
            if m:
                plugin_name = m.group("plugin").strip()
                ace_name = m.group("ace_name").strip()
                resolved = self.schema.resolve_name(plugin_name)
                if resolved:
                    pid, is_beh = resolved
                    return LookupIntent(
                        intent_type="ace_detail",
                        plugin_id=pid,
                        ace_name=ace_name,
                        is_behavior=is_beh,
                        tier=1,
                        confidence=0.95,
                    )

        return None

    # -- Tier 1.5: Keyword inference --------------------------------------

    def _keyword_infer(self, query: str) -> Optional[LookupIntent]:
        """
        Infer ACE type from plugin name + topic keywords.

        Skip rules (applied before tokenisation where possible):
        - Hard-skip words (怎么, 区别, …): always return None, even with a plugin name.
        - Soft-skip words (如何, …): return None only when no plugin name is found.

        When a plugin is found with "如何" phrasing:
        - If remaining non-noise Chinese tokens ≤ 2: proceed as ace_search.
        - If remaining tokens > 2 (complex multi-concept query): return None.
        - When remaining is empty: extract 2-char Chinese windows from the plugin
          token itself and use them as the filter term.
        """
        # Hard skip: always block, even if a plugin name is present
        for word in _HOWTO_HARD_SKIP:
            if word in query:
                _trace(f"字典搜索: 跳过 [概念词'{word}']", "lookup")
                return None

        # Tokenize query — split on particles, then on CJK/ASCII boundaries
        tokens = re.split(ZH_PARTICLES, query)
        split = []
        for t in tokens:
            t = t.strip()
            if t:
                # Split on CJK ↔ ASCII boundary: "Sprite字体" → ["Sprite", "字体"]
                split.extend(p for p in re.split(r'(?<=[\u4e00-\u9fff])(?=[A-Za-z0-9])|(?<=[A-Za-z0-9])(?=[\u4e00-\u9fff])', t) if p)
        tokens = split
        if not tokens:
            return None

        # 1. Find plugin name in tokens
        #    Require the matched plugin name to cover ≥40% of the token to avoid
        #    false positives like "存档系统" matching the System plugin via "系统".
        plugin_id = ""
        is_behavior = False
        plugin_token_idx = -1
        for i, token in enumerate(tokens):
            resolved = self.schema.resolve_name(token)
            if not resolved:
                continue
            pid, is_beh = resolved
            schema_data = self.schema.get_schema(pid, is_beh) or {}
            known_names = [
                schema_data.get("name_zh", ""),
                schema_data.get("name_en", ""),
                schema_data.get("originalId", ""),
                pid,
            ]
            token_lower = token.lower()
            coverage = max(
                (len(n) / len(token) for n in known_names if n and n.lower() in token_lower),
                default=0.0,
            )
            if coverage < 0.4:
                continue  # too weak a match (e.g. "系统" inside "存档系统")
            plugin_id, is_behavior = pid, is_beh
            plugin_token_idx = i
            break

        # Soft skip: block only when no plugin name was found
        if not plugin_id:
            for word in _HOWTO_SOFT_SKIP:
                if word in query:
                    return None
            return None

        # Ambiguity check: if plugin name is a common English word and
        # remaining tokens are all generic, skip lookup (e.g. "custom action")
        remaining_tokens = [t for i, t in enumerate(tokens) if i != plugin_token_idx and t]
        if plugin_id in _AMBIGUOUS_PLUGIN_NAMES:
            remaining_lower = {t.lower() for t in remaining_tokens}
            if remaining_lower and remaining_lower <= _GENERIC_QUERY_WORDS:
                return None

        # 3. Count meaningful tokens to detect complex multi-concept queries.
        #    Skip words and single-char noise are filtered out.
        def _is_useful(tok: str) -> bool:
            if tok.lower() in _HOWTO_NOISE_LOWER:
                return False
            if len(tok) <= 1:
                return False
            return True

        useful_tokens = [t for t in remaining_tokens if _is_useful(t)]
        if len(useful_tokens) > 3:
            return None  # complex multi-concept query → fall through to RAG

        # 4. Build filter term
        if useful_tokens:
            filter_term = " ".join(remaining_tokens)
        else:
            # Bare plugin name (e.g. "Sprite") → return ace_list for all types
            return LookupIntent(
                intent_type="ace_list",
                plugin_id=plugin_id,
                ace_type="conditions,actions,expressions",
                is_behavior=is_behavior,
                tier=1,
                confidence=0.90,
            )

        # 5. Build topic token set (jieba full-mode for ACE type inference)
        topic_tokens = set(remaining_tokens)
        for token in remaining_tokens:
            if any('\u4e00' <= c <= '\u9fff' for c in token):
                topic_tokens.update(seg for seg in jieba.lcut(token, cut_all=True) if len(seg) >= 2)

        # 6. Infer ACE types from topic tokens (narrow search if possible)
        ace_types = _infer_ace_types(topic_tokens)
        if not ace_types:
            ace_types = ["conditions", "actions", "expressions"]

        # Confidence: base 0.70 + bonus for specific ACE types and useful tokens
        conf = 0.70
        if len(ace_types) < 3:
            conf += 0.10  # narrowed ACE types = higher confidence
        if useful_tokens:
            conf += 0.05  # explicit filter keywords present
        return LookupIntent(
            intent_type="ace_search",
            plugin_id=plugin_id,
            ace_type=",".join(ace_types),
            filter_term=filter_term,
            is_behavior=is_behavior,
            tier=1,
            confidence=min(conf, 0.90),
        )

    # -- Tier 2: Embedding similarity -------------------------------------

    def _ensure_template_vectors(self):
        """Lazily encode intent templates."""
        if self._template_vectors is not None or self._embedder is None:
            return
        try:
            import numpy as np
            self._template_vectors = {}
            for intent_type, templates in INTENT_TEMPLATES.items():
                vecs = [self._embedder.encode_single(t) for t in templates]
                self._template_vectors[intent_type] = np.array(vecs)
            logger.info(f"[Lookup] Tier 2 template vectors encoded ({len(INTENT_TEMPLATES)} types)")
        except Exception as e:
            logger.warning(f"[Lookup] Tier 2 vector encoding failed: {e}")
            self._template_vectors = None

    def _embedding_match(self, query: str) -> Optional[LookupIntent]:
        """Match query against intent templates using cosine similarity."""
        if self._embedder is None:
            return None

        self._ensure_template_vectors()
        if not self._template_vectors:
            return None

        try:
            import numpy as np

            query_vec = np.array(self._embedder.encode_single(query))
            best_type = None
            best_score = 0.0

            for intent_type, template_vecs in self._template_vectors.items():
                # Cosine similarity: query_vec vs each template
                dots = template_vecs @ query_vec
                norms = np.linalg.norm(template_vecs, axis=1) * np.linalg.norm(query_vec)
                sims = dots / (norms + 1e-8)
                max_sim = float(np.max(sims))

                if max_sim > best_score:
                    best_score = max_sim
                    best_type = intent_type

            if best_score < 0.75 or best_type is None:
                return None

            # Confidence: use embedding similarity score (already >= 0.75 threshold)
            embed_conf = round(min(best_score, 1.0), 2)

            # For non-translate intents, we need a plugin name in the query
            if best_type in ("ace_list", "ace_detail", "prop_list"):
                plugin_id, is_beh = self._extract_plugin_from_query(query)
                if not plugin_id:
                    return None

                ace_type = "properties" if best_type == "prop_list" else ""
                return LookupIntent(
                    intent_type=best_type,
                    plugin_id=plugin_id,
                    ace_type=ace_type,
                    is_behavior=is_beh,
                    tier=2,
                    confidence=embed_conf,
                )
            elif best_type == "term_translate":
                # Extract the term from query (remove common prefixes)
                term = self._extract_term_from_query(query)
                if term:
                    return LookupIntent(
                        intent_type="term_translate",
                        term=term,
                        tier=2,
                        confidence=embed_conf,
                    )

            return None
        except Exception as e:
            logger.warning(f"[Lookup] Tier 2 matching failed: {e}")
            return None

    def _extract_plugin_from_query(self, query: str) -> tuple[str, bool]:
        """Try to find a plugin/behavior name in the query text."""
        self.schema._load()
        # Try each word / segment as a potential plugin name
        # Split on whitespace and common delimiters
        tokens = re.split(r'[\s,，、的]+', query)
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            resolved = self.schema.resolve_name(token)
            if resolved:
                return resolved
        return ("", False)

    def _extract_term_from_query(self, query: str) -> str:
        """Extract the term to translate from query."""
        # Remove common filler words
        cleaned = re.sub(
            r'(翻译|中文|英文|怎么说|怎么翻译|是什么|的)',
            '', query
        ).strip()
        return cleaned if cleaned else query.strip()

    # -- Tier 3: Ollama small model classification -------------------------

    def _ollama_classify(self, query: str) -> Optional[LookupIntent]:
        """Use Ollama small model for intent classification."""
        if not self._ollama_model or not self._ollama_url:
            return None

        try:
            import requests

            prompt = LOOKUP_CLASSIFY_PROMPT.format(query=query)

            resp = requests.post(
                f"{self._ollama_url}/api/generate",
                json={
                    "model": self._ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0, "num_predict": 100},
                },
                timeout=5,
            )

            if resp.status_code != 200:
                return None

            text = resp.json().get("response", "")
            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', text)
            if not json_match:
                return None

            data = json.loads(json_match.group())
            qtype = data.get("type", "rag")

            if qtype == "rag":
                return None

            plugin_name = data.get("plugin", "")
            ace_type = data.get("ace_type", "")

            # Validate plugin name if needed
            plugin_id = ""
            is_beh = False
            if plugin_name:
                resolved = self.schema.resolve_name(plugin_name)
                if resolved:
                    plugin_id, is_beh = resolved

            if qtype in ("ace_list", "ace_detail", "prop_list") and not plugin_id:
                return None

            intent_type = qtype
            if qtype == "term":
                intent_type = "term_translate"
                return LookupIntent(
                    intent_type=intent_type,
                    term=self._extract_term_from_query(query),
                    tier=3,
                    confidence=0.75,
                )

            return LookupIntent(
                intent_type=intent_type,
                plugin_id=plugin_id,
                ace_type=ace_type,
                is_behavior=is_beh,
                tier=3,
                confidence=0.75,
            )

        except Exception as e:
            logger.debug(f"[Lookup] Tier 3 unavailable: {e}")
            return None


# =============================================================================
# LookupEngine — execute lookup and format results
# =============================================================================

class LookupEngine:
    """
    Main entry point for the direct lookup system.
    Classifies query intent and returns formatted results.
    """

    def __init__(
        self,
        schema_dir: Optional[Path] = None,
        terms: Optional[List[Dict]] = None,
        embedder=None,
        ollama_model: str = "",
        ollama_url: str = "",
    ):
        self.schema_index = SchemaIndex(schema_dir)
        self.term_index = TermIndex(terms=terms)
        self.examples_index = ExamplesIndex()
        self.scripting_index = ScriptingIndex()
        self.classifier = IntentClassifier(
            schema_index=self.schema_index,
            embedder=embedder,
            ollama_model=ollama_model,
            ollama_url=ollama_url,
        )

    def try_lookup(self, query: str) -> Optional[LookupResponse]:
        """
        Attempt to directly answer the query via lookup.
        Returns None if the query should be handled by RAG.
        """
        t0 = time.time()

        intent = self.classifier.classify(query)
        if intent is not None:
            context, matches = self._execute(intent)
            if context:
                elapsed = (time.time() - t0) * 1000
                return LookupResponse(
                    intent=intent,
                    matches=matches,
                    context=context,
                    query_type=f"lookup_{intent.intent_type}",
                    elapsed_ms=elapsed,
                )

        # Fallback: try scripting API search
        scripting_results = self.scripting_index.search(query)
        if scripting_results:
            context_lines = [
                f"{r['class']}.{r['method']}" for r in scripting_results
            ]
            matches = [
                LookupMatch(
                    ace_id=r["method"],
                    ace_type="script_api",
                    plugin_id=r["class"],
                    en=ACELocale(name=f"{r['class']}.{r['method']}"),
                    zh=ACELocale(),
                ) for r in scripting_results
            ]
            elapsed = (time.time() - t0) * 1000
            return LookupResponse(
                intent=LookupIntent(
                    intent_type="script_api",
                    filter_term=query,
                    tier=2,
                    confidence=0.7,
                ),
                matches=matches,
                context="\n".join(context_lines),
                query_type="lookup_script_api",
                elapsed_ms=elapsed,
            )

        return None

    def _execute(self, intent: LookupIntent) -> tuple[str, list[LookupMatch]]:
        """Execute lookup and format as compact English text for LLM context."""
        if intent.intent_type == "ace_list":
            return self._format_ace_list(intent)
        elif intent.intent_type == "prop_list":
            return self._format_prop_list(intent)
        elif intent.intent_type == "ace_detail":
            return self._format_ace_detail(intent)
        elif intent.intent_type == "ace_search":
            return self._format_ace_search(intent)
        elif intent.intent_type == "term_translate":
            return self._format_term_translate(intent)
        elif intent.intent_type == "example_find":
            return self._format_example_find(intent)
        return "", []

    def _get_example_tag(self, schema: dict, intent: "LookupIntent") -> str:
        """Derive the examples_index tag key for a plugin/behavior schema."""
        canonical_id = schema.get("originalId", schema.get("name_en", intent.plugin_id))
        prefix = "behavior" if intent.is_behavior else "plugin"
        return f"{prefix}-{canonical_id}"

    def _format_ace_list(self, intent: LookupIntent) -> tuple[str, list[LookupMatch]]:
        """Format ACE list in compact English format for LLM context."""
        schema = self.schema_index.get_schema(intent.plugin_id, intent.is_behavior)
        if not schema:
            return "", []

        # Support comma-separated ace_types (e.g. "conditions,actions,expressions")
        ace_types = [t.strip() for t in intent.ace_type.split(",") if t.strip()]
        if len(ace_types) > 1:
            all_lines = []
            all_matches = []
            for at in ace_types:
                sub_intent = LookupIntent(
                    intent_type="ace_list", plugin_id=intent.plugin_id,
                    ace_type=at, is_behavior=intent.is_behavior,
                    tier=intent.tier, confidence=intent.confidence,
                    matched_tags=intent.matched_tags,
                )
                lines, matches = self._format_ace_list(sub_intent)
                if lines:
                    all_lines.append(lines)
                    all_matches.extend(matches)
            return "\n".join(all_lines), all_matches

        ace_type = ace_types[0] if ace_types else intent.ace_type
        items = schema.get(ace_type, [])
        if not items:
            return "", []

        prefix = _ACE_PREFIX.get(ace_type, "?")
        plugin_en = schema.get("name_en", schema.get("originalId", intent.plugin_id))
        plugin_zh = schema.get("name_zh", "")

        # Map plural ace_type to singular ace_type label
        _ACE_TYPE_SINGULAR = {"conditions": "condition", "actions": "action", "expressions": "expression"}
        ace_type_label = _ACE_TYPE_SINGULAR.get(ace_type, ace_type)

        lines = []
        zh_pairs: list[tuple[str, str]] = []
        matches: list[LookupMatch] = []

        for item in items:
            name_en = item.get("name_en", "")
            name_zh = item.get("name_zh", "")
            desc = item.get("description_en", "") or item.get("description_zh", "")
            params = item.get("params", [])
            if ace_type == "conditions":
                sig = _format_condition_sig(name_en, params)
            else:
                sig = f"{name_en}({_format_params(params)})"
            lines.append(f"{prefix}: {sig}: {desc}")
            if name_zh and name_zh != name_en:
                zh_pairs.append((name_en, name_zh))
            matches.append(_match_from_item(item, ace_type_label, intent.plugin_id, plugin_zh, name_en, name_zh, params))

        lines.append(_build_zh_line(plugin_en, plugin_zh, zh_pairs))

        # Append related examples from inverted index
        example_tag = self._get_example_tag(schema, intent)
        example_records = self.examples_index.search([example_tag], max_results=3)
        example_line = ExamplesIndex.format_for_ace(example_records)
        if example_line:
            lines.append("")
            lines.append(example_line)

        return "\n".join(l for l in lines if l), matches

    def _format_ace_detail(self, intent: LookupIntent) -> tuple[str, list[LookupMatch]]:
        """Format single ACE with full parameter details in compact English format."""
        schema = self.schema_index.get_schema(intent.plugin_id, intent.is_behavior)
        if not schema:
            return "", []

        # Search across all ACE types for the named item
        target = intent.ace_name.strip().lower()
        found_item = None
        found_type = ""

        for ace_type in ("actions", "conditions", "expressions"):
            for item in schema.get(ace_type, []):
                name_zh = item.get("name_zh", "").lower()
                name_en = item.get("name_en", "").lower()
                item_id = item.get("id", "").lower()
                if target in name_zh or target in name_en or target in item_id:
                    found_item = item
                    found_type = ace_type
                    break
            if found_item:
                break

        if not found_item:
            return "", []

        _ACE_TYPE_SINGULAR = {"conditions": "condition", "actions": "action", "expressions": "expression"}
        plugin_en = schema.get("name_en", intent.plugin_id)
        plugin_zh = schema.get("name_zh", "")
        prefix = _ACE_PREFIX.get(found_type, "?")
        name_en = found_item.get("name_en", "")
        name_zh = found_item.get("name_zh", "")
        desc = found_item.get("description_en", "") or found_item.get("description_zh", "")
        params = found_item.get("params", [])

        if found_type == "conditions":
            sig = _format_condition_sig(name_en, params)
        else:
            sig = f"{name_en}({_format_params(params)})"

        lines = [f"{prefix}: {sig}: {desc}"]

        # Full param details
        if params:
            for p in params:
                pen = p.get("name_en", "")
                ptype = p.get("type", "")
                pdesc = p.get("desc_en", "") or p.get("desc_zh", "")
                lines.append(f"  - {pen} ({ptype}): {pdesc}")

        zh_pairs = [(name_en, name_zh)] if name_zh and name_zh != name_en else []
        lines.append(_build_zh_line(plugin_en, plugin_zh, zh_pairs))

        # Append related examples from inverted index
        example_tag = self._get_example_tag(schema, intent)
        example_records = self.examples_index.search([example_tag], max_results=3)
        example_line = ExamplesIndex.format_for_ace(example_records)
        if example_line:
            lines.append("")
            lines.append(example_line)

        match = _match_from_item(found_item, _ACE_TYPE_SINGULAR.get(found_type, found_type), intent.plugin_id, plugin_zh, name_en, name_zh, params)
        return "\n".join(l for l in lines if l), [match]

    @staticmethod
    def _compact_param(p: dict) -> str:
        """Format a param as compact string: 'Name(type)' or 'Name(type)[opt1/opt2]'."""
        pname = p.get("name_en") or p.get("name_zh", p.get("id", ""))
        ptype = p.get("type", "")
        s = f"{pname}({ptype})"
        items_i18n = p.get("items_i18n", {})
        if items_i18n:
            opts = [v.get("en", k) for k, v in list(items_i18n.items())[:5]]
            s += f"[{'/'.join(opts)}]"
        elif p.get("items"):
            s += f"[{'/'.join(str(i) for i in p['items'][:5])}]"
        return s

    def _format_ace_search(self, intent: LookupIntent) -> tuple[str, list[LookupMatch]]:
        """Format filtered ACE search results in compact English format for LLM context."""
        schema = self.schema_index.get_schema(intent.plugin_id, intent.is_behavior)
        if not schema:
            return "", []

        raw_words = [w for w in intent.filter_term.lower().split() if w]
        if not raw_words:
            return "", []

        # Build filter set: jieba full-mode segmentation for Chinese.
        # Full mode emits all sub-words: "碰撞检测" → ["碰撞", "碰撞检测", "检测"],
        # avoiding cross-boundary noise like "撞检" from sliding windows.
        filter_words = set(raw_words)
        for w in raw_words:
            if any('\u4e00' <= c <= '\u9fff' for c in w):
                filter_words.update(seg for seg in jieba.lcut(w, cut_all=True) if len(seg) >= 2)

        # Synonym expansion: semantically related terms that keyword matching
        # would miss (e.g. "碰撞" won't match "重叠" even though overlap is
        # a form of collision detection in game engines).
        for syn_set in _ACE_SYNONYMS:
            if filter_words & syn_set:
                filter_words |= syn_set

        plugin_en = schema.get("name_en", schema.get("originalId", intent.plugin_id))
        plugin_zh = schema.get("name_zh", "")

        # Sort C → A → E
        ace_types = sorted(
            [t.strip() for t in intent.ace_type.split(",") if t.strip()],
            key=lambda t: _ACE_SORT_ORDER.get(t, 99),
        )

        lines = []
        zh_pairs: list[tuple[str, str]] = []
        matches: list[LookupMatch] = []

        _ACE_TYPE_SINGULAR = {"conditions": "condition", "actions": "action", "expressions": "expression"}

        # Also search _common ACEs (shared by all World instances)
        common_schema = self.schema_index.get_schema("_common", False)
        schemas_to_search = [schema]
        if common_schema:
            schemas_to_search.append(common_schema)

        for cur_schema in schemas_to_search:
            for ace_type in ace_types:
                items = cur_schema.get(ace_type, [])
                if not items:
                    continue
                prefix = _ACE_PREFIX.get(ace_type, "?")

                en_words = [fw for fw in raw_words if fw.isascii()]
                zh_words = [fw for fw in filter_words if any('\u4e00' <= c <= '\u9fff' for c in fw)]

                # Match against name + category + description, but only
                # score by name/category hits. Description is used solely
                # as a pass gate (any keyword present = pass) because Chinese
                # condition descriptions are too noisy ("检测" in 20% of them).
                scored_items: list[tuple[int, dict]] = []
                for item in items:
                    name_text = " ".join([
                        item.get("name_zh", ""),
                        item.get("name_en", ""),
                        item.get("category", ""),
                    ]).lower()
                    desc_text = " ".join([
                        item.get("description_zh", ""),
                        item.get("description_en", ""),
                    ]).lower()
                    all_words = zh_words or en_words or list(filter_words)
                    name_hits = sum(1 for w in all_words if w in name_text)
                    desc_hit = any(w in desc_text for w in all_words)
                    if name_hits == 0 and not desc_hit:
                        continue
                    scored_items.append((name_hits, item))

                if not scored_items:
                    continue

                # Category expansion: if any ACE with a name hit belongs to an
                # expandable category, pull in all ACEs from that category.
                # Only use name-hit items (not desc-only) to avoid noise
                # (e.g. "检测" in description pulling in unrelated categories).
                matched_cats = {it.get("category", "") for h, it in scored_items if h > 0}
                expand_cats = matched_cats & _CATEGORY_EXPAND
                if expand_cats:
                    seen_ids = {it.get("id") for _, it in scored_items}
                    for item in items:
                        if item.get("category", "") in expand_cats and item.get("id") not in seen_ids:
                            scored_items.append((0, item))
                            seen_ids.add(item.get("id"))

                # Keep items with name hits, or all if none matched by name.
                # Sort by (name_hits desc, keyword position in name asc) so
                # ACEs where the keyword is central appear first.
                best_score = max(h for h, _ in scored_items)
                threshold = max(1, (best_score + 1) // 2) if best_score > 0 else 0
                # Category-expanded items (score=0) pass when threshold allows
                kept = [(h, it) for h, it in scored_items if h >= threshold or (h == 0 and it.get("category") in expand_cats)]
                kept.sort(key=lambda x: (
                    -x[0],
                    min((x[1].get("name_zh", "").find(w) for w in zh_words
                         if w in x[1].get("name_zh", "")), default=999),
                ))
                for hits, item in kept:
                    name_en = item.get("name_en", "")
                    name_zh = item.get("name_zh", "")
                    desc = item.get("description_en", "") or item.get("description_zh", "")
                    params = item.get("params", [])

                    if ace_type == "conditions":
                        sig = name_en
                    else:
                        sig = f"{name_en}({_format_params(params)})"

                    # Context: one compact text line per ACE
                    line = f"[{prefix}] {sig}: {desc}"
                    display = item.get("display_en") or item.get("display_zh", "")
                    if display:
                        line += f' display="{display}"'
                    if params:
                        line += f" params={','.join(self._compact_param(p) for p in params)}"
                    lines.append(line)
                    if name_zh and name_zh != name_en:
                        zh_pairs.append((name_en, name_zh))
                    m = _match_from_item(item, _ACE_TYPE_SINGULAR.get(ace_type, ace_type), intent.plugin_id, plugin_zh, name_en, name_zh, params)
                    m.relevance = hits
                    matches.append(m)

        if not lines:
            return "", []

        lines.append(_build_zh_line(plugin_en, plugin_zh, zh_pairs))
        return "\n".join(l for l in lines if l), matches

    def _format_prop_list(self, intent: LookupIntent) -> tuple[str, list[LookupMatch]]:
        """Format property list in compact English format for LLM context."""
        schema = self.schema_index.get_schema(intent.plugin_id, intent.is_behavior)
        if not schema:
            return "", []

        items = schema.get("properties", [])
        if not items:
            return "", []

        plugin_en = schema.get("name_en", schema.get("originalId", intent.plugin_id))
        plugin_zh = schema.get("name_zh", "")

        lines = []
        zh_pairs: list[tuple[str, str]] = []
        matches: list[LookupMatch] = []

        for item in items:
            name_en = item.get("name_en", "")
            name_zh = item.get("name_zh", "")
            desc = item.get("description_en", "") or item.get("description_zh", "")
            lines.append(f"P: {name_en}: {desc}")
            if name_zh and name_zh != name_en:
                zh_pairs.append((name_en, name_zh))
            matches.append(_match_from_item(item, "property", intent.plugin_id, plugin_zh, name_en, name_zh))

        lines.append(_build_zh_line(plugin_en, plugin_zh, zh_pairs))
        return "\n".join(l for l in lines if l), matches

    def _format_term_translate(self, intent: LookupIntent) -> tuple[str, list[LookupMatch]]:
        """Format translation term lookup."""
        results = self.term_index.search(intent.term, max_results=15)
        if not results:
            return "", []

        lines = [
            TERM_TRANSLATE_HEADER.format(term=intent.term, count=len(results)),
            TERM_TABLE_HEADER,
            TERM_TABLE_SEPARATOR,
        ]

        seen = set()
        count = 0
        for r in results:
            pair = (r["zh"], r["en"])
            if pair in seen:
                continue
            seen.add(pair)
            count += 1
            # Shorten long keys
            key = r["key"]
            if len(key) > 50:
                key = "..." + key[-47:]
            lines.append(f"| {count} | {r['zh']} | {r['en']} | `{key}` |")

        lines.append("\n[来源: 1] 数据来源：Construct 3 CDN 翻译词表")
        return "\n".join(lines), []

    def _format_example_find(self, intent: LookupIntent) -> tuple[str, list[LookupMatch]]:
        """Format example recommendations for example_find intent."""
        tags = intent.matched_tags or []
        results = self.examples_index.search(tags, max_results=5)
        if not results and intent.filter_term:
            # Fallback: search all tags for any genre/behavior keyword match
            q_lower = intent.filter_term.lower()
            fallback_tags = [t for t in self.examples_index._index if q_lower in t.lower()][:3]
            results = self.examples_index.search(fallback_tags, max_results=5)
        return ExamplesIndex.format_for_find(results), []
