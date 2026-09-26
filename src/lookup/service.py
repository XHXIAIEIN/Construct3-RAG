"""Canonical deterministic Lookup service.

The service is independent from HTTP and runtime configuration; callers
inject the schema directory.
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


AliasProvider = Callable[[], Iterable[Any]]


class LookupEngine(LookupHandlers):
    """Classify a query and return structured local Schema matches."""

    def __init__(
        self,
        schema_dir: Path,
        terms: list[dict[str, Any]] | None = None,
        *,
        directed_aliases_provider: AliasProvider | None = None,
    ) -> None:
        self._directed_aliases_provider = (
            directed_aliases_provider or (lambda: ACE_DIRECTED_ALIASES)
        )
        self.schema_index = SchemaIndex(Path(schema_dir))
        self.term_index = TermIndex(terms=terms)
        if not self.term_index.is_loaded:
            self.term_index.load_from_schema(self.schema_index)
        self.examples_index = ExamplesIndex()
        self.scripting_index = ScriptingIndex()
        self.classifier = IntentClassifier(schema_index=self.schema_index)

    def try_lookup(self, query: str) -> LookupResponse | None:
        """Return a structured direct hit, or ``None`` when the lookup declines the query."""
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
