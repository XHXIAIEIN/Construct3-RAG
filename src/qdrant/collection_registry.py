"""Typed loader for collection names and manual routing data."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class CollectionSpec:
    key: str
    name: str
    document_collection: bool = False
    default_top_k: int = 5
    score_threshold: float = 0.3
    default_fanout: bool = True
    fusion_weight: float = 1.0


@dataclass(frozen=True)
class CollectionCatalog:
    collections: tuple[CollectionSpec, ...]
    manual_routes: Mapping[str, str]
    subcategories: Mapping[str, Mapping[str, str]]

    @property
    def by_key(self) -> dict[str, CollectionSpec]:
        return {spec.key: spec for spec in self.collections}


def _required_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{location} must be a non-empty string")
    return value.strip()


def _required_bool(value: Any, location: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{location} must be a boolean")
    return value


def _required_int(value: Any, location: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{location} must be an integer >= {minimum}")
    return value


def _required_number(
    value: Any,
    location: str,
    *,
    minimum: float,
    maximum: float,
    minimum_inclusive: bool = True,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{location} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{location} must be finite")
    below_minimum = number < minimum if minimum_inclusive else number <= minimum
    if below_minimum or number > maximum:
        opening = "[" if minimum_inclusive else "("
        raise ValueError(
            f"{location} must be in {opening}{minimum}, {maximum}]"
        )
    return number


def load_collection_catalog(path: Path | None = None) -> CollectionCatalog:
    catalog_path = path or Path(__file__).with_name("collections.json")
    try:
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to load collection catalog: {catalog_path}") from exc
    if not isinstance(raw, dict):
        raise ValueError("collection catalog root must be an object")

    raw_specs = raw.get("collections")
    if not isinstance(raw_specs, list) or not raw_specs:
        raise ValueError("collection catalog requires a non-empty collections list")

    specs: list[CollectionSpec] = []
    keys: set[str] = set()
    names: set[str] = set()
    for index, item in enumerate(raw_specs):
        if not isinstance(item, dict):
            raise ValueError(f"collections[{index}] must be an object")
        key = _required_string(item.get("key"), f"collections[{index}].key")
        name = _required_string(item.get("name"), f"collections[{index}].name")
        if key in keys:
            raise ValueError(f"duplicate collection key: {key}")
        if name in names:
            raise ValueError(f"duplicate collection name: {name}")
        keys.add(key)
        names.add(name)
        specs.append(
            CollectionSpec(
                key=key,
                name=name,
                document_collection=_required_bool(
                    item.get("document_collection", False),
                    f"collections[{index}].document_collection",
                ),
                default_top_k=_required_int(
                    item.get("default_top_k"),
                    f"collections[{index}].default_top_k",
                ),
                score_threshold=_required_number(
                    item.get("score_threshold"),
                    f"collections[{index}].score_threshold",
                    minimum=0.0,
                    maximum=1.0,
                ),
                default_fanout=_required_bool(
                    item.get("default_fanout"),
                    f"collections[{index}].default_fanout",
                ),
                fusion_weight=_required_number(
                    item.get("fusion_weight"),
                    f"collections[{index}].fusion_weight",
                    minimum=0.0,
                    maximum=1.0,
                    minimum_inclusive=False,
                ),
            )
        )

    addon_sdk = next((spec for spec in specs if spec.key == "addon_sdk"), None)
    if addon_sdk is not None and addon_sdk.default_fanout:
        raise ValueError("addon_sdk must not be included in default fanout")

    raw_routes = raw.get("manual_routes", {})
    if not isinstance(raw_routes, dict):
        raise ValueError("manual_routes must be an object")
    routes: dict[str, str] = {}
    for directory, collection_key in raw_routes.items():
        directory = _required_string(directory, "manual route directory")
        collection_key = _required_string(collection_key, f"manual_routes.{directory}")
        if collection_key not in keys:
            raise ValueError(
                f"manual route {directory!r} references unknown collection {collection_key!r}"
            )
        routes[directory] = collection_key

    raw_subcategories = raw.get("subcategories", {})
    if not isinstance(raw_subcategories, dict):
        raise ValueError("subcategories must be an object")
    subcategories: dict[str, dict[str, str]] = {}
    for section, mapping in raw_subcategories.items():
        section = _required_string(section, "subcategory section")
        if not isinstance(mapping, dict):
            raise ValueError(f"subcategories.{section} must be an object")
        subcategories[section] = {
            _required_string(item, f"subcategories.{section} item"): _required_string(
                category, f"subcategories.{section}.{item}"
            )
            for item, category in mapping.items()
        }

    return CollectionCatalog(
        collections=tuple(specs),
        manual_routes=routes,
        subcategories=subcategories,
    )


COLLECTION_CATALOG = load_collection_catalog()
