"""Structural ports implemented by lookup and semantic runtime adapters."""
from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from src.domain.lookup import LookupResponse
from src.domain.retrieval import SearchResult


class SchemaResolverPort(Protocol):
    def resolve_name(self, name: str) -> tuple[str, bool] | None: ...

    def get_schema(self, item_id: str, is_behavior: bool = False) -> dict | None: ...


class LookupPort(Protocol):
    schema_index: SchemaResolverPort

    def try_lookup(self, query: str) -> LookupResponse | None: ...


class SemanticSearchPort(Protocol):
    def semantic_backend_available(self, retry_after_seconds: float = 2.0) -> bool: ...

    def search_plugin_by_name(
        self,
        query: str,
        plugin_en: str,
        section_types: list[str] | None = None,
        top_k: int = 5,
        score_threshold: float = 0.3,
    ) -> list[SearchResult]: ...

    def search_by_section_types(
        self,
        query: str,
        section_types: list[str],
        top_k: int = 10,
        collection_keys: list[str] | None = None,
    ) -> list[SearchResult]: ...

    def search_collections(
        self,
        query: str,
        collection_keys: list[str],
        top_k: int = 10,
    ) -> list[SearchResult]: ...

    def search_all_with_rerank(
        self,
        query: str,
        top_k_per_collection: int = 5,
        final_top_k: int = 10,
        exclude_collections: set[str] | None = None,
    ) -> list[SearchResult]: ...

    def filter_by_adaptive_threshold(
        self,
        results: list[SearchResult],
        min_results: int = 2,
    ) -> list[SearchResult]: ...


LookupProvider = Callable[[], LookupPort]
SemanticProvider = Callable[[], SemanticSearchPort]

__all__ = [
    "LookupPort",
    "LookupProvider",
    "SchemaResolverPort",
    "SemanticProvider",
    "SemanticSearchPort",
]
