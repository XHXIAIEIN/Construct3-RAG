"""Tests for the data-driven collection catalog."""

from __future__ import annotations

import json

import pytest

from src.collection_registry import load_collection_catalog
from src.collections import (
    ALL_COLLECTIONS,
    COLLECTIONS,
    DIR_TO_COLLECTION,
    DOC_COLLECTIONS,
    SUBCATEGORY_MAPPING,
)


def _collection_spec(key: str, name: str, **overrides):
    value = {
        "key": key,
        "name": name,
        "default_top_k": 5,
        "score_threshold": 0.3,
        "default_fanout": True,
        "fusion_weight": 1.0,
    }
    value.update(overrides)
    return value


def test_compatibility_exports_are_derived_from_catalog():
    catalog = load_collection_catalog()

    assert COLLECTIONS == {spec.key: spec.name for spec in catalog.collections}
    assert ALL_COLLECTIONS == [spec.name for spec in catalog.collections]
    assert DOC_COLLECTIONS == [
        spec.name for spec in catalog.collections if spec.document_collection
    ]
    assert DIR_TO_COLLECTION["plugin-reference"] == COLLECTIONS["plugins"]
    assert SUBCATEGORY_MAPPING["plugin-reference"]["array"] == "data-and-storage"
    assert catalog.by_key["terms"].default_top_k == 10
    assert catalog.by_key["terms"].fusion_weight == 0.5
    assert catalog.by_key["examples"].fusion_weight == 0.6
    assert catalog.by_key["addon_sdk"].default_fanout is False


def test_catalog_rejects_duplicate_collection_names(tmp_path):
    path = tmp_path / "collections.json"
    path.write_text(
        json.dumps(
            {
                "collections": [
                    _collection_spec("one", "same"),
                    _collection_spec("two", "same"),
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate collection name"):
        load_collection_catalog(path)


def test_catalog_rejects_unknown_manual_route_target(tmp_path):
    path = tmp_path / "collections.json"
    path.write_text(
        json.dumps(
            {
                "collections": [_collection_spec("guide", "c3_guide")],
                "manual_routes": {"manual": "missing"},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown collection"):
        load_collection_catalog(path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("default_top_k", 0, "default_top_k"),
        ("score_threshold", 1.1, "score_threshold"),
        ("default_fanout", "yes", "default_fanout"),
        ("fusion_weight", 0, "fusion_weight"),
        ("fusion_weight", 1.1, "fusion_weight"),
    ],
)
def test_catalog_rejects_invalid_semantic_policy_ranges(
    tmp_path,
    field,
    value,
    message,
):
    path = tmp_path / "collections.json"
    path.write_text(
        json.dumps(
            {
                "collections": [
                    _collection_spec("guide", "c3_guide", **{field: value})
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        load_collection_catalog(path)


def test_catalog_rejects_addon_sdk_default_fanout(tmp_path):
    path = tmp_path / "collections.json"
    path.write_text(
        json.dumps(
            {
                "collections": [
                    _collection_spec(
                        "addon_sdk",
                        "c3_addon_sdk",
                        default_fanout=True,
                    )
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="addon_sdk.*default fanout"):
        load_collection_catalog(path)
