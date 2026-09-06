"""Real Qdrant, model, reranker, and Direct Lookup adapters.

Imports that can load CUDA libraries or optional services remain inside these
classes so importing the normal pytest suite stays offline and lightweight.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Sequence

from .core import BackendPoint, BackendSearchResult
from .models import ApiFilters, GoldCase
from .stable_ids import normalize_ace_type, normalize_component, stable_result_id


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


class LiveDenseEncoder:
    def __init__(self, model_name: str, device: str | None = None) -> None:
        self.model_name = model_name
        self.device = device or self._default_device()
        self._model = None
        self.load_ms = 0.0
        self.dimension: int | None = None

    @staticmethod
    def _default_device() -> str:
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def prepare(self) -> None:
        if self._model is not None:
            return
        from src.ingest.indexer import EmbeddingModel

        started = time.perf_counter()
        model = EmbeddingModel(self.model_name, device=self.device, native_sparse=False)
        self.dimension = int(model.dimension)  # force the exact artifact to load now
        self._model = model
        self.load_ms = (time.perf_counter() - started) * 1000

    def encode_query(self, query: str) -> Sequence[float]:
        self.prepare()
        return self._model.encode_single(query)  # type: ignore[union-attr]

    def identity(self) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "device": self.device,
            "dimension": self.dimension,
            "load_ms": self.load_ms,
            "query_instruction": (
                "Instruct: Retrieve relevant Construct 3 documentation for the following query\\nQuery: "
                if "qwen3-embedding" in self.model_name.casefold()
                else None
            ),
            "explicit_output_normalization": False,
        }


class LiveSparseEncoder:
    def __init__(self, vocab_path: Path) -> None:
        self.vocab_path = vocab_path.with_suffix(".msgpack")
        self._model = None
        self.load_ms = 0.0

    def prepare(self) -> None:
        if self._model is not None:
            return
        if not self.vocab_path.is_file():
            raise FileNotFoundError(f"BM25 vocabulary not found: {self.vocab_path}")
        from src.ingest.indexer import BM25Vectorizer

        started = time.perf_counter()
        self._model = BM25Vectorizer().load(self.vocab_path)
        self.load_ms = (time.perf_counter() - started) * 1000

    def encode_query(self, query: str) -> Mapping[int, float]:
        self.prepare()
        return self._model.encode(query)  # type: ignore[union-attr]

    def identity(self) -> dict[str, Any]:
        return {
            "type": "BM25Vectorizer",
            "vocab_path": str(self.vocab_path.resolve()),
            "vocab_sha256": sha256_file(self.vocab_path) if self.vocab_path.is_file() else None,
            "vocab_terms": len(self._model.vocab) if self._model is not None else None,
            "load_ms": self.load_ms,
            "k1": getattr(self._model, "k1", 1.5),
            "b": getattr(self._model, "b", 0.75),
        }


class LiveCrossEncoder:
    def __init__(
        self,
        model_name: str,
        *,
        device: str | None = None,
        batch_size: int = 8,
    ) -> None:
        self.model_name = model_name
        self.device = device or LiveDenseEncoder._default_device()
        self.batch_size = batch_size
        self._model = None
        self.load_ms = 0.0

    def prepare(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import CrossEncoder

        started = time.perf_counter()
        self._model = CrossEncoder(self.model_name, device=self.device)
        self.load_ms = (time.perf_counter() - started) * 1000

    def predict(self, query: str, texts: Sequence[str]) -> Sequence[float]:
        self.prepare()
        if not texts:
            return []
        raw = self._model.predict(  # type: ignore[union-attr]
            [[query, text] for text in texts],
            batch_size=self.batch_size,
            show_progress_bar=False,
        )
        values = raw.tolist() if hasattr(raw, "tolist") else list(raw)
        return [float(value[0] if isinstance(value, (list, tuple)) else value) for value in values]

    def identity(self) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "device": self.device,
            "batch_size": self.batch_size,
            "load_ms": self.load_ms,
        }


class LiveQdrantBackend:
    """Named dense+sparse prefetch with Qdrant-internal RRF held constant."""

    def __init__(self, host: str, port: int, *, timeout_seconds: float = 60.0) -> None:
        from qdrant_client import QdrantClient

        self.host = host
        self.port = int(port)
        self.timeout_seconds = float(timeout_seconds)
        self.client = QdrantClient(host=host, port=port, timeout=timeout_seconds)

    @staticmethod
    def _query_filter(filters: ApiFilters):
        if not filters.plugin and not filters.section_types:
            return None
        from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchText

        must = []
        if filters.plugin:
            must.append(
                FieldCondition(
                    key="source", match=MatchText(text=filters.plugin.casefold())
                )
            )
        if filters.section_types:
            # MatchAny is an explicit OR that is itself mandatory.  A top-level
            # ``should`` next to ``must`` is easy to misread as optional and has
            # changed interpretation across vector-database APIs.
            must.append(
                FieldCondition(
                    key="section_type",
                    match=MatchAny(any=list(filters.section_types)),
                )
            )
        return Filter(must=must)

    def search(
        self,
        collection_key: str,
        dense_vector: Sequence[float],
        sparse_vector: Mapping[int, float],
        limit: int,
        filters: ApiFilters,
    ) -> BackendSearchResult:
        from qdrant_client.models import Fusion, FusionQuery, Prefetch, SparseVector
        from src.collections import COLLECTIONS

        collection_name = COLLECTIONS[collection_key]
        started = time.perf_counter()
        try:
            query_filter = self._query_filter(filters)
            response = self.client.query_points(
                collection_name=collection_name,
                prefetch=[
                    Prefetch(
                        query=list(dense_vector),
                        using="dense",
                        filter=query_filter,
                        limit=limit * 2,
                    ),
                    Prefetch(
                        query=SparseVector(
                            indices=[int(index) for index in sorted(sparse_vector)],
                            values=[float(sparse_vector[index]) for index in sorted(sparse_vector)],
                        ),
                        using="sparse",
                        filter=query_filter,
                        limit=limit * 2,
                    ),
                ],
                query=FusionQuery(fusion=Fusion.RRF),
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
            points = tuple(
                BackendPoint(
                    point_id=str(point.id),
                    text=str((point.payload or {}).get("text", "")),
                    score=float(point.score),
                    payload=dict(point.payload or {}),
                )
                for point in response.points
            )
            return BackendSearchResult(
                collection_name=collection_name,
                points=points,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            timeout = "timeout" in message.casefold() or isinstance(exc, TimeoutError)
            return BackendSearchResult(
                collection_name=collection_name,
                elapsed_ms=(time.perf_counter() - started) * 1000,
                error=message,
                timed_out=timeout,
            )

    def identity(self) -> dict[str, Any]:
        from src.collections import COLLECTIONS

        response = self.client.get_collections()
        existing = {item.name for item in response.collections}
        collections: dict[str, Any] = {}
        for key, name in COLLECTIONS.items():
            if name not in existing:
                collections[key] = {"name": name, "present": False}
                continue
            try:
                info = self.client.get_collection(name)
                params = info.config.params
                vectors = getattr(params, "vectors", None)
                dense = vectors.get("dense") if isinstance(vectors, dict) else vectors
                sparse_vectors = getattr(params, "sparse_vectors", None)
                collections[key] = {
                    "name": name,
                    "present": True,
                    "status": _enum_value(getattr(info, "status", None)),
                    "points_count": getattr(info, "points_count", None),
                    "indexed_vectors_count": getattr(info, "indexed_vectors_count", None),
                    "dense": {
                        "name": "dense" if isinstance(vectors, dict) else None,
                        "size": getattr(dense, "size", None),
                        "distance": _enum_value(getattr(dense, "distance", None)),
                    },
                    "sparse_vector_names": (
                        sorted(sparse_vectors.keys()) if isinstance(sparse_vectors, dict) else []
                    ),
                }
            except Exception as exc:
                collections[key] = {
                    "name": name,
                    "present": True,
                    "inspection_error": f"{type(exc).__name__}: {exc}",
                }
        server: dict[str, Any] | None = None
        try:
            with urllib.request.urlopen(
                f"http://{self.host}:{self.port}/", timeout=min(self.timeout_seconds, 5.0)
            ) as response_handle:
                server = json.loads(response_handle.read().decode("utf-8"))
        except Exception as exc:
            server = {"inspection_error": f"{type(exc).__name__}: {exc}"}
        return {
            "host": self.host,
            "port": self.port,
            "timeout_seconds": self.timeout_seconds,
            "server": server,
            "actual_collection_names": sorted(existing),
            "expected_collection_names": sorted(COLLECTIONS.values()),
            "collection_set_matches": existing == set(COLLECTIONS.values()),
            "inner_collection_fusion": "Qdrant Fusion.RRF over named dense+sparse prefetch",
            "inner_prefetch_multiplier": 2,
            "per_collection_output_limit": "EvaluationConfig.candidate_budget_per_collection",
            "collections": collections,
        }


class LiveLookupProbe:
    def __init__(self, schema_dir: Path) -> None:
        self.schema_dir = schema_dir
        self._engine = None
        self.load_ms = 0.0

    def prepare(self) -> None:
        if self._engine is not None:
            return
        from src.rag.lookup import LookupEngine

        started = time.perf_counter()
        self._engine = LookupEngine(schema_dir=self.schema_dir)
        self.load_ms = (time.perf_counter() - started) * 1000

    @staticmethod
    def _match_id(match: Any) -> str:
        collection = normalize_component(match.collection)
        if collection == "examples":
            return stable_result_id("examples", {"slug": match.ace_id})
        if collection == "terms":
            return "|".join(
                (
                    "terms",
                    normalize_component(match.plugin_id),
                    normalize_ace_type(match.ace_type),
                    normalize_component(match.ace_id),
                )
            )
        if collection == "script_api":
            return "|".join(
                (
                    "script_api",
                    normalize_component(match.plugin_id),
                    normalize_component(match.ace_id),
                )
            )
        plugin_type = "behavior" if collection == "behaviors" else "plugin"
        return stable_result_id(
            "ace",
            {
                "plugin_type": plugin_type,
                "plugin_id": match.plugin_id,
                "ace_type": match.ace_type,
                "ace_id": match.ace_id,
            },
        )

    def observe(self, case: GoldCase) -> Mapping[str, Any]:
        if case.api_filters.plugin or case.api_filters.collections or case.api_filters.section_types:
            return {
                "route": "bypass",
                "stable_ids": [],
                "matches": [],
                "elapsed_ms": 0.0,
                "error": None,
            }
        if case.expected_api_route == "semantic":
            return {
                "route": "skipped",
                "stable_ids": [],
                "matches": [],
                "elapsed_ms": 0.0,
                "error": None,
            }
        self.prepare()
        started = time.perf_counter()
        try:
            response = self._engine.try_lookup(case.query)  # type: ignore[union-attr]
        except Exception as exc:
            return {
                "route": "error",
                "stable_ids": [],
                "matches": [],
                "elapsed_ms": (time.perf_counter() - started) * 1000,
                "error": f"{type(exc).__name__}: {exc}",
            }
        elapsed = (time.perf_counter() - started) * 1000
        if response is None or not response.matches:
            return {
                "route": "miss",
                "stable_ids": [],
                "matches": [],
                "elapsed_ms": elapsed,
                "error": None,
            }
        matches = []
        stable_ids = []
        for match in response.matches:
            stable_id = self._match_id(match)
            stable_ids.append(stable_id)
            matches.append(
                {
                    "stable_id": stable_id,
                    "collection": match.collection,
                    "plugin_id": match.plugin_id,
                    "ace_type": match.ace_type,
                    "ace_id": match.ace_id,
                }
            )
        return {
            "route": "hit",
            "stable_ids": stable_ids,
            "matches": matches,
            "elapsed_ms": elapsed,
            "intent": response.intent.intent_type,
            "confidence": response.intent.confidence,
            "error": None,
        }

    def identity(self) -> dict[str, Any]:
        return {
            "schema_dir": str(self.schema_dir.resolve()),
            "load_ms": self.load_ms,
            "real_lookup_engine": True,
        }


def resource_snapshot() -> dict[str, Any]:
    result: dict[str, Any] = {"perf_counter": time.perf_counter()}
    try:
        import psutil

        process = psutil.Process()
        memory = process.memory_info()
        cpu_times = process.cpu_times()
        virtual = psutil.virtual_memory()
        result.update(
            {
                "process_rss_bytes": memory.rss,
                "process_vms_bytes": memory.vms,
                "process_cpu_user_seconds": cpu_times.user,
                "process_cpu_system_seconds": cpu_times.system,
                "system_memory_total_bytes": virtual.total,
                "system_memory_available_bytes": virtual.available,
            }
        )
    except ImportError:
        result["psutil"] = "not installed"
    try:
        import torch

        result["torch_cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            result.update(
                {
                    "gpu_name": torch.cuda.get_device_name(0),
                    "cuda_allocated_bytes": torch.cuda.memory_allocated(0),
                    "cuda_reserved_bytes": torch.cuda.memory_reserved(0),
                    "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated(0),
                    "cuda_peak_reserved_bytes": torch.cuda.max_memory_reserved(0),
                }
            )
    except ImportError:
        result["torch"] = "not installed"
    return result


def runtime_identity() -> dict[str, Any]:
    result: dict[str, Any] = {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cpu_count": os.cpu_count(),
        "packages": {
            name: _package_version(name)
            for name in (
                "qdrant-client",
                "sentence-transformers",
                "transformers",
                "torch",
                "FlagEmbedding",
                "psutil",
            )
        },
    }
    snapshot = resource_snapshot()
    result["memory"] = {
        key: snapshot.get(key)
        for key in ("system_memory_total_bytes", "system_memory_available_bytes")
    }
    result["gpu"] = {
        key: snapshot.get(key)
        for key in ("torch_cuda_available", "gpu_name")
    }
    return result
