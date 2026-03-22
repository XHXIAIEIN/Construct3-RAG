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
    debug: bool = Field(False, description="Include debug info")
    context: bool = Field(False, description="Include LLM context text in lookup results")
    apply_threshold: bool = Field(True, description="Apply adaptive score threshold filtering")
    mode: str = Field(
        "auto",
        pattern="^(auto|lookup|semantic|list)$",
        description="auto (lookup+semantic), lookup (keyword only), semantic (vector only), list (ACE id+name only)",
    )
    scope: str = Field(
        "eventsheet",
        pattern="^(eventsheet|scripts|js|ts|all)$",
        description="Search scope: eventsheet (default), scripts (js+ts), js, ts, all",
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

class DocResult(BaseModel):
    score: float
    path: Optional[str] = None      # manual page path (e.g. "scripting/scripting-reference/...")
    collection: Optional[str] = None
    title: Optional[str] = None
    section: Optional[str] = None
    content: Optional[str] = None

class TermResult(BaseModel):
    score: float
    zh: str
    en: str

class ExampleResult(BaseModel):
    score: float
    project: Optional[str] = None
    content: str

class ACELocaleResult(BaseModel):
    name: str = ""
    desc: Optional[str] = None
    display: Optional[str] = None

class LookupMatchResult(BaseModel):
    """Structured ACE/property match from lookup."""
    ace_id: str
    ace_type: str
    plugin_id: str
    en: ACELocaleResult = ACELocaleResult()
    localized: Optional[ACELocaleResult] = None  # renamed to lang code at serialization
    script_name: Optional[str] = None
    category: Optional[str] = None
    relevance: Optional[int] = None
    params: Optional[List[ACEParam]] = None
    is_trigger: Optional[bool] = None
    is_async: Optional[bool] = None
    return_type: Optional[str] = None

    def to_dict(self, lang: str = "") -> dict:
        """Serialize with en + localized merged into i18n object."""
        d = self.model_dump(exclude_none=True)
        i18n = {}
        if "en" in d:
            i18n["en"] = d.pop("en")
        if lang and "localized" in d:
            i18n[lang] = d.pop("localized")
        elif "localized" in d:
            d.pop("localized")
        if i18n:
            d["i18n"] = i18n
        return d

class LookupSection(BaseModel):
    """Structured lookup results section. Present = hit."""
    # mode=list: grouped name arrays
    conditions: Optional[list[str]] = None
    actions: Optional[list[str]] = None
    expressions: Optional[list[str]] = None
    # mode=lookup/auto: matches[plugin_id][ace_type] = [match, ...]
    matches: Optional[dict[str, dict]] = None
    context: Optional[str] = None

class LookupDebug(BaseModel):
    """Internal lookup diagnostics."""
    plugin: Optional[str] = None
    tier: Optional[int] = None
    confidence: Optional[float] = None
    intent: Optional[str] = None
    keywords: Optional[list[str]] = None

class SemanticDebug(BaseModel):
    """Debug info for semantic search phase."""
    collections: dict[str, dict] = {}
    total_candidates: int = 0
    after_dedup: int = 0

class DebugInfo(BaseModel):
    """Structured debug output."""
    lookup_ms: Optional[float] = None
    lookup: Optional[LookupDebug] = None
    semantic_ms: Optional[float] = None
    semantic: Optional[SemanticDebug] = None

class SemanticSection(BaseModel):
    """Semantic search results grouped by type."""
    terms: Optional[list] = None
    docs: Optional[list] = None
    examples: Optional[list] = None

class SearchResponse(BaseModel):
    query: str
    lang: str
    mode: str
    ms: float
    lookup: Optional[LookupSection] = None
    semantic: Optional[SemanticSection] = None
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


_PLAYGROUND_HTML = Path(__file__).parent.parent / "tests" / "playground.html"


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


def _clean_content(text: str) -> str:
    """Clean indexed text for LLM consumption.

    Strips redundant labels — title, bilingual descriptions, script name
    are already in structured fields. Keeps only unique content.
    """
    skip_prefixes = (
        "脚本名称/Script:", "描述:", "Description:",
        "参数:", "[触发器", "[异步", "返回类型:",
    )
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith(skip_prefixes):
            continue
        # Skip ACE title line (e.g. "插件 精灵(Sprite) 的条件: ...")
        if "的条件:" in line or "的动作:" in line or "的表达式:" in line:
            continue
        lines.append(line)
    return "\n".join(lines)


def _convert_result(r, score_override=None) -> dict:
    """Convert internal SearchResult to typed response dict."""
    score = score_override if score_override is not None else round(r.score, 4)
    meta = r.metadata
    collection = _collection_key(r.source)

    # ACE results → treated as doc (lookup.matches is the structured ACE source)
    if collection == "ace":
        d = DocResult(
            score=score,
            collection="ace",
            title=meta.get("plugin_name_en", meta.get("plugin_name", "")),
            section=meta.get("name_en", ""),
            content=_clean_content(r.text) or None,
        ).model_dump()
        d["_type"] = "doc"
        return d

    if collection == "examples":
        d = ExampleResult(
            score=score,
            project=meta.get("title_en", meta.get("slug", "")) or None,
            content=r.text,
        ).model_dump()
        d["_type"] = "example"
        return d

    if collection == "terms":
        d = TermResult(
            score=score,
            zh=meta.get("zh", ""),
            en=meta.get("en", ""),
        ).model_dump()
        d["_type"] = "term"
        return d

    # Doc results (plugins, behaviors, guide, interface, project, scripting)
    source = meta.get("source", "")
    d = DocResult(
        score=score,
        path=source.replace("\\", "/").removesuffix(".md") if source else None,
        collection=collection or None,
        title=meta.get("h1_heading", meta.get("title", "")) or None,
        section=meta.get("h2_heading", meta.get("section_type", "")) or None,
        content=r.text,
    ).model_dump()
    d["_type"] = "doc"
    return d


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

    # Scope controls which fields are included
    include_scripts = req.scope in ("scripts", "js", "ts", "all")
    include_display = req.scope in ("eventsheet", "all")
    is_list = req.mode == "list"

    if is_list:
        # Group by ace_type → list of names
        grouped: dict[str, list[str]] = {}
        for m in lookup_result.matches:
            name = m.script_name if include_scripts else m.en.name
            grouped.setdefault(m.ace_type, []).append(name)
        matches = None
    else:
        matches = [
            LookupMatchResult(
                ace_id=m.ace_id,
                ace_type=m.ace_type,
                plugin_id=m.plugin_id,
                en=ACELocaleResult(
                    name=m.en.name, desc=m.en.desc or None,
                    display=m.en.display or None if include_display else None,
                ),
                localized=ACELocaleResult(
                    name=m.zh.name, desc=m.zh.desc or None,
                    display=m.zh.display or None if include_display else None,
                ) if include_localized else None,
                script_name=m.script_name if include_scripts else None,
                category=m.category or None,
                relevance=m.relevance or None,
                params=_convert_params(m.params) or None,
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

    # Context: only when requested, strip zh: line for en queries
    context = None
    if req.context:
        ctx = lookup_result.context
        if not include_localized:
            ctx = "\n".join(l for l in ctx.split("\n") if not l.startswith("zh:"))
        context = ctx

    # Group matches by plugin_id → ace_type
    grouped_matches = None
    if matches:
        gm: dict[str, dict[str, list]] = {}
        for m in matches:
            d = m.to_dict(lang=lang if include_localized else "")
            pid = d.pop("plugin_id", m.plugin_id)
            atype = d.pop("ace_type", "other")
            # Pluralize: condition → conditions
            atype_key = atype + "s" if not atype.endswith("s") else atype
            gm.setdefault(pid, {}).setdefault(atype_key, []).append(d)
        grouped_matches = gm or None

    section = LookupSection(
        matches=grouped_matches,
        context=context,
    )
    if is_list:
        section.conditions = grouped.get("condition") or None
        section.actions = grouped.get("action") or None
        section.expressions = grouped.get("expression") or None
    section._plugin_id = intent.plugin_id or ""
    section._debug = LookupDebug(
        plugin=intent.plugin_id or None,
        tier=intent.tier,
        confidence=round(intent.confidence, 2),
        intent=intent.intent_type,
        keywords=keywords or None,
    )
    return section


def _group_semantic(results: list) -> Optional[SemanticSection]:
    """Group flat semantic results by type into SemanticSection."""
    if not results:
        return None
    docs = []
    terms = []
    examples = []
    for r in results:
        t = r.pop("_type", "doc")
        if t == "term":
            terms.append(r)
        elif t == "example":
            examples.append(r)
        else:
            docs.append(r)
    if not docs and not terms and not examples:
        return None
    return SemanticSection(
        docs=docs or None,
        terms=terms or None,
        examples=examples or None,
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
    if req.mode in ("auto", "lookup", "list"):
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
    if lookup_section and semantic_results:
        lookup_plugin = getattr(lookup_section, '_plugin_id', "")
        deduped = []
        for r in semantic_results:
            # Drop ACE collection results (lookup.matches is authoritative)
            if r.get("collection") == "ace":
                continue
            # Drop generic plugin doc for the matched plugin
            if (lookup_plugin and r.get("_type") == "doc"
                    and (r.get("title") or "").lower() == lookup_plugin.lower()):
                continue
            deduped.append(r)
        semantic_results = deduped

    total_ms = round((time.time() - t0) * 1000, 1)
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
        lookup_debug = getattr(lookup_section, '_debug', None) if lookup_section else None
        debug_info = DebugInfo(
            lookup_ms=timing.get("lookup"),
            lookup=lookup_debug,
            semantic_ms=timing.get("semantic"),
            semantic=semantic_debug,
        )

    return SearchResponse(
        query=req.query,
        lang=detected_lang,
        mode=req.mode,
        ms=total_ms,
        lookup=lookup_section,
        semantic=_group_semantic(semantic_results),
        debug=debug_info,
    )
