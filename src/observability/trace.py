"""Lightweight request-local trace collection."""
from __future__ import annotations

import threading

_trace_local = threading.local()


def _trace(message: str, phase: str = "info") -> None:
    """Append an event when the current request enabled trace collection."""
    if hasattr(_trace_local, "events"):
        _trace_local.events.append((phase, message))


__all__ = ["_trace", "_trace_local"]
