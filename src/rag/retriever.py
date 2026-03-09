"""
Hybrid Retriever for Construct 3 RAG
Combines vector search with optional BM25 for better results

Features:
- Semantic similarity search via Qdrant
- Cross-collection reranking with score normalization
- Adaptive score threshold filtering
- Query decomposition for complex multi-step workflows
- Reciprocal Rank Fusion (RRF) for multi-query results
"""
import time
import logging
import statistics
from typing import List, Dict, Any, Set, Tuple
from dataclasses import dataclass

from ._trace import _trace
from src.config import RERANKER_ENABLED, RERANKER_TOP_K, RERANKER_MODEL

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from qdrant_client import QdrantClient
except ImportError:
    print("Warning: qdrant-client not installed")


@dataclass
class SearchResult:
    """Represents a search result"""
    text: str
    score: float
    source: str  # collection name
    metadata: Dict[str, Any]


class HybridRetriever:
    """
    Hybrid retriever combining:
    - Vector search (semantic similarity)
    - Optional keyword matching for terms
    - Adaptive score threshold filtering
    - Query decomposition for complex workflows
    - Reciprocal Rank Fusion (RRF) for multi-query results

    Handling Irrelevant Results:
        Use `filter_by_adaptive_threshold()` to remove low-relevance chunks
        based on score distribution analysis.

    Complex Multi-Step Workflows:
        Use `search_with_decomposition()` which breaks complex queries into
        sub-queries and combines results using RRF.
    """

    # Score threshold configuration
    DEFAULT_SCORE_THRESHOLD = 0.3
    MIN_SCORE_THRESHOLD = 0.2
    HIGH_RELEVANCE_THRESHOLD = 0.6

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        embedding_model_name: str = "BAAI/bge-m3"
    ):
        self.client = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.embedding_model_name = embedding_model_name
        self._embedder = None
        self._qdrant_available = None  # Cache for health check

    @property
    def embedder(self):
        if self._embedder is None:
            import os
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            logger.info(f"[Load] Embedding model: {self.embedding_model_name} ...")
            t0 = time.time()
            from src.ingest.indexer import EmbeddingModel
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
            self._embedder = EmbeddingModel(self.embedding_model_name, device=device)
            logger.info(f"[Load] Embedding model ready ({time.time()-t0:.1f}s)")
        return self._embedder

    def check_health(self) -> Tuple[bool, str]:
        """
        Check if Qdrant vector database is available.

        Returns:
            Tuple of (is_available, status_message)

        Example:
            >>> retriever = HybridRetriever()
            >>> available, msg = retriever.check_health()
            >>> if not available:
            ...     print(f"Qdrant unavailable: {msg}")
        """
        try:
            # Try to get collections list as health check
            self.client.get_collections()
            self._qdrant_available = True
            return True, "Qdrant is healthy"
        except Exception as e:
            self._qdrant_available = False
            return False, f"Qdrant connection failed: {str(e)}"

    def compute_adaptive_threshold(self, results: List[SearchResult]) -> float:
        """
        Compute adaptive score threshold based on result distribution.

        This helps filter out irrelevant chunks by analyzing the score
        distribution and removing results in the "long tail".

        Args:
            results: List of search results with scores

        Returns:
            Computed threshold score. Results below this should be filtered.

        Strategy:
            - If few results (< 3): use minimum threshold
            - Otherwise: use mean - 0.5 * std_dev as cutoff
            - Never go below MIN_SCORE_THRESHOLD

        Example:
            >>> results = retriever.search_plugins("sprite animation", top_k=10)
            >>> threshold = retriever.compute_adaptive_threshold(results)
            >>> filtered = [r for r in results if r.score >= threshold]
        """
        if len(results) < 3:
            return self.MIN_SCORE_THRESHOLD

        scores = [r.score for r in results]
        mean_score = statistics.mean(scores)
        std_dev = statistics.stdev(scores) if len(scores) > 1 else 0

        # Adaptive threshold: mean - 0.5 * std_dev
        # This keeps results within reasonable range of the mean
        threshold = mean_score - (0.5 * std_dev)

        # Clamp to reasonable bounds
        return max(self.MIN_SCORE_THRESHOLD, min(threshold, mean_score))

    @property
    def reranker(self):
        """Lazy-load cross-encoder reranker model on first use."""
        if not hasattr(self, "_reranker") or self._reranker is None:
            import os
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            from FlagEmbedding import FlagReranker
            logger.info(f"[Load] Reranker: {RERANKER_MODEL} ...")
            self._reranker = FlagReranker(RERANKER_MODEL, use_fp16=True)
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
        if not RERANKER_ENABLED or not results:
            return results

        pairs = [[query, r.text] for r in results]
        scores = self.reranker.compute_score(pairs)

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
            >>> print(f"Kept {len(filtered)}/{len(results)} results")
        """
        if len(results) <= min_results:
            return results

        threshold = self.compute_adaptive_threshold(results)
        filtered = [r for r in results if r.score >= threshold]

        # Ensure minimum results
        if len(filtered) < min_results:
            sorted_results = sorted(results, key=lambda x: x.score, reverse=True)
            filtered = sorted_results[:min_results]

        _trace(f"{len(results)} → {len(filtered)}  (阈值 {threshold:.2f})", "filter")

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
            _trace(f"丢弃: {' '.join(drop_parts)}", "filter_drop")

        return filtered

    def reciprocal_rank_fusion(
        self,
        result_lists: List[List[SearchResult]],
        k: int = 60
    ) -> List[SearchResult]:
        """
        Combine multiple retrieval result lists using Reciprocal Rank Fusion.

        RRF is effective for combining results from different queries or
        retrieval methods. It weights results by their rank position across
        all lists, giving higher weight to consistently high-ranked items.

        Args:
            result_lists: List of result lists to fuse
            k: RRF parameter (default: 60, standard value from literature)

        Returns:
            Fused and deduplicated list of SearchResults, sorted by RRF score

        Formula:
            RRF_score(d) = Σ 1 / (k + rank(d))

        Example:
            >>> # Combine results from original and rewritten queries
            >>> results1 = retriever.search_all_with_rerank("sprite collision")
            >>> results2 = retriever.search_all_with_rerank("detect overlap sprite")
            >>> fused = retriever.reciprocal_rank_fusion([results1, results2])
        """
        # Track RRF scores and best result object for each unique text
        rrf_scores: Dict[str, float] = {}
        result_map: Dict[str, SearchResult] = {}

        for results in result_lists:
            for rank, r in enumerate(results):
                # Use first 150 chars as dedup key
                key = r.text[:150].lower().strip()
                rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (k + rank + 1)

                # Keep the result with highest original score
                if key not in result_map or r.score > result_map[key].score:
                    result_map[key] = r

        # Build final list sorted by RRF score
        fused_results = []
        for key, rrf_score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
            if key in result_map:
                result = result_map[key]
                # Update score to RRF score for transparency
                fused_results.append(SearchResult(
                    text=result.text,
                    score=rrf_score,  # Use RRF score
                    source=result.source,
                    metadata={**result.metadata, "original_score": result.score}
                ))

        return fused_results

    def search_collection(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.5
    ) -> List[SearchResult]:
        """Search a single collection"""
        query_vector = self.embedder.encode_single(query)

        try:
            response = self.client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=top_k,
                score_threshold=score_threshold
            )
            results = response.points
        except Exception as e:
            print(f"Search error in {collection_name}: {e}")
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

    def search_guide(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search guide documentation (getting started, tips, overview)"""
        from src.collections import COLLECTIONS
        return self.search_collection(COLLECTIONS["guide"], query, top_k)

    def search_interface(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search interface documentation (editor UI, dialogs, debugger)"""
        from src.collections import COLLECTIONS
        return self.search_collection(COLLECTIONS["interface"], query, top_k)

    def search_project(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search project primitives (events, objects, timelines)"""
        from src.collections import COLLECTIONS
        return self.search_collection(COLLECTIONS["project"], query, top_k)

    def search_plugins(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search plugin reference documentation"""
        from src.collections import COLLECTIONS
        return self.search_collection(COLLECTIONS["plugins"], query, top_k)

    def search_behaviors(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search behavior reference documentation"""
        from src.collections import COLLECTIONS
        return self.search_collection(COLLECTIONS["behaviors"], query, top_k)

    def search_scripting(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search scripting API documentation"""
        from src.collections import COLLECTIONS
        return self.search_collection(COLLECTIONS["scripting"], query, top_k)

    def search_terms(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """Search translation terms"""
        from src.collections import COLLECTIONS
        return self.search_collection(COLLECTIONS["terms"], query, top_k, score_threshold=0.3)

    def search_examples(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search example projects"""
        from src.collections import COLLECTIONS
        return self.search_collection(COLLECTIONS["examples"], query, top_k)

    def search_ace(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search ACE schema (Actions/Conditions/Expressions per plugin)"""
        from src.collections import COLLECTIONS
        return self.search_collection(COLLECTIONS["ace"], query, top_k, score_threshold=0.3)

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
        from src.collections import COLLECTIONS
        from qdrant_client.models import Filter, FieldCondition, MatchText, MatchValue
        collection = COLLECTIONS["plugins"]
        source_key = plugin_en.lower()
        query_vector = self.embedder.encode_single(query)

        # Build filter: source contains plugin name
        must_conditions = [
            FieldCondition(key="source", match=MatchText(text=source_key))
        ]
        # If section_types specified, add OR filter
        if section_types:
            should_conditions = [
                FieldCondition(key="section_type", match=MatchValue(value=st))
                for st in section_types
            ]
            # Nested Filter: must[source] + should[section_types]
            query_filter = Filter(
                must=must_conditions,
                should=should_conditions,
            )
        else:
            query_filter = Filter(must=must_conditions)

        try:
            response = self.client.query_points(
                collection_name=collection,
                query=query_vector,
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
            logger.warning(f"[Search] search_plugin_by_name({plugin_en}) failed: {e}")
            return []

    def search_all_with_rerank(
        self,
        query: str,
        top_k_per_collection: int = 5,
        final_top_k: int = 10
    ) -> List[SearchResult]:
        """
        Search all collections with cross-collection reranking.

        Args:
            query: Search query
            top_k_per_collection: Results per collection before reranking
            final_top_k: Final number of results after reranking

        Returns:
            Reranked list of SearchResults
        """
        logger.info(f"[Search] Multi-collection search (per-collection top_k={top_k_per_collection})...")
        t0 = time.time()

        # Collect all results from all collections
        all_results: List[SearchResult] = []

        # Define collection mapping
        collection_map = {
            "guide": self.search_guide,
            "interface": self.search_interface,
            "project": self.search_project,
            "plugins": self.search_plugins,
            "behaviors": self.search_behaviors,
            "scripting": self.search_scripting,
            "ace": self.search_ace,
            "terms": self.search_terms,
            "examples": self.search_examples,
        }

        coll_hit_summaries = []
        for coll_name, search_fn in collection_map.items():
            try:
                results = search_fn(query, top_k_per_collection)
                for r in results:
                    all_results.append(r)
                logger.info(f"[Search] {coll_name}: {len(results)} hits")
                if results:
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

        logger.info(f"[Search] Raw results: {len(all_results)} total ({time.time()-t0:.1f}s)")

        if not all_results:
            return []

        # Cross-collection reranking using raw cosine similarity scores.
        # bge-m3 returns comparable cosine similarity scores across collections,
        # so per-collection min-max normalization is not needed and would distort ranking.
        logger.info(f"[Rerank] Cross-collection reranking...")

        reranked: List[SearchResult] = []
        seen_texts: Set[str] = set()  # Deduplication

        for r in all_results:
            # Deduplication by text content
            text_key = r.text[:100].lower().strip()
            if text_key not in seen_texts:
                seen_texts.add(text_key)
                reranked.append(r)

        # Sort by final score and return top-k
        reranked.sort(key=lambda x: x.score, reverse=True)

        # Cross-encoder reranking for more accurate relevance ordering
        if RERANKER_ENABLED:
            candidates = reranked[:RERANKER_TOP_K]
            final_results = self._rerank_with_cross_encoder(query, candidates)
        else:
            final_results = reranked[:final_top_k]

        logger.info(f"[Rerank] Done, returning top-{len(final_results)}")
        return final_results

