"""Compatibility facade for :mod:`src.retrieval.semantic`.

New runtime code should import ``HybridRetriever`` from the canonical retrieval
package. Historical types and pure helper exports retain object identity here.
"""

from src.domain.retrieval import SearchResult
from src.retrieval.identity import deduplicate_results, stable_result_id
from src.retrieval.policy import (
    assign_context_tiers,
    estimate_query_complexity,
    weighted_rrf,
)
from src.retrieval.semantic import HybridRetriever

__all__ = [
    "HybridRetriever",
    "SearchResult",
    "assign_context_tiers",
    "deduplicate_results",
    "estimate_query_complexity",
    "stable_result_id",
    "weighted_rrf",
]
