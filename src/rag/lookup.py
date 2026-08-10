"""Compatibility facade for the canonical deterministic Lookup service.

New code should import from :mod:`src.lookup`. This module retains historical
names and binds repository runtime defaults without owning Lookup behavior.
"""

import jieba

from src.config import SCHEMA_DIR
from src.domain.lookup import ACELocale, LookupIntent, LookupMatch, LookupResponse
from src.locale.resources import ACE_DIRECTED_ALIASES
from src.lookup.examples_index import ExamplesIndex
from src.lookup.formatting import (
    _build_zh_line,
    _format_condition_sig,
    _format_params,
    _match_from_item,
)
from src.lookup.intent import IntentClassifier
from src.lookup.schema_index import SchemaIndex, configure_schema_default
from src.lookup.scripting_index import ScriptingIndex
from src.lookup.service import LookupEngine, configure_lookup_defaults
from src.lookup.term_index import TermIndex

from ._trace import _trace


# Historical evaluator compatibility. Production no longer consumes broad,
# undirected synonym or category expansion.
ACE_SYNONYMS: list[frozenset[str]] = []
ACE_CATEGORY_EXPAND: frozenset[str] = frozenset()


def _current_directed_aliases():
    """Read the facade variable so evaluation overrides remain observable."""
    return ACE_DIRECTED_ALIASES


configure_schema_default(SCHEMA_DIR)
configure_lookup_defaults(
    schema_dir=SCHEMA_DIR,
    trace=_trace,
    directed_aliases_provider=_current_directed_aliases,
)


__all__ = [
    "ACELocale",
    "ACE_CATEGORY_EXPAND",
    "ACE_DIRECTED_ALIASES",
    "ACE_SYNONYMS",
    "ExamplesIndex",
    "IntentClassifier",
    "LookupEngine",
    "LookupIntent",
    "LookupMatch",
    "LookupResponse",
    "SCHEMA_DIR",
    "SchemaIndex",
    "ScriptingIndex",
    "TermIndex",
    "jieba",
]
