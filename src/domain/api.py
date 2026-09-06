"""Compatibility exports for HTTP models moved to :mod:`src.interfaces.http`.

New code must import the transport contracts from ``src.interfaces.http``.
This module remains temporarily available for existing integrations.
"""

from src.interfaces.http.models import (
    ACELocaleResult,
    ACEParam,
    DebugInfo,
    DocResult,
    ExampleResult,
    HealthResponse,
    LookupDebug,
    LookupItemResult,
    LookupMatchResult,
    LookupSection,
    PluginInfo,
    SearchRequest,
    SearchResponse,
    SemanticDebug,
    SemanticSection,
    TermResult,
)

__all__ = [
    "ACELocaleResult",
    "ACEParam",
    "DebugInfo",
    "DocResult",
    "ExampleResult",
    "HealthResponse",
    "LookupDebug",
    "LookupItemResult",
    "LookupMatchResult",
    "LookupSection",
    "PluginInfo",
    "SearchRequest",
    "SearchResponse",
    "SemanticDebug",
    "SemanticSection",
    "TermResult",
]
