"""Normalized records produced by ingest parsers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ACEEntry:
    plugin_name: str
    plugin_name_zh: str
    plugin_name_en: str
    plugin_type: str
    category: str
    ace_type: str
    ace_id: str
    name_zh: str
    name_en: str
    description_zh: str
    description_en: str
    script_name: str = ""
    params: list[dict[str, Any]] = field(default_factory=list)
    return_type: str | None = None
    is_trigger: bool = False
    is_async: bool = False


@dataclass
class EffectEntry:
    id: str
    name_zh: str
    name_en: str
    description_zh: str
    description_en: str
    category: str
    parameters: list[dict[str, Any]] = field(default_factory=list)
