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
CATALOG: dict[str, Any] = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

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


def _query_list(*keys: str) -> tuple[Any, ...]:
    """Return the localized lists at ``query.<keys>``, joined in query locale order."""
    value: Any = _QUERY
    for key in keys:
        value = value[key]
    localized = _localized(value, ".".join(("query", *keys)))
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

_DIRECTED_ALIAS_DATA = CATALOG["expansion"]["directed_aliases"]
for _rule_id, _rule in _DIRECTED_ALIAS_DATA.items():
    _validate_metadata(_rule, f"expansion.directed_aliases.{_rule_id}")
    if not set(_rule["enabled_locales"]) <= _LOCALE_SET:
        raise ValueError(f"directed alias has unsupported locale: {_rule_id}")
    _localized(_rule["triggers"], f"expansion.directed_aliases.{_rule_id}.triggers")
    _localized(_rule["additions"], f"expansion.directed_aliases.{_rule_id}.additions")


ACE_INTENT_KEYWORDS: dict[str, frozenset[str]] = {
    ace_type: frozenset(_query_list("ace_types", ace_type, "intent_keywords"))
    for ace_type in _ACE_TYPES
}

ACE_TYPE_ALIASES: dict[str, str] = {
    alias.casefold(): ace_type
    for ace_type in _ACE_TYPES
    for alias in _query_list("ace_types", ace_type, "aliases")
}

_ACE_TYPE_PATTERN = "|".join(
    re.escape(alias)
    for alias in sorted(ACE_TYPE_ALIASES, key=lambda value: (-len(value), value))
)


def _grammar_patterns(intent: str) -> tuple[str, ...]:
    return tuple(
        rule["patterns"][locale].format(ace_type=_ACE_TYPE_PATTERN)
        for locale in QUERY_LOCALE_ORDER
        for rule in _QUERY["grammar"][intent].values()
        if rule["patterns"][locale]
    )


LIST_QUERY_PATTERNS = _grammar_patterns("list")
DETAIL_QUERY_PATTERNS = _grammar_patterns("detail")
TRANSLATE_QUERY_PATTERNS = _grammar_patterns("translate")

HOWTO_HARD_SKIP_ZH: frozenset[str] = frozenset(
    _query_list("howto", "hard_skip", "values")
)
HOWTO_SOFT_SKIP_ZH: frozenset[str] = frozenset(
    _query_list("howto", "soft_skip", "values")
)
DECLINE_MARKERS_EN: tuple[str, ...] = tuple(
    marker.casefold() for marker in _query_list("howto", "decline_markers", "values")
)
EXAMPLE_QUERY_KEYWORDS_ZH_EN: tuple[str, ...] = tuple(
    keyword.casefold() for keyword in _query_list("example_keywords", "values")
)
EFFECT_QUERY_KEYWORDS_ZH_EN: tuple[str, ...] = tuple(
    keyword.casefold() for keyword in _query_list("effect_keywords", "values")
)

_PARTICLE_PATTERNS = _query_list("tokenization", "particle_split_patterns", "values")
QUERY_PARTICLE_SPLIT_PATTERN_ZH = (
    "(?:" + "|".join(f"(?:{pattern})" for pattern in _PARTICLE_PATTERNS) + ")"
    if _PARTICLE_PATTERNS
    else r"\s+"
)
CJK_ASCII_BOUNDARY_PATTERN = (
    r"(?<=[\u4e00-\u9fff])(?=[A-Za-z0-9])|"
    r"(?<=[A-Za-z0-9])(?=[\u4e00-\u9fff])"
)

_ROLE_WORDS = _query_list("tokenization", "entity_role_words", "values")
_ASCII_ROLE_WORDS = tuple(
    word
    for word in _QUERY["tokenization"]["entity_role_words"]["values"]["en-US"]
    if word.isascii()
)
_NON_ASCII_ROLE_WORDS = tuple(word for word in _ROLE_WORDS if not word.isascii())
_ROLE_ALTERNATION = "|".join(map(re.escape, _ROLE_WORDS))
ENTITY_ROLE_SUFFIX_PATTERN_ZH_EN = rf"(?:\s*(?:{_ROLE_ALTERNATION}))\s*$"
ENTITY_ROLE_TOKEN_PATTERN_ZH_EN = "|".join(filter(None, (
    rf"\b(?:{'|'.join(map(re.escape, _ASCII_ROLE_WORDS))})\b" if _ASCII_ROLE_WORDS else "",
    rf"(?:{'|'.join(map(re.escape, _NON_ASCII_ROLE_WORDS))})" if _NON_ASCII_ROLE_WORDS else "",
)))

AMBIGUOUS_PLUGIN_IDS_EN: frozenset[str] = frozenset(
    value.casefold() for value in _query_list("ambiguity", "plugin_ids", "values")
)
GENERIC_QUERY_WORDS_EN: frozenset[str] = frozenset(
    value.casefold()
    for value in _query_list("ambiguity", "generic_query_words", "values")
)
AMBIGUOUS_BARE_TOPICS_ZH_EN: frozenset[str] = frozenset(
    value.casefold() for value in _query_list("ambiguity", "bare_topics", "values")
)


@dataclass(frozen=True, slots=True)
class DirectedAliasRule:
    """One single-hop alias with explicit scope and ranking weight.

    ``exclude_ids`` names ACEs in the scope that the trigger never means,
    though their names contain it.
    """

    rule_id: str
    triggers: frozenset[str]
    additions: frozenset[str]
    exclude_ids: frozenset[str]
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
        exclude_ids=frozenset(raw["exclude_ids"]),
        plugin_ids=frozenset(raw["plugin_ids"]),
        ace_types=frozenset(raw["ace_types"]),
        weight=float(raw["weight"]),
        exact=bool(raw["exact"]),
        allow_chaining=bool(raw["allow_chaining"]),
    )
    for rule_id, raw in _DIRECTED_ALIAS_DATA.items()
    if raw["enabled_locales"]
)


__all__ = [
    "ACE_DIRECTED_ALIASES",
    "ACE_INTENT_KEYWORDS",
    "ACE_TYPE_ALIASES",
    "AMBIGUOUS_BARE_TOPICS_ZH_EN",
    "AMBIGUOUS_PLUGIN_IDS_EN",
    "CATALOG",
    "CATALOG_PATH",
    "CJK_ASCII_BOUNDARY_PATTERN",
    "DECLINE_MARKERS_EN",
    "DETAIL_QUERY_PATTERNS",
    "DirectedAliasRule",
    "EFFECT_QUERY_KEYWORDS_ZH_EN",
    "ENTITY_ROLE_SUFFIX_PATTERN_ZH_EN",
    "ENTITY_ROLE_TOKEN_PATTERN_ZH_EN",
    "EXAMPLE_QUERY_KEYWORDS_ZH_EN",
    "GENERIC_QUERY_WORDS_EN",
    "HOWTO_HARD_SKIP_ZH",
    "HOWTO_SOFT_SKIP_ZH",
    "LIST_QUERY_PATTERNS",
    "QUERY_PARTICLE_SPLIT_PATTERN_ZH",
    "SUPPORTED_LOCALES",
    "TRANSLATE_QUERY_PATTERNS",
]
