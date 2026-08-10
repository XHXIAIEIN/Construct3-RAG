"""Load the locale catalog and expose validated runtime resources.

All language-dependent values live side by side in ``catalog.json``. This
module contains only validation, locale merging, typed rule models, and format
adapters required by production callers.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CATALOG_PATH = Path(__file__).with_name("catalog.json")
with CATALOG_PATH.open("r", encoding="utf-8") as _handle:
    CATALOG: dict[str, Any] = json.load(_handle)

if CATALOG.get("schema_version") != 1:
    raise ValueError("unsupported locale catalog schema_version")

SUPPORTED_LOCALES: tuple[str, ...] = tuple(CATALOG["locales"])
QUERY_LOCALE_ORDER: tuple[str, ...] = tuple(CATALOG["query_locale_order"])
_LOCALE_SET = set(SUPPORTED_LOCALES)

if not SUPPORTED_LOCALES or len(_LOCALE_SET) != len(SUPPORTED_LOCALES):
    raise ValueError("locale catalog must declare unique supported locales")
if set(QUERY_LOCALE_ORDER) != _LOCALE_SET:
    raise ValueError("query_locale_order must contain every supported locale once")


def _localized(value: Any, path: str) -> dict[str, Any]:
    """Validate and return one mapping containing every supported locale."""
    if not isinstance(value, dict) or set(value) != _LOCALE_SET:
        raise ValueError(f"{path} must define exactly {sorted(_LOCALE_SET)}")
    return value


_SOURCE_PREFIXES = set(CATALOG["catalog_contract"]["source_prefixes"])


def _validate_metadata(resource: dict[str, Any], path: str) -> None:
    """Reject anonymous resources that do not explain provenance and usage."""
    required = {"purpose", "source", "consumers", "tests"}
    missing = required - set(resource)
    if missing:
        raise ValueError(f"{path} is missing metadata fields: {sorted(missing)}")
    if not isinstance(resource["purpose"], str) or not resource["purpose"].strip():
        raise ValueError(f"{path}.purpose must be a non-empty string")
    for field in ("source", "consumers", "tests"):
        values = resource[field]
        if not isinstance(values, list) or not values or not all(
            isinstance(value, str) and value.strip() for value in values
        ):
            raise ValueError(f"{path}.{field} must be a non-empty string list")
    unknown_prefixes = {
        source.partition(":")[0]
        for source in resource["source"]
        if source.partition(":")[0] not in _SOURCE_PREFIXES
    }
    if unknown_prefixes:
        raise ValueError(f"{path}.source has unknown prefixes: {sorted(unknown_prefixes)}")


def _merged_localized_list(value: Any, path: str) -> tuple[Any, ...]:
    localized = _localized(value, path)
    return tuple(item for locale in QUERY_LOCALE_ORDER for item in localized[locale])


_QUERY = CATALOG["query"]
_ACE_TYPES = _QUERY["ace_types"]
_SUPPORTED_ACE_TYPES = ("conditions", "actions", "expressions", "properties")
if tuple(_ACE_TYPES) != _SUPPORTED_ACE_TYPES:
    raise ValueError(f"query.ace_types must be ordered as {_SUPPORTED_ACE_TYPES}")

for _ace_type, _resource in _ACE_TYPES.items():
    _validate_metadata(_resource, f"query.ace_types.{_ace_type}")
    _localized(_resource["aliases"], f"query.ace_types.{_ace_type}.aliases")
    _localized(
        _resource["intent_keywords"],
        f"query.ace_types.{_ace_type}.intent_keywords",
    )

for _intent, _rules in _QUERY["grammar"].items():
    for _rule_id, _rule in _rules.items():
        _validate_metadata(_rule, f"query.grammar.{_intent}.{_rule_id}")
        _localized(_rule["patterns"], f"query.grammar.{_intent}.{_rule_id}.patterns")

for _name, _resource in _QUERY["howto"].items():
    _validate_metadata(_resource, f"query.howto.{_name}")
    _localized(_resource["values"], f"query.howto.{_name}.values")
_validate_metadata(_QUERY["example_keywords"], "query.example_keywords")
_localized(_QUERY["example_keywords"]["values"], "query.example_keywords.values")
for _name, _resource in _QUERY["tokenization"].items():
    _validate_metadata(_resource, f"query.tokenization.{_name}")
    _localized(_resource["values"], f"query.tokenization.{_name}.values")
for _name, _resource in _QUERY["ambiguity"].items():
    _validate_metadata(_resource, f"query.ambiguity.{_name}")
    _localized(_resource["values"], f"query.ambiguity.{_name}.values")
for _rule_id, _rule in _QUERY["scoped_ace_type_rules"].items():
    _validate_metadata(_rule, f"query.scoped_ace_type_rules.{_rule_id}")
    _localized(_rule["terms"], f"query.scoped_ace_type_rules.{_rule_id}.terms")

_DIRECTED_ALIAS_DATA = CATALOG["expansion"]["directed_aliases"]
for _rule_id, _rule in _DIRECTED_ALIAS_DATA.items():
    _validate_metadata(_rule, f"expansion.directed_aliases.{_rule_id}")
    if not set(_rule["enabled_locales"]) <= _LOCALE_SET:
        raise ValueError(f"directed alias has unsupported locale: {_rule_id}")
    _localized(_rule["triggers"], f"expansion.directed_aliases.{_rule_id}.triggers")
    _localized(_rule["additions"], f"expansion.directed_aliases.{_rule_id}.additions")

_INDEX = CATALOG["index"]
for _name in (
    "labels", "ace_title_template", "ace_title_markers",
    "common_ace_semantic_hints",
):
    _validate_metadata(_INDEX[_name], f"index.{_name}")
_LABELS = _INDEX["labels"]["values"]
for _group in ("ace_types", "addon_types"):
    for _key, _value in _LABELS[_group].items():
        _localized(_value, f"index.labels.{_group}.{_key}")
for _key, _value in _LABELS.items():
    if _key not in {"ace_types", "addon_types"}:
        _localized(_value, f"index.labels.{_key}")
_localized(_INDEX["ace_title_template"]["values"], "index.ace_title_template.values")
_localized(_INDEX["ace_title_markers"]["values"], "index.ace_title_markers.values")
for _ace_id, _value in _INDEX["common_ace_semantic_hints"]["values"].items():
    _localized(_value, f"index.common_ace_semantic_hints.{_ace_id}")


ACE_INTENT_KEYWORDS: dict[str, frozenset[str]] = {
    ace_type: frozenset(
        _merged_localized_list(
            resource["intent_keywords"],
            f"query.ace_types.{ace_type}.intent_keywords",
        )
    )
    for ace_type, resource in _ACE_TYPES.items()
}

ACE_TYPE_ALIASES: dict[str, str] = {
    alias.casefold(): ace_type
    for ace_type, resource in _ACE_TYPES.items()
    for alias in _merged_localized_list(
        resource["aliases"], f"query.ace_types.{ace_type}.aliases"
    )
}

_ACE_TYPE_PATTERN = "|".join(
    re.escape(alias)
    for alias in sorted(ACE_TYPE_ALIASES, key=lambda value: (-len(value), value))
)


def _grammar_patterns(intent: str) -> tuple[str, ...]:
    patterns: list[str] = []
    for locale in QUERY_LOCALE_ORDER:
        for rule in _QUERY["grammar"][intent].values():
            template = rule["patterns"][locale]
            if template:
                patterns.append(template.format(ace_type=_ACE_TYPE_PATTERN))
    return tuple(patterns)


LIST_QUERY_PATTERNS = _grammar_patterns("list")
DETAIL_QUERY_PATTERNS = _grammar_patterns("detail")
TRANSLATE_QUERY_PATTERNS = _grammar_patterns("translate")

HOWTO_HARD_SKIP_ZH: frozenset[str] = frozenset(
    _merged_localized_list(
        _QUERY["howto"]["hard_skip"]["values"], "query.howto.hard_skip.values"
    )
)
HOWTO_SOFT_SKIP_ZH: frozenset[str] = frozenset(
    _merged_localized_list(
        _QUERY["howto"]["soft_skip"]["values"], "query.howto.soft_skip.values"
    )
)
HOWTO_PRE_LOOKUP_FALLBACK_ZH_EN: frozenset[str] = frozenset(
    _merged_localized_list(
        _QUERY["howto"]["pre_lookup_fallback"]["values"],
        "query.howto.pre_lookup_fallback.values",
    )
)
SEMANTIC_FALLBACK_MARKERS_EN: tuple[str, ...] = tuple(
    marker.casefold()
    for marker in _merged_localized_list(
        _QUERY["howto"]["semantic_fallback_markers"]["values"],
        "query.howto.semantic_fallback_markers.values",
    )
)
EXAMPLE_QUERY_KEYWORDS_ZH_EN: tuple[str, ...] = tuple(
    keyword.casefold()
    for keyword in _merged_localized_list(
        _QUERY["example_keywords"]["values"], "query.example_keywords.values"
    )
)

_PARTICLE_PATTERNS = _merged_localized_list(
    _QUERY["tokenization"]["particle_split_patterns"]["values"],
    "query.tokenization.particle_split_patterns.values",
)
QUERY_PARTICLE_SPLIT_PATTERN_ZH = (
    "(?:" + "|".join(f"(?:{pattern})" for pattern in _PARTICLE_PATTERNS) + ")"
    if _PARTICLE_PATTERNS
    else r"\s+"
)
CJK_ASCII_BOUNDARY_PATTERN = (
    r"(?<=[\u4e00-\u9fff])(?=[A-Za-z0-9])|"
    r"(?<=[A-Za-z0-9])(?=[\u4e00-\u9fff])"
)

_ROLE_WORDS = _localized(
    _QUERY["tokenization"]["entity_role_words"]["values"],
    "query.tokenization.entity_role_words.values",
)
_ASCII_ROLE_WORDS = tuple(word for word in _ROLE_WORDS["en-US"] if word.isascii())
_NON_ASCII_ROLE_WORDS = tuple(
    word
    for locale in QUERY_LOCALE_ORDER
    for word in _ROLE_WORDS[locale]
    if not word.isascii()
)
_ROLE_ALTERNATION = "|".join(
    re.escape(word)
    for locale in QUERY_LOCALE_ORDER
    for word in _ROLE_WORDS[locale]
)
ENTITY_ROLE_SUFFIX_PATTERN_ZH_EN = rf"(?:\s*(?:{_ROLE_ALTERNATION}))\s*$"
ENTITY_ROLE_TOKEN_PATTERN_ZH_EN = "|".join(filter(None, (
    rf"\b(?:{'|'.join(map(re.escape, _ASCII_ROLE_WORDS))})\b" if _ASCII_ROLE_WORDS else "",
    rf"(?:{'|'.join(map(re.escape, _NON_ASCII_ROLE_WORDS))})" if _NON_ASCII_ROLE_WORDS else "",
)))

AMBIGUOUS_PLUGIN_IDS_EN: frozenset[str] = frozenset(
    value.casefold()
    for value in _merged_localized_list(
        _QUERY["ambiguity"]["plugin_ids"]["values"],
        "query.ambiguity.plugin_ids.values",
    )
)
GENERIC_QUERY_WORDS_EN: frozenset[str] = frozenset(
    value.casefold()
    for value in _merged_localized_list(
        _QUERY["ambiguity"]["generic_query_words"]["values"],
        "query.ambiguity.generic_query_words.values",
    )
)
AMBIGUOUS_BARE_TOPICS_ZH_EN: frozenset[str] = frozenset(
    value.casefold()
    for value in _merged_localized_list(
        _QUERY["ambiguity"]["bare_topics"]["values"],
        "query.ambiguity.bare_topics.values",
    )
)


@dataclass(frozen=True, slots=True)
class ScopedAceTypeRule:
    """One ACE type override with locale-merged terms and a stable ID."""

    rule_id: str
    plugin_id: str | None
    terms: frozenset[str]
    ace_types: tuple[str, ...]


SCOPED_ACE_TYPE_RULES_ZH_EN: tuple[ScopedAceTypeRule, ...] = tuple(
    ScopedAceTypeRule(
        rule_id=rule_id,
        plugin_id=raw["plugin_id"],
        terms=frozenset(
            term.casefold()
            for term in _merged_localized_list(
                raw["terms"], f"query.scoped_ace_type_rules.{rule_id}.terms"
            )
        ),
        ace_types=tuple(raw["ace_types"]),
    )
    for rule_id, raw in _QUERY["scoped_ace_type_rules"].items()
)


@dataclass(frozen=True, slots=True)
class DirectedAliasRule:
    """One single-hop alias with explicit scope and ranking weight."""

    rule_id: str
    triggers: frozenset[str]
    additions: frozenset[str]
    plugin_ids: frozenset[str]
    ace_types: frozenset[str]
    weight: float
    exact: bool = True
    allow_chaining: bool = False

    def __post_init__(self) -> None:
        if not 0 < self.weight <= 1:
            raise ValueError("directed alias weight must be in (0, 1]")
        if self.allow_chaining:
            raise ValueError("production directed aliases must remain single-hop")


ACE_DIRECTED_ALIASES: tuple[DirectedAliasRule, ...] = tuple(
    DirectedAliasRule(
        rule_id=rule_id,
        triggers=frozenset(
            term.casefold()
            for locale in raw["enabled_locales"]
            for term in raw["triggers"][locale]
        ),
        additions=frozenset(
            term.casefold()
            for locale in raw["enabled_locales"]
            for term in raw["additions"][locale]
        ),
        plugin_ids=frozenset(raw["plugin_ids"]),
        ace_types=frozenset(raw["ace_types"]),
        weight=float(raw["weight"]),
        exact=bool(raw["exact"]),
        allow_chaining=bool(raw["allow_chaining"]),
    )
    for rule_id, raw in _DIRECTED_ALIAS_DATA.items()
    if raw["enabled_locales"]
)


def _label(name: str, locale: str) -> str:
    return _LABELS[name][locale]


def _group_label(group: str, name: str, locale: str) -> str:
    return _LABELS[group][name][locale]


COMMON_ADDON_NAME_ZH = _label("common_addon_name", "zh-CN")
DESCRIPTION_LABEL_ZH = _label("description", "zh-CN")
SCRIPT_NAME_LABEL_ZH = _label("script_name", "zh-CN")
OPTIONS_LABEL_ZH = _label("options", "zh-CN")
PARAMETERS_LABEL_ZH = _label("parameters", "zh-CN")
RETURN_TYPE_LABEL_ZH = _label("return_type", "zh-CN")
CATEGORY_LABEL_ZH = _label("category", "zh-CN")
EFFECT_LABEL_ZH = _label("effect", "zh-CN")
TRIGGER_TAG_ZH_EN = (
    f"[{_label('trigger', 'zh-CN')}/{_label('trigger', 'en-US')}]"
)
ASYNC_TAG_ZH_EN = f"[{_label('async', 'zh-CN')}/{_label('async', 'en-US')}]"

VECTOR_METADATA_PREFIXES_ZH_EN: tuple[str, ...] = (
    f"{SCRIPT_NAME_LABEL_ZH}/{_label('script_name', 'en-US')}:",
    f"{DESCRIPTION_LABEL_ZH}:",
    f"{_label('description', 'en-US')}:",
    f"{PARAMETERS_LABEL_ZH}:",
    f"[{_label('trigger', 'zh-CN')}",
    f"[{_label('async', 'zh-CN')}",
    f"{RETURN_TYPE_LABEL_ZH}:",
)
ACE_TITLE_MARKERS_ZH: tuple[str, ...] = tuple(
    marker
    for locale in QUERY_LOCALE_ORDER
    for marker in _INDEX["ace_title_markers"]["values"][locale]
)


def format_ace_title_zh_en(
    *,
    addon_type: str,
    addon_zh: str,
    addon_en: str,
    ace_type: str,
    ace_zh: str,
    ace_en: str,
) -> str:
    """Format the existing bilingual vector title from catalog values."""
    return _INDEX["ace_title_template"]["values"]["zh-CN"].format(
        addon_type=_group_label("addon_types", addon_type, "zh-CN"),
        addon_local=addon_zh,
        addon_other=addon_en,
        ace_type=_group_label("ace_types", ace_type, "zh-CN"),
        ace_local=ace_zh,
        ace_other=ace_en,
    )


def format_effect_title_zh_en(name_zh: str, name_en: str) -> str:
    """Format the existing bilingual effect title from catalog values."""
    return f"{EFFECT_LABEL_ZH}/{_label('effect', 'en-US')}: {name_zh} ({name_en})"


COMMON_ACE_SEMANTIC_HINTS_ZH_EN: dict[str, str] = {
    ace_id: "".join(localized[locale] for locale in QUERY_LOCALE_ORDER)
    for ace_id, localized in _INDEX["common_ace_semantic_hints"]["values"].items()
}


__all__ = [
    "ACE_DIRECTED_ALIASES",
    "ACE_INTENT_KEYWORDS",
    "ACE_TITLE_MARKERS_ZH",
    "ACE_TYPE_ALIASES",
    "AMBIGUOUS_BARE_TOPICS_ZH_EN",
    "AMBIGUOUS_PLUGIN_IDS_EN",
    "ASYNC_TAG_ZH_EN",
    "CATALOG",
    "CATALOG_PATH",
    "CATEGORY_LABEL_ZH",
    "CJK_ASCII_BOUNDARY_PATTERN",
    "COMMON_ADDON_NAME_ZH",
    "COMMON_ACE_SEMANTIC_HINTS_ZH_EN",
    "DESCRIPTION_LABEL_ZH",
    "DETAIL_QUERY_PATTERNS",
    "DirectedAliasRule",
    "ENTITY_ROLE_SUFFIX_PATTERN_ZH_EN",
    "ENTITY_ROLE_TOKEN_PATTERN_ZH_EN",
    "EXAMPLE_QUERY_KEYWORDS_ZH_EN",
    "GENERIC_QUERY_WORDS_EN",
    "HOWTO_HARD_SKIP_ZH",
    "HOWTO_PRE_LOOKUP_FALLBACK_ZH_EN",
    "HOWTO_SOFT_SKIP_ZH",
    "LIST_QUERY_PATTERNS",
    "OPTIONS_LABEL_ZH",
    "PARAMETERS_LABEL_ZH",
    "QUERY_PARTICLE_SPLIT_PATTERN_ZH",
    "RETURN_TYPE_LABEL_ZH",
    "SCOPED_ACE_TYPE_RULES_ZH_EN",
    "SCRIPT_NAME_LABEL_ZH",
    "SEMANTIC_FALLBACK_MARKERS_EN",
    "SUPPORTED_LOCALES",
    "TRANSLATE_QUERY_PATTERNS",
    "TRIGGER_TAG_ZH_EN",
    "VECTOR_METADATA_PREFIXES_ZH_EN",
    "format_ace_title_zh_en",
    "format_effect_title_zh_en",
]
