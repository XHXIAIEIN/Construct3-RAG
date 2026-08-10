"""Strict semantic-gold fixture parsing."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from .stable_ids import StableIdError, normalize_component, stable_id_from_spec


Split = Literal["dev", "heldout"]

_API_ROUTES = frozenset({"auto", "semantic", "lookup", "list"})
_LOOKUP_ROUTES = frozenset({"hit", "miss", "skipped", "bypass"})
_SEMANTIC_ROUTES = frozenset({"required", "optional", "skipped"})

DEFAULT_COLLECTION_KEYS = (
    "guide",
    "interface",
    "project",
    "plugins",
    "behaviors",
    "scripting",
    "ace",
    "effects",
    "terms",
    "examples",
)
KNOWN_COLLECTION_KEYS = frozenset((*DEFAULT_COLLECTION_KEYS, "addon_sdk"))


class FixtureError(ValueError):
    """A semantic fixture is malformed or internally contradictory."""


@dataclass(frozen=True)
class ResultJudgment:
    stable_id: str
    within_top_k: int | None = None
    alternatives: tuple[str, ...] = ()


@dataclass(frozen=True)
class ApiFilters:
    plugin: str | None = None
    collections: tuple[str, ...] = ()
    section_types: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin": self.plugin,
            "collections": list(self.collections),
            "section_types": list(self.section_types),
        }


@dataclass(frozen=True)
class GoldCase:
    id: str
    query: str
    locale: str
    task_family: str
    style_tags: tuple[str, ...]
    parent_query_id: str | None
    expected_api_route: str
    expected_lookup_route: str | None
    expected_semantic_route: str | None
    relevant_results: tuple[ResultJudgment, ...]
    forbidden_results: tuple[ResultJudgment, ...]
    allowed_alternatives: tuple[str, ...]
    graded_relevance: dict[str, float]
    max_rank: int | None
    critical: bool
    schema_version: str
    source_path: str | tuple[str, ...] | None
    rationale: str
    split: Split
    api_filters: ApiFilters
    limited_collections: tuple[str, ...]
    dedup_expectations: dict[str, Any] | tuple[dict[str, Any], ...]
    fixture_line: int

    def to_audit_dict(self) -> dict[str, Any]:
        def judgment(row: ResultJudgment) -> dict[str, Any]:
            return {
                "stable_id": row.stable_id,
                "within_top_k": row.within_top_k,
                "alternatives": list(row.alternatives),
            }

        return {
            "id": self.id,
            "query": self.query,
            "locale": self.locale,
            "task_family": self.task_family,
            "style_tags": list(self.style_tags),
            "parent_query_id": self.parent_query_id,
            "expected_api_route": self.expected_api_route,
            "expected_lookup_route": self.expected_lookup_route,
            "expected_semantic_route": self.expected_semantic_route,
            "relevant_results": [judgment(row) for row in self.relevant_results],
            "forbidden_results": [judgment(row) for row in self.forbidden_results],
            "allowed_alternatives": list(self.allowed_alternatives),
            "graded_relevance": dict(self.graded_relevance),
            "max_rank": self.max_rank,
            "api_filters": self.api_filters.to_dict(),
            "fixture_limited_collections": list(self.limited_collections),
            "dedup_expectations": self.dedup_expectations,
            "split": self.split,
            "critical": self.critical,
            "schema_version": self.schema_version,
            "source_path": list(self.source_path) if isinstance(self.source_path, tuple) else self.source_path,
            "rationale": self.rationale,
        }


_REQUIRED_FIELDS = frozenset(
    {
        "id",
        "query",
        "locale",
        "task_family",
        "style_tags",
        "expected_api_route",
        "relevant_results",
        "forbidden_results",
        "allowed_alternatives",
        "graded_relevance",
        "max_rank",
        "critical",
        "schema_version",
        "source_path",
        "rationale",
        "split",
    }
)
_OPTIONAL_FIELDS = frozenset(
    {
        "parent_query_id",
        "expected_lookup_route",
        "expected_semantic_route",
        "api_filters",
        "limited_collections",
        "dedup_expectations",
        "evidence",
    }
)
_RESULT_SPEC_FIELDS = frozenset(
    {
        "stable_id",
        "result_id",
        "id",
        "within_top_k",
        "max_rank",
        "alternatives",
        "allowed_alternatives",
        "collection",
        "plugin_or_behavior",
        "plugin_type",
        "plugin_id",
        "ace_type",
        "ace_id",
        "path",
        "source",
        "source_path",
        "section",
        "slug",
        "effect_id",
        "term_key",
        "term_path",
    }
)


def _error(path: Path, line: int, message: str) -> FixtureError:
    return FixtureError(f"{path}:{line}: {message}")


def _nonempty_string(value: Any, label: str, path: Path, line: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _error(path, line, f"{label} must be a non-empty string")
    return value.strip()


def _string_list(value: Any, label: str, path: Path, line: int) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise _error(path, line, f"{label} must be an array")
    items: list[str] = []
    for index, item in enumerate(value):
        items.append(_nonempty_string(item, f"{label}[{index}]", path, line))
    if len(set(items)) != len(items):
        raise _error(path, line, f"{label} must not contain duplicates")
    return tuple(items)


def _canonical_stable_id(value: Any, label: str, path: Path, line: int) -> str:
    try:
        if isinstance(value, str):
            stable_id = value.strip().casefold()
        elif isinstance(value, dict):
            unknown = set(value) - _RESULT_SPEC_FIELDS
            if unknown:
                raise _error(
                    path, line, f"{label} has unknown field(s): {', '.join(sorted(unknown))}"
                )
            direct = value.get("stable_id") or value.get("result_id") or value.get("id")
            stable_id = str(direct).strip().casefold() if direct is not None else stable_id_from_spec(value)
        else:
            raise _error(path, line, f"{label} must be a stable-ID string or object")
    except StableIdError as exc:
        raise _error(path, line, f"{label}: {exc}") from exc
    parts = stable_id.split("|")
    if len(parts) < 2 or any(not part for part in parts):
        raise _error(path, line, f"{label} must be a non-empty pipe-delimited stable ID")
    return stable_id


def _rank_limit(spec: dict[str, Any], label: str, path: Path, line: int) -> int | None:
    value = spec.get("within_top_k", spec.get("max_rank"))
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _error(path, line, f"{label}.within_top_k must be a positive integer")
    return value


def _result_judgment(value: Any, label: str, path: Path, line: int) -> ResultJudgment:
    stable_id = _canonical_stable_id(value, label, path, line)
    if not isinstance(value, dict):
        return ResultJudgment(stable_id=stable_id)
    alternatives_raw = value.get("alternatives", value.get("allowed_alternatives", []))
    if not isinstance(alternatives_raw, list):
        raise _error(path, line, f"{label}.alternatives must be an array")
    alternatives = tuple(
        _canonical_stable_id(item, f"{label}.alternatives[{index}]", path, line)
        for index, item in enumerate(alternatives_raw)
    )
    if len(set(alternatives)) != len(alternatives):
        raise _error(path, line, f"{label}.alternatives must not contain duplicates")
    return ResultJudgment(stable_id, _rank_limit(value, label, path, line), alternatives)


def _judgment_list(value: Any, label: str, path: Path, line: int) -> tuple[ResultJudgment, ...]:
    if not isinstance(value, list):
        raise _error(path, line, f"{label} must be an array")
    rows = tuple(
        _result_judgment(item, f"{label}[{index}]", path, line)
        for index, item in enumerate(value)
    )
    ids = [row.stable_id for row in rows]
    if len(set(ids)) != len(ids):
        raise _error(path, line, f"{label} contains duplicate stable IDs")
    return rows


def _allowed_alternatives(
    value: Any,
    relevant: tuple[ResultJudgment, ...],
    path: Path,
    line: int,
) -> tuple[tuple[ResultJudgment, ...], tuple[str, ...]]:
    if not isinstance(value, list):
        raise _error(path, line, "allowed_alternatives must be an array")
    updated = {row.stable_id: row for row in relevant}
    independent: list[str] = []
    for index, item in enumerate(value):
        label = f"allowed_alternatives[{index}]"
        if isinstance(item, dict) and any(key in item for key in ("for", "replaces", "must_result")):
            allowed = {"for", "replaces", "must_result", "alternatives", "results"}
            unknown = set(item) - allowed
            if unknown:
                raise _error(path, line, f"{label} has unknown field(s): {', '.join(sorted(unknown))}")
            target_raw = item.get("for") or item.get("replaces") or item.get("must_result")
            alternatives_raw = item.get("alternatives", item.get("results"))
            if not isinstance(alternatives_raw, list) or not alternatives_raw:
                raise _error(path, line, f"{label}.alternatives must be a non-empty array")
            target = _canonical_stable_id(target_raw, f"{label}.for", path, line)
            if target not in updated:
                raise _error(path, line, f"{label} targets unknown relevant result {target}")
            additions = tuple(
                _canonical_stable_id(candidate, f"{label}.alternatives[{alt_index}]", path, line)
                for alt_index, candidate in enumerate(alternatives_raw)
            )
            row = updated[target]
            merged = (*row.alternatives, *additions)
            if len(set(merged)) != len(merged):
                raise _error(path, line, f"{label} duplicates an alternative for {target}")
            updated[target] = replace(row, alternatives=merged)
        else:
            independent.append(_canonical_stable_id(item, label, path, line))
    if len(set(independent)) != len(independent):
        raise _error(path, line, "allowed_alternatives contains duplicate stable IDs")
    return tuple(updated[row.stable_id] for row in relevant), tuple(independent)


def _graded_relevance(value: Any, path: Path, line: int) -> dict[str, float]:
    result: dict[str, float] = {}
    if isinstance(value, dict):
        items = value.items()
    elif isinstance(value, list):
        parsed: list[tuple[Any, Any]] = []
        for index, row in enumerate(value):
            if not isinstance(row, dict) or set(row) - {"stable_id", "result_id", "id", "grade", "relevance"}:
                raise _error(path, line, f"graded_relevance[{index}] must contain only an ID and grade")
            raw_id = row.get("stable_id") or row.get("result_id") or row.get("id")
            parsed.append((raw_id, row.get("grade", row.get("relevance"))))
        items = parsed
    else:
        raise _error(path, line, "graded_relevance must be an object or array")
    for raw_id, raw_grade in items:
        stable_id = _canonical_stable_id(raw_id, "graded_relevance key", path, line)
        if isinstance(raw_grade, bool) or not isinstance(raw_grade, (int, float)) or raw_grade < 0:
            raise _error(path, line, f"graded_relevance[{stable_id}] must be a non-negative number")
        if stable_id in result:
            raise _error(path, line, f"graded_relevance duplicates {stable_id}")
        result[stable_id] = float(raw_grade)
    return result


def _api_filters(value: Any, path: Path, line: int) -> ApiFilters:
    if value is None:
        return ApiFilters()
    if not isinstance(value, dict):
        raise _error(path, line, "api_filters must be an object")
    unknown = set(value) - {"plugin", "collections", "section_types"}
    if unknown:
        raise _error(path, line, f"api_filters has unknown field(s): {', '.join(sorted(unknown))}")
    plugin_raw = value.get("plugin")
    plugin = None if plugin_raw is None else _nonempty_string(plugin_raw, "api_filters.plugin", path, line)
    collections = _string_list(value.get("collections", []), "api_filters.collections", path, line)
    collections = tuple(normalize_component(item) for item in collections)
    unknown_collections = set(collections) - KNOWN_COLLECTION_KEYS
    if unknown_collections:
        raise _error(path, line, f"api_filters.collections has unknown values: {', '.join(sorted(unknown_collections))}")
    section_types = _string_list(value.get("section_types", []), "api_filters.section_types", path, line)
    return ApiFilters(plugin, collections, tuple(normalize_component(item) for item in section_types))


def _source_path(value: Any, path: Path, line: int) -> str | tuple[str, ...] | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, list):
        return _string_list(value, "source_path", path, line)
    raise _error(path, line, "source_path must be null, a non-empty string, or an array of strings")


def _optional_string(value: Any, label: str, path: Path, line: int) -> str | None:
    return None if value is None else _nonempty_string(value, label, path, line)


def _dedup_expectations(
    value: Any, path: Path, line: int
) -> dict[str, Any] | tuple[dict[str, Any], ...]:
    """Validate exact-ID lookup/semantic dedup adjudication metadata.

    Both the compact object form and the row-oriented array form are accepted.
    The latter is useful when one query contains several independently judged
    remove/preserve pairs.  Stable-ID-looking fields are canonicalized here so
    evaluation never compares fixture spelling to runtime spelling.
    """

    if value is None:
        return {}
    if not isinstance(value, (dict, list)):
        raise _error(path, line, "dedup_expectations must be an object or array")

    def validate(item: Any, label: str) -> Any:
        if item is None or isinstance(item, (str, int, float, bool)):
            return item
        if isinstance(item, list):
            values = [validate(child, f"{label}[{index}]") for index, child in enumerate(item)]
            leaf = label.rsplit(".", 1)[-1]
            if leaf.endswith("_ids"):
                if not all(isinstance(child, str) for child in values):
                    raise _error(path, line, f"{label} must contain stable-ID strings")
                canonical = [
                    _canonical_stable_id(child, f"{label}[{index}]", path, line)
                    for index, child in enumerate(values)
                ]
                if len(set(canonical)) != len(canonical):
                    raise _error(path, line, f"{label} must not contain duplicates")
                return canonical
            return values
        if isinstance(item, dict):
            normalized: dict[str, Any] = {}
            for key, child in item.items():
                normalized_key = _nonempty_string(key, f"{label} key", path, line)
                child_label = f"{label}.{normalized_key}"
                if normalized_key in {
                    "id",
                    "stable_id",
                    "result_id",
                    "remove_id",
                    "preserve_id",
                    "lookup_id",
                    "semantic_id",
                }:
                    normalized[normalized_key] = _canonical_stable_id(
                        child, child_label, path, line
                    )
                else:
                    normalized[normalized_key] = validate(child, child_label)
            return normalized
        raise _error(path, line, f"{label} must contain only JSON values")

    validated = validate(value, "dedup_expectations")
    if isinstance(validated, list):
        if not all(isinstance(row, dict) for row in validated):
            raise _error(path, line, "dedup_expectations array rows must be objects")
        return tuple(validated)
    return validated


def _parse_case(raw: Any, path: Path, line: int) -> GoldCase:
    if not isinstance(raw, dict):
        raise _error(path, line, "each JSONL row must be an object")
    case = dict(raw)
    evidence = case.get("evidence")
    if evidence is not None:
        if not isinstance(evidence, dict) or set(evidence) - {"schema_version", "source_path", "rationale"}:
            raise _error(path, line, "evidence may contain only schema_version, source_path, and rationale")
        for field in ("schema_version", "source_path", "rationale"):
            if field not in case and field in evidence:
                case[field] = evidence[field]
    unknown = set(case) - _REQUIRED_FIELDS - _OPTIONAL_FIELDS
    if unknown:
        raise _error(path, line, f"unknown field(s): {', '.join(sorted(unknown))}")
    missing = _REQUIRED_FIELDS - set(case)
    if missing:
        raise _error(path, line, f"missing required field(s): {', '.join(sorted(missing))}")

    relevant = _judgment_list(case["relevant_results"], "relevant_results", path, line)
    forbidden = _judgment_list(case["forbidden_results"], "forbidden_results", path, line)
    relevant, alternatives = _allowed_alternatives(
        case["allowed_alternatives"], relevant, path, line
    )
    grades = _graded_relevance(case["graded_relevance"], path, line)
    relevant_ids = {row.stable_id for row in relevant}
    substitute_ids = {item for row in relevant for item in row.alternatives}
    alternative_ids = set(alternatives)
    judged_positive = relevant_ids | substitute_ids | alternative_ids
    unknown_grades = set(grades) - judged_positive
    if unknown_grades:
        raise _error(path, line, f"graded_relevance references unjudged IDs: {', '.join(sorted(unknown_grades))}")
    if not relevant and (alternative_ids or grades):
        raise _error(
            path,
            line,
            "negative-only cases cannot define allowed alternatives or graded relevance",
        )
    forbidden_ids = {row.stable_id for row in forbidden}
    overlap = forbidden_ids & judged_positive
    if overlap:
        raise _error(path, line, f"results cannot be both positive/allowed and forbidden: {', '.join(sorted(overlap))}")

    max_rank = case["max_rank"]
    if max_rank is not None and (
        isinstance(max_rank, bool) or not isinstance(max_rank, int) or max_rank < 1
    ):
        raise _error(path, line, "max_rank must be null or a positive integer")
    if relevant and max_rank is None:
        raise _error(path, line, "max_rank must be a positive integer when relevant_results is non-empty")
    if not relevant and max_rank is not None:
        raise _error(path, line, "negative-only cases must set max_rank to null")
    if not isinstance(case["critical"], bool):
        raise _error(path, line, "critical must be a boolean")
    split = case["split"]
    if split not in {"dev", "heldout"}:
        raise _error(path, line, "split must be dev or heldout")
    parent = case.get("parent_query_id")
    if parent is not None:
        parent = _nonempty_string(parent, "parent_query_id", path, line)
    limited = _string_list(case.get("limited_collections", []), "limited_collections", path, line)
    limited = tuple(normalize_component(item) for item in limited)
    unknown_limited = set(limited) - KNOWN_COLLECTION_KEYS
    if unknown_limited:
        raise _error(path, line, f"limited_collections has unknown values: {', '.join(sorted(unknown_limited))}")

    expected_api_route = _nonempty_string(
        case["expected_api_route"], "expected_api_route", path, line
    ).casefold()
    if expected_api_route not in _API_ROUTES:
        raise _error(
            path,
            line,
            f"expected_api_route must be one of {', '.join(sorted(_API_ROUTES))}",
        )
    expected_lookup_route = _optional_string(
        case.get("expected_lookup_route"), "expected_lookup_route", path, line
    )
    if expected_lookup_route is not None:
        expected_lookup_route = expected_lookup_route.casefold()
        if expected_lookup_route not in _LOOKUP_ROUTES:
            raise _error(
                path,
                line,
                f"expected_lookup_route must be one of {', '.join(sorted(_LOOKUP_ROUTES))}",
            )
    expected_semantic_route = _optional_string(
        case.get("expected_semantic_route"), "expected_semantic_route", path, line
    )
    if expected_semantic_route is not None:
        expected_semantic_route = expected_semantic_route.casefold()
        if expected_semantic_route not in _SEMANTIC_ROUTES:
            raise _error(
                path,
                line,
                f"expected_semantic_route must be one of {', '.join(sorted(_SEMANTIC_ROUTES))}",
            )

    return GoldCase(
        id=_nonempty_string(case["id"], "id", path, line),
        query=_nonempty_string(case["query"], "query", path, line),
        locale=_nonempty_string(case["locale"], "locale", path, line),
        task_family=_nonempty_string(case["task_family"], "task_family", path, line),
        style_tags=_string_list(case["style_tags"], "style_tags", path, line),
        parent_query_id=parent,
        expected_api_route=expected_api_route,
        expected_lookup_route=expected_lookup_route,
        expected_semantic_route=expected_semantic_route,
        relevant_results=relevant,
        forbidden_results=forbidden,
        allowed_alternatives=alternatives,
        graded_relevance=grades,
        max_rank=max_rank,
        critical=case["critical"],
        schema_version=_nonempty_string(case["schema_version"], "schema_version", path, line),
        source_path=_source_path(case["source_path"], path, line),
        rationale=_nonempty_string(case["rationale"], "rationale", path, line),
        split=split,
        api_filters=_api_filters(case.get("api_filters"), path, line),
        limited_collections=limited,
        dedup_expectations=_dedup_expectations(case.get("dedup_expectations"), path, line),
        fixture_line=line,
    )


def load_fixture(path: Path, split: str = "all") -> list[GoldCase]:
    """Load, strictly validate, and optionally select a frozen fixture split."""

    if split not in {"dev", "heldout", "all"}:
        raise FixtureError(f"split must be dev, heldout, or all; got {split!r}")
    if not path.is_file():
        raise FixtureError(f"semantic gold fixture does not exist: {path}")
    cases: list[GoldCase] = []
    seen: set[str] = set()
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise _error(path, line_no, f"invalid JSON: {exc.msg}") from exc
        case = _parse_case(raw, path, line_no)
        if case.id in seen:
            raise _error(path, line_no, f"duplicate id: {case.id}")
        seen.add(case.id)
        cases.append(case)
    if not cases:
        raise FixtureError(f"semantic gold fixture is empty: {path}")
    selected = cases if split == "all" else [case for case in cases if case.split == split]
    if not selected:
        raise FixtureError(f"semantic gold fixture has no rows for split={split}: {path}")
    return selected
