"""Transport-independent state carried through the search workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from src.domain.lookup import LookupResponse

# Also the values POST /search accepts: a change here is a public API change
LanguageCode = Literal["en", "zh", "ja", "ko"]
SearchMode = Literal["auto", "lookup", "list"]
SearchScope = Literal["eventsheet", "scripts", "js", "ts", "all"]


class SearchStage(str, Enum):
    INITIALIZE = "initialize"
    LOOKUP = "lookup"
    RESPOND = "respond"


@dataclass(frozen=True)
class SearchCommand:
    query: str
    lang: LanguageCode | None = None
    debug: bool = False
    context: bool = False
    mode: SearchMode = "auto"
    scope: SearchScope = "eventsheet"


@dataclass
class SearchExecution:
    """State of one search while it runs; it holds no HTTP or Pydantic models."""

    command: SearchCommand
    lang: LanguageCode
    stage: SearchStage = SearchStage.INITIALIZE
    lookup_result: LookupResponse | None = None
    timing_ms: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchOutcome:
    command: SearchCommand
    lang: LanguageCode
    elapsed_ms: float
    lookup_result: LookupResponse | None
    timing_ms: dict[str, float]


__all__ = [
    "LanguageCode",
    "SearchCommand",
    "SearchExecution",
    "SearchMode",
    "SearchOutcome",
    "SearchScope",
    "SearchStage",
]
