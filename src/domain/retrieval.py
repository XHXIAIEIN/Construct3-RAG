"""Pure data contracts for semantic retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


QueryComplexity = Literal["simple", "moderate", "complex"]
RetrievalStatus = Literal["healthy", "degraded", "unavailable"]


@dataclass(frozen=True)
class RetrievalPreset:
    """Retrieval parameters derived from query complexity."""

    complexity: QueryComplexity
    top_k_per_collection: int
    final_top_k: int


@dataclass
class SearchResult:
    """Transport-independent result returned by a retrieval backend."""

    text: str
    score: float
    source: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class RetrievalHealth:
    """Typed health snapshot returned by a semantic retrieval backend."""

    status: RetrievalStatus
    qdrant_connected: bool
    message: str
    collections: dict[str, int] = field(default_factory=dict)
    total_documents: int = 0
    missing_collections: tuple[str, ...] = ()
