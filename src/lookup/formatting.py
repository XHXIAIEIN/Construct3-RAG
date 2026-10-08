"""Pure formatting helpers for Lookup compatibility context and matches."""

from __future__ import annotations

from src.domain.lookup import ACELocale, LookupMatch
from src.lookup.schema_layout import SCHEMA_ACE_TYPES


ACE_PREFIX: dict[str, str] = {
    "conditions": "C",
    "actions": "A",
    "expressions": "E",
}
# Results list conditions, then actions, then expressions, as a schema file does.
ACE_SORT_ORDER: dict[str, int] = {
    ace_type: order for order, ace_type in enumerate(SCHEMA_ACE_TYPES)
}
TERM_TRANSLATE_HEADER = '**"{term}"** translation results ({count} items):\n'
TERM_TABLE_HEADER = "| # | Chinese | English | Key |"
TERM_TABLE_SEPARATOR = "|---|---------|---------|-----|"

_GENERIC_PARAM_TYPES = frozenset({"cmp"})


def _semantic_params(params: list[dict]) -> list[dict]:
    """The parameters that say what the ACE does, without comparison operands."""
    return [
        param
        for param in params
        if param.get("type", "") not in _GENERIC_PARAM_TYPES
    ]


def _joined_names(params: list[dict]) -> str:
    return ",".join(
        param.get("name_en", "").strip()
        for param in params
        if param.get("name_en", "").strip()
    )


def format_params(params: list[dict]) -> str:
    """Build a compact multi-parameter action/expression signature."""
    semantic = _semantic_params(params)
    return _joined_names(semantic) if len(semantic) > 1 else ""


def format_condition_sig(name_en: str, params: list[dict]) -> str:
    """Build a condition signature, omitting generic comparison operands."""
    param_text = _joined_names(_semantic_params(params))
    return f"{name_en}({param_text})" if param_text else name_en


def format_signature(ace_type: str, name_en: str, params: list[dict]) -> str:
    """The signature of an ACE as a list or detail line shows it."""
    if ace_type == "conditions":
        return format_condition_sig(name_en, params)
    return f"{name_en}({format_params(params)})"


def build_zh_line(
    plugin_en: str,
    plugin_zh: str,
    zh_pairs: list[tuple[str, str]],
) -> str:
    """Build the compact English-to-Chinese compatibility mapping line."""
    parts: list[str] = []
    if plugin_zh and plugin_zh != plugin_en:
        parts.append(f"{plugin_en}={plugin_zh}")
    seen: set[str] = set()
    for en, zh in zh_pairs:
        if en and en not in seen:
            seen.add(en)
            parts.append(f"{en}={zh}")
    return f"zh: {','.join(parts)}" if parts else ""


def match_from_item(
    item: dict,
    ace_type: str,
    plugin_id: str,
    plugin_zh: str,
    name_en: str = "",
    name_zh: str = "",
    params: list | None = None,
    collection: str = "plugins",
) -> LookupMatch:
    """Build a domain match from one merged Schema item."""
    name_en = name_en or item.get("name_en", "")
    name_zh = name_zh or item.get("name_zh", "")
    return LookupMatch(
        ace_id=item.get("id", name_en),
        ace_type=ace_type,
        plugin_id=plugin_id,
        collection=collection,
        en=ACELocale(
            name=name_en,
            desc=item.get("description_en", ""),
            display=item.get("display_en", ""),
        ),
        zh=ACELocale(
            name=name_zh,
            desc=item.get("description_zh", ""),
            display=item.get("display_zh", ""),
        ),
        plugin_name_zh=plugin_zh,
        script_name=item.get("scriptName", item.get("script_name", "")),
        category=item.get("category", ""),
        params=params if params is not None else item.get("params", []),
        is_trigger=item.get("isTrigger", False),
        is_async=item.get("isAsync", False),
        return_type=item.get("returnType", ""),
    )
