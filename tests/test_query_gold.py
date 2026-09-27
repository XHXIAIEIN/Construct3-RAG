"""Direct Lookup against the gold set in ``fixtures/query_gold.jsonl``.

Each case says whether the service answers (``hit``) or declines (``miss``),
and for an answer which intent, entity and results it must give. A result is
named by its stable key: collection, plugin id, ACE type, ACE id.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.domain.lookup import LookupIntent, LookupResponse
from src.lookup import LookupEngine
from src.settings import load_settings


GOLD = Path(__file__).with_name("fixtures") / "query_gold.jsonl"
KEY = ("collection", "plugin_id", "ace_type", "ace_id")
DEFAULT_WITHIN = 5
FIELDS = {
    "id", "query", "locale", "task_family", "expected_lookup", "expected_intent",
    "expected_entity", "expected_ace_types", "must_results", "forbidden_results",
    "min_results", "max_results", "source_path", "rationale",
}
SINGULAR = {"conditions": "condition", "actions": "action", "expressions": "expression", "properties": "property"}


def _cases() -> list[dict[str, Any]]:
    return [json.loads(line) for line in GOLD.read_text(encoding="utf-8").splitlines() if line.strip()]


CASES = _cases()


@pytest.fixture(scope="module")
def engine() -> LookupEngine:
    return LookupEngine(schema_dir=load_settings().schema.directory)


def _key(spec: dict[str, Any]) -> tuple[str, ...]:
    return tuple(spec[field] for field in KEY)


def _entity(engine: LookupEngine, intent: LookupIntent | None, response: LookupResponse | None) -> dict[str, str] | None:
    if intent is not None and intent.plugin_id:
        kind = intent.entity_kind or ("behavior" if intent.is_behavior else "plugin")
        return {"kind": kind, "id": intent.plugin_id}
    if intent is not None:
        addons = [tag for tag in intent.matched_tags if tag.startswith(("plugin-", "behavior-"))]
        if len(addons) == 1:
            kind, item_id = addons[0].split("-", 1)
            return {"kind": kind, "id": item_id}
    if response is not None and response.intent.intent_type == "script_api":
        return {"kind": "script_class", "id": response.matches[0].plugin_id}
    return None


def _same_entity(engine: LookupEngine, expected: dict[str, str] | None, actual: dict[str, str] | None) -> bool:
    if expected is None or actual is None:
        return expected == actual
    if expected["kind"] != actual["kind"]:
        return False
    if expected["kind"] in {"plugin", "behavior"}:
        # An example tag names the addon by its original id, "FileSystem".
        return engine.schema_index.resolve_name(expected["id"]) == engine.schema_index.resolve_name(actual["id"])
    return expected["id"] == actual["id"]


def test_every_case_uses_only_the_documented_fields_and_a_unique_id():
    ids = [case["id"] for case in CASES]
    assert len(ids) == len(set(ids))
    for case in CASES:
        assert set(case) <= FIELDS, case["id"]
        assert case["expected_lookup"] in {"hit", "miss"}, case["id"]
        assert case["rationale"].strip(), case["id"]
        if case["expected_lookup"] == "hit":
            assert case.get("expected_intent") and case.get("must_results"), case["id"]


def test_every_source_path_exists():
    root = GOLD.parents[2]
    missing = [
        (case["id"], path)
        for case in CASES
        for path in ([case["source_path"]] if isinstance(case.get("source_path"), str) else case.get("source_path", []))
        if not (root / path).exists()
    ]
    assert missing == []


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_gold_case(engine: LookupEngine, case: dict[str, Any]) -> None:
    query = case["query"]
    response = engine.try_lookup(query)
    classified = engine.classifier.classify(query)
    keys = [(m.collection, m.plugin_id, m.ace_type, m.ace_id) for m in response.matches] if response else []
    ranks: dict[tuple[str, ...], int] = {}
    for rank, key in enumerate(keys, 1):
        ranks.setdefault(key, rank)
    shown = f"{query!r} returned {keys[:8]}"

    if case["expected_lookup"] == "miss":
        assert response is None, shown
    else:
        assert response is not None and keys, f"{query!r} was declined"
        assert response.intent.intent_type == case["expected_intent"]

    if "expected_entity" in case:
        actual = _entity(engine, classified or (response.intent if response else None), response)
        assert _same_entity(engine, case["expected_entity"], actual), f"entity {actual}"

    if case.get("expected_ace_types"):
        expected = {SINGULAR.get(t, t) for t in case["expected_ace_types"]}
        declared = response.intent.ace_type
        actual_types = {SINGULAR.get(t, t) for t in declared.split(",") if t} if declared else {k[2] for k in keys}
        assert actual_types == expected

    for spec in case.get("must_results", []):
        options = [_key(spec), *(_key(alt) for alt in spec.get("alternatives", []))]
        best = min((ranks[o] for o in options if o in ranks), default=None)
        within = spec.get("within_top_k", DEFAULT_WITHIN)
        assert best is not None and best <= within, f"{_key(spec)} not within {within}: {shown}"

    for spec in case.get("forbidden_results", []):
        rank = ranks.get(_key(spec))
        within = spec.get("within_top_k", DEFAULT_WITHIN)
        assert rank is None or rank > within, f"{_key(spec)} at {rank}: {shown}"

    if "min_results" in case:
        assert len(keys) >= case["min_results"], shown
    if "max_results" in case:
        assert len(keys) <= case["max_results"], shown
