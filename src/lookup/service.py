"""Canonical deterministic Lookup service.

The service is independent from HTTP, ``src.rag``, and runtime configuration.
Callers either inject a Schema directory explicitly or let a compatibility
composition root configure one through :func:`configure_lookup_defaults`.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from src.domain.lookup import ACELocale, LookupIntent, LookupMatch, LookupResponse
from src.locale.resources import ACE_DIRECTED_ALIASES
from src.lookup.examples_index import ExamplesIndex
from src.lookup.handlers import LookupHandlers
from src.lookup.intent import IntentClassifier
from src.lookup.schema_index import SchemaIndex
from src.lookup.scripting_index import ScriptingIndex
from src.lookup.term_index import TermIndex


TraceSink = Callable[[str, str], None]
AliasProvider = Callable[[], Iterable[Any]]


def _noop_trace(message: str, phase: str = "info") -> None:
    """Default trace sink when the canonical service is used directly."""


_default_schema_dir: Path | None = None
_default_trace: TraceSink = _noop_trace
_default_alias_provider: AliasProvider = lambda: ACE_DIRECTED_ALIASES


def configure_lookup_defaults(
    *,
    schema_dir: Path | None = None,
    trace: TraceSink | None = None,
    directed_aliases_provider: AliasProvider | None = None,
) -> None:
    """Configure legacy defaults at an outer composition boundary."""
    global _default_schema_dir, _default_trace, _default_alias_provider
    if schema_dir is not None:
        _default_schema_dir = Path(schema_dir)
    if trace is not None:
        _default_trace = trace
    if directed_aliases_provider is not None:
        _default_alias_provider = directed_aliases_provider


class LookupEngine(LookupHandlers):
    """Classify a query and return structured local Schema matches."""

    def __init__(
        self,
        schema_dir: Path | None = None,
        terms: list[dict[str, Any]] | None = None,
        *,
        trace: TraceSink | None = None,
        directed_aliases_provider: AliasProvider | None = None,
    ) -> None:
        resolved_schema_dir = Path(schema_dir) if schema_dir is not None else _default_schema_dir
        if resolved_schema_dir is None:
            raise TypeError(
                "LookupEngine requires schema_dir when used outside the "
                "src.rag.lookup compatibility facade"
            )

        self._trace = trace or _default_trace
        self._directed_aliases_provider = (
            directed_aliases_provider or _default_alias_provider
        )
        self.schema_index = SchemaIndex(resolved_schema_dir)
        self.term_index = TermIndex(terms=terms)
        if not self.term_index.is_loaded:
            self.term_index.load_from_schema(self.schema_index)
        self.examples_index = ExamplesIndex()
        self.scripting_index = ScriptingIndex()
        self.classifier = IntentClassifier(
            schema_index=self.schema_index,
            trace=self._trace,
        )

    def try_lookup(self, query: str) -> LookupResponse | None:
        """Return a structured direct hit, or ``None`` for semantic fallback."""
        started_at = time.time()
        intent = self.classifier.classify(query)
        if intent is not None:
            context, matches = self._execute(intent)
            if matches:
                return LookupResponse(
                    intent=intent,
                    matches=matches,
                    context=context,
                    query_type=f"lookup_{intent.intent_type}",
                    elapsed_ms=(time.time() - started_at) * 1000,
                )

        scripting_results = self.scripting_index.search(query)
        if not scripting_results:
            return None

        matches = [
            LookupMatch(
                ace_id=result["method"],
                ace_type="script_api",
                plugin_id=result["class"],
                collection="script_api",
                en=ACELocale(
                    name=f"{result['class']}.{result['method']}"
                ),
                zh=ACELocale(),
            )
            for result in scripting_results
        ]
        return LookupResponse(
            intent=LookupIntent(
                intent_type="script_api",
                filter_term=query,
                tier=1,
                confidence=0.95,
            ),
            matches=matches,
            context="\n".join(
                f"{result['class']}.{result['method']}"
                for result in scripting_results
            ),
            query_type="lookup_script_api",
            elapsed_ms=(time.time() - started_at) * 1000,
        )
