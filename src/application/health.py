"""Transport-independent health use case for the optional search service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from src.domain.retrieval import RetrievalHealth
from src.schema_layout import schema_is_complete

class RetrievalHealthPort(Protocol):
    def get_health(self) -> RetrievalHealth: ...


@dataclass(frozen=True)
class HealthOutcome:
    status: str
    qdrant: bool
    schema_ready: bool
    embedding_model: str
    message: str
    collections: dict[str, int] = field(default_factory=dict)
    total_documents: int = 0
    missing_collections: tuple[str, ...] = ()


def build_health_outcome(
    *,
    lite_mode: bool,
    schema_dir: Path,
    embedding_model: str,
    get_retriever: Callable[[], RetrievalHealthPort],
) -> HealthOutcome:
    """Aggregate local schema readiness and typed retrieval backend health."""
    schema_ready = schema_is_complete(schema_dir)
    if lite_mode:
        return HealthOutcome(
            status="lite",
            qdrant=False,
            schema_ready=schema_ready,
            embedding_model="",
            message=(
                "Lite mode: lookup only"
                if schema_ready
                else "Lite mode: schema data missing; run python scripts/init.py"
            ),
        )

    try:
        detail = get_retriever().get_health()
    except Exception:
        return HealthOutcome(
            status="lite",
            qdrant=False,
            schema_ready=schema_ready,
            embedding_model=embedding_model,
            message=(
                "Qdrant unavailable, falling back to lookup only"
                if schema_ready
                else "Qdrant and lookup schema data are unavailable"
            ),
        )

    return HealthOutcome(
        status=detail.status,
        qdrant=detail.qdrant_connected,
        schema_ready=schema_ready,
        embedding_model=embedding_model,
        message=detail.message,
        collections=dict(detail.collections),
        total_documents=detail.total_documents,
        missing_collections=tuple(detail.missing_collections),
    )

__all__ = [
    "HealthOutcome",
    "RetrievalHealthPort",
    "build_health_outcome",
]
