"""Service-independent semantic evaluation pipeline.

The live adapters are intentionally injected.  This module owns the comparison
contract: one dense/sparse query encoding, one per-collection candidate batch,
identical fanout/RRF/rerank inputs, deterministic fusion, exact stable-ID
deduplication with backfill, and a hard final budget.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Protocol, Sequence

from .metrics import evaluate_dedup_expectations, evaluate_ranking
from .models import (
    DEFAULT_COLLECTION_KEYS,
    KNOWN_COLLECTION_KEYS,
    ApiFilters,
    GoldCase,
)
from .stable_ids import StableIdError, normalize_component, stable_result_id


STRATEGIES = ("limited", "fanout", "rrf", "rerank")
DEFAULT_WEIGHTS = {
    "guide": 1.0,
    "interface": 1.0,
    "project": 1.0,
    "plugins": 1.0,
    "behaviors": 1.0,
    "scripting": 1.0,
    "ace": 1.0,
    "effects": 1.0,
    "examples": 0.6,
    "terms": 0.5,
    "addon_sdk": 1.0,
}


class DenseEncoder(Protocol):
    def encode_query(self, query: str) -> Sequence[float]: ...


class SparseEncoder(Protocol):
    def encode_query(self, query: str) -> Mapping[int, float]: ...


class CandidateBackend(Protocol):
    def search(
        self,
        collection_key: str,
        dense_vector: Sequence[float],
        sparse_vector: Mapping[int, float],
        limit: int,
        filters: ApiFilters,
    ) -> "BackendSearchResult": ...


class CrossEncoder(Protocol):
    def predict(self, query: str, texts: Sequence[str]) -> Sequence[float]: ...


class LookupProbe(Protocol):
    def observe(self, case: GoldCase) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class BackendPoint:
    point_id: str
    text: str
    score: float
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class BackendSearchResult:
    collection_name: str
    points: tuple[BackendPoint, ...] = ()
    elapsed_ms: float = 0.0
    error: str | None = None
    timed_out: bool = False


@dataclass(frozen=True)
class Candidate:
    stable_id: str
    collection_key: str
    collection_name: str
    point_id: str
    text: str
    payload: Mapping[str, Any]
    raw_score: float
    collection_rank: int
    fused_score: float | None = None
    reranker_score: float | None = None

    @property
    def final_score(self) -> float:
        if self.reranker_score is not None:
            return self.reranker_score
        if self.fused_score is not None:
            return self.fused_score
        return self.raw_score


@dataclass(frozen=True)
class CollectionBatch:
    collection_key: str
    collection_name: str
    candidates: tuple[Candidate, ...] = ()
    invalid_candidates: tuple[dict[str, Any], ...] = ()
    elapsed_ms: float = 0.0
    error: str | None = None
    timed_out: bool = False


@dataclass(frozen=True)
class CandidateBatch:
    query: str
    dense_dimension: int
    dense_digest: str | None
    sparse_terms: int
    sparse_digest: str | None
    collections: tuple[CollectionBatch, ...]
    embedding_ms: float
    sparse_ms: float
    fatal_error: str | None = None

    @property
    def qdrant_ms(self) -> float:
        return sum(collection.elapsed_ms for collection in self.collections)

    def collection_map(self) -> dict[str, CollectionBatch]:
        return {collection.collection_key: collection for collection in self.collections}

    def digest_for(self, collection_keys: Sequence[str]) -> str:
        selected = set(collection_keys)
        rows: list[dict[str, Any]] = []
        for collection in self.collections:
            if collection.collection_key not in selected:
                continue
            rows.append(
                {
                    "collection_key": collection.collection_key,
                    "collection_name": collection.collection_name,
                    "error": collection.error,
                    "timed_out": collection.timed_out,
                    "candidates": [
                        {
                            "point_id": candidate.point_id,
                            "stable_id": candidate.stable_id,
                            "rank": candidate.collection_rank,
                            "raw_score": candidate.raw_score,
                        }
                        for candidate in collection.candidates
                    ],
                    "invalid_candidates": list(collection.invalid_candidates),
                }
            )
        return _json_digest(rows)


@dataclass(frozen=True)
class EvaluationConfig:
    strategies: tuple[str, ...] = STRATEGIES
    candidate_budget_per_collection: int = 10
    final_top_k: int = 10
    reranker_top_k: int = 20
    limited_collections: tuple[str, ...] = ()
    fanout_collections: tuple[str, ...] = DEFAULT_COLLECTION_KEYS
    weights: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    rrf_base_k: int = 60
    adaptive_threshold: bool = False
    diversity_injection: bool = False
    bm25_enabled: bool = True

    def __post_init__(self) -> None:
        strategies = tuple(dict.fromkeys(normalize_component(item) for item in self.strategies))
        unknown_strategies = set(strategies) - set(STRATEGIES)
        if unknown_strategies:
            raise ValueError(f"unknown strategies: {', '.join(sorted(unknown_strategies))}")
        if not strategies:
            raise ValueError("at least one semantic strategy is required")
        object.__setattr__(self, "strategies", strategies)

        limited = tuple(normalize_component(item) for item in self.limited_collections)
        fanout = tuple(normalize_component(item) for item in self.fanout_collections)
        for label, values in (("limited_collections", limited), ("fanout_collections", fanout)):
            unknown = set(values) - KNOWN_COLLECTION_KEYS
            if unknown:
                raise ValueError(f"{label} has unknown values: {', '.join(sorted(unknown))}")
            if len(set(values)) != len(values):
                raise ValueError(f"{label} must not contain duplicates")
        if "limited" in strategies and not limited:
            raise ValueError("limited strategy requires a frozen non-empty limited_collections set")
        if any(item in strategies for item in ("fanout", "rrf", "rerank")) and not fanout:
            raise ValueError("fanout collection set must not be empty")
        object.__setattr__(self, "limited_collections", limited)
        object.__setattr__(self, "fanout_collections", fanout)

        if self.candidate_budget_per_collection < 1:
            raise ValueError("candidate_budget_per_collection must be positive")
        if self.final_top_k < 1 or self.final_top_k > 10:
            raise ValueError("final_top_k must be between 1 and the frozen hard cap of 10")
        if self.reranker_top_k < self.final_top_k:
            raise ValueError("reranker_top_k must be at least final_top_k")
        if self.rrf_base_k < 1:
            raise ValueError("rrf_base_k must be positive")
        if self.adaptive_threshold:
            raise ValueError("core comparison must disable adaptive thresholding")
        if self.diversity_injection:
            raise ValueError("core comparison must disable diversity injection")
        if not self.bm25_enabled:
            raise ValueError("stage-two comparison holds dense+BM25 Qdrant RRF constant")
        normalized_weights = {normalize_component(key): float(value) for key, value in self.weights.items()}
        if any(not math.isfinite(value) or value <= 0 for value in normalized_weights.values()):
            raise ValueError("all RRF weights must be positive finite numbers")
        object.__setattr__(self, "weights", normalized_weights)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategies": list(self.strategies),
            "candidate_budget_per_collection": self.candidate_budget_per_collection,
            "final_top_k": self.final_top_k,
            "reranker_top_k": self.reranker_top_k,
            "limited_collections": list(self.limited_collections),
            "fanout_collections": list(self.fanout_collections),
            "weights": dict(self.weights),
            "rrf_base_k": self.rrf_base_k,
            "weighted_rrf_formula": (
                "per collection k=round(rrf_base_k/max(weight,0.1)); "
                "contribution=1/(k+one_based_collection_rank)"
            ),
            "adaptive_threshold": self.adaptive_threshold,
            "diversity_injection": self.diversity_injection,
            "bm25_enabled": self.bm25_enabled,
        }


def _json_digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _vector_digest(values: Sequence[float]) -> str:
    return _json_digest([float(value) for value in values])


def _sparse_digest(values: Mapping[int, float]) -> str:
    return _json_digest([[int(index), float(values[index])] for index in sorted(values)])


def _candidate_identity_summary(candidate: Candidate) -> dict[str, Any]:
    payload = candidate.payload
    return {
        "point_id": candidate.point_id,
        "stable_id": candidate.stable_id,
        "collection": candidate.collection_key,
        "collection_name": candidate.collection_name,
        "collection_rank": candidate.collection_rank,
        "raw_score": candidate.raw_score,
        "fused_score": candidate.fused_score,
        "reranker_score": candidate.reranker_score,
        "final_score": candidate.final_score,
        "source": payload.get("source") or payload.get("path"),
        "section": payload.get("h2_heading") or payload.get("section") or payload.get("section_type"),
        "section_type": payload.get("section_type"),
        "plugin_name": payload.get("plugin_name"),
        "plugin_type": payload.get("plugin_type"),
        "ace_type": payload.get("ace_type"),
        "ace_id": payload.get("ace_id"),
        "slug": payload.get("slug"),
        "effect_id": payload.get("effect_id"),
    }


class EvaluationRunner:
    """Run frozen semantic strategies over injected real or fake adapters."""

    def __init__(
        self,
        *,
        config: EvaluationConfig,
        encoder: DenseEncoder,
        sparse_encoder: SparseEncoder,
        backend: CandidateBackend,
        reranker: CrossEncoder | None = None,
        lookup_probe: LookupProbe | None = None,
        resource_probe: Any | None = None,
    ) -> None:
        self.config = config
        self.encoder = encoder
        self.sparse_encoder = sparse_encoder
        self.backend = backend
        self.reranker = reranker
        self.lookup_probe = lookup_probe
        self.resource_probe = resource_probe
        if "rerank" in config.strategies and reranker is None:
            raise ValueError("rerank strategy requires a CrossEncoder adapter")

    def run(self, cases: Sequence[GoldCase]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index, case in enumerate(cases):
            before = self._resource_snapshot()
            lookup = self._observe_lookup(case)
            collections = self._retrieval_union(case)
            batch = self._build_candidate_batch(case, collections)
            semantic_route = self._semantic_route(case, batch)
            strategies = {
                strategy: self._evaluate_strategy(case, lookup, batch, strategy, index == 0)
                for strategy in self.config.strategies
            }
            after = self._resource_snapshot()
            rows.append(
                {
                    "case": case.to_audit_dict(),
                    "routes": {
                        "api_route": case.expected_api_route,
                        "lookup": lookup,
                        "semantic": semantic_route,
                        "contract_failures": [
                            failure
                            for failure, failed in (
                                ("lookup route mismatch", lookup.get("route_matches") is False),
                                ("lookup probe error", bool(lookup.get("error"))),
                                ("semantic route unsatisfied", not semantic_route["route_satisfied"]),
                            )
                            if failed
                        ],
                    },
                    "candidate_batch": self._batch_report(batch),
                    "strategies": strategies,
                    "resources": {"before": before, "after": after},
                }
            )
        return rows

    def _resource_snapshot(self) -> dict[str, Any] | None:
        if self.resource_probe is None:
            return None
        try:
            value = self.resource_probe()
            return dict(value) if value is not None else None
        except Exception as exc:  # resource telemetry must not falsify quality output
            return {"error": f"{type(exc).__name__}: {exc}"}

    def _observe_lookup(self, case: GoldCase) -> dict[str, Any]:
        if self.lookup_probe is None:
            route = "bypass" if case.api_filters != ApiFilters() else "skipped"
            return {
                "route": route,
                "expected_route": case.expected_lookup_route,
                "route_matches": (
                    case.expected_lookup_route is None
                    or route == case.expected_lookup_route
                ),
                "stable_ids": [],
                "matches": [],
                "elapsed_ms": 0.0,
                "error": None,
            }
        try:
            observed = dict(self.lookup_probe.observe(case))
        except Exception as exc:
            observed = {
                "route": "error",
                "stable_ids": [],
                "matches": [],
                "elapsed_ms": 0.0,
                "error": f"{type(exc).__name__}: {exc}",
            }
        observed.setdefault("stable_ids", [])
        observed.setdefault("matches", [])
        observed.setdefault("elapsed_ms", 0.0)
        observed.setdefault("error", None)
        observed["expected_route"] = case.expected_lookup_route
        observed["route_matches"] = (
            case.expected_lookup_route is None
            or observed.get("route") == case.expected_lookup_route
        )
        return observed

    def _effective_collections(self, case: GoldCase, strategy: str) -> tuple[str, ...]:
        # Match the current API precedence: plugin filter, then explicit
        # collections, otherwise the strategy's frozen collection set.
        if case.api_filters.plugin:
            return ("plugins",)
        if case.api_filters.collections:
            return case.api_filters.collections
        if strategy == "limited":
            return self.config.limited_collections
        return self.config.fanout_collections

    def _retrieval_union(self, case: GoldCase) -> tuple[str, ...]:
        ordered: list[str] = []
        for strategy in self.config.strategies:
            for collection in self._effective_collections(case, strategy):
                if collection not in ordered:
                    ordered.append(collection)
        return tuple(ordered)

    def _build_candidate_batch(
        self, case: GoldCase, collections: Sequence[str]
    ) -> CandidateBatch:
        dense_started = time.perf_counter()
        try:
            dense = [float(value) for value in self.encoder.encode_query(case.query)]
            if not dense or any(not math.isfinite(value) for value in dense):
                raise ValueError("dense encoder returned an empty or non-finite vector")
        except Exception as exc:
            return CandidateBatch(
                query=case.query,
                dense_dimension=0,
                dense_digest=None,
                sparse_terms=0,
                sparse_digest=None,
                collections=(),
                embedding_ms=(time.perf_counter() - dense_started) * 1000,
                sparse_ms=0.0,
                fatal_error=f"dense embedding failed: {type(exc).__name__}: {exc}",
            )
        embedding_ms = (time.perf_counter() - dense_started) * 1000

        sparse_started = time.perf_counter()
        try:
            sparse = {
                int(index): float(value)
                for index, value in self.sparse_encoder.encode_query(case.query).items()
            }
            if any(index < 0 or not math.isfinite(value) for index, value in sparse.items()):
                raise ValueError("sparse encoder returned invalid indices or weights")
        except Exception as exc:
            return CandidateBatch(
                query=case.query,
                dense_dimension=len(dense),
                dense_digest=_vector_digest(dense),
                sparse_terms=0,
                sparse_digest=None,
                collections=(),
                embedding_ms=embedding_ms,
                sparse_ms=(time.perf_counter() - sparse_started) * 1000,
                fatal_error=f"BM25 query encoding failed: {type(exc).__name__}: {exc}",
            )
        sparse_ms = (time.perf_counter() - sparse_started) * 1000

        batches: list[CollectionBatch] = []
        for collection_key in collections:
            started = time.perf_counter()
            try:
                raw = self.backend.search(
                    collection_key,
                    dense,
                    sparse,
                    self.config.candidate_budget_per_collection,
                    case.api_filters,
                )
            except Exception as exc:
                elapsed = (time.perf_counter() - started) * 1000
                batches.append(
                    CollectionBatch(
                        collection_key=collection_key,
                        collection_name=f"c3_{collection_key}",
                        elapsed_ms=elapsed,
                        error=f"{type(exc).__name__}: {exc}",
                        timed_out=isinstance(exc, TimeoutError),
                    )
                )
                continue
            valid: list[Candidate] = []
            invalid: list[dict[str, Any]] = []
            for rank, point in enumerate(raw.points, 1):
                try:
                    stable_id = stable_result_id(collection_key, point.payload)
                except StableIdError as exc:
                    invalid.append(
                        {
                            "point_id": str(point.point_id),
                            "rank": rank,
                            "raw_score": float(point.score),
                            "error": str(exc),
                        }
                    )
                    continue
                valid.append(
                    Candidate(
                        stable_id=stable_id,
                        collection_key=collection_key,
                        collection_name=raw.collection_name,
                        point_id=str(point.point_id),
                        text=point.text,
                        payload=dict(point.payload),
                        raw_score=float(point.score),
                        collection_rank=rank,
                    )
                )
            batches.append(
                CollectionBatch(
                    collection_key=collection_key,
                    collection_name=raw.collection_name,
                    candidates=tuple(valid),
                    invalid_candidates=tuple(invalid),
                    elapsed_ms=raw.elapsed_ms or (time.perf_counter() - started) * 1000,
                    error=raw.error,
                    timed_out=raw.timed_out,
                )
            )
        return CandidateBatch(
            query=case.query,
            dense_dimension=len(dense),
            dense_digest=_vector_digest(dense),
            sparse_terms=len(sparse),
            sparse_digest=_sparse_digest(sparse),
            collections=tuple(batches),
            embedding_ms=embedding_ms,
            sparse_ms=sparse_ms,
        )

    def _semantic_route(self, case: GoldCase, batch: CandidateBatch) -> dict[str, Any]:
        attempted = len(batch.collections)
        errors = sum(bool(collection.error) for collection in batch.collections)
        if batch.fatal_error or (attempted and errors == attempted):
            route = "failed"
        elif errors:
            route = "degraded"
        else:
            route = "executed"
        expected = case.expected_semantic_route
        satisfies = expected != "required" or route in {"executed", "degraded"}
        return {
            "route": route,
            "expected_route": expected,
            "route_satisfied": satisfies,
            "attempted_collections": attempted,
            "error_collections": [
                collection.collection_key for collection in batch.collections if collection.error
            ],
            "fatal_error": batch.fatal_error,
        }

    def _merge_raw(
        self, batch: CandidateBatch, collections: Sequence[str]
    ) -> tuple[list[Candidate], float]:
        started = time.perf_counter()
        batch_map = batch.collection_map()
        order = {key: index for index, key in enumerate(collections)}
        candidates = [
            candidate
            for key in collections
            for candidate in batch_map.get(key, CollectionBatch(key, f"c3_{key}")).candidates
        ]
        candidates.sort(
            key=lambda candidate: (
                -candidate.raw_score,
                order[candidate.collection_key],
                candidate.collection_rank,
                candidate.stable_id,
                candidate.point_id,
            )
        )
        return candidates, (time.perf_counter() - started) * 1000

    def _weighted_rrf(
        self, batch: CandidateBatch, collections: Sequence[str]
    ) -> tuple[list[Candidate], float]:
        started = time.perf_counter()
        batch_map = batch.collection_map()
        scores: dict[str, float] = {}
        representatives: dict[str, Candidate] = {}
        first_order: dict[str, tuple[int, int]] = {}
        for collection_index, key in enumerate(collections):
            collection = batch_map.get(key)
            if collection is None:
                continue
            weight = self.config.weights.get(key, 0.5)
            k = round(self.config.rrf_base_k / max(weight, 0.1))
            seen_in_collection: set[str] = set()
            for candidate in collection.candidates:
                if candidate.stable_id in seen_in_collection:
                    continue
                seen_in_collection.add(candidate.stable_id)
                scores[candidate.stable_id] = scores.get(candidate.stable_id, 0.0) + (
                    1.0 / (k + candidate.collection_rank)
                )
                first_order.setdefault(
                    candidate.stable_id, (collection_index, candidate.collection_rank)
                )
                current = representatives.get(candidate.stable_id)
                if current is None or candidate.raw_score > current.raw_score:
                    representatives[candidate.stable_id] = candidate
        fused = [
            replace(representatives[stable_id], fused_score=score)
            for stable_id, score in scores.items()
        ]
        fused.sort(
            key=lambda candidate: (
                -float(candidate.fused_score or 0.0),
                first_order[candidate.stable_id],
                -candidate.raw_score,
                candidate.stable_id,
            )
        )
        return fused, (time.perf_counter() - started) * 1000

    @staticmethod
    def _dedup_ordered(candidates: Sequence[Candidate]) -> tuple[list[Candidate], list[str]]:
        seen: set[str] = set()
        unique: list[Candidate] = []
        duplicates: list[str] = []
        for candidate in candidates:
            if candidate.stable_id in seen:
                duplicates.append(candidate.stable_id)
                continue
            seen.add(candidate.stable_id)
            unique.append(candidate)
        return unique, duplicates

    def _evaluate_strategy(
        self,
        case: GoldCase,
        lookup: Mapping[str, Any],
        batch: CandidateBatch,
        strategy: str,
        cold_query: bool,
    ) -> dict[str, Any]:
        collections = self._effective_collections(case, strategy)
        digest = batch.digest_for(collections)
        errors: list[str] = []
        if batch.fatal_error:
            errors.append(batch.fatal_error)

        if strategy in {"limited", "fanout"}:
            ordered, fusion_ms = self._merge_raw(batch, collections)
        else:
            ordered, fusion_ms = self._weighted_rrf(batch, collections)
        reranker_ms = 0.0
        reranker_input_ids: list[str] = []
        if strategy == "rerank" and not errors:
            candidates = ordered[: self.config.reranker_top_k]
            unrereanked_tail = ordered[self.config.reranker_top_k :]
            reranker_input_ids = [candidate.stable_id for candidate in candidates]
            started = time.perf_counter()
            try:
                scores = [float(value) for value in self.reranker.predict(  # type: ignore[union-attr]
                    case.query, [candidate.text for candidate in candidates]
                )]
                if len(scores) != len(candidates):
                    raise ValueError(
                        f"reranker returned {len(scores)} scores for {len(candidates)} candidates"
                    )
                if any(not math.isfinite(score) for score in scores):
                    raise ValueError("reranker returned a non-finite score")
                prior_order = {candidate.stable_id: index for index, candidate in enumerate(candidates)}
                ordered = [
                    replace(candidate, reranker_score=score)
                    for candidate, score in zip(candidates, scores)
                ]
                ordered.sort(
                    key=lambda candidate: (
                        -float(candidate.reranker_score or 0.0),
                        prior_order[candidate.stable_id],
                        candidate.stable_id,
                    )
                )
                # Keep the frozen RRF tail for exact-ID backfill when Direct
                # Lookup removes many of the reranked top candidates.  Only
                # the first reranker_top_k rows receive CrossEncoder scores.
                ordered.extend(unrereanked_tail)
            except Exception as exc:
                errors.append(f"reranker failed: {type(exc).__name__}: {exc}")
                ordered = []
            reranker_ms = (time.perf_counter() - started) * 1000

        selected_collection_set = set(collections)
        raw_selected = [
            candidate
            for collection in batch.collections
            if collection.collection_key in selected_collection_set
            for candidate in collection.candidates
        ]
        input_count = len(raw_selected)
        raw_seen: set[str] = set()
        raw_duplicates: list[str] = []
        for candidate in raw_selected:
            if candidate.stable_id in raw_seen:
                raw_duplicates.append(candidate.stable_id)
            else:
                raw_seen.add(candidate.stable_id)
        unique, duplicates = self._dedup_ordered(ordered)
        pre_lookup = unique[: self.config.final_top_k]
        lookup_ids = [str(item) for item in lookup.get("stable_ids", [])]
        lookup_set = set(lookup_ids)
        post_lookup_all = [candidate for candidate in unique if candidate.stable_id not in lookup_set]
        post_lookup = post_lookup_all[: self.config.final_top_k]
        lookup_removed = [
            candidate.stable_id for candidate in unique if candidate.stable_id in lookup_set
        ]
        backfilled = [
            candidate.stable_id
            for candidate in post_lookup
            if candidate.stable_id not in {item.stable_id for item in pre_lookup}
        ]
        pre_ids = [candidate.stable_id for candidate in pre_lookup]
        post_ids = [candidate.stable_id for candidate in post_lookup]
        combined_ids = list(dict.fromkeys([*lookup_ids, *post_ids]))

        selected_batches = [
            collection
            for collection in batch.collections
            if collection.collection_key in selected_collection_set
        ]
        collection_errors = [collection.collection_key for collection in selected_batches if collection.error]
        errors.extend(
            f"collection {collection.collection_key}: {collection.error}"
            for collection in selected_batches
            if collection.error
        )
        errors.extend(
            f"collection {collection.collection_key} point {invalid.get('point_id')}: "
            f"stable identity failed: {invalid.get('error')}"
            for collection in selected_batches
            for invalid in collection.invalid_candidates
        )
        # Validate the full selected Qdrant pool, not just the displayed top-k.
        # Otherwise a leaking filter can be hidden below the final budget.
        filter_validation = self._validate_filters(case, raw_selected)
        dedup_expectations = evaluate_dedup_expectations(
            case.dedup_expectations, lookup_ids, post_ids
        )
        contract_failures: list[str] = []
        if not filter_validation["passes"]:
            contract_failures.append("Qdrant filter leaked out-of-scope candidates")
        if dedup_expectations["applicable"] and not dedup_expectations["passes"]:
            contract_failures.append("fixture dedup expectation failed")
        if len(pre_ids) > self.config.final_top_k or len(post_ids) > self.config.final_top_k:
            contract_failures.append("hard final result budget exceeded")
        qdrant_ms = sum(collection.elapsed_ms for collection in selected_batches)
        semantic_total = batch.embedding_ms + batch.sparse_ms + qdrant_ms + fusion_ms + reranker_ms
        return {
            "strategy": strategy,
            "collections": list(collections),
            "candidate_batch_digest": digest,
            "candidate_batch_shared_group": (
                "fanout-rrf-rerank" if strategy in {"fanout", "rrf", "rerank"} else "limited"
            ),
            "per_collection_candidate_counts": {
                collection.collection_key: len(collection.candidates)
                for collection in selected_batches
            },
            "candidates_before_fusion": input_count,
            "candidates_after_fusion": len(ordered),
            "reranker_input_count": len(reranker_input_ids),
            "reranker_input_stable_ids": reranker_input_ids,
            "exact_dedup": {
                "key": "canonical stable result ID",
                "input_count": input_count,
                "unique_count": len(raw_seen),
                "removed_count": len(raw_duplicates),
                "removed_ids": raw_duplicates,
                "post_fusion_duplicate_ids": duplicates,
                "lookup_overlap_removed_ids": lookup_removed,
                "backfilled_ids": backfilled,
            },
            "final_budget": self.config.final_top_k,
            "ordered_pre_lookup_stable_ids": pre_ids,
            "ordered_stable_ids": post_ids,
            "ordered_pre_lookup_results": [
                {**_candidate_identity_summary(candidate), "final_rank": rank}
                for rank, candidate in enumerate(pre_lookup, 1)
            ],
            "ordered_results": [
                {**_candidate_identity_summary(candidate), "final_rank": rank}
                for rank, candidate in enumerate(post_lookup, 1)
            ],
            "metrics": {
                "semantic_pre_lookup": evaluate_ranking(pre_ids, case),
                "semantic_post_lookup": evaluate_ranking(post_ids, case),
                "lookup_then_semantic_projection": evaluate_ranking(combined_ids, case),
            },
            "dedup_expectations": dedup_expectations,
            "filter_validation": filter_validation,
            "collection_accounting": {
                "attempted": len(selected_batches),
                "succeeded": len(selected_batches) - len(collection_errors),
                "errors": len(collection_errors),
                "error_collections": collection_errors,
                "timed_out_collections": [
                    collection.collection_key for collection in selected_batches if collection.timed_out
                ],
            },
            "timings_ms": {
                "lookup": float(lookup.get("elapsed_ms", 0.0)),
                "embedding": batch.embedding_ms,
                "sparse": batch.sparse_ms,
                "qdrant": qdrant_ms,
                "qdrant_by_collection": {
                    collection.collection_key: collection.elapsed_ms
                    for collection in selected_batches
                },
                "fusion": fusion_ms,
                "reranker": reranker_ms,
                "semantic_total": semantic_total,
                "api_projection_total": semantic_total + float(lookup.get("elapsed_ms", 0.0)),
            },
            "cold_query": cold_query,
            "errors": errors,
            "contract_failures": contract_failures,
            "degraded": bool(errors),
        }

    @staticmethod
    def _validate_filters(case: GoldCase, candidates: Sequence[Candidate]) -> dict[str, Any]:
        violations: list[str] = []
        allowed_collections = set(case.api_filters.collections)
        plugin = (case.api_filters.plugin or "").casefold()
        plugin_slug = plugin.replace(" ", "-")
        section_types = set(case.api_filters.section_types)
        for candidate in candidates:
            if allowed_collections and candidate.collection_key not in allowed_collections:
                violations.append(candidate.stable_id)
                continue
            if plugin:
                source = str(candidate.payload.get("source", "")).casefold()
                if candidate.collection_key != "plugins" or (
                    plugin not in source and plugin_slug not in source
                ):
                    violations.append(candidate.stable_id)
                    continue
            if (
                section_types
                and normalize_component(candidate.payload.get("section_type"))
                not in section_types
            ):
                violations.append(candidate.stable_id)
        return {
            "plugin": case.api_filters.plugin,
            "collections": list(case.api_filters.collections),
            "section_types": list(case.api_filters.section_types),
            "violation_ids": list(dict.fromkeys(violations)),
            "validated_candidate_count": len(candidates),
            "passes": not violations,
        }

    @staticmethod
    def _batch_report(batch: CandidateBatch) -> dict[str, Any]:
        return {
            "query": batch.query,
            "dense_vector": {
                "dimension": batch.dense_dimension,
                "sha256": batch.dense_digest,
            },
            "sparse_vector": {
                "nonzero_terms": batch.sparse_terms,
                "sha256": batch.sparse_digest,
            },
            "embedding_call_count": 1 if batch.dense_digest else 0,
            "sparse_encoding_call_count": 1 if batch.sparse_digest is not None else 0,
            "timings_ms": {
                "embedding": batch.embedding_ms,
                "sparse": batch.sparse_ms,
                "qdrant": batch.qdrant_ms,
            },
            "fatal_error": batch.fatal_error,
            "collections": [
                {
                    "collection": collection.collection_key,
                    "collection_name": collection.collection_name,
                    "elapsed_ms": collection.elapsed_ms,
                    "error": collection.error,
                    "timed_out": collection.timed_out,
                    "candidate_count": len(collection.candidates),
                    "invalid_candidate_count": len(collection.invalid_candidates),
                    "invalid_candidates": list(collection.invalid_candidates),
                    "ordered_candidates": [
                        _candidate_identity_summary(candidate)
                        for candidate in collection.candidates
                    ],
                }
                for collection in batch.collections
            ],
        }
