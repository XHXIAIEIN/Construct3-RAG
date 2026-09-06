"""Pydantic contracts exposed by the optional HTTP search service."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

LanguageCode = Literal["en", "zh", "ja", "ko"]
SearchMode = Literal["auto", "lookup", "semantic", "list"]
SearchScope = Literal["eventsheet", "scripts", "js", "ts", "all"]
ContextTier = Literal["full", "normal", "brief"]


class SearchRequest(BaseModel):
    query: str = Field(..., max_length=500, description="Search query")
    top_k: int = Field(
        10,
        ge=1,
        le=50,
        description=(
            "Requested semantic result budget; complexity routing may raise it, "
            "and complete Direct Schema lists are not truncated"
        ),
    )
    lang: LanguageCode | None = Field(
        None,
        description=(
            "Language hint: 'zh'/'ja'/'ko' includes terms collection "
            "(bilingual); 'en' skips terms"
        ),
    )
    collections: list[str] | None = Field(
        None,
        description="Full-mode semantic filter for collections",
    )
    plugin: str | None = Field(
        None,
        description="Full-mode semantic filter by plugin name",
    )
    section_types: list[str] | None = Field(
        None,
        description="Full-mode semantic section filter used with plugin",
    )
    debug: bool = Field(False, description="Include debug info")
    context: bool = Field(False, description="Include compatibility lookup context")
    apply_threshold: bool = Field(True, description="Filter semantic results adaptively")
    mode: SearchMode = "auto"
    scope: SearchScope = "eventsheet"

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value

    @model_validator(mode="after")
    def lookup_modes_reject_semantic_filters(self) -> "SearchRequest":
        if self.mode in {"lookup", "list"} and any(
            (self.plugin, self.collections, self.section_types)
        ):
            raise ValueError(
                f"mode='{self.mode}' cannot be combined with semantic filters"
            )
        return self


class PluginInfo(BaseModel):
    """Compatibility model retained for existing API consumers."""

    id: str
    name: str
    name_localized: str = ""


class ACEParam(BaseModel):
    name: str
    type: str = "any"
    desc: str = ""


class DocResult(BaseModel):
    score: float
    path: str | None = None
    collection: str | None = None
    title: str | None = None
    section: str | None = None
    content: str | None = None
    context_tier: ContextTier | None = None


class TermResult(BaseModel):
    score: float
    zh: str
    en: str
    context_tier: ContextTier | None = None


class ExampleResult(BaseModel):
    score: float
    project: str | None = None
    content: str
    context_tier: ContextTier | None = None


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


class SemanticDebug(BaseModel):
    collections: dict[str, dict[str, float | int]] = Field(default_factory=dict)
    total_candidates: int = 0
    after_dedup: int = 0


class DebugInfo(BaseModel):
    lookup_ms: float | None = None
    lookup: LookupDebug | None = None
    semantic_ms: float | None = None
    semantic: SemanticDebug | None = None


class SemanticSection(BaseModel):
    terms: list[TermResult] | None = None
    docs: list[DocResult] | None = None
    examples: list[ExampleResult] | None = None


class SearchResponse(BaseModel):
    query: str
    lang: LanguageCode
    mode: SearchMode
    ms: float
    lookup: LookupSection | None = None
    semantic: SemanticSection | None = None
    debug: DebugInfo | None = None


class HealthResponse(BaseModel):
    status: str
    qdrant: bool
    schema_ready: bool
    embedding_model: str
    message: str
    collections: dict[str, int] = Field(default_factory=dict)
    total_documents: int = 0
    missing_collections: list[str] = Field(default_factory=list)


__all__ = [
    "ACELocaleResult",
    "ACEParam",
    "ContextTier",
    "DebugInfo",
    "DocResult",
    "ExampleResult",
    "HealthResponse",
    "LanguageCode",
    "LookupDebug",
    "LookupItemResult",
    "LookupMatchResult",
    "LookupSection",
    "PluginInfo",
    "SearchMode",
    "SearchRequest",
    "SearchResponse",
    "SearchScope",
    "SemanticDebug",
    "SemanticSection",
    "TermResult",
]
