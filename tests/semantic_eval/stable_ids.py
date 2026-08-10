"""Stable result identities for the frozen semantic gold set.

Qdrant point IDs and chunk text are implementation details.  Evaluation keys
must instead be derived from versioned payload fields so the same judgment can
survive a deterministic re-index of the same source snapshot.
"""

from __future__ import annotations

import posixpath
import re
import unicodedata
from collections.abc import Mapping
from typing import Any


class StableIdError(ValueError):
    """Raised when a Qdrant payload cannot produce an evidence-backed ID."""


_ACE_TYPE_ALIASES = {
    "actions": "action",
    "conditions": "condition",
    "expressions": "expression",
    "properties": "property",
}
_TERM_PATH_KINDS = {"plugins", "behaviors"}
_TERM_PATH_TYPES = {"actions", "conditions", "expressions"}
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


def _text(value: Any) -> str:
    if value is None:
        return ""
    return unicodedata.normalize("NFKC", str(value)).strip()


def normalize_component(value: Any) -> str:
    """Normalize a non-path key component without inventing missing values."""

    text = _text(value).casefold()
    text = re.sub(r"\s+", " ", text)
    return text.replace("|", "%7c")


def normalize_collection_key(value: Any) -> str:
    """Return the short registry key for either ``plugins`` or ``c3_plugins``."""

    normalized = normalize_component(value)
    return _COLLECTION_NAME_TO_KEY.get(normalized, normalized)


def normalize_ace_type(value: Any) -> str:
    normalized = normalize_component(value)
    return _ACE_TYPE_ALIASES.get(normalized, normalized[:-1] if normalized.endswith("s") else normalized)


def normalize_source_path(value: Any) -> str:
    """Normalize indexed relative paths to slash-separated, suffixless keys."""

    text = _text(value).replace("\\", "/")
    text = re.sub(r"^[a-zA-Z]:/", "", text)
    text = re.sub(r"^\./+", "", text)
    text = re.sub(r"/+", "/", text)
    normalized = posixpath.normpath(text) if text else ""
    if normalized in {"", "."}:
        return ""
    if normalized.casefold().endswith(".md"):
        normalized = normalized[:-3]
    return normalize_component(normalized).replace("%7c", "%7c")


def normalize_section(value: Any) -> str:
    # Gold docs use URL-style section slugs, e.g. ``Array expressions`` ->
    # ``array-expressions``.  Mapping character-by-character keeps CJK letters
    # while removing Markdown/backtick/anchor punctuation deterministically.
    section = _text(value).casefold()
    section = "".join(char if char.isalnum() else "-" for char in section)
    section = re.sub(r"-+", "-", section).strip("-")
    return section or "root"


def _require(value: Any, field: str, collection: str) -> str:
    normalized = normalize_component(value)
    if not normalized:
        raise StableIdError(f"{collection}: payload is missing required field {field}")
    return normalized


def _term_path_identity(path: Any) -> str | None:
    if isinstance(path, (list, tuple)):
        # ``C3Fetcher.export_terms`` stores the canonical CDN traversal path as
        # a JSON array.  Keeping its components intact avoids parsing Python's
        # list representation and makes a rebuilt index identity-stable.
        parts = [normalize_component(part) for part in path if _text(part)]
    else:
        raw = _text(path).replace("\\", "/")
        if not raw:
            return None
        # Older indexes used slash-joined paths and, before that, text.* keys.
        parts = [normalize_component(part) for part in raw.split("/") if _text(part)]
        if len(parts) < 4 and "/" not in raw:
            parts = [normalize_component(part) for part in raw.split(".") if _text(part)]
    for index, part in enumerate(parts):
        if part not in _TERM_PATH_KINDS or index + 3 >= len(parts):
            continue
        plugin_id = parts[index + 1]
        ace_type = parts[index + 2]
        ace_id = parts[index + 3]
        if plugin_id and ace_type in _TERM_PATH_TYPES and ace_id:
            return f"terms|{plugin_id}|{normalize_ace_type(ace_type)}|{ace_id}"
    return None


