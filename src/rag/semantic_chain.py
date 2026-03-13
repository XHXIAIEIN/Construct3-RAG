# src/rag/semantic_chain.py
"""Semantic decomposition chain for zero-dictionary query understanding."""
from __future__ import annotations
import copy
import dataclasses
import hashlib
import json
import logging
import re
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal
import numpy as np
from pydantic import BaseModel, Field
from src.collections import DOC_COLLECTIONS

# Doc collections always searched at minimum weight — ensures manual content is
# never excluded by the threshold even when the query doesn't match a descriptor.
_DOC_COLLECTION_FLOOR = 0.05
_DOC_COLLECTION_SET = set(DOC_COLLECTIONS)

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
        return []
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
    result = dataclasses.replace(dq, intents=[QueryIntent("default", keywords, 1.0)])
    return result


logger = logging.getLogger(__name__)

_FALLBACK_DQ = DecomposedQuery(
    query_type="unknown", c3_objects=[], action_verbs=[],
    intents=[], solution_rewrite="", confidence=0.0,
)


class StructuredOutputBackend(ABC):
    """Abstract base for all decomposition backends."""

    @property
    def available(self) -> bool:
        return True

    @abstractmethod
    def decompose(self, query: str) -> DecomposedQuery: ...


def _parse_dq_from_json(raw: str) -> DecomposedQuery | None:
    """Extract and validate a DecomposedQuery from raw LLM text."""
    # Strip markdown code fences
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    json_str = match.group(1) if match else raw.strip()
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        # Try finding first { ... } block
        m = re.search(r"\{[\s\S]+\}", json_str)
        if not m:
            return None
        try:
            data = json.loads(m.group())
        except json.JSONDecodeError:
            return None

    try:
        intents = [
            QueryIntent(
                label=str(i.get("label", "")),
                keywords=[str(k) for k in i.get("keywords", [])],
                weight=float(i.get("weight", 1.0)),
            )
            for i in data.get("intents", [])
        ]
        dq = DecomposedQuery(
            query_type=str(data.get("query_type", "unknown")),
            c3_objects=[str(o) for o in data.get("c3_objects", [])],
            action_verbs=[str(v) for v in data.get("action_verbs", [])],
            intents=normalize_intents(intents),
            solution_rewrite=str(data.get("solution_rewrite", "")),
            confidence=float(data.get("confidence", 0.5)),
        )
        return ensure_intents(dq)
    except (TypeError, KeyError, AttributeError, ValueError) as e:
        logger.debug("DecomposedQuery parse error: %s", e)
        return None


class RawLLMBackend(StructuredOutputBackend):
    """Always-available fallback: prompt LLM, regex-extract JSON."""

    def __init__(self, llm, prompt_template: str):
        self._llm = llm
        self._prompt = prompt_template

    def decompose(self, query: str) -> DecomposedQuery:
        prompt = self._prompt.replace("{query}", query)
        try:
            raw = self._llm.generate(prompt)
            result = _parse_dq_from_json(raw)
            if result is not None:
                return result
        except Exception as e:
            logger.debug("RawLLMBackend error: %s", e)
        return copy.deepcopy(_FALLBACK_DQ)


class _IntentModel(BaseModel):
    label: str
    keywords: list[str] = Field(default_factory=list)
    weight: float = 1.0


class _DecomposedQueryModel(BaseModel):
    query_type: str = "unknown"
    c3_objects: list[str] = Field(default_factory=list)
    action_verbs: list[str] = Field(default_factory=list)
    intents: list[_IntentModel] = Field(default_factory=list)
    solution_rewrite: str = ""
    confidence: float = 0.5


