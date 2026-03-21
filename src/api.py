"""
Construct 3 RAG — FastAPI retrieval service.

Endpoints:
    GET  /health    — Qdrant + embedding model status
    POST /search    — Unified retrieval: lookup first, then semantic search
"""
import time
import logging
from typing import List, Optional

import jieba
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from pathlib import Path
from fastapi.responses import HTMLResponse

from src.config import QDRANT_HOST, QDRANT_PORT, EMBEDDING_MODEL, LITE_MODE

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
    mode: str = Field(
        "auto",
        pattern="^(auto|lookup|semantic)$",
        description="Execution mode: auto (both), lookup (keyword only), semantic (vector only)",
    )


# ── Result types (discriminated by "type" field) ──

class PluginInfo(BaseModel):
    id: str
    name: str
    name_localized: str = ""  # non-en name, only when lang != en

class ACEParam(BaseModel):
    name: str
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

class ACELocaleResult(BaseModel):
    name: str = ""
    desc: str = ""
    display: str = ""

class LookupMatchResult(BaseModel):
    """Structured ACE/property match from lookup."""
    ace_id: str
    ace_type: str
    plugin_id: str
    en: ACELocaleResult = ACELocaleResult()
    localized: Optional[ACELocaleResult] = None
    script_name: str = ""
    category: str = ""
    relevance: int = 0
    params: List[ACEParam] = []
    is_trigger: bool = False
    is_async: bool = False
    return_type: Optional[str] = None

class LookupSection(BaseModel):
    """Structured lookup results section."""
    hit: bool
    tier: int = 0
    confidence: float = 0.0
    intent: str = ""
    lang: Optional[str] = None  # localized language code (e.g. "zh"), null when en-only
    plugin: Optional[PluginInfo] = None
    keywords: list[str] = []
    matches: List[LookupMatchResult] = []
    context: str = ""   # compact LLM text

class SemanticDebug(BaseModel):
    """Debug info for semantic search phase."""
    collections: dict[str, dict] = {}   # {name: {hits: N, top_score: F}}
    total_candidates: int = 0
    after_dedup: int = 0

class DebugInfo(BaseModel):
    """Structured debug output."""
    timing_ms: dict[str, float] = {}   # {lookup, semantic, total}
    semantic: Optional[SemanticDebug] = None

class SearchResponse(BaseModel):
    query: str
    lang: str
    mode: str              # "auto" | "lookup" | "semantic"
    latency_ms: float
    lookup: Optional[LookupSection] = None   # null when mode=semantic or no hit
    semantic: list = []    # ACEResult | DocResult | ... (empty when mode=lookup)
    debug: Optional[DebugInfo] = None


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


@app.get("/playground")
def playground():
    """Interactive API Playground UI. Always read from disk, no cache."""
    from fastapi.responses import Response
    content = _PLAYGROUND_HTML.read_text(encoding="utf-8")
    return Response(content=content, media_type="text/html",
                    headers={"Cache-Control": "no-store"})


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


def _has_chinese(text: str) -> bool:
    return any(0x4e00 <= ord(ch) <= 0x9fff for ch in text)


def _do_lookup(req: SearchRequest, _trace) -> Optional[LookupSection]:
    """Execute lookup phase. Returns LookupSection or None."""
    use_lookup = not req.plugin and not req.collections
    if not use_lookup:
        return None

    _trace("尝试 lookup 直查...", "lookup")
    lookup_result = _try_lookup(req.query)
    if lookup_result is None:
        _trace("lookup 未命中", "lookup")
        return None

    intent = lookup_result.intent
    _trace(f"lookup 命中: {intent.intent_type} conf={intent.confidence:.2f}", "lookup")

    # Determine language — en is always included, non-en locale is optional
    lang = req.lang or _detect_lang(req.query)
    include_localized = lang != "en"

    def _convert_params(raw_params: list) -> list[ACEParam]:
        return [
            ACEParam(
                name=p.get("name_en") or p.get("name_zh", p.get("id", "")),
                type=p.get("type", "any"),
                desc=p.get("desc_en") or p.get("desc_zh", ""),
            ) for p in raw_params
        ]

    matches = [
        LookupMatchResult(
            ace_id=m.ace_id,
            ace_type=m.ace_type,
            plugin_id=m.plugin_id,
            en=ACELocaleResult(name=m.en.name, desc=m.en.desc, display=m.en.display),
            localized=ACELocaleResult(name=m.zh.name, desc=m.zh.desc, display=m.zh.display) if include_localized else None,
            script_name=m.script_name,
            category=m.category,
            relevance=m.relevance,
            params=_convert_params(m.params),
            is_trigger=m.is_trigger,
            is_async=m.is_async,
            return_type=m.return_type or None,
        ) for m in lookup_result.matches
    ]

    # Keywords from filter_term
    filter_term = intent.filter_term or ""
    if filter_term:
        if _has_chinese(filter_term):
            keywords = [w for w in jieba.lcut(filter_term) if w.strip()]
        else:
            keywords = filter_term.split()
    else:
        keywords = []

    # Resolve plugin info from schema_index if plugin_id is set
    plugin_info: Optional[PluginInfo] = None
    plugin_id = intent.plugin_id or ""
    if plugin_id:
        try:
            engine = _get_lookup_engine()
            schema = engine.schema_index.get_schema(plugin_id, is_behavior=False)
            if schema is None:
                schema = engine.schema_index.get_schema(plugin_id, is_behavior=True)
            if schema:
                plugin_info = PluginInfo(
                    id=plugin_id,
                    name=schema.get("name_en", plugin_id),
                    name_localized=schema.get("name_zh", "") if include_localized else "",
                )
            else:
                plugin_info = PluginInfo(id=plugin_id, name=plugin_id)
        except Exception:
            plugin_info = PluginInfo(id=plugin_id, name=plugin_id)

    return LookupSection(
        hit=True,
        tier=intent.tier,
        confidence=intent.confidence,
        intent=intent.intent_type,
        lang=lang if include_localized else None,
        plugin=plugin_info,
        keywords=keywords,
        matches=matches,
        context=lookup_result.context,
    )


