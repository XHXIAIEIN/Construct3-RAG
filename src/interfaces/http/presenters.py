"""Map transport-independent search outcomes to typed HTTP responses."""

from __future__ import annotations

import jieba

from src.application.health import HealthOutcome
from src.application.models import SearchCommand, SearchOutcome
from src.domain.lookup import LookupResponse

from .models import (
    ACELocaleResult,
    ACEParam,
    DebugInfo,
    HealthResponse,
    LookupDebug,
    LookupItemResult,
    LookupMatchResult,
    LookupSection,
    SearchRequest,
    SearchResponse,
)


def request_to_command(request: SearchRequest) -> SearchCommand:
    """Copy a validated HTTP request into the application command contract."""
    return SearchCommand(
        query=request.query,
        lang=request.lang,
        debug=request.debug,
        context=request.context,
        mode=request.mode,
        scope=request.scope,
    )


def present_health_outcome(outcome: HealthOutcome) -> HealthResponse:
    """Map the application health snapshot to its public HTTP contract."""
    return HealthResponse(
        status=outcome.status,
        schema_ready=outcome.schema_ready,
        message=outcome.message,
    )


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
    # Korean are valid language hints, but must not relabel Chinese lookup
    # text as if it were a ja/ko translation.
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


def _keywords(filter_term: str) -> list[str]:
    if not filter_term:
        return []
    if any(0x4E00 <= ord(char) <= 0x9FFF for char in filter_term):
        return [word for word in jieba.lcut(filter_term) if word.strip()]
    return filter_term.split()


def _present_debug(outcome: SearchOutcome) -> DebugInfo:
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

    return DebugInfo(
        lookup_ms=outcome.timing_ms.get(SearchStageName.LOOKUP),
        lookup=lookup_debug,
    )


class SearchStageName:
    """Avoid importing the workflow enum into the HTTP presentation layer."""

    LOOKUP = "lookup"


def present_search_outcome(outcome: SearchOutcome) -> SearchResponse:
    """Build the public response without mutating internal workflow state."""
    return SearchResponse(
        query=outcome.command.query,
        lang=outcome.lang,
        mode=outcome.command.mode,
        ms=outcome.elapsed_ms,
        lookup=_present_lookup(outcome.lookup_result, outcome.command, outcome.lang),
        debug=_present_debug(outcome) if outcome.command.debug else None,
    )


__all__ = [
    "present_health_outcome",
    "present_search_outcome",
    "request_to_command",
]
