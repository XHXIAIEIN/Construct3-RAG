"""Lightweight per-request trace collector (thread-local).

Each event is a (phase, message) tuple so the display layer can
group and style events by phase without parsing message strings.

Usage:
    from ._trace import _trace, _trace_local

    # Entry point (answer_smart):
    _trace_local.events = []
    ...
    resp.trace = list(_trace_local.events)

    # Any called function:
    _trace("Tier1: 未命中", "lookup")   # no-op outside answer_smart
"""
import threading

_trace_local = threading.local()


def _trace(msg: str, phase: str = "info") -> None:
    """Append a (phase, msg) event to the current request's trace list.

    No-op when called outside of an answer_smart() context.
    """
    if hasattr(_trace_local, 'events'):
        _trace_local.events.append((phase, msg))
