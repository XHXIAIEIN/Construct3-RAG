"""Retrieval package with optional semantic components loaded on demand.

Importing ``src.rag.lookup`` is part of the minimal offline product path and
must not import the Qdrant-backed retriever as a package side effect.  Keep the
historical ``from src.rag import HybridRetriever`` API through a lazy export.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .retriever import HybridRetriever as HybridRetriever

__all__ = ["HybridRetriever"]


def __getattr__(name: str):
    if name == "HybridRetriever":
        from .retriever import HybridRetriever

        globals()[name] = HybridRetriever
        return HybridRetriever
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