class InstructorBackend(StructuredOutputBackend):
    """Pydantic validation via instructor library (Ollama provider only)."""

    def __init__(self, llm, prompt_template: str):
        self._llm = llm
        self._prompt = prompt_template
        self._client = None
        self._available: bool | None = None  # cached; None = not yet checked

    @property
    def available(self) -> bool:
        if self._available is not None:
            return self._available
        if getattr(self._llm, "provider", None) != "ollama":
            self._available = False
            return False
        try:
            import instructor
            from ollama import Client
            host = getattr(self._llm, "ollama_host", "localhost")
            port = getattr(self._llm, "ollama_port", 11434)
            self._client = instructor.from_ollama(
                Client(host=f"http://{host}:{port}"),
                mode=instructor.Mode.JSON,
            )
            self._available = True
            return True
        except Exception:
            self._available = False
            return False

    def decompose(self, query: str) -> DecomposedQuery:
        # Use cached _client directly — avoids re-triggering network call via available
        if self._client is None:
            return copy.deepcopy(_FALLBACK_DQ)
        try:
            model_name = getattr(self._llm, "model", "qwen2.5:7b")
            prompt = self._prompt.replace("{query}", query)
            result: _DecomposedQueryModel = self._client.chat.completions.create(
                model=model_name,
                response_model=_DecomposedQueryModel,
                messages=[{"role": "user", "content": prompt}],
            )
            intents = [
                QueryIntent(i.label, i.keywords, i.weight)
                for i in result.intents
            ]
            dq = DecomposedQuery(
                query_type=result.query_type,
                c3_objects=result.c3_objects,
                action_verbs=result.action_verbs,
                intents=normalize_intents(intents),
                solution_rewrite=result.solution_rewrite,
                confidence=result.confidence,
            )
            return ensure_intents(dq)
        except Exception as e:
            logger.debug("InstructorBackend error: %s", e)
            return copy.deepcopy(_FALLBACK_DQ)


COLLECTION_DESCRIPTORS: dict[str, str] = {
    "c3_guide":     "Construct 3 manual tutorial guide how-to concept explanation documentation",
    "c3_interface": "Construct 3 editor interface UI toolbar menu layout panel dialog",
    "c3_project":   "Construct 3 project structure events objects timelines flowcharts families",
    "c3_plugins":   "Construct 3 plugin object type properties behavior scripting SDK",
    "c3_behaviors": "Construct 3 behavior platform movement physics collision tween pathfinding",
    "c3_scripting": "Construct 3 JavaScript TypeScript runtime API script module",
    "c3_ace":       "Construct 3 plugin action condition expression API parameter reference",
    "c3_effects":   "Construct 3 visual effect shader WebGL blend parameter",
    "c3_terms":     "Construct 3 Chinese English translation term glossary vocabulary",
    "c3_examples":  "Construct 3 example project game template event sheet code sample",
}

QUERY_TYPE_BIAS: dict[str, dict[str, float]] = {
    "howto":        {"c3_ace": 0.3, "c3_guide": 0.2},
    "explain":      {"c3_guide": 0.3, "c3_project": 0.2},
    "troubleshoot": {"c3_guide": 0.2, "c3_examples": 0.3},
    "translate":    {"c3_terms": 0.6},
    "list_ace":     {"c3_ace": 0.5},
    "code_gen":     {"c3_scripting": 0.3, "c3_examples": 0.3},
    "unknown":      {},
}


