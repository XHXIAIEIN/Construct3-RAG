# src/rag/semantic_chain.py
"""Semantic decomposition chain for zero-dictionary query understanding."""
from __future__ import annotations
import copy
import dataclasses
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal
from pydantic import BaseModel, Field

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
        prompt = self._prompt.format(query=query)
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

    @property
    def available(self) -> bool:
        if getattr(self._llm, "provider", None) != "ollama":
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
            return True
        except Exception:
            return False

    def decompose(self, query: str) -> DecomposedQuery:
        if not self.available or self._client is None:
            return copy.deepcopy(_FALLBACK_DQ)
        try:
            model_name = getattr(self._llm, "model", "qwen2.5:7b")
            prompt = self._prompt.format(query=query)
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
