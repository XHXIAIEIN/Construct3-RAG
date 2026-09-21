"""Transport-independent health use case for the optional search service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.lookup.schema_layout import schema_is_complete


@dataclass(frozen=True)
class HealthOutcome:
    status: str
    schema_ready: bool
    message: str


def build_health_outcome(*, schema_dir: Path) -> HealthOutcome:
    """Report whether the local schema data the lookup reads is complete."""
    if schema_is_complete(schema_dir):
        return HealthOutcome(status="ok", schema_ready=True, message="Lookup ready")
    return HealthOutcome(
        status="unavailable",
        schema_ready=False,
        message="Schema data missing; run python scripts/init.py",
    )


__all__ = [
    "HealthOutcome",
    "build_health_outcome",
]
