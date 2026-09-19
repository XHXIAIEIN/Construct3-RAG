"""Compatibility facade for :mod:`src.qdrant.retrieval.semantic`.

New runtime code should import ``HybridRetriever`` from the canonical retrieval
package. Historical types and pure helper exports retain object identity here.
"""

from src.domain.retrieval import SearchResult
from src.qdrant.retrieval.identity import deduplicate_results, stable_result_id
from src.qdrant.retrieval.policy import (
    assign_context_tiers,
    estimate_query_complexity,
    weighted_rrf,
)
from src.qdrant.retrieval.semantic import HybridRetriever

__all__ = [
    "HybridRetriever",
    "SearchResult",
    "assign_context_tiers",
    "deduplicate_results",
    "estimate_query_complexity",
    "stable_result_id",
    "weighted_rrf",
]