def _do_semantic(req: SearchRequest, _trace) -> list:
    """Execute semantic search phase. Returns list of result dicts."""
    if LITE_MODE:
        return []
    try:
        retriever = _get_retriever()
    except Exception as e:
        logger.warning(f"Semantic search unavailable: {e}")
        return []

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
        _trace(f"collection 过滤: {total} 候选, dedup 后 {after_rerank}", "search")

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
        _trace(f"检索完成: {total} 候选", "search")

    # Adaptive threshold filtering
    if req.apply_threshold and results:
        before = len(results)
        results = retriever.filter_by_adaptive_threshold(results)
        _trace(f"阈值过滤: {before} → {len(results)}", "filter")

    return [_convert_result(r) for r in results]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def health():
    if LITE_MODE:
        return HealthResponse(
            status="lite",
            qdrant=False,
            embedding_model="",
            message="Lite mode: lookup only",
        )
    try:
        retriever = _get_retriever()
        detail = retriever.health_check()
    except Exception:
        return HealthResponse(
            status="lite",
            qdrant=False,
            embedding_model=EMBEDDING_MODEL,
            message="Qdrant unavailable, falling back to lookup only",
        )
    return HealthResponse(
        status=detail["status"],
        qdrant=detail["qdrant_connected"],
        embedding_model=EMBEDDING_MODEL,
        message=detail["message"],
        collections=detail["collections"],
        total_documents=detail["total_documents"],
        missing_collections=detail["missing_collections"],
    )



@app.post("/search", response_model=SearchResponse, response_model_exclude_none=True)
def search(req: SearchRequest):
    t0 = time.time()

    # Suppress internal _trace calls (legacy); we build structured debug instead
    from src.rag._trace import _trace_local
    _trace_local.events = []
    def _noop(*a, **kw): pass

    lookup_section = None
    semantic_results = []
    timing: dict[str, float] = {}

    # ── Lookup phase ──
    if req.mode in ("auto", "lookup"):
        t_lk = time.time()
        lookup_section = _do_lookup(req, _noop)
        timing["lookup"] = round((time.time() - t_lk) * 1000, 1)

    # ── Semantic phase ──
    if req.mode in ("auto", "semantic"):
        t_sem = time.time()
        semantic_results = _do_semantic(req, _noop)
        timing["semantic"] = round((time.time() - t_sem) * 1000, 1)
        before_dedup = len(semantic_results)

    # ── Dedup: when lookup hit, drop ACE + plugin overview docs from semantic ──
    if lookup_section and lookup_section.hit and semantic_results:
        lookup_plugin = lookup_section.plugin.id if lookup_section.plugin else ""
        deduped = []
        for r in semantic_results:
            if r.get("type") == "ace":
                continue
            if (r.get("type") == "doc" and lookup_plugin
                    and r.get("title", "").lower() == lookup_plugin.lower()):
                continue
            deduped.append(r)
        semantic_results = deduped

    latency_ms = (time.time() - t0) * 1000
    timing["total"] = round(latency_ms, 1)
    detected_lang = req.lang or _detect_lang(req.query)

    # Build debug info
    debug_info = None
    if req.debug:
        semantic_debug = None
        if "semantic" in timing:
            coll_stats = {}
            for r in semantic_results:
                coll = r.get("collection", r.get("type", "unknown"))
                if coll not in coll_stats:
                    coll_stats[coll] = {"hits": 0, "top_score": 0.0}
                coll_stats[coll]["hits"] += 1
                coll_stats[coll]["top_score"] = max(coll_stats[coll]["top_score"], r.get("score", 0))
            semantic_debug = SemanticDebug(
                collections=coll_stats,
                total_candidates=before_dedup if 'before_dedup' in dir() else 0,
                after_dedup=len(semantic_results),
            )
        debug_info = DebugInfo(timing_ms=timing, semantic=semantic_debug)

    return SearchResponse(
        query=req.query,
        lang=detected_lang,
        mode=req.mode,
        latency_ms=round(latency_ms, 1),
        lookup=lookup_section,
        semantic=semantic_results,
        debug=debug_info,
    )
