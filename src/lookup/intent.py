"""Deterministic query intent classification."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Optional

import jieba

from src.domain.lookup import LookupIntent
from src.locale.resources import (
    ACE_INTENT_KEYWORDS,
    ACE_TYPE_ALIASES,
    AMBIGUOUS_BARE_TOPICS_ZH_EN,
    AMBIGUOUS_PLUGIN_IDS_EN,
    CJK_ASCII_BOUNDARY_PATTERN,
    DETAIL_QUERY_PATTERNS,
    ENTITY_ROLE_SUFFIX_PATTERN_ZH_EN,
    ENTITY_ROLE_TOKEN_PATTERN_ZH_EN,
    EXAMPLE_QUERY_KEYWORDS_ZH_EN,
    GENERIC_QUERY_WORDS_EN,
    HOWTO_HARD_SKIP_ZH,
    HOWTO_PRE_LOOKUP_FALLBACK_ZH_EN,
    HOWTO_SOFT_SKIP_ZH,
    LIST_QUERY_PATTERNS,
    QUERY_PARTICLE_SPLIT_PATTERN_ZH,
    SCOPED_ACE_TYPE_RULES_ZH_EN,
    SEMANTIC_FALLBACK_MARKERS_EN,
    TRANSLATE_QUERY_PATTERNS,
)
from src.lookup.schema_index import SchemaIndex

logger = logging.getLogger(__name__)


def _noop_trace(message: str, phase: str = "info") -> None:
    """Default trace sink for the transport-independent classifier."""


_LIST_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in LIST_QUERY_PATTERNS]
_DETAIL_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in DETAIL_QUERY_PATTERNS]
_TRANSLATE_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in TRANSLATE_QUERY_PATTERNS]

_HOWTO_NOISE_LOWER: frozenset[str] = frozenset(
    word.lower() for word in (HOWTO_HARD_SKIP_ZH | HOWTO_SOFT_SKIP_ZH)
)


def _infer_ace_types(query_tokens: set[str]) -> list[str]:
    """Infer ACE types from query tokens using keyword mapping.

    Returns list of matched ACE types (e.g. ["conditions", "actions"]).
    """
    matched = []
    for ace_type, keywords in ACE_INTENT_KEYWORDS.items():
        if query_tokens & keywords:
            matched.append(ace_type)
    return matched


class IntentClassifier:
    """
    Deterministic rule and schema-name classifier.
    """

    def __init__(
        self,
        schema_index: SchemaIndex,
        trace: Callable[[str, str], None] | None = None,
    ):
        self.schema = schema_index
        self._trace = trace or _noop_trace

    def _display_name(self, plugin_id: str, is_behavior: bool) -> str:
        """Return human-readable name_en for a plugin/behavior ID."""
        data = self.schema.get_schema(plugin_id, is_behavior)
        if data:
            return data.get("name_en", plugin_id)
        return plugin_id

    def classify(self, query: str) -> Optional[LookupIntent]:
        """
        Classify a query using explicit grammar and versioned schema names.
        Returns LookupIntent if matched, None if should go to RAG.
        """
        # Explicit translation is checked before conceptual blockers because
        # valid phrases such as "数组英文是什么" contain "是什么".
        intent = self._detect_translation(query)
        if intent:
            logger.info("[Lookup] explicit translation hit")
            return intent

        # Exact list/detail grammar is also authoritative even when the ACE
        # wording includes "参数是什么".
        intent = self._rule_based(query)
        if intent:
            logger.info(f"[Lookup] rule hit: {intent.intent_type} plugin={intent.plugin_id}")
            name = self._display_name(intent.plugin_id, intent.is_behavior)
            self._trace(
                f"Exact match: {intent.intent_type} · {name} conf={intent.confidence:.2f}",
                "lookup",
            )
            return intent

        if self._requires_semantic_fallback(query):
            self._trace("Direct lookup skipped for semantic-style query", "lookup")
            return None

        # Example-find detection
        intent = self._detect_example_find(query)
        if intent:
            logger.info(f"[Lookup] example_find hit: tags={intent.matched_tags}")
            self._trace(
                f"Example lookup: tags={intent.matched_tags} conf={intent.confidence:.2f}",
                "lookup",
            )
            return intent

        self._trace("Exact match missed", "lookup")

        # Keyword inference (plugin + topic → ace_search)
        intent = self._keyword_infer(query)
        if intent:
            if intent.intent_type == "semantic_fallback":
                self._trace(
                    f"Entity parsed but topic falls back: {intent.plugin_id}",
                    "lookup",
                )
                return intent
            logger.info(
                f"[Lookup] topic hit: ace_search plugin={intent.plugin_id} "
                f"ace_type={intent.ace_type} filter={intent.filter_term}"
            )
            name = self._display_name(intent.plugin_id, intent.is_behavior)
            self._trace(
                f"Keyword search: {name} conf={intent.confidence:.2f}",
                "lookup",
            )
            if intent.filter_term:
                self._trace(f"Keywords: {intent.filter_term}", "lookup")
            return intent
        self._trace("Keyword search missed", "lookup")

        effect = self.schema.find_effect_in_query(query)
        if effect:
            effect_id, _, _ = effect
            return LookupIntent(
                intent_type="semantic_fallback",
                plugin_id=effect_id,
                entity_kind="effect",
                tier=1,
                confidence=0.95,
            )
        return None

    @staticmethod
    def _requires_semantic_fallback(query: str) -> bool:
        q_lower = query.lower()
        return (
            any(marker in query for marker in HOWTO_HARD_SKIP_ZH)
            or any(marker in query for marker in HOWTO_PRE_LOOKUP_FALLBACK_ZH_EN)
            or any(marker in q_lower for marker in SEMANTIC_FALLBACK_MARKERS_EN)
        )

    @staticmethod
    def _normalize_entity_phrase(value: str) -> str:
        """Remove explicit role words while preserving the exact entity name."""
        return re.sub(
            ENTITY_ROLE_SUFFIX_PATTERN_ZH_EN,
            "",
            value.strip(),
            flags=re.IGNORECASE,
        ).strip()

    def _detect_translation(self, query: str) -> Optional[LookupIntent]:
        for pat in _TRANSLATE_PATTERNS:
            m = pat.search(query)
            if not m:
                continue
            term = m.group("term").strip()
            if term and len(term) < 50:
                return LookupIntent(
                    intent_type="term_translate",
                    term=term,
                    tier=1,
                    confidence=0.95,
                )
        return None

    # -- Example-find detection -------------------------------------------

    def _detect_example_find(self, query: str) -> Optional[LookupIntent]:
        """Detect example-seeking queries like '有没有Tween的示例'."""
        q_lower = query.lower()
        if not any(kw in q_lower for kw in EXAMPLE_QUERY_KEYWORDS_ZH_EN):
            return None
        matched_tags: List[str] = []
        entity = self.schema.find_name_in_query(query)
        if entity:
            plugin_id, is_behavior, _, _ = entity
            schema = self.schema.get_schema(plugin_id, is_behavior) or {}
            canonical_id = schema.get("originalId", plugin_id)
            prefix = "behavior" if is_behavior else "plugin"
            matched_tags.append(f"{prefix}-{canonical_id}")
        return LookupIntent(
            intent_type="example_find",
            plugin_id="",
            filter_term=query,
            matched_tags=matched_tags,
            confidence=0.7 if matched_tags else 0.5,
        )

    # -- Explicit rule grammar --------------------------------------------

    def _rule_based(self, query: str) -> Optional[LookupIntent]:
        """Match query against known regex patterns."""

        # Try list patterns
        for pat in _LIST_PATTERNS:
            m = pat.search(query)
            if m:
                plugin_name = self._normalize_entity_phrase(m.group("plugin"))
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

        # Try detail patterns (last, as they're most greedy)
        for pat in _DETAIL_PATTERNS:
            m = pat.search(query)
            if m:
                plugin_name = self._normalize_entity_phrase(m.group("plugin"))
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

    # -- Exact entity plus topic inference --------------------------------

    def _keyword_infer(self, query: str) -> Optional[LookupIntent]:
        """Infer a narrow ACE search from an exact entity span plus topic."""
        entity = self.schema.find_name_in_query(query)
        if entity is None:
            return None
        plugin_id, is_behavior, start, end = entity

        # Remove only the matched entity span. This handles compact Chinese
        # forms such as "数组排序" while preserving the topic "排序".
        remainder = f"{query[:start]} {query[end:]}"
        remainder = re.sub(
            ENTITY_ROLE_TOKEN_PATTERN_ZH_EN,
            " ",
            remainder,
            flags=re.IGNORECASE,
        )

        # Tokenize topic — split on particles, then on CJK/ASCII boundaries.
        tokens = re.split(QUERY_PARTICLE_SPLIT_PATTERN_ZH, remainder)
        split = []
        for t in tokens:
            t = t.strip()
            if t:
                # Split on CJK ↔ ASCII boundary: "Sprite字体" → ["Sprite", "字体"]
                split.extend(
                    part for part in re.split(CJK_ASCII_BOUNDARY_PATTERN, t)
                    if part
                )
        tokens = split

        # Ambiguity check: if plugin name is a common English word and
        # remaining tokens are all generic, skip lookup (e.g. "custom action")
        remaining_tokens = [t for t in tokens if t]
        if plugin_id in AMBIGUOUS_PLUGIN_IDS_EN:
            remaining_lower = {t.lower() for t in remaining_tokens}
            if remaining_lower and remaining_lower <= GENERIC_QUERY_WORDS_EN:
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
        if not useful_tokens:
            # Bare plugin name (e.g. "Sprite") → return ace_list for all types
            return LookupIntent(
                intent_type="ace_list",
                plugin_id=plugin_id,
                ace_type="conditions,actions,expressions",
                is_behavior=is_behavior,
                tier=1,
                confidence=0.90,
            )
        filter_term = " ".join(remaining_tokens)

        compact_topic = re.sub(r"\s+", "", filter_term).lower()
        if compact_topic in AMBIGUOUS_BARE_TOPICS_ZH_EN:
            self._trace(
                f"Ambiguous bare topic '{filter_term}' falls back",
                "lookup",
            )
            return LookupIntent(
                intent_type="semantic_fallback",
                plugin_id=plugin_id,
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
        topic_lower = {token.lower() for token in topic_tokens}
        ace_types = []
        for rule in SCOPED_ACE_TYPE_RULES_ZH_EN:
            if rule.plugin_id not in (None, plugin_id):
                continue
            if rule.terms & topic_lower:
                ace_types = list(rule.ace_types)
                break
        if not ace_types:
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
