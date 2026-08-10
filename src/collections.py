"""Compatibility exports derived from the typed collection catalog."""

from __future__ import annotations

from src.collection_registry import COLLECTION_CATALOG, CollectionCatalog, CollectionSpec

__all__ = [
    "COLLECTION_CATALOG",
    "CollectionCatalog",
    "CollectionSpec",
    "COLLECTIONS",
    "DOC_COLLECTIONS",
    "ALL_COLLECTIONS",
    "DIR_TO_COLLECTION",
    "SUBCATEGORY_MAPPING",
]


COLLECTIONS = {
    spec.key: spec.name
    for spec in COLLECTION_CATALOG.collections
}

DOC_COLLECTIONS = [
    spec.name
    for spec in COLLECTION_CATALOG.collections
    if spec.document_collection
]

ALL_COLLECTIONS = [spec.name for spec in COLLECTION_CATALOG.collections]

DIR_TO_COLLECTION = {
    directory: COLLECTIONS[collection_key]
    for directory, collection_key in COLLECTION_CATALOG.manual_routes.items()
}

SUBCATEGORY_MAPPING = {
    section: dict(mapping)
    for section, mapping in COLLECTION_CATALOG.subcategories.items()
}