def stable_result_id(collection_key: str, payload: Mapping[str, Any]) -> str:
    """Return the frozen identity for a Qdrant result payload.

    Supported identities:

    - ACE: ``ace|plugin_or_behavior|plugin_id|ace_type|ace_id``
    - docs/addon SDK: ``collection|normalized_source_path|section``
    - examples: ``examples|slug``
    - effects: ``effects|effect_id``
    - terms: parsed ACE path, otherwise ``terms|term_key``
    """

    key = normalize_collection_key(collection_key)
    if not key:
        raise StableIdError("collection key is empty")

    if key == "ace":
        plugin_type = normalize_component(
            payload.get("plugin_type") or payload.get("plugin_or_behavior")
        )
        if plugin_type not in {"plugin", "behavior"}:
            raise StableIdError(
                "ace: plugin_type must be 'plugin' or 'behavior' for a stable identity"
            )
        plugin_id = _require(
            payload.get("plugin_name") or payload.get("plugin_id"), "plugin_name", key
        )
        ace_type = normalize_ace_type(payload.get("ace_type"))
        if not ace_type:
            raise StableIdError("ace: payload is missing required field ace_type")
        ace_id = _require(payload.get("ace_id"), "ace_id", key)
        return f"ace|{plugin_type}|{plugin_id}|{ace_type}|{ace_id}"

    if key == "examples":
        return f"examples|{_require(payload.get('slug'), 'slug', key)}"

    if key == "effects":
        return f"effects|{_require(payload.get('effect_id'), 'effect_id', key)}"

    if key == "terms":
        path_identity = _term_path_identity(payload.get("path"))
        if path_identity:
            return path_identity
        return f"terms|{_require(payload.get('term_key'), 'term_key', key)}"

    source = normalize_source_path(payload.get("source") or payload.get("path"))
    if not source:
        raise StableIdError(f"{key}: payload is missing required field source")
    # H1 is the document title, not a section identity.  Root chunks therefore
    # stay ``root`` instead of changing identity when a page title is edited.
    # H2 text is deliberately slugged (rather than merely case-folded) so the
    # live Qdrant payload and hand-adjudicated Markdown anchors use the same key.
    section = normalize_section(
        payload.get("h2_heading")
        or payload.get("section")
        or payload.get("section_type")
    )
    return f"{key}|{source}|{section}"


def stable_id_from_spec(spec: Mapping[str, Any]) -> str:
    """Canonicalize a fixture result object that does not use ``stable_id``."""

    collection = normalize_collection_key(spec.get("collection"))
    if not collection:
        raise StableIdError("result spec is missing collection")

    if {"plugin_id", "ace_type", "ace_id"}.issubset(spec):
        plugin_type = normalize_component(
            spec.get("plugin_or_behavior") or spec.get("plugin_type")
        )
        if not plugin_type:
            if collection == "behaviors":
                plugin_type = "behavior"
            elif collection in {"plugins", "ace"}:
                plugin_type = "plugin"
        return stable_result_id(
            "ace",
            {
                "plugin_type": plugin_type,
                "plugin_id": spec.get("plugin_id"),
                "ace_type": spec.get("ace_type"),
                "ace_id": spec.get("ace_id"),
            },
        )

    if collection == "examples":
        return stable_result_id(collection, {"slug": spec.get("slug")})
    if collection == "effects":
        return stable_result_id(collection, {"effect_id": spec.get("effect_id")})
    if collection == "terms":
        return stable_result_id(
            collection,
            {"path": spec.get("term_path") or spec.get("path"), "term_key": spec.get("term_key")},
        )
    return stable_result_id(
        collection,
        {
            "source": spec.get("path") or spec.get("source_path") or spec.get("source"),
            "section": spec.get("section"),
        },
    )
