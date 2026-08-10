"""Transport-independent search application workflow.

The canonical SOP is explicit and request-local:

``initialize -> validate -> lookup -> semantic -> deduplicate -> respond``

HTTP conversion is delegated to :mod:`src.interfaces.http.presenters`. The
legacy :meth:`SearchWorkflow.run` method remains as a thin compatibility wrapper;
new callers should pass a :class:`SearchCommand` to :meth:`execute`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from src.application.models import (
    LanguageCode,
    SearchCommand,
    SearchExecution,
    SearchOutcome,
    SearchStage,
)
from src.application.ports import LookupProvider, SemanticProvider, SemanticSearchPort
from src.collection_registry import COLLECTION_CATALOG
from src.domain.retrieval import SearchResult
from src.retrieval.identity import lookup_match_stable_id, stable_result_id
from src.retrieval.policy import estimate_query_complexity

if TYPE_CHECKING:
    from src.interfaces.http.models import SearchRequest, SearchResponse

logger = logging.getLogger(__name__)

_TERMS_USEFUL_LANGS = frozenset({"zh", "ja", "ko"})
_LANGUAGES = frozenset({"en", "zh", "ja", "ko"})
_COLLECTION_KEYS = tuple(spec.key for spec in COLLECTION_CATALOG.collections)
_COLLECTION_KEY_SET = frozenset(_COLLECTION_KEYS)


class UnknownCollectionError(ValueError):
    """Raised before execution when a request names an unknown collection."""

    def __init__(self, collection: str):
        self.collection = collection
        super().__init__(
            f"Unknown collection: {collection}. Valid: {list(_COLLECTION_KEYS)}"
        )


class InvalidSearchRequestError(ValueError):
    """Raised when a direct application command violates the search contract."""


def detect_language(query: str) -> LanguageCode:
    """Detect Chinese, Japanese, Korean, or default English text."""
    for char in query:
        codepoint = ord(char)
        if 0x4E00 <= codepoint <= 0x9FFF:
            return "zh"
        if 0x3040 <= codepoint <= 0x30FF:
            return "ja"
        if 0xAC00 <= codepoint <= 0xD7AF or 0x1100 <= codepoint <= 0x11FF:
            return "ko"
    return "en"


class SearchWorkflow:
    """Execute search policy against typed lookup and semantic ports."""

    def __init__(
        self,
        *,
        get_lookup_engine: LookupProvider,
        get_retriever: SemanticProvider,
        lite_mode: bool,
    ) -> None:
        self._get_lookup_engine = get_lookup_engine
        self._get_retriever = get_retriever
        self._lite_mode = lite_mode

    def run(self, request: SearchRequest | SearchCommand) -> SearchResponse:
        """Compatibility entry point accepting the historical HTTP request model."""
        from src.interfaces.http.presenters import (
            present_search_outcome,
            request_to_command,
        )

        command = request if isinstance(request, SearchCommand) else request_to_command(request)
        return present_search_outcome(self.execute(command))

    def execute(self, command: SearchCommand) -> SearchOutcome:
        """Run the canonical SOP and return transport-independent state."""
        started_at = time.perf_counter()
        execution = SearchExecution(
            command=command,
            lang=command.lang or detect_language(command.query),
        )

        self._validate(execution)
        if command.mode in {"auto", "lookup", "list"}:
            self._measure(execution, SearchStage.LOOKUP, self._run_lookup)
        if command.mode in {"auto", "semantic"}:
            self._measure(execution, SearchStage.SEMANTIC, self._run_semantic)

        execution.stage = SearchStage.DEDUPLICATE
        self._deduplicate_lookup_overlap(execution)
        execution.stage = SearchStage.RESPOND
        return SearchOutcome(
            command=command,
            lang=execution.lang,
            elapsed_ms=round((time.perf_counter() - started_at) * 1000, 1),
            lookup_result=execution.lookup_result,
            semantic_results=tuple(execution.semantic_results),
            timing_ms=dict(execution.timing_ms),
            semantic_candidates=execution.semantic_candidates,
        )

    def _measure(
        self,
        execution: SearchExecution,
        stage: SearchStage,
        operation: Callable[[SearchExecution], None],
    ) -> None:
        execution.stage = stage
        started_at = time.perf_counter()
        operation(execution)
        execution.timing_ms[stage.value] = round(
            (time.perf_counter() - started_at) * 1000,
            1,
        )

    @staticmethod
    def _validate(execution: SearchExecution) -> None:
        command = execution.command
        if not command.query.strip():
            raise InvalidSearchRequestError("query must not be blank")
        if command.lang is not None and command.lang not in _LANGUAGES:
            raise InvalidSearchRequestError(f"Unsupported language: {command.lang}")
        if command.mode in {"lookup", "list"} and any(
            (command.plugin, command.collections, command.section_types)
        ):
            raise InvalidSearchRequestError(
                f"mode='{command.mode}' cannot be combined with semantic filters"
            )
        for collection in command.collections:
            if collection not in _COLLECTION_KEY_SET:
                raise UnknownCollectionError(collection)

    def _run_lookup(self, execution: SearchExecution) -> None:
        command = execution.command
        if command.plugin or command.collections or command.section_types:
            return
        try:
            result = self._get_lookup_engine().try_lookup(command.query)
        except Exception as exc:
            logger.warning("Lookup failed: %s", exc)
            return
        if result is None or not result.matches:
            return

        execution.lookup_result = result
        execution.lookup_result_ids = {
            identity
            for match in result.matches
            if (
                identity := lookup_match_stable_id(
                    match,
                    is_behavior=result.intent.is_behavior,
                )
            )
            is not None
        }

    def _run_semantic(self, execution: SearchExecution) -> None:
        if self._lite_mode:
            return
        try:
            retriever = self._get_retriever()
            if not retriever.semantic_backend_available():
                logger.warning("Semantic search unavailable: recent Qdrant health failure")
                return
            results = self._retrieve(execution, retriever)
            execution.semantic_candidates = len(results)
            if execution.command.apply_threshold and results:
                results = retriever.filter_by_adaptive_threshold(results)
            execution.semantic_results = list(results)
        except Exception as exc:
            logger.warning("Semantic search unavailable: %s", exc)

    def _retrieve(
        self,
        execution: SearchExecution,
        retriever: SemanticSearchPort,
    ) -> list[SearchResult]:
        command = execution.command
        if command.plugin:
            return retriever.search_plugin_by_name(
                query=command.query,
                plugin_en=self._canonical_plugin_name(command.plugin),
                section_types=list(command.section_types) or None,
                top_k=command.top_k,
            )
        if command.collections:
            if command.section_types:
                return retriever.search_by_section_types(
                    query=command.query,
                    section_types=list(command.section_types),
                    top_k=command.top_k,
                    collection_keys=list(command.collections),
                )
            return retriever.search_collections(
                query=command.query,
                collection_keys=list(command.collections),
                top_k=command.top_k,
            )
        if command.section_types:
            return retriever.search_by_section_types(
                query=command.query,
                section_types=list(command.section_types),
                top_k=command.top_k,
            )

        preset = estimate_query_complexity(command.query)
        excluded = {"terms"} if execution.lang not in _TERMS_USEFUL_LANGS else None
        return retriever.search_all_with_rerank(
            query=command.query,
            top_k_per_collection=preset.top_k_per_collection,
            final_top_k=max(preset.final_top_k, command.top_k),
            exclude_collections=excluded,
        )

    def _canonical_plugin_name(self, requested_name: str) -> str:
        try:
            schema_index = self._get_lookup_engine().schema_index
            resolved = schema_index.resolve_name(requested_name)
            if not resolved:
                return requested_name
            plugin_id, is_behavior = resolved
            schema = schema_index.get_schema(plugin_id, is_behavior=is_behavior)
            return schema.get("name_en") or requested_name if schema else requested_name
        except Exception as exc:
            logger.warning("Plugin filter canonicalization failed: %s", exc)
            return requested_name

    @staticmethod
    def _deduplicate_lookup_overlap(execution: SearchExecution) -> None:
        if not execution.lookup_result_ids or not execution.semantic_results:
            return
        execution.semantic_results = [
            result
            for result in execution.semantic_results
            if stable_result_id(result) not in execution.lookup_result_ids
        ]


__all__ = [
    "InvalidSearchRequestError",
    "SearchCommand",
    "SearchOutcome",
    "SearchStage",
    "SearchWorkflow",
    "UnknownCollectionError",
    "detect_language",
]
