"""Transport-independent search workflow.

:meth:`SearchWorkflow.execute` runs one search command through three stages:

``initialize -> lookup -> respond``

Validation runs inside ``initialize``; it is not a stage of its own.

:mod:`src.interfaces.http.presenters` converts to and from HTTP.
:meth:`SearchWorkflow.run` is the compatibility wrapper for callers that hold
an HTTP ``SearchRequest``; other callers pass a :class:`SearchCommand` to
:meth:`SearchWorkflow.execute`.
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
    """A search command with a blank query or an unsupported language."""


def detect_language(query: str) -> LanguageCode:
    """Language of the query's first Chinese, Japanese or Korean character, else English."""
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
    """Run search commands against the lookup port."""

    def __init__(self, *, get_lookup_engine: LookupProvider) -> None:
        self._get_lookup_engine = get_lookup_engine

    def run(self, request: SearchRequest) -> SearchResponse:
        """Run an HTTP request through :meth:`execute` and present the outcome."""
        from src.interfaces.http.presenters import (
            present_search_outcome,
            request_to_command,
        )

        return present_search_outcome(self.execute(request_to_command(request)))

    def execute(self, command: SearchCommand) -> SearchOutcome:
        """Validate the command, run the lookup and return the outcome."""
        started_at = time.perf_counter()
        execution = SearchExecution(
            command=command,
            lang=command.lang or detect_language(command.query),
        )

        self._validate(command)

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
    def _validate(command: SearchCommand) -> None:
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
