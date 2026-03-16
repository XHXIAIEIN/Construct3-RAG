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

from pathlib import Path
from fastapi.responses import HTMLResponse

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
_fetcher = None


def _get_fetcher():
    """Lazy-init CDN fetcher. Ensures schemas are exported on first call."""
    global _fetcher
    if _fetcher is None:
        from src.config import C3_VERSION, C3_CDN_BASE, C3_CACHE_DIR
        from src.ingest.c3_fetcher import C3Fetcher
        _fetcher = C3Fetcher(version=C3_VERSION, base_url=C3_CDN_BASE, cache_dir=C3_CACHE_DIR)
        _fetcher.ensure_ready()
    return _fetcher


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
        fetcher = _get_fetcher()
        _lookup_engine = LookupEngine(terms=fetcher.export_terms())
    return _lookup_engine


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str = Field(..., max_length=500, description="Search query")
    top_k: int = Field(10, ge=1, le=50, description="Max results to return")
    lang: Optional[str] = Field(
        None,
        description="Language hint: 'zh'/'ja'/'ko' includes terms collection (bilingual), "
                    "'en' skips terms. Auto-detected from query characters if omitted.",
    )
    collections: Optional[List[str]] = Field(
        None, description="Limit search to specific collections (e.g. ['plugins', 'ace'])"
    )
    plugin: Optional[str] = Field(
        None, description="Filter by plugin name (e.g. 'Sprite')"
    )
    section_types: Optional[List[str]] = Field(
        None, description="Filter by section type (e.g. ['actions', 'conditions'])"
    )
    debug: bool = Field(
        False, description="Include trace log in diagnostics"
    )
    apply_threshold: bool = Field(
        True, description="Apply adaptive score threshold filtering"
    )
    skip_lookup: bool = Field(
        False, description="Skip lookup, go directly to semantic search"
    )


# ── Result types (discriminated by "type" field) ──

class PluginInfo(BaseModel):
    id: str
    name: str
    name_zh: str = ""

class ACEParam(BaseModel):
    name: str
    name_zh: str = ""
    type: str = "any"
    desc: str = ""

class ACEResult(BaseModel):
    type: str = "ace"
    score: float
    plugin: PluginInfo
    ace_type: str  # condition | action | expression
    id: str
    name: str
    name_zh: str = ""
    description: str = ""
    description_zh: str = ""
    script_name: str = ""
    params: List[ACEParam] = []
    is_trigger: bool = False
    is_async: bool = False
    return_type: Optional[str] = None
    category: str = ""

class DocResult(BaseModel):
    type: str = "doc"
    score: float
    source: str
    collection: str
    title: str = ""
    section: str = ""
    content: str

class ExampleResult(BaseModel):
    type: str = "example"
    score: float
    source: str
    project: str = ""
    project_zh: str = ""
    content: str

class TermResult(BaseModel):
    type: str = "term"
    score: float
    zh: str
    en: str
    category: str = ""

class LookupResult(BaseModel):
    type: str = "lookup"
    score: float = 1.0
    intent: str
    plugin: str = ""
    content: str

class TraceStep(BaseModel):
    phase: str
    message: str

class SearchResponse(BaseModel):
    query: str
    lang: str
    route: str
    latency_ms: float
    results: list  # mixed types: ACEResult | DocResult | ExampleResult | TermResult | LookupResult
    trace: List[TraceStep] = []


class HealthResponse(BaseModel):
    status: str
    qdrant: bool
    embedding_model: str
    message: str
    collections: dict = {}
    total_documents: int = 0
    missing_collections: list = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_lang(query: str) -> str:
    """Detect query language from character ranges.

    Returns 'zh' for Chinese, 'ja' for Japanese, 'ko' for Korean,
    'en' for Latin-only text.
    """
    for ch in query:
        cp = ord(ch)
        # CJK Unified Ideographs (shared by zh/ja/ko, default to zh)
        if 0x4e00 <= cp <= 0x9fff:
            return "zh"
        # Hiragana / Katakana → Japanese
        if 0x3040 <= cp <= 0x30ff:
            return "ja"
        # Hangul → Korean
        if 0xac00 <= cp <= 0xd7af or 0x1100 <= cp <= 0x11ff:
            return "ko"
    return "en"


# terms collection contains bilingual translation pairs —
# only useful when query is in a non-English language
_TERMS_USEFUL_LANGS = {"zh", "ja", "ko"}


_PLAYGROUND_HTML = Path(__file__).parent.parent / "playground.html"


@app.get("/playground", response_class=HTMLResponse)
def playground():
    """Interactive API Playground UI."""
    return _PLAYGROUND_HTML.read_text(encoding="utf-8")


def _collection_key(source_name: str) -> str:
    from src.collections import COLLECTIONS
    for key, name in COLLECTIONS.items():
        if name == source_name:
            return key
    return source_name


