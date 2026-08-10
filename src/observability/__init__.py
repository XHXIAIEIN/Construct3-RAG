"""Request-local diagnostics shared without depending on legacy RAG modules."""
from .trace import _trace, _trace_local

__all__ = ["_trace", "_trace_local"]
