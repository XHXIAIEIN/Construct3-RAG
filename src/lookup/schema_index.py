"""Versioned bilingual Schema index used by deterministic lookup."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

_default_schema_dir: Path | None = None


def configure_schema_default(schema_dir: Path) -> None:
    """Bind the legacy no-argument constructor at a composition boundary."""
    global _default_schema_dir
    _default_schema_dir = Path(schema_dir)


def _is_ascii_identifier_char(char: str) -> bool:
    return char == "_" or "0" <= char <= "9" or "a" <= char.lower() <= "z"


def _merge_bilingual(en: dict, zh: dict) -> dict:
    """Merge CDN-native English and Chinese Schema records."""
    merged = {
        "id": en.get("id", ""),
        "originalId": en.get("id", ""),
        "name_en": en.get("name", en.get("id", "")),
        "name_zh": zh.get("name", en.get("name", "")),
        "description_en": en.get("description", ""),
        "description_zh": zh.get("description", ""),
        "plugin_type": en.get("type", "plugin"),
        "aceCategories": list(en.get("aceCategories", {}).keys()),
    }

    for ace_type in ("conditions", "actions", "expressions"):
        zh_map = {
            item.get("id", ""): item for item in zh.get(ace_type, [])
        }
        merged_items = []
        for en_item in en.get(ace_type, []):
            ace_id = en_item.get("id", "")
            zh_item = zh_map.get(ace_id, {})
            entry: dict[str, Any] = {"id": ace_id}
            if ace_type == "expressions":
                entry["name_en"] = en_item.get("translated-name", ace_id)
                entry["name_zh"] = zh_item.get(
                    "translated-name", entry["name_en"]
                )
            else:
                entry["name_en"] = en_item.get("list-name", ace_id)
                entry["name_zh"] = zh_item.get("list-name", entry["name_en"])

            entry["description_en"] = en_item.get("description", "")
            entry["description_zh"] = zh_item.get("description", "")
            entry["display_en"] = en_item.get("display-text", "")
            entry["display_zh"] = zh_item.get("display-text", "")
            entry["scriptName"] = en_item.get("scriptName", "")
            entry["category"] = en_item.get("category", "")

            en_params = en_item.get("params", {})
            zh_params = zh_item.get("params", {})
            params_list: list[dict[str, Any]] = []
            if isinstance(en_params, dict):
                for param_id, en_param in en_params.items():
                    zh_param = (
                        zh_params.get(param_id, {})
                        if isinstance(zh_params, dict)
                        else {}
                    )
                    param: dict[str, Any] = {
                        "id": param_id,
                        "type": en_param.get("type", "any"),
                        "name_en": en_param.get("name", param_id),
                        "name_zh": zh_param.get(
                            "name", en_param.get("name", param_id)
                        ),
                        "desc_en": en_param.get("desc", ""),
                        "desc_zh": zh_param.get("desc", ""),
                    }
                    if "items" in en_param:
                        en_items = en_param["items"]
                        param["items"] = (
                            list(en_items.keys())
                            if isinstance(en_items, dict)
                            else en_items
                        )
                        zh_items = zh_param.get("items", {})
                        if isinstance(en_items, dict):
                            param["items_i18n"] = {
                                key: {
                                    "en": value,
                                    "zh": (
                                        zh_items.get(key, value)
                                        if isinstance(zh_items, dict)
                                        else value
                                    ),
                                }
                                for key, value in en_items.items()
                            }
                    if en_param.get("initialValue"):
                        param["initialValue"] = en_param["initialValue"]
                    params_list.append(param)
            elif isinstance(en_params, list):
                params_list = en_params
            entry["params"] = params_list

            if en_item.get("isTrigger"):
                entry["isTrigger"] = True
            if en_item.get("isAsync"):
                entry["isAsync"] = True
            if en_item.get("returnType"):
                entry["returnType"] = en_item["returnType"]
            merged_items.append(entry)
        merged[ace_type] = merged_items

    en_properties = en.get("properties", {})
    zh_properties = zh.get("properties", {})
    properties = []
    if isinstance(en_properties, dict):
        for property_id, en_property in en_properties.items():
            zh_property = (
                zh_properties.get(property_id, {})
                if isinstance(zh_properties, dict)
                else {}
            )
            properties.append(
                {
                    "id": property_id,
                    "name_en": en_property.get("name", property_id),
                    "name_zh": zh_property.get(
                        "name", en_property.get("name", property_id)
                    ),
                    "description_en": en_property.get("desc", ""),
                    "description_zh": zh_property.get("desc", ""),
                }
            )
    elif isinstance(en_properties, list):
        properties = en_properties
    merged["properties"] = properties
    return merged


class SchemaIndex:
    """Lazy index of version-matched plugin, behavior, and effect names."""

    def __init__(self, schema_dir: Path | None = None):
        resolved_schema_dir = (
            Path(schema_dir) if schema_dir is not None else _default_schema_dir
        )
        if resolved_schema_dir is None:
            raise TypeError(
                "SchemaIndex requires schema_dir when used outside the "
                "src.rag.lookup compatibility facade"
            )
        self._schema_dir = resolved_schema_dir
        self._plugins: dict[str, dict] = {}
        self._behaviors: dict[str, dict] = {}
        self._name_map: dict[str, tuple[str, bool]] = {}
        self._effect_name_map: dict[str, str] = {}
        self._loaded = False

    @property
    def schema_dir(self) -> Path:
        return self._schema_dir

    def ensure_loaded(self) -> None:
        """Load local Schema files exactly once."""
        if self._loaded:
            return
        self._loaded = True

        index_data: dict = {}
        index_path = self._schema_dir / "_index.json"
        if index_path.exists():
            try:
                index_data = json.loads(index_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.error(
                    "[SchemaIndex] Invalid schema index %s: %s",
                    index_path,
                    exc,
                )

        for addon_type, store, is_behavior in (
            ("plugins", self._plugins, False),
            ("behaviors", self._behaviors, True),
        ):
            en_dir = self._schema_dir / "en-US" / addon_type
            zh_dir = self._schema_dir / "zh-CN" / addon_type
            index_section = index_data.get(addon_type, {})
            if not en_dir.is_dir():
                logger.error(
                    "[SchemaIndex] Missing %s. Run `python scripts/init.py` "
                    "or restore data/c3-schemas.",
                    en_dir,
                )
                continue

            for path in sorted(en_dir.glob("*.json")):
                if path.stem == "index":
                    continue
                try:
                    en_data = json.loads(path.read_text(encoding="utf-8"))
                    zh_path = zh_dir / path.name
                    zh_data = (
                        json.loads(zh_path.read_text(encoding="utf-8"))
                        if zh_path.exists()
                        else {}
                    )
                    merged = _merge_bilingual(en_data, zh_data)
                    item_id = merged.get("id", path.stem)
                    if item_id in index_section:
                        merged["originalId"] = index_section[item_id].get(
                            "originalId", item_id
                        )
                    store[item_id] = merged
                    self._register_names(merged, item_id, is_behavior)
                except (json.JSONDecodeError, OSError, TypeError) as exc:
                    logger.warning(
                        "[SchemaIndex] Failed to load %s: %s",
                        path.name,
                        exc,
                    )

        for effect_id, effect in index_data.get("effects", {}).items():
            for value in (
                effect_id,
                effect.get("name_en", ""),
                effect.get("name_zh", ""),
            ):
                if value:
                    self._effect_name_map[value.lower()] = effect_id

        if not self._plugins and not self._behaviors:
            logger.error(
                "[SchemaIndex] No lookup schemas loaded from %s",
                self._schema_dir,
            )
        logger.info(
            "[SchemaIndex] Loaded %d plugins, %d behaviors, %d name mappings",
            len(self._plugins),
            len(self._behaviors),
            len(self._name_map),
        )

    # Compatibility for callers that used the historical private loader.
    _load = ensure_loaded

    def _register_names(
        self,
        data: dict,
        item_id: str,
        is_behavior: bool,
    ) -> None:
        entry = (item_id, is_behavior)
        self._name_map[item_id.lower()] = entry
        original_id = data.get("originalId", "")
        if original_id:
            self._name_map[original_id.lower()] = entry
        for key in ("name_zh", "name_en"):
            name = data.get(key, "")
            if name:
                self._name_map[name.lower()] = entry

    def iter_schemas(self) -> Iterator[tuple[str, str, dict]]:
        """Iterate ``(addon_type, id, schema)`` without exposing stores."""
        self.ensure_loaded()
        for addon_type, store in (
            ("plugins", self._plugins),
            ("behaviors", self._behaviors),
        ):
            for item_id, schema in store.items():
                yield addon_type, item_id, schema

    def resolve_name(self, name: str) -> tuple[str, bool] | None:
        """Resolve an exact, case-insensitive plugin or behavior name."""
        self.ensure_loaded()
        query = name.strip().lower()
        return self._name_map.get(query) if query else None

    def find_name_in_query(
        self,
        query: str,
    ) -> tuple[str, bool, int, int] | None:
        """Find the longest registered entity span in free-form text."""
        self.ensure_loaded()
        query_lower = query.lower()
        candidates: list[tuple[int, int, int, str, bool]] = []
        for registered, (plugin_id, is_behavior) in self._name_map.items():
            start = query_lower.find(registered)
            while start >= 0:
                end = start + len(registered)
                if registered.isascii():
                    left_ok = start == 0 or not _is_ascii_identifier_char(
                        query_lower[start - 1]
                    )
                    right_ok = (
                        end == len(query_lower)
                        or not _is_ascii_identifier_char(query_lower[end])
                    )
                    if not (left_ok and right_ok):
                        start = query_lower.find(registered, start + 1)
                        continue
                candidates.append(
                    (len(registered), -start, end, plugin_id, is_behavior)
                )
                break
        if not candidates:
            return None
        _, negative_start, end, plugin_id, is_behavior = max(candidates)
        return plugin_id, is_behavior, -negative_start, end

    def find_effect_in_query(self, query: str) -> tuple[str, int, int] | None:
        """Find a versioned effect name without making it a Direct Lookup hit."""
        self.ensure_loaded()
        query_lower = query.lower()
        candidates: list[tuple[int, int, int, str]] = []
        for registered, effect_id in self._effect_name_map.items():
            start = query_lower.find(registered)
            if start < 0:
                continue
            end = start + len(registered)
            if registered.isascii():
                left_ok = start == 0 or not _is_ascii_identifier_char(
                    query_lower[start - 1]
                )
                right_ok = (
                    end == len(query_lower)
                    or not _is_ascii_identifier_char(query_lower[end])
                )
                if not (left_ok and right_ok):
                    continue
            candidates.append((len(registered), -start, end, effect_id))
        if not candidates:
            return None
        _, negative_start, end, effect_id = max(candidates)
        return effect_id, -negative_start, end

    def get_schema(
        self,
        item_id: str,
        is_behavior: bool = False,
    ) -> dict | None:
        self.ensure_loaded()
        store = self._behaviors if is_behavior else self._plugins
        return store.get(item_id)

    def get_ace_list(
        self,
        item_id: str,
        ace_type: str,
        is_behavior: bool = False,
    ) -> list[dict]:
        schema = self.get_schema(item_id, is_behavior)
        return schema.get(ace_type, []) if schema else []

    def get_all_ids(self) -> tuple[list[str], list[str]]:
        self.ensure_loaded()
        return list(self._plugins), list(self._behaviors)