def _convert_result(r, score_override=None) -> dict:
    """Convert internal SearchResult to typed response dict."""
    score = score_override if score_override is not None else round(r.score, 4)
    meta = r.metadata
    source = meta.get("source", r.source)
    collection = _collection_key(r.source)

    # ACE results (from c3_ace collection)
    if collection == "ace" and meta.get("ace_type"):
        return ACEResult(
            score=score,
            plugin=PluginInfo(
                id=meta.get("plugin_name", ""),
                name=meta.get("plugin_name_en", meta.get("plugin_name", "")),
                name_zh=meta.get("plugin_name_zh", ""),
            ),
            ace_type=meta.get("ace_type", ""),
            id=meta.get("ace_id", ""),
            name=meta.get("name_en", ""),
            name_zh=meta.get("name_zh", ""),
            description=meta.get("description_en", "") if meta.get("description_en") else "",
            description_zh=meta.get("description_zh", "") if meta.get("description_zh") else "",
            script_name=meta.get("script_name", ""),
            is_trigger=meta.get("is_trigger", False),
            is_async=meta.get("is_async", False),
            return_type=meta.get("return_type") or None,
            category=meta.get("category", ""),
        ).model_dump()

    # Example results
    if collection == "examples":
        return ExampleResult(
            score=score,
            source=source,
            project=meta.get("title_en", meta.get("slug", "")),
            project_zh=meta.get("title_zh", ""),
            content=r.text,
        ).model_dump()

    # Term results
    if collection == "terms":
        return TermResult(
            score=score,
            zh=meta.get("zh", ""),
            en=meta.get("en", ""),
            category=meta.get("category", ""),
        ).model_dump()

    # Doc results (plugins, behaviors, guide, interface, project, scripting)
    return DocResult(
        score=score,
        source=source,
        collection=collection,
        title=meta.get("h1_heading", meta.get("title", "")),
        section=meta.get("h2_heading", meta.get("section_type", "")),
        content=r.text,
    ).model_dump()


def _try_lookup(query: str):
    """Try structured lookup. Returns LookupResponse or None."""
    try:
        engine = _get_lookup_engine()
        result = engine.try_lookup(query)
    except Exception as e:
        logger.warning(f"Lookup failed: {e}")
        return None

    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def health():
    retriever = _get_retriever()
    detail = retriever.health_check()
    return HealthResponse(
        status=detail["status"],
        qdrant=detail["qdrant_connected"],
        embedding_model=EMBEDDING_MODEL,
        message=detail["message"],
        collections=detail["collections"],
        total_documents=detail["total_documents"],
        missing_collections=detail["missing_collections"],
    )


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    t0 = time.time()

    # Initialize trace collection for this request
    from src.rag._trace import _trace_local, _trace
    _trace_local.events = []
    _trace(f"query: {req.query[:60]}", "input")

    # ── Step 1: Try lookup (unless skipped or filters are set) ──────────
    lookup_answer = None
    lookup_intent = None
    lookup_plugin = ""
    use_lookup = not req.skip_lookup and not req.plugin and not req.collections
    if use_lookup:
        _trace("尝试 lookup 直查...", "lookup")
        lookup_result = _try_lookup(req.query)
        if lookup_result is not None:
            lookup_answer = lookup_result.answer
            lookup_intent = lookup_result.intent.intent_type
            lookup_plugin = lookup_result.intent.plugin_id or ""
            _trace(f"lookup 命中: {lookup_intent}，继续语义搜索补充", "lookup")
        else:
            _trace("lookup 未命中，转语义搜索", "lookup")

    # ── Step 2: Semantic search (always runs) ─────────────────────────
    retriever = _get_retriever()

    # Branch: plugin-specific filtered search
    if req.plugin:
        _trace(f"插件过滤: {req.plugin} types={req.section_types}", "search")
        results = retriever.search_plugin_by_name(
            query=req.query,
            plugin_en=req.plugin,
            section_types=req.section_types,
            top_k=req.top_k,
        )
        total = len(results)
        after_rerank = total
        route = "plugin_filter"
        _trace(f"返回 {total} 条结果", "search")

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
        lang = req.lang or _detect_lang(req.query)
        exclude = {"terms"} if lang not in _TERMS_USEFUL_LANGS else None
        _trace(f"语义搜索: lang={lang}, exclude={exclude or 'none'}", "search")

        results = retriever.search_all_with_rerank(
            query=req.query,
            top_k_per_collection=5,
            final_top_k=req.top_k,
            exclude_collections=exclude,
        )
        total = len(results)
        after_rerank = total
        route = "semantic"

    _trace(f"检索完成: {total} 候选, rerank 后 {after_rerank}", "search")

    # Adaptive threshold filtering
    after_threshold = len(results)
    if req.apply_threshold and results:
        results = retriever.filter_by_adaptive_threshold(results)
        after_threshold = len(results)
        _trace(f"阈值过滤: {after_rerank} → {after_threshold}", "filter")

    latency_ms = (time.time() - t0) * 1000
    _trace(f"完成: {after_threshold} 条结果, {latency_ms:.0f}ms", "done")

    detected_lang = req.lang or _detect_lang(req.query)

    # Merge: lookup result (if any) goes first, then semantic results
    result_items = []
    if lookup_answer:
        result_items.append(LookupResult(
            intent=lookup_intent or "",
            plugin=lookup_plugin,
            content=lookup_answer,
        ).model_dump())
        route = "lookup+semantic"

    for r in results:
        result_items.append(_convert_result(r))

    result_items = result_items[:req.top_k]

    return SearchResponse(
        query=req.query,
        lang=detected_lang,
        route=route,
        latency_ms=round(latency_ms, 1),
        results=result_items,
        trace=[TraceStep(phase=p, message=m) for p, m in getattr(_trace_local, 'events', [])] if req.debug else [],
    )