def _cosine(a: list[float] | np.ndarray, b: list[float] | np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class CollectionRouter:
    """Routes queries to Qdrant collections via embedding similarity + query_type bias."""

    def __init__(self, embedder, threshold: float = 0.2):
        self._embedder = embedder
        self._default_threshold = threshold
        self._descriptor_vecs: dict[str, list[float]] | None = None

    def _ensure_descriptors(self) -> None:
        if self._descriptor_vecs is not None:
            return
        texts = list(COLLECTION_DESCRIPTORS.values())
        vecs = self._embedder.encode(texts)
        self._descriptor_vecs = {
            name: vecs[i]
            for i, name in enumerate(COLLECTION_DESCRIPTORS)
        }

    def route(
        self,
        query: str,
        query_type: str = "unknown",
        threshold: float | None = None,
    ) -> dict[str, float]:
        """Return weight map for all collections.

        Collections with weight below threshold are zeroed out.
        """
        self._ensure_descriptors()
        assert self._descriptor_vecs is not None
        query_vec = self._embedder.encode_single(query)
        bias = QUERY_TYPE_BIAS.get(query_type, {})
        thr = threshold if threshold is not None else self._default_threshold
        weights = {}
        for name, desc_vec in self._descriptor_vecs.items():
            sim = _cosine(query_vec, desc_vec)
            w = min(1.0, max(0.0, sim + bias.get(name, 0.0)))
            if w < thr:
                # Doc collections: apply floor so manual content is always searched.
                # Non-doc collections (ace, terms, examples, effects): zero out.
                w = _DOC_COLLECTION_FLOOR if name in _DOC_COLLECTION_SET else 0.0
            weights[name] = w
        return weights


def _normalize_query(query: str) -> str:
    """Normalize query for cache key: NFKC + strip + lowercase."""
    q = unicodedata.normalize("NFKC", query)
    q = " ".join(q.split())
    q = q.lower()
    return q


def _cache_key(query: str) -> str:
    return hashlib.sha256(_normalize_query(query).encode()).hexdigest()


class SemanticChain:
    """Orchestrates semantic decomposition → collection routing → multi-path retrieval."""

    def __init__(
        self,
        backend: StructuredOutputBackend | None,
        router: CollectionRouter | None,
        retriever,  # HybridRetriever instance
        enabled: bool = True,
        threshold: float = 0.2,
        top_k_per_intent: int = 5,
        top_k_hyde: int = 5,
        top_k_keyword: int = 3,
    ):
        self._backend = backend
        self._router = router
        self._retriever = retriever
        self._enabled = enabled
        self._threshold = threshold
        self._top_k_intent = top_k_per_intent
        self._top_k_hyde = top_k_hyde
        self._top_k_keyword = top_k_keyword
        self._cache: dict[str, DecomposedQuery] = {}

    def decompose(self, query: str) -> DecomposedQuery | None:
        if not self._enabled or self._backend is None:
            return None
        key = _cache_key(query)
        if key not in self._cache:
            self._cache[key] = self._backend.decompose(query)
        return self._cache[key]

    def _path_a_intent_search(
        self, intents: list, top_collections: list, semantic_blend: float
    ) -> tuple[list, list]:
        result_lists: list = []
        weights: list[float] = []
        for intent in intents[:3]:
            if not intent.keywords or not top_collections:
                continue
            search_query = " ".join(intent.keywords[:6])
            for col in top_collections[:2]:
                try:
                    results = self._retriever.search_collection(
                        col, search_query, top_k=self._top_k_intent
                    )
                    result_lists.append(results)
                    weights.append(intent.weight * semantic_blend)
                except Exception:
                    pass
        return result_lists, weights

    def _path_b_hyde_search(
        self, solution_rewrite: str, top_collections: list, semantic_blend: float
    ) -> tuple[list, list]:
        result_lists: list = []
        weights: list[float] = []
        if solution_rewrite and top_collections:
            for col in top_collections[:2]:
                try:
                    results = self._retriever.search_collection(
                        col, solution_rewrite, top_k=self._top_k_hyde
                    )
                    result_lists.append(results)
                    weights.append(0.4 * semantic_blend)
                except Exception:
                    pass
        return result_lists, weights

    def _path_c_keyword_fallback(
        self, solution_rewrite: str, top_collections: list, semantic_blend: float
    ) -> tuple[list, list]:
        result_lists: list = []
        weights: list[float] = []
        if solution_rewrite and top_collections:
            for col in top_collections[:1]:
                try:
                    results = self._retriever.search_collection(
                        col, solution_rewrite, top_k=self._top_k_keyword
                    )
                    result_lists.append(results)
                    weights.append(0.2 * semantic_blend)
                except Exception:
                    pass
        return result_lists, weights

    def run(self, query: str) -> tuple[list, list] | None:
        """Run full semantic chain. Returns (result_lists, weights) or None if disabled."""
        if not self._enabled or self._backend is None:
            return None

        dq = self.decompose(query)
        if self._router is None:
            return [], []

        collection_weights = self._router.route(query, dq.query_type, self._threshold)
        top_collections = [
            c for c, w in sorted(collection_weights.items(), key=lambda x: x[1], reverse=True)
            if w >= self._threshold
        ][:3]

        semantic_blend = max(0.2, dq.confidence * 0.5)

        a_lists, a_weights = self._path_a_intent_search(dq.intents, top_collections, semantic_blend)
        b_lists, b_weights = self._path_b_hyde_search(dq.solution_rewrite, top_collections, semantic_blend)
        c_lists, c_weights = self._path_c_keyword_fallback(dq.solution_rewrite, top_collections, semantic_blend)

        result_lists = a_lists + b_lists + c_lists
        weights = a_weights + b_weights + c_weights
        return result_lists, weights
