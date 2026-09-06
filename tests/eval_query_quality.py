#!/usr/bin/env python3
"""Evaluate offline Direct Lookup quality against the structured query gold set.

The evaluator deliberately stops at the Direct Lookup boundary.  A lookup miss is
reported as a semantic fallback route, but Qdrant, embedding models, Ollama and the
network are never invoked.

Examples:
    python tests/eval_query_quality.py
    python tests/eval_query_quality.py --strategy current --split dev --output report.json
    python tests/eval_query_quality.py --strategy all --output report.json --verbose
    python tests/eval_query_quality.py --strategy literal --fail-on-quality

With the default ``--output -`` the complete JSON report is written to stdout.
When a file is selected, a readable per-query report is printed to stdout and the
complete machine-readable report is written to that file.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "query_gold.jsonl"
sys.path.insert(0, str(ROOT))


class FixtureError(ValueError):
    """Raised when the gold fixture cannot be evaluated unambiguously."""


_RESULT_KEY_FIELDS = ("collection", "plugin_id", "ace_type", "ace_id")
_COLLECTION_ALIASES = {
    "plugin": "plugins",
    "c3_plugins": "plugins",
    "plugins": "plugins",
    "behavior": "behaviors",
    "behaviour": "behaviors",
    "c3_behaviors": "behaviors",
    "behaviors": "behaviors",
    "script": "script_api",
    "c3_scripting": "script_api",
    "scripting": "script_api",
    "script_api": "script_api",
    "example": "examples",
    "c3_examples": "examples",
    "examples": "examples",
    "term": "terms",
    "c3_terms": "terms",
    "terms": "terms",
    "effect": "effects",
    "c3_effects": "effects",
    "effects": "effects",
}
_ACE_TYPE_ALIASES = {
    "conditions": "condition",
    "condition": "condition",
    "actions": "action",
    "action": "action",
    "expressions": "expression",
    "expression": "expression",
    "properties": "property",
    "property": "property",
    "script": "script_api",
    "scripting": "script_api",
    "script_api": "script_api",
    "examples": "example",
    "example": "example",
    "effects": "effect",
    "effect": "effect",
    "terms": "term",
    "term": "term",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FixtureError(f"Gold fixture not found: {path}")

    cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FixtureError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise FixtureError(f"{path}:{line_no}: each line must be a JSON object")

        case = dict(raw)
        evidence = case.get("evidence") or {}
        if evidence and not isinstance(evidence, dict):
            raise FixtureError(f"{path}:{line_no}: evidence must be an object")
        for field in ("schema_version", "source_path", "rationale"):
            if field not in case and field in evidence:
                case[field] = evidence[field]

        required = (
            "id",
            "query",
            "locale",
            "task_family",
            "style_tags",
            "expected_lookup",
            "expected_semantic",
            "expected_intent",
            "expected_entity",
            "must_results",
            "forbidden_results",
            "allowed_alternatives",
            "critical",
            "schema_version",
            "source_path",
            "rationale",
            "split",
        )
        missing = [field for field in required if field not in case]
        if missing:
            raise FixtureError(
                f"{path}:{line_no}: missing required field(s): {', '.join(missing)}"
            )

        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id.strip():
            raise FixtureError(f"{path}:{line_no}: id must be a non-empty string")
        if case_id in seen_ids:
            raise FixtureError(f"{path}:{line_no}: duplicate id: {case_id}")
        seen_ids.add(case_id)
        if not isinstance(case["query"], str) or not case["query"].strip():
            raise FixtureError(f"{path}:{line_no}: query must be a non-empty string")
        if case["split"] not in {"dev", "heldout"}:
            raise FixtureError(f"{path}:{line_no}: split must be dev or heldout")
        if not isinstance(case["style_tags"], list):
            raise FixtureError(f"{path}:{line_no}: style_tags must be an array")
        for field in ("must_results", "forbidden_results", "allowed_alternatives"):
            if not isinstance(case[field], list):
                raise FixtureError(f"{path}:{line_no}: {field} must be an array")

        for field in ("must_results", "forbidden_results"):
            for index, spec in enumerate(case[field]):
                _validate_result_spec(spec, path, line_no, f"{field}[{index}]")
        for index, spec in enumerate(case["allowed_alternatives"]):
            _validate_alternative_spec(
                spec, path, line_no, f"allowed_alternatives[{index}]"
            )

        case["_line"] = line_no
        cases.append(case)
    if not cases:
        raise FixtureError(f"Gold fixture is empty: {path}")
    return cases


def _validate_result_spec(
    spec: Any, path: Path, line_no: int, label: str
) -> None:
    if not isinstance(spec, dict):
        raise FixtureError(f"{path}:{line_no}: {label} must be an object")
    missing = [field for field in _RESULT_KEY_FIELDS if field not in spec]
    if missing:
        raise FixtureError(
            f"{path}:{line_no}: {label} must use the full stable key; "
            f"missing {', '.join(missing)}"
        )
    for field in _RESULT_KEY_FIELDS:
        if not isinstance(spec[field], str):
            raise FixtureError(f"{path}:{line_no}: {label}.{field} must be a string")
    for rank_field in ("within_top_k", "max_rank"):
        if rank_field in spec and (
            not isinstance(spec[rank_field], int) or spec[rank_field] < 1
        ):
            raise FixtureError(
                f"{path}:{line_no}: {label}.{rank_field} must be a positive integer"
            )
    for alt_field in ("alternatives", "allowed_alternatives"):
        alternatives = spec.get(alt_field, [])
        if not isinstance(alternatives, list):
            raise FixtureError(f"{path}:{line_no}: {label}.{alt_field} must be an array")
        for index, alternative in enumerate(alternatives):
            _validate_result_spec(
                alternative, path, line_no, f"{label}.{alt_field}[{index}]"
            )


def _validate_alternative_spec(
    spec: Any, path: Path, line_no: int, label: str
) -> None:
    if not isinstance(spec, dict):
        raise FixtureError(f"{path}:{line_no}: {label} must be an object")
    if all(field in spec for field in _RESULT_KEY_FIELDS):
        _validate_result_spec(spec, path, line_no, label)
        return

    target = spec.get("for") or spec.get("must_result") or spec.get("replaces")
    alternatives = spec.get("alternatives") or spec.get("results")
    if target is None or alternatives is None:
        raise FixtureError(
            f"{path}:{line_no}: {label} must be a stable result or an explicit "
            "{for, alternatives} mapping"
        )
    _validate_result_spec(target, path, line_no, f"{label}.for")
    if not isinstance(alternatives, list) or not alternatives:
        raise FixtureError(f"{path}:{line_no}: {label}.alternatives must be non-empty")
    for index, alternative in enumerate(alternatives):
        _validate_result_spec(
            alternative, path, line_no, f"{label}.alternatives[{index}]"
        )


def _normalise_collection(value: str) -> str:
    lowered = value.strip().lower()
    return _COLLECTION_ALIASES.get(lowered, lowered)


def _normalise_ace_type(value: str) -> str:
    lowered = value.strip().lower()
    return _ACE_TYPE_ALIASES.get(lowered, lowered)


def _normalise_plugin_id(
    engine: Any,
    plugin_id: str,
    collection: str,
    entity_kind: str | None = None,
) -> str:
    raw = plugin_id.strip()
    if not raw or collection not in {"plugins", "behaviors"}:
        return raw
    resolved = engine.schema_index.resolve_name(raw)
    if resolved is None:
        return raw
    resolved_id, is_behavior = resolved
    expected_kind = entity_kind or ("behavior" if collection == "behaviors" else "plugin")
    if expected_kind == "plugin" and is_behavior:
        return raw
    if expected_kind == "behavior" and not is_behavior:
        return raw
    return resolved_id


def _canonical_spec(spec: dict[str, Any], engine: Any) -> dict[str, Any]:
    collection = _normalise_collection(spec["collection"])
    ace_type = _normalise_ace_type(spec["ace_type"])
    plugin_id = _normalise_plugin_id(
        engine,
        spec["plugin_id"],
        collection,
        spec.get("entity_kind"),
    )
    canonical = {
        "collection": collection,
        "plugin_id": plugin_id,
        "ace_type": ace_type,
        "ace_id": spec["ace_id"].strip(),
    }
    canonical["stable_key"] = _stable_key(canonical)
    for field in ("within_top_k", "max_rank"):
        if field in spec:
            canonical[field] = spec[field]
    return canonical


def _stable_tuple(result: dict[str, Any]) -> tuple[str, str, str, str]:
    return tuple(str(result[field]) for field in _RESULT_KEY_FIELDS)  # type: ignore[return-value]


def _stable_key(result: dict[str, Any]) -> str:
    return "|".join(str(result[field]) for field in _RESULT_KEY_FIELDS)


def _infer_collection(match: Any, response: Any) -> str:
    explicit = getattr(match, "collection", "")
    if explicit:
        return _normalise_collection(str(explicit))
    ace_type = _normalise_ace_type(str(getattr(match, "ace_type", "")))
    if ace_type == "script_api":
        return "script_api"
    if ace_type == "example":
        return "examples"
    if ace_type == "effect":
        return "effects"
    if ace_type == "term":
        return "terms"
    intent = getattr(response, "intent", None)
    return "behaviors" if intent is not None and intent.is_behavior else "plugins"


def _schema_has_match(schema: dict[str, Any] | None, match: Any) -> bool:
    """Return whether a schema owns the stable ACE/property ID on ``match``."""
    if not schema:
        return False
    ace_type = _normalise_ace_type(str(getattr(match, "ace_type", "")))
    section = {
        "condition": "conditions",
        "action": "actions",
        "expression": "expressions",
        "property": "properties",
    }.get(ace_type)
    if section is None:
        return False
    ace_id = str(getattr(match, "ace_id", ""))
    return any(str(item.get("id", "")) == ace_id for item in schema.get(section, []))


def _canonical_match_source(
    match: Any,
    response: Any,
    engine: Any,
    ambiguous_occurrences: Counter[tuple[str, str]],
) -> tuple[str, str]:
    """Recover the source schema hidden by ``LookupMatch.plugin_id``.

    ``_format_ace_search`` searches the requested addon and then ``_common``, but
    currently stamps both result sets with the requested plugin ID.  The evaluator
    restores the source key from the same r495 schemas and keeps the raw ID beside
    it.  If both schemas own an identical ACE ID, search order makes the first
    occurrence the addon and the second one ``_common``.
    """
    collection = _infer_collection(match, response)
    raw_plugin_id = str(getattr(match, "plugin_id", ""))
    intent = getattr(response, "intent", None)
    if str(getattr(match, "category", "")).strip().lower() == "common":
        return "plugins", "_common"
    if (
        collection not in {"plugins", "behaviors"}
        or intent is None
        or intent.intent_type != "ace_search"
    ):
        return collection, _normalise_plugin_id(engine, raw_plugin_id, collection)

    common_schema = engine.schema_index.get_schema("_common", False)
    addon_schema = engine.schema_index.get_schema(intent.plugin_id, intent.is_behavior)
    in_common = _schema_has_match(common_schema, match)
    in_addon = _schema_has_match(addon_schema, match)
    if not in_common:
        return collection, _normalise_plugin_id(engine, raw_plugin_id, collection)
    if not in_addon:
        return "plugins", "_common"

    occurrence_key = (
        _normalise_ace_type(str(getattr(match, "ace_type", ""))),
        str(getattr(match, "ace_id", "")),
    )
    occurrence = ambiguous_occurrences[occurrence_key]
    ambiguous_occurrences[occurrence_key] += 1
    if occurrence > 0:
        return "plugins", "_common"
    return collection, _normalise_plugin_id(engine, raw_plugin_id, collection)


def _ordered_results(response: Any, engine: Any) -> list[dict[str, Any]]:
    if response is None:
        return []
    results: list[dict[str, Any]] = []
    ambiguous_occurrences: Counter[tuple[str, str]] = Counter()
    for rank, match in enumerate(response.matches, 1):
        raw_plugin_id = str(getattr(match, "plugin_id", ""))
        collection, plugin_id = _canonical_match_source(
            match, response, engine, ambiguous_occurrences
        )
        canonical = {
            "collection": collection,
            "plugin_id": plugin_id,
            "ace_type": _normalise_ace_type(str(getattr(match, "ace_type", ""))),
            "ace_id": str(getattr(match, "ace_id", "")),
        }
        results.append(
            {
                "rank": rank,
                **canonical,
                "stable_key": _stable_key(canonical),
                "raw_plugin_id": raw_plugin_id,
                "name_en": getattr(getattr(match, "en", None), "name", ""),
                "name_zh": getattr(getattr(match, "zh", None), "name", ""),
                "category": str(getattr(match, "category", "") or ""),
                "relevance": int(getattr(match, "relevance", 0) or 0),
            }
        )
    return results


def _intent_snapshot(intent: Any) -> dict[str, Any] | None:
    if intent is None:
        return None
    return {
        "intent_type": intent.intent_type,
        "plugin_id": intent.plugin_id or None,
        "ace_type": intent.ace_type or None,
        "ace_name": intent.ace_name or None,
        "term": intent.term or None,
        "filter_term": intent.filter_term or None,
        "tier": intent.tier,
        "is_behavior": intent.is_behavior,
        "entity_kind": getattr(intent, "entity_kind", "") or None,
        "matched_tags": list(intent.matched_tags),
        "confidence": intent.confidence,
    }


def _entity_from_intent(intent: Any, response: Any) -> dict[str, str] | None:
    if intent is not None and intent.plugin_id:
        return {
            "kind": (
                getattr(intent, "entity_kind", "")
                or ("behavior" if intent.is_behavior else "plugin")
            ),
            "id": intent.plugin_id,
        }
    if intent is not None and intent.matched_tags:
        addon_tags = [
            tag for tag in intent.matched_tags
            if tag.startswith("plugin-") or tag.startswith("behavior-")
        ]
        if len(addon_tags) == 1:
            kind, item_id = addon_tags[0].split("-", 1)
            return {"kind": kind, "id": item_id}
    if response is not None and response.intent.intent_type == "script_api" and response.matches:
        return {"kind": "script_class", "id": response.matches[0].plugin_id}
    return None


def _canonical_entity(entity: Any, engine: Any) -> dict[str, str] | None:
    if entity is None:
        return None
    if isinstance(entity, str):
        entity = {"id": entity}
    if not isinstance(entity, dict):
        return None
    kind = str(entity.get("kind", "")).strip().lower()
    item_id = str(entity.get("id", entity.get("plugin_id", ""))).strip()
    if kind in {"plugin", "behavior"} and item_id:
        collection = "behaviors" if kind == "behavior" else "plugins"
        item_id = _normalise_plugin_id(engine, item_id, collection, kind)
    canonical: dict[str, str] = {}
    if kind:
        canonical["kind"] = kind
    if item_id:
        canonical["id"] = item_id
    return canonical or None


def _entity_matches(expected: Any, actual: Any, engine: Any) -> bool:
    expected_entities = expected if isinstance(expected, list) else [expected]
    actual_canonical = _canonical_entity(actual, engine)
    for candidate in expected_entities:
        expected_canonical = _canonical_entity(candidate, engine)
        if expected_canonical is None:
            if actual_canonical is None:
                return True
            continue
        if actual_canonical is None:
            continue
        if all(actual_canonical.get(key) == value for key, value in expected_canonical.items()):
            return True
    return False


@contextlib.contextmanager
def _expansion_policy(lookup_module: Any, strategy: str) -> Iterator[dict[str, Any]]:
    original_synonyms = getattr(lookup_module, "ACE_SYNONYMS", [])
    original_categories = getattr(lookup_module, "ACE_CATEGORY_EXPAND", frozenset())
    original_directed_aliases = getattr(lookup_module, "ACE_DIRECTED_ALIASES", ())
    if strategy == "literal":
        lookup_module.ACE_SYNONYMS = []
        lookup_module.ACE_CATEGORY_EXPAND = frozenset()
        lookup_module.ACE_DIRECTED_ALIASES = ()
    try:
        yield {
            "synonyms": lookup_module.ACE_SYNONYMS,
            "categories": lookup_module.ACE_CATEGORY_EXPAND,
            "directed_aliases": lookup_module.ACE_DIRECTED_ALIASES,
        }
    finally:
        lookup_module.ACE_SYNONYMS = original_synonyms
        lookup_module.ACE_CATEGORY_EXPAND = original_categories
        lookup_module.ACE_DIRECTED_ALIASES = original_directed_aliases


@contextlib.contextmanager
def _temporary_expansions(
    lookup_module: Any,
    synonyms: Any,
    categories: Any,
    directed_aliases: Any,
) -> Iterator[None]:
    old_synonyms = lookup_module.ACE_SYNONYMS
    old_categories = lookup_module.ACE_CATEGORY_EXPAND
    old_directed_aliases = lookup_module.ACE_DIRECTED_ALIASES
    lookup_module.ACE_SYNONYMS = synonyms
    lookup_module.ACE_CATEGORY_EXPAND = categories
    lookup_module.ACE_DIRECTED_ALIASES = directed_aliases
    try:
        yield
    finally:
        lookup_module.ACE_SYNONYMS = old_synonyms
        lookup_module.ACE_CATEGORY_EXPAND = old_categories
        lookup_module.ACE_DIRECTED_ALIASES = old_directed_aliases


def _captured_lookup(engine: Any, query: str) -> tuple[Any, Any, float]:
    captured: dict[str, Any] = {"intent": None}
    classifier = engine.classifier
    original_classify = classifier.classify

    def classify_with_capture(value: str) -> Any:
        intent = original_classify(value)
        captured["intent"] = intent
        return intent

    classifier.classify = classify_with_capture
    try:
        started = time.perf_counter()
        response = engine.try_lookup(query)
        elapsed_ms = (time.perf_counter() - started) * 1000
    finally:
        classifier.classify = original_classify
    return response, captured["intent"], elapsed_ms


def _base_filter_words(lookup_module: Any, filter_term: str) -> set[str]:
    raw_words = [word for word in filter_term.lower().split() if word]
    words = set(raw_words)
    for word in raw_words:
        if any("\u4e00" <= char <= "\u9fff" for char in word):
            words.update(
                segment
                for segment in lookup_module.jieba.lcut(word, cut_all=True)
                if len(segment) >= 2
            )
    return words


def _diagnostic_results(matches: list[Any], intent: Any, engine: Any) -> list[dict[str, Any]]:
    response = type(
        "DiagnosticResponse",
        (),
        {"matches": matches, "intent": intent},
    )()
    return _ordered_results(response, engine)


def _rank_changes(
    baseline: list[dict[str, Any]], candidate: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    baseline_ranks = {result["stable_key"]: result["rank"] for result in baseline}
    changes = []
    for result in candidate:
        old_rank = baseline_ranks.get(result["stable_key"])
        if old_rank is not None and old_rank != result["rank"]:
            changes.append(
                {
                    "stable_key": result["stable_key"],
                    "from_rank": old_rank,
                    "to_rank": result["rank"],
                }
            )
    return changes


def _directed_rule_scopes(
    engine: Any,
    intent: Any,
    base_words: set[str],
    rule: Any,
) -> list[dict[str, Any]]:
    schema = engine.schema_index.get_schema(intent.plugin_id, intent.is_behavior)
    if not schema:
        return []
    source_ids = [intent.plugin_id]
    supports_common = getattr(engine, "_supports_common_aces", None)
    if callable(supports_common) and supports_common(schema, intent.is_behavior):
        if engine.schema_index.get_schema("_common", False):
            source_ids.append("_common")
    ace_types = [value.strip() for value in intent.ace_type.split(",") if value.strip()]
    plugin_ids = {str(value) for value in rule.plugin_ids}
    rule_ace_types = {str(value) for value in rule.ace_types}
    from_terms = {str(value).lower() for value in rule.triggers}
    trigger_terms = sorted(base_words & from_terms)
    if not trigger_terms or (rule.exact and not base_words <= from_terms):
        return []
    return [
        {
            "plugin_id": source_id,
            "ace_type": ace_type,
            "trigger_terms": trigger_terms,
        }
        for source_id in source_ids
        for ace_type in ace_types
        if source_id in plugin_ids and ace_type in rule_ace_types
    ]


def _expansion_diagnostics(
    engine: Any,
    lookup_module: Any,
    strategy: str,
    intent: Any,
    actual_results: list[dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    empty = {
        "count": 0,
        "term_addition_count": 0,
        "category_result_addition_count": 0,
        "result_addition_count": 0,
        "directed_alias_term_addition_count": 0,
        "legacy_synonym_term_addition_count": 0,
        "sources": [],
    }
    if strategy == "literal" or intent is None or intent.intent_type != "ace_search":
        return empty

    base_words = _base_filter_words(lookup_module, intent.filter_term)
    expanded_words = set(base_words)
    synonym_sources: list[dict[str, Any]] = []
    for synonym_set in policy["synonyms"]:
        normalised_set = {str(value).lower() for value in synonym_set}
        trigger_terms = sorted(expanded_words & normalised_set)
        if not trigger_terms:
            continue
        added_terms = sorted(normalised_set - expanded_words)
        if added_terms:
            synonym_sources.append(
                {
                    "type": "ace_synonyms",
                    "trigger_terms": trigger_terms,
                    "added_terms": added_terms,
                }
            )
            expanded_words.update(normalised_set)

    with _temporary_expansions(lookup_module, [], frozenset(), ()):
        _, literal_matches = engine._execute(intent)
    with _temporary_expansions(
        lookup_module, policy["synonyms"], frozenset(), ()
    ):
        _, synonym_only_matches = engine._execute(intent)
    with _temporary_expansions(
        lookup_module, policy["synonyms"], policy["categories"], ()
    ):
        _, legacy_full_matches = engine._execute(intent)

    literal_results = _diagnostic_results(literal_matches, intent, engine)
    synonym_only_results = _diagnostic_results(synonym_only_matches, intent, engine)
    legacy_full_results = _diagnostic_results(legacy_full_matches, intent, engine)
    literal_keys = {result["stable_key"] for result in literal_results}
    synonym_only_keys = {result["stable_key"] for result in synonym_only_results}
    actual_direct_results = [
        result
        for result in actual_results
        if result["collection"] in {"plugins", "behaviors"}
    ]
    actual_keys = {result["stable_key"] for result in actual_direct_results}

    synonym_result_keys = [
        result["stable_key"]
        for result in synonym_only_results
        if result["stable_key"] not in literal_keys
    ]
    synonym_rank_changes = _rank_changes(literal_results, synonym_only_results)
    legacy_synonym_observed = bool(synonym_result_keys or synonym_rank_changes)
    if synonym_sources and legacy_synonym_observed:
        for source in synonym_sources:
            source["observed_result_effect"] = True
        synonym_sources[-1]["added_result_keys"] = synonym_result_keys
        synonym_sources[-1]["rank_changes"] = synonym_rank_changes
    elif synonym_sources:
        # Compatibility constants can still exist without being consumed by
        # production.  Do not count or attribute them without an observed delta.
        synonym_sources = []

    category_added = [
        result for result in legacy_full_results
        if result["stable_key"] not in synonym_only_keys
    ]
    categories: dict[str, list[str]] = {}
    for result in category_added:
        category = result["category"] or "unknown"
        categories.setdefault(category, []).append(result["stable_key"])
    category_sources = [
        {
            "type": "ace_category_expand",
            "category": category,
            "added_result_keys": keys,
        }
        for category, keys in sorted(categories.items())
    ]

    directed_sources: list[dict[str, Any]] = []
    directed_added_terms: set[str] = set()
    for rule in policy["directed_aliases"]:
        scopes = _directed_rule_scopes(engine, intent, base_words, rule)
        if not scopes:
            continue
        added_terms = {
            str(value).lower() for value in rule.additions
        } - base_words
        directed_added_terms.update(added_terms)
        with _temporary_expansions(
            lookup_module,
            policy["synonyms"],
            policy["categories"],
            (rule,),
        ):
            _, rule_matches = engine._execute(intent)
        rule_results = _diagnostic_results(rule_matches, intent, engine)
        legacy_keys = {result["stable_key"] for result in legacy_full_results}
        directed_sources.append(
            {
                "type": "ace_directed_alias",
                "rule_id": rule.rule_id,
                "weight": rule.weight,
                "allow_chaining": rule.allow_chaining,
                "scopes": scopes,
                "added_terms": sorted(added_terms),
                "added_result_keys": [
                    result["stable_key"]
                    for result in rule_results
                    if result["stable_key"] not in legacy_keys
                ],
                "rank_changes": _rank_changes(legacy_full_results, rule_results),
            }
        )

    legacy_term_count = len(expanded_words - base_words) if legacy_synonym_observed else 0
    directed_term_count = len(directed_added_terms)
    category_count = len(category_added)
    all_result_additions = actual_keys - literal_keys
    return {
        "count": legacy_term_count + directed_term_count + category_count,
        "term_addition_count": legacy_term_count + directed_term_count,
        "category_result_addition_count": category_count,
        "result_addition_count": len(all_result_additions),
        "directed_alias_term_addition_count": directed_term_count,
        "legacy_synonym_term_addition_count": legacy_term_count,
        "sources": synonym_sources + category_sources + directed_sources,
    }


def _expected_lookup(value: Any) -> str:
    if isinstance(value, bool):
        return "hit" if value else "miss"
    lowered = str(value).strip().lower()
    if lowered in {"hit", "lookup", "direct_lookup", "required", "true"}:
        return "hit"
    if lowered in {"miss", "fallback", "semantic", "false", "none"}:
        return "miss"
    raise FixtureError(f"Unknown expected_lookup value: {value!r}")


def _semantic_judgment(value: Any, actual_route: str) -> dict[str, Any]:
    lowered = str(value).strip().lower() if value is not None else "optional"
    if lowered in {"required", "fallback", "semantic"}:
        passed = actual_route == "semantic_fallback"
    elif lowered in {"forbidden", "not_required", "none", "lookup"}:
        passed = actual_route == "direct_lookup"
    elif lowered in {"optional", "allowed", "either"}:
        passed = True
    else:
        raise FixtureError(f"Unknown expected_semantic value: {value!r}")
    return {"expected": lowered, "executed": False, "passed": passed}


def _rank_limit(spec: dict[str, Any], case: dict[str, Any], default: int = 5) -> int:
    return int(
        spec.get("within_top_k")
        or spec.get("max_rank")
        or case.get("max_rank")
        or default
    )


def _canonical_alternatives(
    case: dict[str, Any], engine: Any, groups: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    independent: list[dict[str, Any]] = []
    group_by_key = {
        group["required"]["stable_key"]: group
        for group in groups
    }
    for alternative in case["allowed_alternatives"]:
        if all(field in alternative for field in _RESULT_KEY_FIELDS):
            independent.append(_canonical_spec(alternative, engine))
            continue
        target_raw = (
            alternative.get("for")
            or alternative.get("must_result")
            or alternative.get("replaces")
        )
        target = _canonical_spec(target_raw, engine)
        group = group_by_key.get(target["stable_key"])
        if group is None:
            raise FixtureError(
                f"case {case['id']}: allowed alternative targets unknown must result "
                f"{target['stable_key']}"
            )
        alternatives = alternative.get("alternatives") or alternative.get("results") or []
        group["alternatives"].extend(
            _canonical_spec(candidate, engine) for candidate in alternatives
        )
    return independent


def _required_groups(case: dict[str, Any], engine: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: list[dict[str, Any]] = []
    for raw in case["must_results"]:
        required = _canonical_spec(raw, engine)
        alternatives: list[dict[str, Any]] = []
        for field in ("alternatives", "allowed_alternatives"):
            alternatives.extend(
                _canonical_spec(candidate, engine) for candidate in raw.get(field, [])
            )
        groups.append({"required": required, "alternatives": alternatives})
    independent = _canonical_alternatives(case, engine, groups)
    return groups, independent


def _rank_judgments(
    case: dict[str, Any],
    engine: Any,
    results: list[dict[str, Any]],
    evaluate_direct_ranking: bool,
) -> dict[str, Any]:
    ranks: dict[str, int] = {}
    for result in results:
        ranks.setdefault(result["stable_key"], result["rank"])

    groups, independent_alternatives = _required_groups(case, engine)
    must_items: list[dict[str, Any]] = []
    for group in groups:
        required = group["required"]
        options = [required, *group["alternatives"]]
        option_hits = [
            (ranks[option["stable_key"]], option)
            for option in options
            if option["stable_key"] in ranks
        ]
        best_rank, matched_option = min(option_hits, default=(None, None), key=lambda pair: pair[0] or math.inf)
        limit = _rank_limit(required, case)
        passed = best_rank is not None and best_rank <= limit
        must_items.append(
            {
                "expected": required,
                "alternatives": group["alternatives"],
                "matched": passed if evaluate_direct_ranking else None,
                "matched_key": matched_option["stable_key"] if matched_option else None,
                "rank": best_rank,
                "max_rank": limit,
            }
        )

    forbidden_items: list[dict[str, Any]] = []
    for raw in case["forbidden_results"]:
        expected = _canonical_spec(raw, engine)
        rank = ranks.get(expected["stable_key"])
        limit = _rank_limit(expected, case)
        violated = rank is not None and rank <= limit
        forbidden_items.append(
            {
                "expected": expected,
                "violated": violated,
                "rank": rank,
                "within_top_k": limit,
            }
        )

    allowed_items = []
    for expected in independent_alternatives:
        rank = ranks.get(expected["stable_key"])
        allowed_items.append(
            {
                "expected": expected,
                "hit": rank is not None,
                "rank": rank,
            }
        )

    hit_at: dict[str, bool | None] = {}
    for cutoff in (1, 3, 5):
        hit_at[str(cutoff)] = (
            all(
                any(
                    ranks.get(option["stable_key"], math.inf) <= cutoff
                    for option in [group["required"], *group["alternatives"]]
                )
                for group in groups
            )
            if groups and evaluate_direct_ranking
            else None
        )

    first_relevant_rank = min(
        (
            ranks[option["stable_key"]]
            for group in groups
            for option in [group["required"], *group["alternatives"]]
            if option["stable_key"] in ranks
        ),
        default=None,
    )
    reciprocal_rank = (
        1.0 / first_relevant_rank
        if first_relevant_rank and evaluate_direct_ranking
        else 0.0
        if evaluate_direct_ranking
        else None
    )
    ndcg_5 = (
        _ndcg_at_5(results, groups, independent_alternatives)
        if evaluate_direct_ranking
        else None
    )

    return {
        "must": {
            "evaluated": evaluate_direct_ranking,
            "status": (
                "evaluated"
                if evaluate_direct_ranking
                else "not_evaluated_semantic_required"
            ),
            "passed": (
                all(item["matched"] for item in must_items)
                if evaluate_direct_ranking
                else True
            ),
            "items": must_items,
            "hit_at": hit_at,
            "first_relevant_rank": first_relevant_rank,
            "reciprocal_rank": reciprocal_rank,
            "ndcg_at_5": ndcg_5,
        },
        "forbidden": {
            "passed": not any(item["violated"] for item in forbidden_items),
            "items": forbidden_items,
        },
        "allowed_alternatives": {"items": allowed_items},
    }


def _ndcg_at_5(
    results: list[dict[str, Any]],
    groups: list[dict[str, Any]],
    independent_alternatives: list[dict[str, Any]],
) -> float | None:
    if not groups:
        return None
    option_to_group: dict[str, int] = {}
    for index, group in enumerate(groups):
        for option in [group["required"], *group["alternatives"]]:
            option_to_group[option["stable_key"]] = index
    allowed_keys = {item["stable_key"] for item in independent_alternatives}
    satisfied_groups: set[int] = set()
    seen_keys: set[str] = set()
    gains: list[float] = []
    for result in results[:5]:
        key = result["stable_key"]
        relevance = 0.0
        group_index = option_to_group.get(key)
        if group_index is not None and group_index not in satisfied_groups:
            relevance = 2.0
            satisfied_groups.add(group_index)
        elif key in allowed_keys and key not in seen_keys:
            relevance = 1.0
        gains.append(relevance)
        seen_keys.add(key)

    dcg = sum((2**gain - 1) / math.log2(rank + 1) for rank, gain in enumerate(gains, 1))
    ideal_gains = ([2.0] * len(groups) + [1.0] * len(allowed_keys))[:5]
    idcg = sum(
        (2**gain - 1) / math.log2(rank + 1)
        for rank, gain in enumerate(ideal_gains, 1)
    )
    return dcg / idcg if idcg else 0.0


def _intent_pass(expected: Any, actual: str | None) -> bool:
    if isinstance(expected, list):
        return actual in expected
    return actual == expected


def _ace_type_judgment(
    case: dict[str, Any],
    effective_intent: Any,
    results: list[dict[str, Any]],
    evaluate_direct_structure: bool,
) -> dict[str, Any]:
    expected_raw = case.get("expected_ace_types", [])
    if not evaluate_direct_structure:
        return {
            "expected": sorted(_normalise_ace_type(value) for value in expected_raw),
            "actual": [],
            "passed": True,
            "evaluated": False,
            "status": "not_evaluated_semantic_required",
        }
    if not expected_raw:
        return {
            "expected": [],
            "actual": [],
            "passed": True,
            "evaluated": False,
            "status": "not_applicable",
        }
    expected = {_normalise_ace_type(value) for value in expected_raw}
    raw_actual = effective_intent.ace_type if effective_intent is not None else ""
    if raw_actual:
        actual = {
            _normalise_ace_type(value)
            for value in raw_actual.split(",")
            if value.strip()
        }
    else:
        # Detail and scripting intents do not carry an ace_type on the intent;
        # their structured matches are the authoritative observable type.
        actual = {result["ace_type"] for result in results}
    return {
        "expected": sorted(expected),
        "actual": sorted(actual),
        "passed": expected == actual,
        "evaluated": True,
        "status": "evaluated",
    }


def _count_judgment(
    case: dict[str, Any], count: int, evaluate_direct_structure: bool
) -> dict[str, Any]:
    minimum = case.get("min_results")
    maximum = case.get("max_results")
    if not evaluate_direct_structure:
        return {
            "actual": count,
            "min_results": minimum,
            "max_results": maximum,
            "passed": True,
            "evaluated": False,
            "status": "not_evaluated_semantic_required",
        }
    minimum_ok = minimum is None or count >= int(minimum)
    maximum_ok = maximum is None or count <= int(maximum)
    return {
        "actual": count,
        "min_results": minimum,
        "max_results": maximum,
        "passed": minimum_ok and maximum_ok,
        "evaluated": True,
        "status": "evaluated",
    }


def _evaluate_case(
    case: dict[str, Any],
    engine: Any,
    lookup_module: Any,
    strategy: str,
    policy: dict[str, Any],
) -> dict[str, Any]:
    response, classified_intent, latency_ms = _captured_lookup(engine, case["query"])
    effective_intent = response.intent if response is not None else None
    actual_route = "direct_lookup" if response is not None else "semantic_fallback"
    actual_lookup = "hit" if response is not None else "miss"
    results = _ordered_results(response, engine)
    result_keys = [result["stable_key"] for result in results]
    unique_result_count = len(set(result_keys))
    duplicate_count = len(result_keys) - unique_result_count

    expected_lookup = _expected_lookup(case["expected_lookup"])
    route_passed = expected_lookup == actual_lookup
    semantic = _semantic_judgment(case["expected_semantic"], actual_route)
    actual_intent = effective_intent.intent_type if effective_intent is not None else None
    intent_passed = _intent_pass(case["expected_intent"], actual_intent)
    actual_entity = _entity_from_intent(classified_intent or effective_intent, response)
    entity_passed = _entity_matches(case["expected_entity"], actual_entity, engine)
    evaluate_direct_structure = expected_lookup == "hit"
    rank_judgments = _rank_judgments(
        case, engine, results, evaluate_direct_structure
    )
    count_judgment = _count_judgment(
        case, len(results), evaluate_direct_structure
    )
    ace_types = _ace_type_judgment(
        case, effective_intent, results, evaluate_direct_structure
    )
    expansion = _expansion_diagnostics(
        engine,
        lookup_module,
        strategy,
        classified_intent or effective_intent,
        results,
        policy,
    )

    checks = {
        "route": route_passed,
        "semantic_route": semantic["passed"],
        "intent": intent_passed,
        "entity": entity_passed,
        "ace_types": ace_types["passed"],
        "must_results": rank_judgments["must"]["passed"],
        "forbidden_results": rank_judgments["forbidden"]["passed"],
        "result_count": count_judgment["passed"],
    }
    failed_checks = [name for name, passed in checks.items() if not passed]
    evidence = {
        "schema_version": case["schema_version"],
        "source_path": case["source_path"],
        "rationale": case["rationale"],
    }
    return {
        "id": case["id"],
        "query": case["query"],
        "locale": case["locale"],
        "task_family": case["task_family"],
        "style_tags": case["style_tags"],
        "split": case["split"],
        "critical": bool(case["critical"]),
        "evidence": evidence,
        "expected": {
            "lookup": expected_lookup,
            "semantic": case["expected_semantic"],
            "intent": case["expected_intent"],
            "entity": case["expected_entity"],
            "ace_types": case.get("expected_ace_types", []),
        },
        "actual": {
            "route": actual_route,
            "lookup": actual_lookup,
            "semantic_executed": False,
            "intent": actual_intent,
            "classified_intent": _intent_snapshot(classified_intent),
            "entity": actual_entity,
            "query_type": response.query_type if response is not None else None,
            "context_present": bool(response and response.context),
            "context_length": len(response.context) if response is not None else 0,
            "lookup_shape": (
                "structured_matches"
                if results
                else "context_only"
                if response is not None and response.context
                else "empty_response"
                if response is not None
                else "miss"
            ),
            "valid_structured_lookup": response is not None and bool(results),
            "results": results,
            "result_count": len(results),
            "unique_result_count": unique_result_count,
            "duplicate_count": duplicate_count,
            "latency_ms": latency_ms,
            "engine_elapsed_ms": response.elapsed_ms if response is not None else None,
            "expansion": expansion,
        },
        "judgments": {
            "route": {
                "expected_lookup": expected_lookup,
                "actual_lookup": actual_lookup,
                "passed": route_passed,
            },
            "semantic": semantic,
            "intent": {
                "expected": case["expected_intent"],
                "actual": actual_intent,
                "passed": intent_passed,
            },
            "entity": {
                "expected": _canonical_entity(case["expected_entity"], engine)
                if not isinstance(case["expected_entity"], list)
                else [
                    _canonical_entity(entity, engine)
                    for entity in case["expected_entity"]
                ],
                "actual": _canonical_entity(actual_entity, engine),
                "passed": entity_passed,
            },
            "ace_types": ace_types,
            "count": count_judgment,
            **rank_judgments,
        },
        "passed": not failed_checks,
        "failed_checks": failed_checks,
    }


def _rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "value": numerator / denominator if denominator else None,
        "numerator": numerator,
        "denominator": denominator,
    }


def _percentile(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def _latency_stats(values: Sequence[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "mean_ms": None,
            "median_ms": None,
            "p95_ms": None,
            "min_ms": None,
            "max_ms": None,
        }
    return {
        "count": len(values),
        "mean_ms": statistics.fmean(values),
        "median_ms": statistics.median(values),
        "p95_ms": _percentile(values, 0.95),
        "min_ms": min(values),
        "max_ms": max(values),
    }


def _summary(rows: list[dict[str, Any]], engine_init_ms: float) -> dict[str, Any]:
    total = len(rows)
    required_rows = [
        row
        for row in rows
        if row["judgments"]["must"]["items"]
        and row["judgments"]["must"]["evaluated"]
    ]
    fallback_rows = [
        row
        for row in rows
        if row["expected"]["lookup"] == "miss"
        or str(row["expected"]["semantic"]).lower() == "required"
    ]
    false_direct = [
        row for row in fallback_rows if row["actual"]["route"] == "direct_lookup"
    ]
    correct_fallback = [
        row for row in fallback_rows if row["actual"]["route"] == "semantic_fallback"
    ]
    duplicate_results = sum(row["actual"]["duplicate_count"] for row in rows)
    all_results = sum(row["actual"]["result_count"] for row in rows)
    duplicate_queries = sum(row["actual"]["duplicate_count"] > 0 for row in rows)
    direct_rows = [row for row in rows if row["actual"]["route"] == "direct_lookup"]
    context_only_rows = [
        row for row in direct_rows if row["actual"]["lookup_shape"] == "context_only"
    ]
    latencies = [row["actual"]["latency_ms"] for row in rows]
    warm_latencies = [row["actual"]["warm_latency_ms"] for row in rows]
    expansion_counts = [row["actual"]["expansion"]["count"] for row in rows]
    expansion_source_counts: Counter[str] = Counter()
    for row in rows:
        expansion_source_counts.update(
            source["type"] for source in row["actual"]["expansion"]["sources"]
        )

    hit_metrics = {
        f"hit_at_{cutoff}": _rate(
            sum(row["judgments"]["must"]["hit_at"][str(cutoff)] is True for row in required_rows),
            len(required_rows),
        )
        for cutoff in (1, 3, 5)
    }
    mrr_values = [row["judgments"]["must"]["reciprocal_rank"] for row in required_rows]
    ndcg_values = [
        row["judgments"]["must"]["ndcg_at_5"]
        for row in required_rows
        if row["judgments"]["must"]["ndcg_at_5"] is not None
    ]
    critical_rows = [row for row in rows if row["critical"]]
    cold_query_ms = latencies[0] if latencies else None

    return {
        "total_queries": total,
        "passed_queries": sum(row["passed"] for row in rows),
        "failed_queries": sum(not row["passed"] for row in rows),
        "critical": {
            "total": len(critical_rows),
            "passed": sum(row["passed"] for row in critical_rows),
            "failed_ids": [row["id"] for row in critical_rows if not row["passed"]],
        },
        "route_accuracy": _rate(
            sum(row["judgments"]["route"]["passed"] for row in rows), total
        ),
        "intent_accuracy": _rate(
            sum(row["judgments"]["intent"]["passed"] for row in rows), total
        ),
        "entity_accuracy": _rate(
            sum(row["judgments"]["entity"]["passed"] for row in rows), total
        ),
        **hit_metrics,
        "mrr": statistics.fmean(mrr_values) if mrr_values else None,
        "ndcg_at_5": statistics.fmean(ndcg_values) if ndcg_values else None,
        "false_direct_lookup_rate": _rate(len(false_direct), len(fallback_rows)),
        "correct_fallback_rate": _rate(len(correct_fallback), len(fallback_rows)),
        "forbidden_violation_rate": _rate(
            sum(not row["judgments"]["forbidden"]["passed"] for row in rows), total
        ),
        "duplicate_result_rate": _rate(duplicate_results, all_results),
        "queries_with_duplicates_rate": _rate(duplicate_queries, total),
        "structured_lookup_shape": {
            "direct_lookup_queries": len(direct_rows),
            "valid_structured_queries": sum(
                row["actual"]["valid_structured_lookup"] for row in direct_rows
            ),
            "context_only_queries": len(context_only_rows),
            "context_only_ids": [row["id"] for row in context_only_rows],
            "context_only_rate": _rate(len(context_only_rows), len(direct_rows)),
        },
        "latency": {
            "engine_init_ms": engine_init_ms,
            "cold_query_ms": cold_query_ms,
            "cold_total_ms": engine_init_ms + cold_query_ms if cold_query_ms is not None else engine_init_ms,
            "warm": _latency_stats(warm_latencies),
            "first_pass": _latency_stats(latencies),
            "warm_repeat_stability": _rate(
                sum(row["actual"]["warm_repeat_stable"] for row in rows), total
            ),
        },
        "expansion": {
            "mean_count": statistics.fmean(expansion_counts) if expansion_counts else 0.0,
            "p95_count": _percentile(expansion_counts, 0.95),
            "max_count": max(expansion_counts, default=0),
            "queries_with_expansion": sum(value > 0 for value in expansion_counts),
            "source_occurrences": dict(sorted(expansion_source_counts.items())),
        },
    }


def _family_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    families: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        families.setdefault(row["task_family"], []).append(row)
    summary: dict[str, Any] = {}
    for family, family_rows in sorted(families.items()):
        required = [
            row
            for row in family_rows
            if row["judgments"]["must"]["items"]
            and row["judgments"]["must"]["evaluated"]
        ]
        fallback = [row for row in family_rows if row["expected"]["lookup"] == "miss"]
        summary[family] = {
            "queries": len(family_rows),
            "passed": sum(row["passed"] for row in family_rows),
            "route_accuracy": _rate(
                sum(row["judgments"]["route"]["passed"] for row in family_rows),
                len(family_rows),
            ),
            "hit_at_5": _rate(
                sum(row["judgments"]["must"]["hit_at"]["5"] is True for row in required),
                len(required),
            ),
            "false_direct_lookup_rate": _rate(
                sum(row["actual"]["route"] == "direct_lookup" for row in fallback),
                len(fallback),
            ),
        }
    return summary


def _run_strategy(
    strategy: str, cases: list[dict[str, Any]], lookup_module: Any
) -> dict[str, Any]:
    with _expansion_policy(lookup_module, strategy) as policy:
        init_started = time.perf_counter()
        engine = lookup_module.LookupEngine(
            schema_dir=lookup_module.SCHEMA_DIR,
        )
        engine_init_ms = (time.perf_counter() - init_started) * 1000
        rows = [
            _evaluate_case(case, engine, lookup_module, strategy, policy)
            for case in cases
        ]
        # Repeat after every lazy local index/tokenizer path has had a chance to
        # initialize.  This separates genuinely warm latency from first-pass
        # spikes and also provides a one-repeat ordering stability check.
        for case, row in zip(cases, rows):
            started = time.perf_counter()
            warm_response = engine.try_lookup(case["query"])
            warm_latency_ms = (time.perf_counter() - started) * 1000
            warm_results = _ordered_results(warm_response, engine)
            warm_signature = {
                "route": "direct_lookup" if warm_response is not None else "semantic_fallback",
                "intent": warm_response.intent.intent_type if warm_response is not None else None,
                "result_keys": [result["stable_key"] for result in warm_results],
            }
            first_signature = {
                "route": row["actual"]["route"],
                "intent": row["actual"]["intent"],
                "result_keys": [
                    result["stable_key"] for result in row["actual"]["results"]
                ],
            }
            row["actual"]["warm_latency_ms"] = warm_latency_ms
            row["actual"]["warm_repeat_stable"] = warm_signature == first_signature
    return {
        "strategy": strategy,
        "policy": {
            "ace_synonym_sets": len(policy["synonyms"]),
            "ace_category_count": len(policy["categories"]),
            "ace_directed_alias_count": len(policy["directed_aliases"]),
            "entity_resolution": True,
            "jieba": True,
            "schema_index": True,
            "scripting_index": True,
            "examples_index": True,
            "embedder": False,
            "ollama": False,
            "qdrant": False,
            "network": False,
        },
        "summary": _summary(rows, engine_init_ms),
        "by_task_family": _family_summary(rows),
        "queries": rows,
    }


def _metric_value(summary: dict[str, Any], name: str) -> float | None:
    value = summary[name]
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def _comparison(current: dict[str, Any], literal: dict[str, Any]) -> dict[str, Any]:
    metrics = (
        "route_accuracy",
        "intent_accuracy",
        "entity_accuracy",
        "hit_at_1",
        "hit_at_3",
        "hit_at_5",
        "mrr",
        "ndcg_at_5",
        "false_direct_lookup_rate",
        "correct_fallback_rate",
        "duplicate_result_rate",
    )
    deltas: dict[str, Any] = {}
    for metric in metrics:
        current_value = _metric_value(current["summary"], metric)
        literal_value = _metric_value(literal["summary"], metric)
        deltas[metric] = {
            "current": current_value,
            "literal": literal_value,
            "literal_minus_current": (
                literal_value - current_value
                if current_value is not None and literal_value is not None
                else None
            ),
        }

    current_rows = {row["id"]: row for row in current["queries"]}
    changed_queries = []
    for literal_row in literal["queries"]:
        current_row = current_rows[literal_row["id"]]
        current_keys = [r["stable_key"] for r in current_row["actual"]["results"]]
        literal_keys = [r["stable_key"] for r in literal_row["actual"]["results"]]
        if (
            current_row["actual"]["route"] != literal_row["actual"]["route"]
            or current_row["actual"]["intent"] != literal_row["actual"]["intent"]
            or current_keys != literal_keys
        ):
            changed_queries.append(
                {
                    "id": literal_row["id"],
                    "query": literal_row["query"],
                    "current_route": current_row["actual"]["route"],
                    "literal_route": literal_row["actual"]["route"],
                    "current_intent": current_row["actual"]["intent"],
                    "literal_intent": literal_row["actual"]["intent"],
                    "current_result_keys": current_keys,
                    "literal_result_keys": literal_keys,
                }
            )
    return {
        "metric_deltas": deltas,
        "changed_query_count": len(changed_queries),
        "changed_queries": changed_queries,
    }


def _schema_metadata(lookup_module: Any) -> dict[str, Any]:
    index_path = Path(lookup_module.SCHEMA_DIR) / "_index.json"
    version = ""
    if index_path.is_file():
        try:
            version = str(json.loads(index_path.read_text(encoding="utf-8")).get("version", ""))
        except (OSError, json.JSONDecodeError):
            version = ""
    return {
        "directory": str(Path(lookup_module.SCHEMA_DIR).resolve()),
        "index_path": str(index_path.resolve()),
        "version": version,
    }


def _fixture_audit(cases: list[dict[str, Any]], live_schema_version: str) -> dict[str, Any]:
    version_counts = Counter(str(case["schema_version"]) for case in cases)
    split_counts = Counter(str(case["split"]) for case in cases)
    family_counts = Counter(str(case["task_family"]) for case in cases)
    locale_counts = Counter(str(case["locale"]) for case in cases)
    missing_sources: list[str] = []
    nonexistent_sources: list[dict[str, str]] = []
    for case in cases:
        source = case["source_path"]
        sources = source if isinstance(source, list) else [source]
        if case["must_results"] and not any(sources):
            missing_sources.append(case["id"])
        for item in sources:
            if not item or not isinstance(item, str):
                continue
            path_text = item.split("#", 1)[0]
            candidate = (ROOT / path_text).resolve()
            if not candidate.exists():
                nonexistent_sources.append({"id": case["id"], "source_path": item})
    version_mismatch_ids = [
        case["id"]
        for case in cases
        if live_schema_version and str(case["schema_version"]) != live_schema_version
    ]
    return {
        "version_counts": dict(sorted(version_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "task_family_counts": dict(sorted(family_counts.items())),
        "locale_counts": dict(sorted(locale_counts.items())),
        "missing_source_for_ranked_case_ids": missing_sources,
        "nonexistent_sources": nonexistent_sources,
        "live_schema_version_mismatch_ids": version_mismatch_ids,
    }


def _print_human(report: dict[str, Any], verbose: bool) -> None:
    for name, strategy in report["strategies"].items():
        print(f"\n=== {name} ({strategy['summary']['total_queries']} queries) ===")
        for row in strategy["queries"]:
            marker = "PASS" if row["passed"] else "FAIL"
            actual = row["actual"]
            entity = actual["entity"] or {}
            entity_text = (
                f"{entity.get('kind')}:{entity.get('id')}" if entity else "-"
            )
            print(
                f"[{marker}] {row['id']} | {row['query']} | "
                f"route={actual['route']} intent={actual['intent'] or '-'} "
                f"entity={entity_text} results={actual['result_count']} "
                f"latency={actual['latency_ms']:.2f}ms "
                f"expansions={actual['expansion']['count']}"
            )
            if row["failed_checks"]:
                print(f"  failed: {', '.join(row['failed_checks'])}")
            if verbose:
                for result in actual["results"]:
                    print(f"  {result['rank']:>3}. {result['stable_key']}")
                must = row["judgments"]["must"]
                forbidden = row["judgments"]["forbidden"]
                print(
                    f"  must={'pass' if must['passed'] else 'FAIL'} "
                    f"forbidden={'pass' if forbidden['passed'] else 'FAIL'}"
                )
        summary = strategy["summary"]
        print(
            "summary: "
            f"passed={summary['passed_queries']}/{summary['total_queries']} "
            f"Hit@1/3/5={_format_rate(summary['hit_at_1'])}/"
            f"{_format_rate(summary['hit_at_3'])}/{_format_rate(summary['hit_at_5'])} "
            f"MRR={_format_number(summary['mrr'])} "
            f"nDCG@5={_format_number(summary['ndcg_at_5'])} "
            f"false-direct={_format_rate(summary['false_direct_lookup_rate'])} "
            f"fallback={_format_rate(summary['correct_fallback_rate'])}"
        )


def _format_rate(rate: dict[str, Any]) -> str:
    value = rate["value"]
    return "n/a" if value is None else f"{value:.3f}"


def _format_number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _write_json(report: dict[str, Any], destination: str) -> None:
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if destination == "-":
        sys.stdout.write(payload)
        return
    path = Path(destination)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    print(f"\nJSON report: {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare offline Direct Lookup strategies against tests/fixtures/query_gold.jsonl. "
            "No Qdrant, model or network access is used."
        )
    )
    parser.add_argument(
        "--strategy",
        choices=("current", "literal", "all"),
        default="all",
        help="Lookup expansion policy to evaluate (default: all)",
    )
    parser.add_argument(
        "--split",
        choices=("dev", "heldout", "all"),
        default="all",
        help="Gold-set split to evaluate (default: all)",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE,
        help=f"JSONL gold fixture (default: {DEFAULT_FIXTURE.relative_to(ROOT)})",
    )
    parser.add_argument(
        "--output",
        default="-",
        metavar="PATH|-",
        help="Write the full JSON report to PATH, or stdout for '-' (default: -)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="When writing JSON to a file, print every ordered stable result key",
    )
    parser.add_argument(
        "--fail-on-quality",
        action="store_true",
        help="Exit non-zero when any selected gold query fails (baseline runs default to exit 0)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    fixture = args.fixture.resolve()
    cases = _read_jsonl(fixture)
    if args.split != "all":
        cases = [case for case in cases if case["split"] == args.split]
    if not cases:
        raise FixtureError(f"No {args.split!r} cases selected from {fixture}")

    import src.rag.lookup as lookup_module

    strategies = (
        ["current", "literal"] if args.strategy == "all" else [args.strategy]
    )
    schema = _schema_metadata(lookup_module)
    report: dict[str, Any] = {
        "format_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "fixture": str(fixture),
            "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
            "selected_split": args.split,
            "selected_strategies": strategies,
            "query_count": len(cases),
            "schema": schema,
            "mode": "offline_direct_lookup",
            "semantic_route_interpretation": (
                "A lookup miss is recorded as semantic_fallback; semantic retrieval is not executed."
            ),
            "ranking_definitions": {
                "case_pass": (
                    "all required stable-key groups satisfy their adjudicated max_rank, "
                    "all forbidden/count/route/intent/entity checks pass; complete-list "
                    "cases may use a max_rank beyond five"
                ),
                "hit_at_k": "case-level all-required stable-key groups within top K",
                "mrr": "reciprocal rank of the first required stable-key group hit",
                "ndcg_at_5": "graded relevance: must/substitute=2, independent allowed alternative=1",
                "expansion_count": (
                    "observed legacy synonym terms, triggered directed-alias terms, "
                    "plus results added directly by category expansion"
                ),
                "cold_latency": "LookupEngine construction plus the first selected query",
                "warm_latency": (
                    "one repeat of every selected query after the full first pass initialized local paths"
                ),
            },
            "external_services": {
                "qdrant": False,
                "embedding_model": False,
                "ollama": False,
                "network": False,
            },
        },
        "fixture_audit": _fixture_audit(cases, schema["version"]),
        "strategies": {},
    }
    for strategy in strategies:
        report["strategies"][strategy] = _run_strategy(
            strategy, cases, lookup_module
        )
    if set(strategies) == {"current", "literal"}:
        report["comparison"] = _comparison(
            report["strategies"]["current"],
            report["strategies"]["literal"],
        )

    if args.output != "-":
        _print_human(report, args.verbose)
    _write_json(report, args.output)

    failures = sum(
        strategy["summary"]["failed_queries"]
        for strategy in report["strategies"].values()
    )
    return 1 if args.fail_on_quality and failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FixtureError as exc:
        print(f"fixture error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
