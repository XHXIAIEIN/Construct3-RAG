"""Pure data contracts for deterministic lookup.

This module intentionally contains no schema loading, query parsing, formatting,
or transport behavior.  Those responsibilities belong to the lookup engine and
application workflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LookupIntent:
    """Classified intent from a user query."""

    intent_type: str
    plugin_id: str = ""
    ace_type: str = ""
    ace_name: str = ""
    term: str = ""
    filter_term: str = ""
    tier: int = 0
    is_behavior: bool = False
    matched_tags: list[str] = field(default_factory=list)
    confidence: float = 0.0
    entity_kind: str = ""


@dataclass
class ACELocale:
    """Localized text for one ACE entry."""

    name: str = ""
    desc: str = ""
    display: str = ""


@dataclass
class LookupMatch:
    """One structured lookup match."""

    ace_id: str
    ace_type: str
    plugin_id: str
    collection: str = ""
    en: ACELocale = field(default_factory=ACELocale)
    zh: ACELocale = field(default_factory=ACELocale)
    plugin_name_zh: str = ""
    script_name: str = ""
    category: str = ""
    relevance: int = 0
    params: list[dict[str, Any]] = field(default_factory=list)
    is_trigger: bool = False
    is_async: bool = False
    return_type: str = ""


@dataclass
class LookupResponse:
    """Result returned by the deterministic lookup service."""

    intent: LookupIntent
    matches: list[LookupMatch] = field(default_factory=list)
    context: str = ""
    query_type: str = ""
    elapsed_ms: float = 0.0
