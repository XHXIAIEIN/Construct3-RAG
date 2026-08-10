"""Map transport-independent search outcomes to typed HTTP responses."""

from __future__ import annotations

from typing import TypeAlias

import jieba

from src.application.health import HealthOutcome
from src.application.models import SearchCommand, SearchOutcome
from src.domain.lookup import LookupResponse
from src.domain.retrieval import SearchResult
from src.locale.resources import ACE_TITLE_MARKERS_ZH, VECTOR_METADATA_PREFIXES_ZH_EN
from src.retrieval.identity import collection_key

from .models import (
    ACELocaleResult,
    ACEParam,
    ContextTier,
    DebugInfo,
    DocResult,
    ExampleResult,
    HealthResponse,
    LookupDebug,
    LookupItemResult,
    LookupMatchResult,
    LookupSection,
    SearchRequest,
    SearchResponse,
    SemanticDebug,
    SemanticSection,
    TermResult,
)

SemanticResult: TypeAlias = DocResult | TermResult | ExampleResult


def request_to_command(request: SearchRequest) -> SearchCommand:
    """Copy a validated HTTP request into the application command contract."""
    return SearchCommand(
        query=request.query,
        top_k=request.top_k,
        lang=request.lang,
        collections=tuple(request.collections or ()),
        plugin=request.plugin,
        section_types=tuple(request.section_types or ()),
        debug=request.debug,
        context=request.context,
        apply_threshold=request.apply_threshold,
        mode=request.mode,
        scope=request.scope,
    )


def present_health_outcome(outcome: HealthOutcome) -> HealthResponse:
    """Map the application health snapshot to its public HTTP contract."""
    return HealthResponse(
        status=outcome.status,
        qdrant=outcome.qdrant,
        schema_ready=outcome.schema_ready,
        embedding_model=outcome.embedding_model,
        message=outcome.message,
        collections=dict(outcome.collections),
        total_documents=outcome.total_documents,
        missing_collections=list(outcome.missing_collections),
    )


