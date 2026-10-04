"""Transport-independent search application workflow.

The canonical SOP is explicit and request-local:

``initialize -> lookup -> respond``

Validation runs inside ``initialize``; it is not a stage of its own.

HTTP conversion is delegated to :mod:`src.interfaces.http.presenters`. The
legacy :meth:`SearchWorkflow.run` method remains as a thin compatibility wrapper;
new callers should pass a :class:`SearchCommand` to :meth:`execute`.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, get_args

from src.application.models import (
    LanguageCode,
    SearchCommand,
    SearchExecution,
    SearchOutcome,
    SearchStage,
)
from src.application.ports import LookupProvider

if TYPE_CHECKING:
    from src.interfaces.http.models import SearchRequest, SearchResponse

logger = logging.getLogger(__name__)

_LANGUAGES = frozenset(get_args(LanguageCode))


def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 1)


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
    """Execute search policy against the typed lookup port."""

    def __init__(self, *, get_lookup_engine: LookupProvider) -> None:
        self._get_lookup_engine = get_lookup_engine

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

        execution.stage = SearchStage.LOOKUP
        lookup_started_at = time.perf_counter()
        self._run_lookup(execution)
        execution.timing_ms[SearchStage.LOOKUP.value] = _elapsed_ms(lookup_started_at)

        execution.stage = SearchStage.RESPOND
        return SearchOutcome(
            command=command,
            lang=execution.lang,
            elapsed_ms=_elapsed_ms(started_at),
            lookup_result=execution.lookup_result,
            timing_ms=dict(execution.timing_ms),
        )

    @staticmethod
    def _validate(execution: SearchExecution) -> None:
        command = execution.command
        if not command.query.strip():
            raise InvalidSearchRequestError("query must not be blank")
        if command.lang is not None and command.lang not in _LANGUAGES:
            raise InvalidSearchRequestError(f"Unsupported language: {command.lang}")

    def _run_lookup(self, execution: SearchExecution) -> None:
        try:
            result = self._get_lookup_engine().try_lookup(execution.command.query)
        except Exception as exc:
            logger.warning("Lookup failed: %s", exc)
            return
        if result is not None and result.matches:
            execution.lookup_result = result


__all__ = [
    "InvalidSearchRequestError",
    "SearchWorkflow",
    "detect_language",
]
