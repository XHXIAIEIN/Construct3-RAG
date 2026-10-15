"""Load ``catalog.json`` and expose its validated query resources.

The catalog keeps the values of every locale side by side under stable concept
IDs. This module validates them, joins the locales in query locale order, and
builds the keyword sets, regex patterns and directed alias rules that
``src.lookup`` reads.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
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

_SOURCE_PREFIXES = set(CATALOG["catalog_contract"]["source_prefixes"])
_QUERY = CATALOG["query"]


def _localized(value: Any, path: str) -> dict[str, Any]:
    """Return ``value`` after checking that it maps exactly the supported locales."""
    if not isinstance(value, dict) or set(value) != _LOCALE_SET:
        raise ValueError(f"{path} must define exactly {sorted(_LOCALE_SET)}")
    return value


def _validate_metadata(resource: dict[str, Any], path: str) -> None:
    """Check the purpose, source, consumers and tests fields of one catalog resource."""
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
        source.partition(":")[0] for source in resource["source"]
    } - _SOURCE_PREFIXES
    if unknown_prefixes:
        raise ValueError(f"{path}.source has unknown prefixes: {sorted(unknown_prefixes)}")


def _query_list(*keys: str) -> tuple[Any, ...]:
    """Return the localized lists at ``query.<keys>``, joined in query locale order."""
    value: Any = _QUERY
    for key in keys:
        value = value[key]
    localized = _localized(value, ".".join(("query", *keys)))
    return tuple(item for locale in QUERY_LOCALE_ORDER for item in localized[locale])


def _casefolded_values(*keys: str) -> tuple[str, ...]:
    """Return the casefolded ``query.<keys>.values`` lists, joined in query locale order."""
    return tuple(value.casefold() for value in _query_list(*keys, "values"))


def _alternation(words: Iterable[str]) -> str:
    """Join ``words`` into one regex alternation that matches each word literally."""
    return "|".join(map(re.escape, words))


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

for _section in ("howto", "tokenization", "ambiguity"):
    for _name, _resource in _QUERY[_section].items():
        _validate_metadata(_resource, f"query.{_section}.{_name}")
        _localized(_resource["values"], f"query.{_section}.{_name}.values")
for _name in ("example_keywords", "effect_keywords"):
    _validate_metadata(_QUERY[_name], f"query.{_name}")
    _localized(_QUERY[_name]["values"], f"query.{_name}.values")

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

_ACE_TYPE_PATTERN = _alternation(
    sorted(ACE_TYPE_ALIASES, key=lambda value: (-len(value), value))
)


def _grammar_patterns(intent: str) -> tuple[str, ...]:
    """Return the ``intent`` patterns of every locale with ``{ace_type}`` filled in."""
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
DECLINE_MARKERS_EN: tuple[str, ...] = _casefolded_values("howto", "decline_markers")
EXAMPLE_QUERY_KEYWORDS_ZH_EN: tuple[str, ...] = _casefolded_values("example_keywords")
EFFECT_QUERY_KEYWORDS_ZH_EN: tuple[str, ...] = _casefolded_values("effect_keywords")

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
_ASCII_ROLE_WORDS = tuple(word for word in _ROLE_WORDS if word.isascii())
_NON_ASCII_ROLE_WORDS = tuple(word for word in _ROLE_WORDS if not word.isascii())
ENTITY_ROLE_SUFFIX_PATTERN_ZH_EN = rf"(?:\s*(?:{_alternation(_ROLE_WORDS)}))\s*$"
# Word boundaries around ASCII role words only
# re counts Chinese characters as word characters, so no \b falls inside a Chinese phrase
ENTITY_ROLE_TOKEN_PATTERN_ZH_EN = "|".join(filter(None, (
    rf"\b(?:{_alternation(_ASCII_ROLE_WORDS)})\b" if _ASCII_ROLE_WORDS else "",
    rf"(?:{_alternation(_NON_ASCII_ROLE_WORDS)})" if _NON_ASCII_ROLE_WORDS else "",
)))

AMBIGUOUS_PLUGIN_IDS_EN: frozenset[str] = frozenset(
    _casefolded_values("ambiguity", "plugin_ids")
)
GENERIC_QUERY_WORDS_EN: frozenset[str] = frozenset(
    _casefolded_values("ambiguity", "generic_query_words")
)
AMBIGUOUS_BARE_TOPICS_ZH_EN: frozenset[str] = frozenset(
    _casefolded_values("ambiguity", "bare_topics")
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


def _enabled_terms(raw: dict[str, Any], field: str) -> frozenset[str]:
    """Casefold the ``field`` terms of every locale the alias rule enables."""
    return frozenset(
        term.casefold()
        for locale in raw["enabled_locales"]
        for term in raw[field][locale]
    )


ACE_DIRECTED_ALIASES: tuple[DirectedAliasRule, ...] = tuple(
    DirectedAliasRule(
        rule_id=rule_id,
        triggers=_enabled_terms(raw, "triggers"),
        additions=_enabled_terms(raw, "additions"),
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
