"""Canonical optional Qdrant semantic retrieval adapter."""

import time
import logging
import statistics
from pathlib import Path
from typing import List, Dict, Any, Tuple

from src.collection_registry import COLLECTION_CATALOG
from src.observability.trace import _trace
from src.domain.retrieval import RetrievalHealth, SearchResult
from src.retrieval.identity import _collection_key, deduplicate_results, stable_result_id
from src.retrieval.policy import weighted_rrf
from src.vector import BM25Vectorizer, EmbeddingModel

logger = logging.getLogger(__name__)

try:
    from qdrant_client import QdrantClient
except ImportError:
    QdrantClient = None  # type: ignore[assignment]


class HybridRetriever:
    """Qdrant search with optional sparse fusion and cross-encoder reranking."""

    # Score threshold configuration
    DEFAULT_SCORE_THRESHOLD = 0.3
    MIN_SCORE_THRESHOLD = 0.005  # RRF scores are 1/(60+rank) ≈ 0.01-0.016; 0.2 would filter everything
    HIGH_RELEVANCE_THRESHOLD = 0.6

    # Runtime policy defaults. Composition roots should inject configured
    # values; class defaults keep direct and historical construction stable.
    bm25_enabled = False
    bm25_vocab_path = Path(__file__).parents[2] / "data" / "bm25_vocab.msgpack"
    native_sparse = False
    reranker_enabled = True
    reranker_model = "BAAI/bge-reranker-v2-m3"
    reranker_top_k = 20

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        embedding_model_name: str = "Qwen/Qwen3-Embedding-0.6B",
        *,
        bm25_enabled: bool = False,
        bm25_vocab_path: Path | str | None = None,
        native_sparse: bool = False,
        reranker_enabled: bool = True,
        reranker_model: str = "BAAI/bge-reranker-v2-m3",
        reranker_top_k: int = 20,
    ):
        if QdrantClient is None:
            raise RuntimeError("qdrant-client is not installed")
        self.client = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.embedding_model_name = embedding_model_name
        self.bm25_enabled = bm25_enabled
        self.bm25_vocab_path = (
            Path(bm25_vocab_path)
            if bm25_vocab_path is not None
            else type(self).bm25_vocab_path
        )
        self.native_sparse = native_sparse
        self.reranker_enabled = reranker_enabled
        self.reranker_model = reranker_model
        self.reranker_top_k = reranker_top_k
        self._embedder = None
        self._qdrant_available = None  # Cache for health check
        self._qdrant_failure_at = 0.0
        self._bm25 = None  # Lazy-loaded when the injected BM25 policy is enabled

    @property
    def bm25(self):
        """Lazy-load the injected BM25 vocabulary when enabled."""
        if self._bm25 is None:
            if not self.bm25_enabled:
                return None
            if self.bm25_vocab_path.exists():
                self._bm25 = BM25Vectorizer().load(self.bm25_vocab_path)
            else:
                logger.warning(
                    "[BM25] Vocab not found at %s — BM25 disabled",
                    self.bm25_vocab_path,
                )
        return self._bm25

    @property
    def embedder(self):
        if self._embedder is None:
            import os
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            logger.info(f"[Load] Embedding model: {self.embedding_model_name} ...")
            t0 = time.time()
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
            self._embedder = EmbeddingModel(
                self.embedding_model_name,
                device=device,
                native_sparse=self.native_sparse,
            )
            logger.info(f"[Load] Embedding model ready ({time.time()-t0:.1f}s)")
        return self._embedder

    def check_health(self) -> Tuple[bool, str]:
        """
        Check if Qdrant vector database is available.

        Returns:
            Tuple of (is_available, status_message)
        """
        try:
            self.client.get_collections()
            self._qdrant_available = True
            self._qdrant_failure_at = 0.0
            return True, "Qdrant is healthy"
        except Exception as e:
            self._mark_qdrant_unavailable()
            return False, f"Qdrant connection failed: {str(e)}"

    def _mark_qdrant_unavailable(self) -> None:
        self._qdrant_available = False
        self._qdrant_failure_at = time.monotonic()

    def semantic_backend_available(self, retry_after_seconds: float = 2.0) -> bool:
        """Fast-fail a recently confirmed outage, then allow one recovery probe."""
        if self._qdrant_available is None:
            return self.check_health()[0]
        if self._qdrant_available is True:
            return True
        failure_at = float(getattr(self, "_qdrant_failure_at", 0.0) or 0.0)
        if time.monotonic() - failure_at < retry_after_seconds:
            return False
        return self.check_health()[0]

    def get_health(self) -> RetrievalHealth:
        """Return a typed backend and managed-collection health snapshot."""
        try:
            response = self.client.get_collections()
            existing = {c.name for c in response.collections}
        except Exception as e:
            self._mark_qdrant_unavailable()
            return RetrievalHealth(
                status="unavailable",
                qdrant_connected=False,
                message=f"Qdrant connection failed: {e}",
            )

        self._qdrant_available = True
        self._qdrant_failure_at = 0.0

        collections: dict[str, int] = {}
        missing_collections: list[str] = []
        total = 0
        for name in self._ALL_MANAGED_COLLECTIONS:
            if name in existing:
                try:
                    info = self.client.get_collection(name)
                    count = info.points_count or 0
                    collections[name] = count
                    total += count
                except Exception:
                    collections[name] = -1
            else:
                missing_collections.append(name)

        if missing_collections:
            status = "degraded"
            message = (
                f"{len(missing_collections)} collection(s) missing: "
                f"{', '.join(missing_collections)}"
            )
        elif total == 0:
            status = "degraded"
            message = "All collections exist but contain 0 documents"
        else:
            status = "healthy"
            message = f"{len(collections)} collections, {total} documents"

        return RetrievalHealth(
            status=status,
            qdrant_connected=True,
            message=message,
            collections=collections,
            total_documents=total,
            missing_collections=tuple(missing_collections),
        )

    def health_check(self) -> Dict[str, Any]:
        """Compatibility wrapper for callers expecting the historical dict."""
        health = self.get_health()
        return {
            "status": health.status,
            "qdrant_connected": health.qdrant_connected,
            "collections": dict(health.collections),
            "total_documents": health.total_documents,
            "missing_collections": list(health.missing_collections),
            "message": health.message,
        }

    def compute_adaptive_threshold(self, results: List[SearchResult]) -> float:
        """
        Compute adaptive score threshold based on result distribution.

        Strategy:
            - If few results (< 3): use minimum threshold
            - Otherwise: use mean - 0.5 * std_dev as cutoff
            - Never go below MIN_SCORE_THRESHOLD
        """
        if len(results) < 3:
            return self.MIN_SCORE_THRESHOLD

        scores = [r.score for r in results]
        mean_score = statistics.mean(scores)
        std_dev = statistics.stdev(scores) if len(scores) > 1 else 0

        threshold = mean_score - (0.5 * std_dev)
        return max(self.MIN_SCORE_THRESHOLD, min(threshold, mean_score))

    @property
    def reranker(self):
        """Lazy-load cross-encoder reranker model on first use.

        Uses sentence-transformers CrossEncoder (compatible with Python 3.14)
        instead of FlagEmbedding FlagReranker which requires older Python.
        """
        if not hasattr(self, "_reranker") or self._reranker is None:
            from sentence_transformers import CrossEncoder
            logger.info(f"[Load] Reranker: {self.reranker_model} ...")
            t0 = time.time()
            self._reranker = CrossEncoder(self.reranker_model)
            logger.info(f"[Load] Reranker ready ({time.time()-t0:.1f}s)")
        return self._reranker

    def _rerank_with_cross_encoder(
        self,
        query: str,
        results: List[SearchResult]
    ) -> List[SearchResult]:
        """
        Rerank results using cross-encoder (joint query-document scoring).

        Cross-encoders see both query and document together, capturing interaction
        signals that independent bi-encoder embeddings miss. Typical accuracy
        improvement: +0.1 to +0.2 on precision@k.

        Args:
            query: Original user query
            results: Candidates to rerank (typically top-k from RRF)

        Returns:
            Results reordered by cross-encoder relevance score
        """
        if not self.reranker_enabled or not results:
            return results

        pairs = [[query, r.text] for r in results]
        scores = self.reranker.predict(pairs).tolist()

        reranked = sorted(
            zip(results, scores),
            key=lambda x: x[1],
            reverse=True
        )
        return [SearchResult(
            text=r.text,
            score=float(score),
            source=r.source,
            metadata={**r.metadata, "reranker_score": float(score),
                      "original_score": r.score}
        ) for r, score in reranked]

    def filter_by_adaptive_threshold(
        self,
        results: List[SearchResult],
        min_results: int = 2
    ) -> List[SearchResult]:
        """
        Filter results using adaptive threshold while ensuring minimum results.

        This is the primary method for handling irrelevant semantic search results.
        It removes low-scoring chunks that are likely irrelevant while preserving
        a minimum number of results for context.

        Args:
            results: List of search results to filter
            min_results: Minimum number of results to keep (default: 2)

        Returns:
            Filtered list of SearchResults

        Example:
            >>> results = retriever.search_all_with_rerank(query)
            >>> # Remove likely irrelevant chunks
            >>> filtered = retriever.filter_by_adaptive_threshold(results)
        """
        if len(results) <= min_results:
            return results

        threshold = self.compute_adaptive_threshold(results)
        filtered = [r for r in results if r.score >= threshold]

        # Ensure minimum results
        if len(filtered) < min_results:
            sorted_results = sorted(results, key=lambda x: x.score, reverse=True)
            filtered = sorted_results[:min_results]

        _trace(f"{len(results)} → {len(filtered)} (threshold {threshold:.2f})", "filter")

        # Trace dropped items by collection
        kept_ids = set(id(r) for r in filtered)
        dropped = [r for r in results if id(r) not in kept_ids]
        if dropped:
            drop_by_coll: dict[str, list[float]] = {}
            for r in dropped:
                drop_by_coll.setdefault(r.source, []).append(r.score)
            drop_parts = [
                f"{c}×{len(v)}(max {max(v):.2f})" for c, v in drop_by_coll.items()
            ]
            _trace(f"Dropped: {' '.join(drop_parts)}", "filter_drop")

        return filtered

    def search_collection(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.5,
        query_filter: Any = None,
    ) -> List[SearchResult]:
        """Search a single collection.

        When BM25 is enabled and its vocabulary is loaded: uses Qdrant prefetch + RRF
        fusion over both dense and sparse vectors.
        Otherwise: plain dense vector search (legacy).
        """
        query_vector = self.embedder.encode_single(query)
        use_native_sparse = self.embedder._is_bge_m3_native

        try:
            if use_native_sparse or (self.bm25_enabled and self.bm25 is not None):
                from qdrant_client.models import Prefetch, FusionQuery, Fusion, SparseVector
                if use_native_sparse:
                    sv = self.embedder.encode_sparse([query])[0]
                else:
                    sv = self.bm25.encode(query)
                response = self.client.query_points(
                    collection_name=collection_name,
                    prefetch=[
                        Prefetch(
                            query=query_vector,
                            using="dense",
                            filter=query_filter,
                            limit=top_k * 2,
                        ),
                        Prefetch(
                            query=SparseVector(
                                indices=list(sv.keys()),
                                values=list(sv.values()),
                            ),
                            using="sparse",
                            filter=query_filter,
                            limit=top_k * 2,
                        ),
                    ],
                    query=FusionQuery(fusion=Fusion.RRF),
                    query_filter=query_filter,
                    limit=top_k,
                )
            else:
                response = self.client.query_points(
                    collection_name=collection_name,
                    query=query_vector,
                    using="dense",
                    query_filter=query_filter,
                    limit=top_k,
                    score_threshold=score_threshold,
                )
            results = response.points
        except Exception as e:
            logger.warning("Search error in %s: %s", collection_name, e)
            self._mark_qdrant_unavailable()
            return []

        return [
            SearchResult(
                text=r.payload.get("text", ""),
                score=r.score,
                source=collection_name,
                metadata={k: v for k, v in r.payload.items() if k != "text"}
            )
            for r in results
        ]

    # Compatibility class attributes, derived from the typed data catalog.
    _COLLECTION_DEFAULTS: Dict[str, tuple[int, float]] = {
        spec.key: (spec.default_top_k, spec.score_threshold)
        for spec in COLLECTION_CATALOG.collections
    }
    _DEFAULT_FANOUT_COLLECTIONS: Tuple[str, ...] = tuple(
        spec.key
        for spec in COLLECTION_CATALOG.collections
        if spec.default_fanout
    )
    _COLL_WEIGHTS: Dict[str, float] = {
        spec.key: spec.fusion_weight
        for spec in COLLECTION_CATALOG.collections
    }
    _COLLECTION_NAMES: Dict[str, str] = {
        spec.key: spec.name
        for spec in COLLECTION_CATALOG.collections
    }
    _ALL_MANAGED_COLLECTIONS: Tuple[str, ...] = tuple(
        spec.name
        for spec in COLLECTION_CATALOG.collections
    )

    def _search(
        self,
        key: str,
        query: str,
        top_k: int | None = None,
        score_threshold: float | None = None,
        query_filter: Any = None,
    ) -> List[SearchResult]:
        """Search a named collection using its registered defaults."""
        default_top_k, default_threshold = self._COLLECTION_DEFAULTS[key]
        return self.search_collection(
            self._COLLECTION_NAMES[key],
            query,
            top_k if top_k is not None else default_top_k,
            score_threshold if score_threshold is not None else default_threshold,
            query_filter=query_filter,
        )

    def search_collections(
        self,
        query: str,
        collection_keys: List[str],
        top_k: int = 10,
    ) -> List[SearchResult]:
        """Search explicit collections through a stable public adapter method.

        The wider candidate pool allows exact identity deduplication to backfill
        duplicate chunks without exposing ``_search`` or backend health state to
        application orchestration.
        """
        candidates: List[SearchResult] = []
        candidate_limit = max(top_k * 3, top_k)
        for key in collection_keys:
            if key not in self._COLLECTION_DEFAULTS:
                raise ValueError(f"Unknown collection: {key}")
            if self._qdrant_available is False:
                break
            candidates.extend(self._search(key, query, top_k=candidate_limit))
        ordered = sorted(candidates, key=lambda item: item.score, reverse=True)
        return deduplicate_results(ordered)[:top_k]

    def search_guide(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search guide documentation (getting started, tips, overview)"""
        return self._search("guide", query, top_k)

    def search_interface(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search interface documentation (editor UI, dialogs, debugger)"""
        return self._search("interface", query, top_k)

    def search_project(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search project primitives (events, objects, timelines)"""
        return self._search("project", query, top_k)

    def search_plugins(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search plugin reference documentation"""
        return self._search("plugins", query, top_k)

    def search_behaviors(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search behavior reference documentation"""
        return self._search("behaviors", query, top_k)

    def search_scripting(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search scripting API documentation"""
        return self._search("scripting", query, top_k)

    def search_terms(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """Search translation terms"""
        return self._search("terms", query, top_k)

    def search_examples(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search example projects"""
        return self._search("examples", query, top_k)

    def search_ace(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search ACE schema (Actions/Conditions/Expressions per plugin)"""
        return self._search("ace", query, top_k)

    def search_effects(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search effect definitions (blur, glow, blend modes, etc.)"""
        return self._search("effects", query, top_k)

    def search_plugin_by_name(
        self,
        query: str,
        plugin_en: str,
        section_types: List[str] | None = None,
        top_k: int = 5,
        score_threshold: float = 0.3,
    ) -> List[SearchResult]:
        """Search plugins collection filtered by plugin name + ACE type, ranked by query semantics.

        Args:
            query: User's original query (for semantic ranking)
            plugin_en: Plugin English name (e.g. "Array")
            section_types: ACE type filter, e.g. ["conditions", "expressions"].
                           None means no section_type filter.
            top_k: Number of results per search
            score_threshold: Minimum similarity score
        """
        from qdrant_client.models import Filter, FieldCondition, MatchAny, MatchValue
        collection = self._COLLECTION_NAMES["plugins"]
        query_vector = self.embedder.encode_single(query)

        # h1_heading is the canonical plugin title on every chunk.  Exact
        # matching avoids substring leaks such as Sprite -> Sprite Font.
        must_conditions = [
            FieldCondition(key="h1_heading", match=MatchValue(value=plugin_en))
        ]
        # If section_types specified, add OR filter
        if section_types:
            # Explicit OR inside a mandatory condition.  A top-level should
            # next to must is not a reliable mandatory filter contract.
            must_conditions.append(
                FieldCondition(
                    key="section_type",
                    match=MatchAny(any=list(section_types)),
                )
            )
        query_filter = Filter(must=must_conditions)

        try:
            response = self.client.query_points(
                collection_name=collection,
                query=query_vector,
                using="dense",
                query_filter=query_filter,
                limit=top_k,
                score_threshold=score_threshold,
            )
            results = [
                SearchResult(
                    text=r.payload.get("text", ""),
                    score=r.score,
                    source=collection,
                    metadata={k: v for k, v in r.payload.items() if k != "text"}
                )
                for r in response.points
            ]
            if results:
                types_found = {r.metadata.get("section_type", "general") for r in results}
                logger.info(
                    f"[PluginSearch] {plugin_en} section_types={section_types} "
                    f"→ {len(results)} hits ({', '.join(str(t) for t in types_found)})"
                )
            return results
        except Exception as e:
            self._mark_qdrant_unavailable()
            logger.warning(f"[Search] search_plugin_by_name({plugin_en}) failed: {e}")
            return []

    def search_by_section_types(
        self,
        query: str,
        section_types: List[str],
        top_k: int = 10,
        collection_keys: List[str] | None = None,
    ) -> List[SearchResult]:
        """Search only payloads whose section_type matches the requested OR set."""
        from qdrant_client.models import FieldCondition, Filter, MatchAny

        query_filter = Filter(
            must=[
                FieldCondition(
                    key="section_type",
                    match=MatchAny(any=list(section_types)),
                )
            ]
        )
        keys = collection_keys or ["plugins", "behaviors", "addon_sdk"]
        candidates: List[SearchResult] = []
        candidate_limit = max(top_k * 3, top_k)
        for key in keys:
            if getattr(self, "_qdrant_available", None) is False:
                break
            candidates.extend(
                self._search(
                    key,
                    query,
                    top_k=candidate_limit,
                    query_filter=query_filter,
                )
            )
        ordered = sorted(candidates, key=lambda result: result.score, reverse=True)
        return deduplicate_results(ordered)[:top_k]

    def search_all_with_rerank(
        self,
        query: str,
        top_k_per_collection: int = 5,
        final_top_k: int = 10,
        exclude_collections: set | None = None,
    ) -> List[SearchResult]:
        """
        Search all collections with cross-collection reranking.

        Args:
            query: Search query
            top_k_per_collection: Results per collection before reranking
            final_top_k: Final number of results after reranking
            exclude_collections: Collection keys to skip (e.g. {"terms"})

        Returns:
            Reranked list of SearchResults
        """
        return self._search_single_query(
            query, top_k_per_collection, final_top_k, exclude_collections
        )

    def _search_single_query(
        self,
        query: str,
        top_k_per_collection: int = 5,
        final_top_k: int = 10,
        exclude_collections: set | None = None,
    ) -> List[SearchResult]:
        """Core retrieval for a single query: weighted RRF + optional reranker."""
        # Guard: hard-cap query length to protect embedding quality.
        _MAX_QUERY_CHARS = 500
        if len(query) > _MAX_QUERY_CHARS:
            logger.warning(f"[Search] Query truncated {len(query)} → {_MAX_QUERY_CHARS} chars")
            query = query[:_MAX_QUERY_CHARS]

        logger.info(f"[Search] Multi-collection search (per-collection top_k={top_k_per_collection})...")
        t0 = time.time()

        result_lists: List[List[SearchResult]] = []
        weights: List[float] = []
        # Track per-collection best result for diversity guarantee
        coll_best: Dict[str, SearchResult] = {}

        coll_hit_summaries = []
        _exclude = exclude_collections or set()
        for coll_name in self._DEFAULT_FANOUT_COLLECTIONS:
            if getattr(self, "_qdrant_available", None) is False:
                break
            if coll_name in _exclude:
                continue
            try:
                results = self._search(coll_name, query, top_k_per_collection)
                logger.info(f"[Search] {coll_name}: {len(results)} hits")
                if results:
                    result_lists.append(results)
                    weights.append(self._COLL_WEIGHTS[coll_name])
                    coll_best[coll_name] = results[0]
                    top_r = max(results, key=lambda r: r.score)
                    max_score = top_r.score
                    src = top_r.metadata.get("source", "")
                    src_name = src.split("/")[-1].replace(".md", "")[:12] if "/" in src else src[:12]
                    hint = f" {src_name}" if src_name else ""
                    coll_hit_summaries.append(f"{coll_name}×{len(results)}({max_score:.2f}{hint})")
            except Exception as e:
                logger.warning(f"[Search] {coll_name} failed: {e}")

        if coll_hit_summaries:
            _trace(' '.join(coll_hit_summaries), "retrieve")

        logger.info(f"[Search] Raw lists: {len(result_lists)} collections ({time.time()-t0:.1f}s)")

        if not result_lists:
            return []

        # Weighted RRF fusion: reference collections contribute more to ranking
        fused = weighted_rrf(result_lists, weights)

        logger.info(f"[Rerank] Weighted RRF: {len(fused)} unique results")

        # Cross-encoder reranking if available
        if self.reranker_enabled:
            candidates = fused[:self.reranker_top_k]
            final_results = [
                *self._rerank_with_cross_encoder(query, candidates),
                *fused[self.reranker_top_k:],
            ]
        else:
            final_results = fused

        # Exact identity dedup keeps distinct H2 chunks/effects/terms/examples
        # while allowing the fused tail to backfill duplicate reranker entries.
        deduped = deduplicate_results(final_results)

        result = deduped[:final_top_k]

        # Diversity guarantee: if a collection had results but none survived
        # reranking, inject its best result at the end. This prevents small
        # collections (e.g. effects with short docs) from being completely
        # overshadowed by verbose reference docs.
        represented = {_collection_key(r.source) for r in result}
        seen_ids = {
            identity
            for item in result
            if (identity := stable_result_id(item)) is not None
        }
        injected = []
        for coll_name, best in coll_best.items():
            if len(result) >= final_top_k:
                break
            if coll_name not in represented:
                identity = stable_result_id(best)
                if identity is not None and identity in seen_ids:
                    continue
                injected.append(coll_name)
                result.append(best)
                represented.add(coll_name)
                if identity is not None:
                    seen_ids.add(identity)
        if injected:
            logger.info(f"[Rerank] Diversity inject: {', '.join(injected)}")

        logger.info(f"[Rerank] Done, returning {len(result)} (deduped from {len(final_results)})")
        return result[:final_top_k]
