"""FastAPI composition root for the optional Construct 3 search service.

The HTTP layer owns routing and dependency construction only.  Request/response
contracts live in :mod:`src.interfaces.http.models`; the searchable SOP lives in
:mod:`src.application.search`.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from src.application.health import build_health_outcome
from src.application.search import (
    InvalidSearchRequestError,
    SearchWorkflow,
    UnknownCollectionError,
    detect_language,
)
from src.config import (
    BGE_M3_NATIVE_SPARSE,
    BM25_ENABLED,
    DATA_DIR,
    EMBEDDING_MODEL,
    LITE_MODE,
    QDRANT_HOST,
    QDRANT_PORT,
    RERANKER_ENABLED,
    RERANKER_MODEL,
    RERANKER_TOP_K,
    SCHEMA_DIR,
)
from src.interfaces.http.models import (
    ACELocaleResult,
    ACEParam,
    DebugInfo,
    DocResult,
    ExampleResult,
    HealthResponse,
    LookupDebug,
    LookupItemResult,
    LookupMatchResult,
    LookupSection,
    PluginInfo,
    SearchRequest,
    SearchResponse,
    SemanticDebug,
    SemanticSection,
    TermResult,
)
from src.interfaces.http.presenters import (
    present_health_outcome,
    present_search_outcome,
    request_to_command,
)
from src.observability.trace import _trace_local

app = FastAPI(
    title="Construct 3 RAG",
    description="Retrieval service for Construct 3 documentation",
    version="1.0.0",
)

_retriever = None
_lookup_engine = None
_PLAYGROUND_HTML = Path(__file__).parent.parent / "tests" / "playground.html"


def _get_retriever():
    """Construct the optional semantic adapter only when a request needs it."""
    global _retriever
    if _retriever is None:
        from src.retrieval.semantic import HybridRetriever

        _retriever = HybridRetriever(
            qdrant_host=QDRANT_HOST,
            qdrant_port=QDRANT_PORT,
            embedding_model_name=EMBEDDING_MODEL,
            bm25_enabled=BM25_ENABLED,
            bm25_vocab_path=DATA_DIR / "bm25_vocab.msgpack",
            native_sparse=BGE_M3_NATIVE_SPARSE,
            reranker_enabled=RERANKER_ENABLED,
            reranker_model=RERANKER_MODEL,
            reranker_top_k=RERANKER_TOP_K,
        )
    return _retriever


def _get_lookup_engine():
    """Construct the offline deterministic lookup adapter lazily."""
    global _lookup_engine
    if _lookup_engine is None:
        from src.lookup import LookupEngine

        _lookup_engine = LookupEngine(schema_dir=SCHEMA_DIR)
    return _lookup_engine


def _search_workflow() -> SearchWorkflow:
    """Bind current runtime settings and lazy providers to one request workflow."""
    return SearchWorkflow(
        get_lookup_engine=_get_lookup_engine,
        get_retriever=_get_retriever,
        lite_mode=LITE_MODE,
    )


@app.get("/playground")
def playground() -> Response:
    """Serve the lightweight API playground without caching it."""
    return Response(
        content=_PLAYGROUND_HTML.read_text(encoding="utf-8"),
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return present_health_outcome(
        build_health_outcome(
            lite_mode=LITE_MODE,
            schema_dir=SCHEMA_DIR,
            embedding_model=EMBEDDING_MODEL,
            get_retriever=_get_retriever,
        )
    )


@app.post("/search", response_model=SearchResponse, response_model_exclude_none=True)
def search(request: SearchRequest) -> SearchResponse:
    _trace_local.events = []
    try:
        outcome = _search_workflow().execute(request_to_command(request))
        return present_search_outcome(outcome)
    except UnknownCollectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except InvalidSearchRequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# Compatibility alias for callers that imported the previous private helper.
_detect_lang = detect_language


__all__ = [
    "app",
    "SearchRequest",
    "SearchResponse",
    "HealthResponse",
    "PluginInfo",
    "ACEParam",
    "DocResult",
    "TermResult",
    "ExampleResult",
    "ACELocaleResult",
    "LookupMatchResult",
    "LookupItemResult",
    "LookupSection",
    "LookupDebug",
    "SemanticDebug",
    "SemanticSection",
    "DebugInfo",
]
