"""Bilingual translation-term index."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from src.lookup.schema_layout import SCHEMA_ACE_TYPES

if TYPE_CHECKING:
    from src.lookup.schema_index import SchemaIndex


logger = logging.getLogger(__name__)


class TermIndex:
    """Index CDN terms, falling back to identities in the local Schema."""

    def __init__(self, terms: list[dict[str, Any]] | None = None):
        self._terms: list[dict[str, str]] = []
        self._loaded = False
        if terms is not None:
            self._ingest(terms)

    @property
    def is_loaded(self) -> bool:
        """Whether a caller explicitly supplied or derived the term source."""
        return self._loaded

    def _ingest(self, terms: list[dict[str, Any]]) -> None:
        """Load terms from ``C3Fetcher.export_terms()`` format."""
        self._loaded = True
        for term in terms:
            zh = str(term.get("zh", "")).strip()
            en = str(term.get("en", "")).strip()
            key = str(term.get("term_key", ""))
            if zh and en:
                self._terms.append({"key": key, "zh": zh, "en": en})
        logger.info("[TermIndex] Loaded %d terms", len(self._terms))

    def load_from_schema(self, schema_index: "SchemaIndex") -> None:
        """Extract en/zh name pairs through the SchemaIndex public iterator."""
        seen_keys = {term["key"] for term in self._terms if term.get("key")}
        before = len(self._terms)

        def add(term_key: str, record: dict[str, Any]) -> None:
            en = record.get("name_en", "")
            zh = record.get("name_zh", "")
            if en and zh and en != zh and term_key not in seen_keys:
                seen_keys.add(term_key)
                self._terms.append({"key": term_key, "zh": zh, "en": en})

        for addon_type, plugin_id, schema in schema_index.iter_schemas():
            add(f"{addon_type}.{plugin_id}.name", schema)
            for ace_type in SCHEMA_ACE_TYPES:
                for item in schema.get(ace_type, []):
                    ace_id = item.get("id", "")
                    add(f"{addon_type}.{plugin_id}.{ace_type}.{ace_id}", item)

        self._loaded = True
        added = len(self._terms) - before
        if added:
            logger.info("[TermIndex] Added %d terms from schema data", added)

    def search(self, query: str, max_results: int = 20) -> list[dict[str, str]]:
        """Return exact value matches first, followed by substring matches."""
        query_lower = query.strip().lower()
        if not query_lower:
            return []

        exact: list[dict[str, str]] = []
        partial: list[dict[str, str]] = []
        for term in self._terms:
            zh_lower = term["zh"].lower()
            en_lower = term["en"].lower()
            if zh_lower == query_lower or en_lower == query_lower:
                exact.append(term)
            elif query_lower in zh_lower or query_lower in en_lower:
                partial.append(term)
        return (exact + partial)[:max_results]
