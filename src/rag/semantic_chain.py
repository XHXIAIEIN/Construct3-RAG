# src/rag/semantic_chain.py
"""Semantic decomposition chain for zero-dictionary query understanding."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal
import copy

QUERY_TYPES = Literal[
    "howto", "explain", "troubleshoot", "translate",
    "list_ace", "code_gen", "unknown",
]


@dataclass
class QueryIntent:
    label: str
    keywords: list[str]
    weight: float  # normalized to sum=1.0 across all intents


@dataclass
class DecomposedQuery:
    query_type: str
    c3_objects: list[str]
    action_verbs: list[str]
    intents: list[QueryIntent]
    solution_rewrite: str
    confidence: float  # 0.0–1.0


def normalize_intents(intents: list[QueryIntent]) -> list[QueryIntent]:
    """Normalize intent weights to sum to 1.0."""
    if not intents:
        return intents
    total = sum(i.weight for i in intents)
    if total <= 0:
        equal = 1.0 / len(intents)
        return [QueryIntent(i.label, i.keywords, equal) for i in intents]
    return [QueryIntent(i.label, i.keywords, i.weight / total) for i in intents]


def ensure_intents(dq: DecomposedQuery) -> DecomposedQuery:
    """If intents is empty, insert a default intent using available keywords."""
    if dq.intents:
        return dq
    keywords = list(dq.c3_objects) + list(dq.action_verbs)
    result = copy.replace(dq, intents=[QueryIntent("default", keywords, 1.0)])
    return result
