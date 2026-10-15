"""Records of a deterministic lookup: the intent, the matches and the response.

Schema loading, query parsing and formatting belong in :mod:`src.lookup`, and
transport in :mod:`src.interfaces.http`.
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
    """Text of one ACE in one language."""

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
    """Result of one lookup: the intent and its matches."""

    intent: LookupIntent
    matches: list[LookupMatch] = field(default_factory=list)
    context: str = ""
    query_type: str = ""
    elapsed_ms: float = 0.0
