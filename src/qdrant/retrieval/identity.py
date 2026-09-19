"""Stable retrieval identities and exact deduplication policy."""

from __future__ import annotations

import posixpath
import re
import unicodedata
from typing import Any

from src.domain.lookup import LookupMatch
from src.domain.retrieval import SearchResult

_COLLECTION_NAME_TO_KEY = {
    "c3_guide": "guide",
    "c3_interface": "interface",
    "c3_project": "project",
    "c3_plugins": "plugins",
    "c3_behaviors": "behaviors",
    "c3_scripting": "scripting",
    "c3_ace": "ace",
    "c3_effects": "effects",
    "c3_terms": "terms",
    "c3_examples": "examples",
    "c3_addon_sdk": "addon_sdk",
}


def _identity_component(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip().casefold()
    return re.sub(r"\s+", " ", text).replace("|", "%7c")


def collection_key(value: Any) -> str:
    normalized = _identity_component(value)
    return _COLLECTION_NAME_TO_KEY.get(normalized, normalized)


def _source_path(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().replace("\\", "/")
    text = re.sub(r"^[a-zA-Z]:/", "", text)
    text = re.sub(r"^\./+", "", text)
    text = re.sub(r"/+", "/", text)
    normalized = posixpath.normpath(text) if text else ""
    if normalized in {"", "."}:
        return ""
    if normalized.casefold().endswith(".md"):
        normalized = normalized[:-3]
    return _identity_component(normalized)


def _section_slug(value: Any) -> str:
    section = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    section = "".join(char if char.isalnum() else "-" for char in section)
    return re.sub(r"-+", "-", section).strip("-") or "root"


def _ace_type(value: Any) -> str:
    normalized = _identity_component(value)
    aliases = {
        "actions": "action",
        "conditions": "condition",
        "expressions": "expression",
        "properties": "property",
    }
    return aliases.get(
        normalized,
        normalized[:-1] if normalized.endswith("s") else normalized,
    )


def _term_path_identity(value: Any) -> str | None:
    if isinstance(value, (list, tuple)):
        parts = [_identity_component(part) for part in value if str(part or "").strip()]
    else:
        raw = str(value or "").strip().replace("\\", "/")
        if not raw:
            return None
        parts = [_identity_component(part) for part in raw.split("/") if part.strip()]
        if len(parts) < 4 and "/" not in raw:
            parts = [_identity_component(part) for part in raw.split(".") if part.strip()]
    for index, part in enumerate(parts):
        if part not in {"plugins", "behaviors"} or index + 3 >= len(parts):
            continue
        plugin_id, item_type, item_id = parts[index + 1 : index + 4]
        if plugin_id and item_type in {"actions", "conditions", "expressions"} and item_id:
            return f"terms|{plugin_id}|{_ace_type(item_type)}|{item_id}"
    return None


def stable_result_id(result: SearchResult) -> str | None:
    """Return an exact rebuild-stable identity when payload fields support one."""
    key = collection_key(result.source)
    metadata = result.metadata

    if key == "ace":
        plugin_type = _identity_component(
            metadata.get("plugin_type") or metadata.get("plugin_or_behavior")
        )
        plugin_id = _identity_component(
            metadata.get("plugin_name") or metadata.get("plugin_id")
        )
        item_type = _ace_type(metadata.get("ace_type"))
        item_id = _identity_component(metadata.get("ace_id"))
        if plugin_type in {"plugin", "behavior"} and plugin_id and item_type and item_id:
            return f"ace|{plugin_type}|{plugin_id}|{item_type}|{item_id}"
        return None

    if key == "examples":
        slug = _identity_component(metadata.get("slug"))
        return f"examples|{slug}" if slug else None
    if key == "effects":
        effect_id = _identity_component(metadata.get("effect_id"))
        return f"effects|{effect_id}" if effect_id else None
    if key == "terms":
        path_identity = _term_path_identity(metadata.get("path"))
        if path_identity:
            return path_identity
        term_key = _identity_component(metadata.get("term_key"))
        return f"terms|{term_key}" if term_key else None

    source = _source_path(metadata.get("source") or metadata.get("path"))
    if not key or not source:
        return None
    section = _section_slug(
        metadata.get("h2_heading")
        or metadata.get("section")
        or metadata.get("section_type")
    )
    return f"{key}|{source}|{section}"


def lookup_match_stable_id(
    match: LookupMatch,
    *,
    is_behavior: bool = False,
) -> str | None:
    """Return the semantic-compatible identity for one structured lookup match."""
    key = collection_key(
        match.collection or ("behaviors" if is_behavior else "plugins")
    )
    plugin_id = _identity_component(match.plugin_id)
    item_type = _ace_type(match.ace_type)
    item_id = _identity_component(match.ace_id)

    if key == "examples":
        return f"examples|{item_id}" if item_id else None
    if key == "terms":
        if plugin_id and item_type and item_id:
            return f"terms|{plugin_id}|{item_type}|{item_id}"
        return None
    if key == "script_api":
        if plugin_id and item_id:
            return f"script_api|{plugin_id}|{item_id}"
        return None
    if not all((key, plugin_id, item_type, item_id)):
        return None
    plugin_type = "behavior" if key == "behaviors" else "plugin"
    return f"ace|{plugin_type}|{plugin_id}|{item_type}|{item_id}"


def deduplicate_results(results: list[SearchResult]) -> list[SearchResult]:
    """Remove only exact stable-ID duplicates while preserving order."""
    seen: set[str] = set()
    unique: list[SearchResult] = []
    for result in results:
        identity = stable_result_id(result)
        if identity is not None:
            if identity in seen:
                continue
            seen.add(identity)
        unique.append(result)
    return unique


# Compatibility name used inside the historical retriever module.
_collection_key = collection_key
