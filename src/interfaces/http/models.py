"""Pydantic contracts exposed by the optional HTTP search service."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

LanguageCode = Literal["en", "zh", "ja", "ko"]
SearchMode = Literal["auto", "lookup", "list"]
SearchScope = Literal["eventsheet", "scripts", "js", "ts", "all"]


class SearchRequest(BaseModel):
    # A field this model does not have is an error, not something to drop: a
    # caller that sends a filter must not get an unfiltered answer back.
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., max_length=500, description="Search query")
    lang: LanguageCode | None = Field(
        None,
        description=(
            "Language of the query, detected from it when omitted; 'zh' adds "
            "the Chinese names to lookup matches"
        ),
    )
    debug: bool = Field(False, description="Include debug info")
    context: bool = Field(False, description="Include compatibility lookup context")
    mode: SearchMode = "auto"
    scope: SearchScope = "eventsheet"

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value


class ACEParam(BaseModel):
    name: str
    type: str = "any"
    desc: str = ""


class ACELocaleResult(BaseModel):
    name: str = ""
    desc: str | None = None
    display: str | None = None


class LookupMatchResult(BaseModel):
    ace_id: str
    ace_type: str
    plugin_id: str
    en: ACELocaleResult = Field(default_factory=ACELocaleResult)
    localized: ACELocaleResult | None = None
    script_name: str | None = None
    category: str | None = None
    relevance: int | None = None
    params: list[ACEParam] | None = None
    is_trigger: bool | None = None
    is_async: bool | None = None
    return_type: str | None = None

    def to_dict(self, lang: str = "") -> dict[str, Any]:
        """Serialize English and optional localized values under one map."""
        payload = self.model_dump(exclude_none=True)
        localized: dict[str, Any] = {}
        if "en" in payload:
            localized["en"] = payload.pop("en")
        if lang and "localized" in payload:
            localized[lang] = payload.pop("localized")
        else:
            payload.pop("localized", None)
        if localized:
            payload["name"] = localized
        return payload


class LookupItemResult(BaseModel):
    """Typed item nested under ``matches[plugin_id][ace_type]``."""

    ace_id: str
    name: dict[str, ACELocaleResult] = Field(default_factory=dict)
    script_name: str | None = None
    category: str | None = None
    relevance: int | None = None
    params: list[ACEParam] | None = None
    is_trigger: bool | None = None
    is_async: bool | None = None
    return_type: str | None = None


class LookupDebug(BaseModel):
    plugin: str | None = None
    tier: int | None = None
    confidence: float | None = None
    intent: str | None = None
    keywords: list[str] | None = None


class LookupSection(BaseModel):
    conditions: list[str] | None = None
    actions: list[str] | None = None
    expressions: list[str] | None = None
    matches: dict[str, dict[str, list[LookupItemResult]]] | None = None
    context: str | None = None


class DebugInfo(BaseModel):
    lookup_ms: float | None = None
    lookup: LookupDebug | None = None


class SearchResponse(BaseModel):
    query: str
    lang: LanguageCode
    mode: SearchMode
    ms: float
    lookup: LookupSection | None = None
    debug: DebugInfo | None = None


class HealthResponse(BaseModel):
    status: str
    schema_ready: bool
    message: str


__all__ = [
    "ACELocaleResult",
    "ACEParam",
    "DebugInfo",
    "HealthResponse",
    "LanguageCode",
    "LookupDebug",
    "LookupItemResult",
    "LookupMatchResult",
    "LookupSection",
    "SearchMode",
    "SearchRequest",
    "SearchResponse",
    "SearchScope",
]
