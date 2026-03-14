"""
Construct 3 RAG — FastAPI retrieval service.

Endpoints:
    GET  /health    — Qdrant + embedding model status
    POST /search    — Unified retrieval: lookup first, then semantic search
"""
import time
import logging
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.config import QDRANT_HOST, QDRANT_PORT, EMBEDDING_MODEL

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Construct 3 RAG",
    description="Retrieval service for Construct 3 documentation",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Lazy-loaded singletons
# ---------------------------------------------------------------------------
_retriever = None
_lookup_engine = None


def _get_retriever():
    global _retriever
    if _retriever is None:
        from src.rag.retriever import HybridRetriever
        _retriever = HybridRetriever(
            qdrant_host=QDRANT_HOST,
            qdrant_port=QDRANT_PORT,
            embedding_model_name=EMBEDDING_MODEL,
        )
    return _retriever


def _get_lookup_engine():
    global _lookup_engine
    if _lookup_engine is None:
        from src.rag.lookup import LookupEngine
        _lookup_engine = LookupEngine()
    return _lookup_engine


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str = Field(..., max_length=500, description="Search query")
    top_k: int = Field(10, ge=1, le=50, description="Max results to return")
    collections: Optional[List[str]] = Field(
        None, description="Limit search to specific collections (e.g. ['plugins', 'ace'])"
    )
    plugin: Optional[str] = Field(
        None, description="Filter by plugin name (e.g. 'Sprite')"
    )
    section_types: Optional[List[str]] = Field(
        None, description="Filter by section type (e.g. ['actions', 'conditions'])"
    )
    apply_threshold: bool = Field(
        True, description="Apply adaptive score threshold filtering"
    )
    skip_lookup: bool = Field(
        False, description="Skip lookup, go directly to semantic search"
    )


class SearchResultItem(BaseModel):
    text: str
    score: float
    collection: str
    source: str
    metadata: dict


class LookupDetail(BaseModel):
    intent: str
    query_type: str
    intent_detail: dict


class SearchDiagnostics(BaseModel):
    route: str  # "lookup" | "semantic" | "plugin_filter" | "collection_filter"
    total_candidates: int
    after_rerank: int
    after_threshold: int
    latency_ms: float
    lookup_detail: Optional[LookupDetail] = None


class SearchResponse(BaseModel):
    results: List[SearchResultItem]
    diagnostics: SearchDiagnostics


class HealthResponse(BaseModel):
    status: str
    qdrant: bool
    embedding_model: str
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collection_key(source_name: str) -> str:
    from src.collections import COLLECTIONS
    for key, name in COLLECTIONS.items():
        if name == source_name:
            return key
    return source_name


def _try_lookup(query: str):
    """Try structured lookup. Returns (LookupResponse, LookupDetail) or (None, None)."""
    try:
        engine = _get_lookup_engine()
        result = engine.try_lookup(query)
    except Exception as e:
        logger.warning(f"Lookup failed: {e}")
        return None, None

    if result is None:
        return None, None

    detail = LookupDetail(
        intent=result.intent.intent_type,
        query_type=result.query_type,
        intent_detail={
            "intent_type": result.intent.intent_type,
            "plugin_id": result.intent.plugin_id,
            "ace_type": result.intent.ace_type,
            "ace_name": result.intent.ace_name,
            "term": result.intent.term,
            "tier": result.intent.tier,
            "is_behavior": result.intent.is_behavior,
        },
    )
    return result, detail


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def health():
    retriever = _get_retriever()
    ok, msg = retriever.check_health()
    return HealthResponse(
        status="ok" if ok else "degraded",
        qdrant=ok,
        embedding_model=EMBEDDING_MODEL,
        message=msg,
    )


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    t0 = time.time()

    # ── Step 1: Try lookup (unless skipped or filters are set) ──────────
    use_lookup = not req.skip_lookup and not req.plugin and not req.collections
    if use_lookup:
        lookup_result, lookup_detail = _try_lookup(req.query)
        if lookup_result is not None:
            latency_ms = (time.time() - t0) * 1000
            return SearchResponse(
                results=[
                    SearchResultItem(
                        text=lookup_result.answer,
                        score=1.0,
                        collection="lookup",
                        source="structured",
                        metadata={},
                    )
                ],
                diagnostics=SearchDiagnostics(
                    route="lookup",
                    total_candidates=1,
                    after_rerank=1,
                    after_threshold=1,
                    latency_ms=round(latency_ms, 1),
                    lookup_detail=lookup_detail,
                ),
            )

    # ── Step 2: Semantic search ─────────────────────────────────────────
    retriever = _get_retriever()

    # Branch: plugin-specific filtered search
    if req.plugin:
        results = retriever.search_plugin_by_name(
            query=req.query,
            plugin_en=req.plugin,
            section_types=req.section_types,
            top_k=req.top_k,
        )
        total = len(results)
        after_rerank = total
        route = "plugin_filter"

    # Branch: collection-scoped search
    elif req.collections:
        from src.collections import COLLECTIONS
        all_results: list = []
        for coll_key in req.collections:
            if coll_key not in COLLECTIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown collection: {coll_key}. "
                           f"Valid: {list(COLLECTIONS.keys())}",
                )
            coll_results = retriever._search(coll_key, req.query, top_k=req.top_k)
            all_results.extend(coll_results)
        # Dedup + sort
        seen = set()
        results = []
        for r in sorted(all_results, key=lambda x: x.score, reverse=True):
            key = r.text[:100].lower().strip()
            if key not in seen:
                seen.add(key)
                results.append(r)
        results = results[:req.top_k]
        total = len(all_results)
        after_rerank = len(results)
        route = "collection_filter"

    # Default: full cross-collection search with rerank
    else:
        results = retriever.search_all_with_rerank(
            query=req.query,
            top_k_per_collection=5,
            final_top_k=req.top_k,
        )
        total = len(results)
        after_rerank = total
        route = "semantic"

    # Adaptive threshold filtering
    after_threshold = len(results)
    if req.apply_threshold and results:
        results = retriever.filter_by_adaptive_threshold(results)
        after_threshold = len(results)

    latency_ms = (time.time() - t0) * 1000

    return SearchResponse(
        results=[
            SearchResultItem(
                text=r.text,
                score=round(r.score, 4),
                collection=_collection_key(r.source),
                source=r.metadata.get("source", ""),
                metadata={k: v for k, v in r.metadata.items() if k != "source"},
            )
            for r in results
        ],
        diagnostics=SearchDiagnostics(
            route=route,
            total_candidates=total,
            after_rerank=after_rerank,
            after_threshold=after_threshold,
            latency_ms=round(latency_ms, 1),
        ),
    )
