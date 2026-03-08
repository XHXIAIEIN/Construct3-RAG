"""
Query Routing & Direct Lookup System for Construct 3 RAG

Three-tier intent classification + direct JSON/CSV lookup:
- Tier 1: Rule-based regex matching (instant, 0 cost)
- Tier 2: bge-m3 embedding similarity (~50ms)
- Tier 3: Ollama small model classification (~1-2s, optional)

If all tiers miss → fallback to standard RAG pipeline.
"""
import re
import json
import csv
import logging
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from ._trace import _trace

from src.config import SCHEMA_DIR, SOURCE_DIR, TRANSLATION_CSV
from src.locale.keywords import (
    ACE_TYPE_ALIASES, ACE_INTENT_KEYWORDS, HOWTO_SKIP_WORDS,
    ZH_PARTICLES, INTENT_TEMPLATES,
)
from src.locale import (
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


@dataclass
class LookupResponse:
    """Result from a direct lookup."""
    answer: str            # markdown formatted answer
    query_type: str        # "lookup_ace_list" etc.
    intent: LookupIntent
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
# TermIndex — CSV translation terms
# =============================================================================

class TermIndex:
    """
    Index of translation terms from the POEditor CSV.
    Format: key, zh, _, _, _, en (6 columns)
    """

    def __init__(self, source_dir: Optional[Path] = None, csv_name: Optional[str] = None):
        self._source_dir = source_dir or SOURCE_DIR
        self._csv_name = csv_name or TRANSLATION_CSV
        self._terms: List[Dict[str, str]] = []  # [{"key": ..., "zh": ..., "en": ...}]
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        self._loaded = True

        csv_path = self._source_dir / self._csv_name
        if not csv_path.exists():
            logger.warning(f"[TermIndex] CSV not found: {csv_path}")
            return

        with open(csv_path, encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 6:
                    continue
                key, zh = row[0], row[1].strip()
                en = row[5].strip()
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
        self._load()
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
            _trace(f"示例查找: tags={intent.matched_tags}", "lookup")
            return intent

        # Tier 1: Rule-based
        intent = self._rule_based(query)
        if intent:
            logger.info(f"[Lookup] Tier 1 hit: {intent.intent_type} plugin={intent.plugin_id}")
            name = self._display_name(intent.plugin_id, intent.is_behavior)
            _trace(f"精确匹配: {intent.intent_type} · {name}", "lookup")
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
            _trace(f"字典搜索: {name}", "lookup")
            if intent.filter_term:
                _trace(f"关键词: {intent.filter_term}", "lookup")
            return intent
        _trace("字典搜索: 未命中", "lookup")

        # Tier 2: Embedding similarity
        intent = self._embedding_match(query)
        if intent:
            logger.info(f"[Lookup] Tier 2 hit: {intent.intent_type} plugin={intent.plugin_id}")
            name = self._display_name(intent.plugin_id, intent.is_behavior)
            _trace(f"语义模板: {intent.intent_type} · {name}", "lookup")
            return intent
        _trace("语义模板: 未命中", "lookup")

        # Tier 3: Ollama small model
        intent = self._ollama_classify(query)
        if intent:
            logger.info(f"[Lookup] Tier 3 hit: {intent.intent_type} plugin={intent.plugin_id}")
            name = self._display_name(intent.plugin_id, intent.is_behavior)
            _trace(f"LLM分类: {intent.intent_type} · {name}", "lookup")
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

        # Tokenize query — split on whitespace, punctuation, AND Chinese particles
        tokens = re.split(ZH_PARTICLES, query)
        tokens = [t.strip() for t in tokens if t.strip()]
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

        # 2. Collect non-plugin tokens as topic/filter candidates
        remaining_tokens = [t for i, t in enumerate(tokens) if i != plugin_token_idx and t]

        # 3. Count meaningful Chinese tokens to detect complex multi-concept queries.
        #    Tokens that are pure ASCII, pure digits, or exactly a skip word are noise.
        def _is_useful(tok: str) -> bool:
            if tok.lower() in _HOWTO_NOISE_LOWER:
                return False
            cleaned = tok.replace(" ", "").replace("\u3000", "")
            return not cleaned.isascii()

        useful_tokens = [t for t in remaining_tokens if _is_useful(t)]
        if len(useful_tokens) > 2:
            return None  # complex multi-concept query → fall through to RAG

        # 4. Build filter term
        if useful_tokens:
            # Use full remaining tokens; _format_ace_search will generate 2-char windows
            filter_term = " ".join(remaining_tokens)
        else:
            # No external content: extract 2-char Chinese windows from the plugin token
            # so queries like "如何实现计时器" can search timer ACEs via "计时" etc.
            plugin_token = tokens[plugin_token_idx]
            zh_pairs = [
                plugin_token[j:j + 2]
                for j in range(len(plugin_token) - 1)
                if all('\u4e00' <= c <= '\u9fff' for c in plugin_token[j:j + 2])
            ]
            filter_term = " ".join(zh_pairs)

        if not filter_term:
            return None  # no useful filter (e.g. ASCII-only plugin token)

        # 5. Build topic token set (with 2-char substrings for ACE type inference)
        topic_tokens = set(remaining_tokens)
        for token in remaining_tokens:
            for j in range(len(token) - 1):
                pair = token[j:j + 2]
                if all('\u4e00' <= c <= '\u9fff' for c in pair):
                    topic_tokens.add(pair)

        # 6. Infer ACE types from topic tokens (narrow search if possible)
        ace_types = _infer_ace_types(topic_tokens)
        if not ace_types:
            ace_types = ["conditions", "actions", "expressions"]

        return LookupIntent(
            intent_type="ace_search",
            plugin_id=plugin_id,
            ace_type=",".join(ace_types),
            filter_term=filter_term,
            is_behavior=is_behavior,
            tier=1,
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
                )
            elif best_type == "term_translate":
                # Extract the term from query (remove common prefixes)
                term = self._extract_term_from_query(query)
                if term:
                    return LookupIntent(
                        intent_type="term_translate",
                        term=term,
                        tier=2,
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
                )

            return LookupIntent(
                intent_type=intent_type,
                plugin_id=plugin_id,
                ace_type=ace_type,
                is_behavior=is_beh,
                tier=3,
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
        source_dir: Optional[Path] = None,
        embedder=None,
        ollama_model: str = "",
        ollama_url: str = "",
    ):
        self.schema_index = SchemaIndex(schema_dir)
        self.term_index = TermIndex(source_dir)
        self.examples_index = ExamplesIndex()
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
        if intent is None:
            return None

        answer = self._execute(intent)
        if not answer:
            # Lookup failed (e.g., plugin has no matching ACE) → fallback to RAG
            logger.info("[Lookup] No results, falling back to RAG")
            return None

        elapsed = (time.time() - t0) * 1000
        return LookupResponse(
            answer=answer,
            query_type=f"lookup_{intent.intent_type}",
            intent=intent,
            elapsed_ms=elapsed,
        )

    def _execute(self, intent: LookupIntent) -> str:
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
        return ""

    def _get_example_tag(self, schema: dict, intent: "LookupIntent") -> str:
        """Derive the examples_index tag key for a plugin/behavior schema."""
        canonical_id = schema.get("originalId", schema.get("name_en", intent.plugin_id))
        prefix = "behavior" if intent.is_behavior else "plugin"
        return f"{prefix}-{canonical_id}"

    def _format_ace_list(self, intent: LookupIntent) -> str:
        """Format ACE list in compact English format for LLM context."""
        schema = self.schema_index.get_schema(intent.plugin_id, intent.is_behavior)
        if not schema:
            return ""

        ace_type = intent.ace_type
        items = schema.get(ace_type, [])
        if not items:
            return ""

        prefix = _ACE_PREFIX.get(ace_type, "?")
        plugin_en = schema.get("name_en", schema.get("originalId", intent.plugin_id))
        plugin_zh = schema.get("name_zh", "")

        lines = []
        zh_pairs: list[tuple[str, str]] = []

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

        lines.append(_build_zh_line(plugin_en, plugin_zh, zh_pairs))

        # Append related examples from inverted index
        example_tag = self._get_example_tag(schema, intent)
        example_records = self.examples_index.search([example_tag], max_results=3)
        example_line = ExamplesIndex.format_for_ace(example_records)
        if example_line:
            lines.append("")
            lines.append(example_line)

        return "\n".join(l for l in lines if l)

    def _format_ace_detail(self, intent: LookupIntent) -> str:
        """Format single ACE with full parameter details in compact English format."""
        schema = self.schema_index.get_schema(intent.plugin_id, intent.is_behavior)
        if not schema:
            return ""

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
            return ""

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

        return "\n".join(l for l in lines if l)

    def _format_ace_search(self, intent: LookupIntent) -> str:
        """Format filtered ACE search results in compact English format for LLM context."""
        schema = self.schema_index.get_schema(intent.plugin_id, intent.is_behavior)
        if not schema:
            return ""

        raw_words = [w for w in intent.filter_term.lower().split() if w]
        if not raw_words:
            return ""

        # Build filter set: original words + 2-char substrings for Chinese matching
        filter_words = set(raw_words)
        for w in raw_words:
            for j in range(len(w) - 1):
                pair = w[j:j + 2]
                if all('\u4e00' <= c <= '\u9fff' for c in pair):
                    filter_words.add(pair)

        plugin_en = schema.get("name_en", schema.get("originalId", intent.plugin_id))
        plugin_zh = schema.get("name_zh", "")

        # Sort C → A → E
        ace_types = sorted(
            [t.strip() for t in intent.ace_type.split(",") if t.strip()],
            key=lambda t: _ACE_SORT_ORDER.get(t, 99),
        )

        lines = []
        zh_pairs: list[tuple[str, str]] = []

        for ace_type in ace_types:
            items = schema.get(ace_type, [])
            if not items:
                continue
            prefix = _ACE_PREFIX.get(ace_type, "?")

            for item in items:
                searchable = " ".join([
                    item.get("name_zh", ""),
                    item.get("name_en", ""),
                    item.get("description_zh", ""),
                    item.get("description_en", ""),
                    item.get("category", ""),
                ]).lower()
                if not any(fw in searchable for fw in filter_words):
                    continue

                name_en = item.get("name_en", "")
                name_zh = item.get("name_zh", "")
                desc = item.get("description_en", "") or item.get("description_zh", "")
                params = item.get("params", [])

                if ace_type == "conditions":
                    sig = name_en
                else:
                    sig = f"{name_en}({_format_params(params)})"

                lines.append(f"{prefix}: {sig}: {desc}")
                if name_zh and name_zh != name_en:
                    zh_pairs.append((name_en, name_zh))

        if not lines:
            return ""

        lines.append(_build_zh_line(plugin_en, plugin_zh, zh_pairs))
        return "\n".join(l for l in lines if l)

    def _format_prop_list(self, intent: LookupIntent) -> str:
        """Format property list in compact English format for LLM context."""
        schema = self.schema_index.get_schema(intent.plugin_id, intent.is_behavior)
        if not schema:
            return ""

        items = schema.get("properties", [])
        if not items:
            return ""

        plugin_en = schema.get("name_en", schema.get("originalId", intent.plugin_id))
        plugin_zh = schema.get("name_zh", "")

        lines = []
        zh_pairs: list[tuple[str, str]] = []

        for item in items:
            name_en = item.get("name_en", "")
            name_zh = item.get("name_zh", "")
            desc = item.get("description_en", "") or item.get("description_zh", "")
            lines.append(f"P: {name_en}: {desc}")
            if name_zh and name_zh != name_en:
                zh_pairs.append((name_en, name_zh))

        lines.append(_build_zh_line(plugin_en, plugin_zh, zh_pairs))
        return "\n".join(l for l in lines if l)

    def _format_term_translate(self, intent: LookupIntent) -> str:
        """Format translation term lookup."""
        results = self.term_index.search(intent.term, max_results=15)
        if not results:
            return ""

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

        lines.append("\n[来源: 1] 数据来源：Construct 3 翻译词表 (zh_r475.csv)")
        return "\n".join(lines)

    def _format_example_find(self, intent: LookupIntent) -> str:
        """Format example recommendations for example_find intent."""
        tags = intent.matched_tags or []
        results = self.examples_index.search(tags, max_results=5)
        if not results and intent.filter_term:
            # Fallback: search all tags for any genre/behavior keyword match
            q_lower = intent.filter_term.lower()
            fallback_tags = [t for t in self.examples_index._index if q_lower in t.lower()][:3]
            results = self.examples_index.search(fallback_tags, max_results=5)
        return ExamplesIndex.format_for_find(results)
