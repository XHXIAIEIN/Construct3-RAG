"""Deterministic retrieval routing, context, and fusion policies."""

from __future__ import annotations

import re
from typing import Any

from src.domain.retrieval import QueryComplexity, RetrievalPreset, SearchResult
from src.retrieval.identity import stable_result_id

_PRESETS: dict[QueryComplexity, RetrievalPreset] = {
    "simple": RetrievalPreset("simple", 3, 5),
    "moderate": RetrievalPreset("moderate", 5, 10),
    "complex": RetrievalPreset("complex", 8, 15),
}
_COMPOUND_SPLITTERS = re.compile(r"[？?；;、]")
_MULTI_QUESTION = re.compile(r"[？?]")


def estimate_query_complexity(query: str) -> RetrievalPreset:
    """Choose a zero-cost retrieval budget from query structure."""
    normalized = query.strip()
    length = len(normalized)
    if length <= 15:
        return _PRESETS["simple"]
    questions = len(_MULTI_QUESTION.findall(normalized))
    splitters = len(_COMPOUND_SPLITTERS.findall(normalized))
    if questions >= 2 or (length >= 25 and splitters >= 3):
        return _PRESETS["complex"]
    if length >= 30 and splitters >= 1:
        return _PRESETS["complex"]
    return _PRESETS["moderate"]


def assign_context_tiers(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Annotate response results with relative full/normal/brief context tiers."""
    if not results:
        return results
    max_score = max(result.get("score", 0) for result in results)
    if max_score <= 0:
        for result in results:
            result["context_tier"] = "normal"
        return results
    for index, result in enumerate(results):
        ratio = result.get("score", 0) / max_score
        if index == 0 and ratio >= 0.8:
            result["context_tier"] = "full"
        elif ratio >= 0.5:
            result["context_tier"] = "normal"
        else:
            result["context_tier"] = "brief"
    return results


def weighted_rrf(
    result_lists: list[list[SearchResult]],
    weights: list[float],
) -> list[SearchResult]:
    """Fuse ranked lists using weighted reciprocal rank and exact identities."""
    rrf_scores: dict[tuple[Any, ...], float] = {}
    result_map: dict[tuple[Any, ...], SearchResult] = {}
    for list_index, (results, weight) in enumerate(zip(result_lists, weights)):
        k = round(60 / max(weight, 0.1))
        seen_in_list: set[str] = set()
        for rank, result in enumerate(results):
            identity = stable_result_id(result)
            if identity is not None:
                if identity in seen_in_list:
                    continue
                seen_in_list.add(identity)
                key: tuple[Any, ...] = ("stable", identity)
            else:
                key = ("unidentified", list_index, rank)
            rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (k + rank + 1)
            if key not in result_map or result.score > result_map[key].score:
                result_map[key] = result
    return [
        SearchResult(
            text=result_map[key].text,
            score=rrf_scores[key],
            source=result_map[key].source,
            metadata={
                **result_map[key].metadata,
                "original_score": result_map[key].score,
            },
        )
        for key in sorted(rrf_scores, key=rrf_scores.__getitem__, reverse=True)
    ]