def _clean_content(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line or line.startswith(VECTOR_METADATA_PREFIXES_ZH_EN):
            continue
        if any(marker in line for marker in ACE_TITLE_MARKERS_ZH):
            continue
        lines.append(line)
    return "\n".join(lines)


def _convert_params(raw_params: list[dict]) -> list[ACEParam]:
    return [
        ACEParam(
            name=param.get("name_en") or param.get("name_zh", param.get("id", "")),
            type=param.get("type", "any"),
            desc=param.get("desc_en") or param.get("desc_zh", ""),
        )
        for param in raw_params
    ]


def _present_lookup(
    result: LookupResponse | None,
    command: SearchCommand,
    lang: str,
) -> LookupSection | None:
    if result is None or not result.matches:
        return None

    # The committed Lookup schema is bilingual (en-US/zh-CN). Japanese and
    # Korean are valid semantic language hints, but must not relabel Chinese
    # lookup text as if it were a ja/ko translation.
    include_localized = lang == "zh"
    include_scripts = command.scope in {"scripts", "js", "ts", "all"}
    include_display = command.scope in {"eventsheet", "all"}
    is_list = command.mode == "list"

    if is_list:
        grouped_names: dict[str, list[str]] = {}
        for match in result.matches:
            name = match.script_name if include_scripts else match.en.name
            grouped_names.setdefault(match.ace_type, []).append(name)
        if not any(grouped_names.values()):
            return None
        return LookupSection(
            conditions=grouped_names.get("condition") or None,
            actions=grouped_names.get("action") or None,
            expressions=grouped_names.get("expression") or None,
            context=_lookup_context(result, command, include_localized),
        )

    grouped_matches: dict[str, dict[str, list[LookupItemResult]]] = {}
    for match in result.matches:
        response_match = LookupMatchResult(
            ace_id=match.ace_id,
            ace_type=match.ace_type,
            plugin_id=match.plugin_id,
            en=ACELocaleResult(
                name=match.en.name,
                desc=match.en.desc or None,
                display=(match.en.display or None) if include_display else None,
            ),
            localized=(
                ACELocaleResult(
                    name=match.zh.name,
                    desc=match.zh.desc or None,
                    display=(match.zh.display or None) if include_display else None,
                )
                if include_localized
                else None
            ),
            script_name=match.script_name if include_scripts else None,
            category=match.category or None,
            relevance=match.relevance or None,
            params=_convert_params(match.params) or None,
            is_trigger=match.is_trigger,
            is_async=match.is_async,
            return_type=match.return_type or None,
        )
        payload = response_match.to_dict(lang if include_localized else "")
        plugin_id = payload.pop("plugin_id", match.plugin_id)
        ace_type = payload.pop("ace_type", "other")
        group_key = ace_type if ace_type.endswith("s") else f"{ace_type}s"
        grouped_matches.setdefault(plugin_id, {}).setdefault(group_key, []).append(
            LookupItemResult.model_validate(payload)
        )

    return LookupSection(
        matches=grouped_matches or None,
        context=_lookup_context(result, command, include_localized),
    )


def _lookup_context(
    result: LookupResponse,
    command: SearchCommand,
    include_localized: bool,
) -> str | None:
    if not command.context:
        return None
    context = result.context
    if not include_localized:
        context = "\n".join(
            line for line in context.split("\n") if not line.startswith("zh:")
        )
    return context


def _context_tiers(results: tuple[SearchResult, ...]) -> list[ContextTier]:
    if not results:
        return []
    max_score = max(result.score for result in results)
    if max_score <= 0:
        return ["normal"] * len(results)
    tiers: list[ContextTier] = []
    for index, result in enumerate(results):
        ratio = result.score / max_score
        if index == 0 and ratio >= 0.8:
            tiers.append("full")
        elif ratio >= 0.5:
            tiers.append("normal")
        else:
            tiers.append("brief")
    return tiers


def _convert_semantic_result(
    result: SearchResult,
    context_tier: ContextTier,
) -> SemanticResult:
    score = round(result.score, 4)
    metadata = result.metadata
    collection = collection_key(result.source)

    if collection == "ace":
        return DocResult(
            score=score,
            collection="ace",
            title=metadata.get("plugin_name_en", metadata.get("plugin_name", "")),
            section=metadata.get("name_en", ""),
            content=_clean_content(result.text) or None,
            context_tier=context_tier,
        )
    if collection == "examples":
        return ExampleResult(
            score=score,
            project=metadata.get("title_en", metadata.get("slug", "")) or None,
            content=result.text,
            context_tier=context_tier,
        )
    if collection == "terms":
        return TermResult(
            score=score,
            zh=metadata.get("zh", ""),
            en=metadata.get("en", ""),
            context_tier=context_tier,
        )
    if collection == "effects":
        name_zh = metadata.get("name_zh", "")
        name_en = metadata.get("name_en", "")
        title = f"{name_zh} ({name_en})" if name_zh and name_en else name_zh or name_en
        return DocResult(
            score=score,
            collection="effects",
            title=title or None,
            section=metadata.get("category") or None,
            content=result.text,
            context_tier=context_tier,
        )

    source = metadata.get("source", "")
    return DocResult(
        score=score,
        path=source.replace("\\", "/").removesuffix(".md") if source else None,
        collection=collection or None,
        title=metadata.get("h1_heading", metadata.get("title", "")) or None,
        section=metadata.get("h2_heading", metadata.get("section_type", "")) or None,
        content=result.text,
        context_tier=context_tier,
    )


def _present_semantic(
    results: tuple[SearchResult, ...],
) -> tuple[SemanticSection | None, tuple[SemanticResult, ...]]:
    if not results:
        return None, ()
    converted = tuple(
        _convert_semantic_result(result, tier)
        for result, tier in zip(results, _context_tiers(results))
    )
    return (
        SemanticSection(
            docs=[item for item in converted if isinstance(item, DocResult)] or None,
            terms=[item for item in converted if isinstance(item, TermResult)] or None,
            examples=[item for item in converted if isinstance(item, ExampleResult)] or None,
        ),
        converted,
    )


def _keywords(filter_term: str) -> list[str]:
    if not filter_term:
        return []
    if any(0x4E00 <= ord(char) <= 0x9FFF for char in filter_term):
        return [word for word in jieba.lcut(filter_term) if word.strip()]
    return filter_term.split()


def _present_debug(
    outcome: SearchOutcome,
    semantic_results: tuple[SemanticResult, ...],
) -> DebugInfo:
    lookup_debug = None
    if outcome.lookup_result is not None:
        intent = outcome.lookup_result.intent
        lookup_debug = LookupDebug(
            plugin=intent.plugin_id or None,
            tier=intent.tier,
            confidence=round(intent.confidence, 2),
            intent=intent.intent_type,
            keywords=_keywords(intent.filter_term) or None,
        )

    semantic_debug = None
    if SearchStageName.SEMANTIC in outcome.timing_ms:
        collection_stats: dict[str, dict[str, float | int]] = {}
        for result in semantic_results:
            if isinstance(result, DocResult):
                collection = result.collection or "doc"
            elif isinstance(result, TermResult):
                collection = "term"
            else:
                collection = "example"
            stats = collection_stats.setdefault(collection, {"hits": 0, "top_score": 0.0})
            stats["hits"] = int(stats["hits"]) + 1
            stats["top_score"] = max(float(stats["top_score"]), result.score)
        semantic_debug = SemanticDebug(
            collections=collection_stats,
            total_candidates=outcome.semantic_candidates,
            after_dedup=len(outcome.semantic_results),
        )

    return DebugInfo(
        lookup_ms=outcome.timing_ms.get(SearchStageName.LOOKUP),
        lookup=lookup_debug,
        semantic_ms=outcome.timing_ms.get(SearchStageName.SEMANTIC),
        semantic=semantic_debug,
    )


class SearchStageName:
    """Avoid importing the workflow enum into the HTTP presentation layer."""

    LOOKUP = "lookup"
    SEMANTIC = "semantic"


def present_search_outcome(outcome: SearchOutcome) -> SearchResponse:
    """Build the public response without mutating internal workflow state."""
    lookup = _present_lookup(outcome.lookup_result, outcome.command, outcome.lang)
    semantic, converted = _present_semantic(outcome.semantic_results)
    return SearchResponse(
        query=outcome.command.query,
        lang=outcome.lang,
        mode=outcome.command.mode,
        ms=outcome.elapsed_ms,
        lookup=lookup,
        semantic=semantic,
        debug=_present_debug(outcome, converted) if outcome.command.debug else None,
    )


__all__ = [
    "present_health_outcome",
    "present_search_outcome",
    "request_to_command",
]
