"""Compatibility exports for the split deterministic lookup indexes."""

from .examples_index import ExamplesIndex
from .schema_index import SchemaIndex
from .scripting_index import ScriptingIndex
from .term_index import TermIndex

__all__ = [
    "ExamplesIndex",
    "SchemaIndex",
    "ScriptingIndex",
    "TermIndex",
]
