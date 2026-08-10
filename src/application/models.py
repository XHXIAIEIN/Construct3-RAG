"""Transport-independent state carried through the search workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from src.domain.lookup import LookupResponse
from src.domain.retrieval import SearchResult

LanguageCode = Literal["en", "zh", "ja", "ko"]
SearchMode = Literal["auto", "lookup", "semantic", "list"]
SearchScope = Literal["eventsheet", "scripts", "js", "ts", "all"]


class SearchStage(str, Enum):
    INITIALIZE = "initialize"
    LOOKUP = "lookup"
    SEMANTIC = "semantic"
    DEDUPLICATE = "deduplicate"
    RESPOND = "respond"


@dataclass(frozen=True)
class SearchCommand:
    query: str
    top_k: int = 10
    lang: LanguageCode | None = None
    collections: tuple[str, ...] = ()
    plugin: str | None = None
    section_types: tuple[str, ...] = ()
    debug: bool = False
    context: bool = False
    apply_threshold: bool = True
    mode: SearchMode = "auto"
    scope: SearchScope = "eventsheet"


@dataclass
class SearchExecution:
    """Mutable request-local state; it contains no HTTP/Pydantic models."""

    command: SearchCommand
    lang: LanguageCode
    stage: SearchStage = SearchStage.INITIALIZE
    lookup_result: LookupResponse | None = None
    semantic_results: list[SearchResult] = field(default_factory=list)
    lookup_result_ids: set[str] = field(default_factory=set)
    timing_ms: dict[str, float] = field(default_factory=dict)
    semantic_candidates: int = 0


@dataclass(frozen=True)
class SearchOutcome:
    command: SearchCommand
    lang: LanguageCode
    elapsed_ms: float
    lookup_result: LookupResponse | None
    semantic_results: tuple[SearchResult, ...]
    timing_ms: dict[str, float]
    semantic_candidates: int

__all__ = [
    "LanguageCode",
    "SearchCommand",
    "SearchExecution",
    "SearchMode",
    "SearchOutcome",
    "SearchScope",
    "SearchStage",
]
