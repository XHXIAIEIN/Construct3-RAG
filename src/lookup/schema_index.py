"""Versioned bilingual Schema index used by deterministic lookup."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from src.lookup.schema_layout import (
    SCHEMA_ACE_TYPES,
    SCHEMA_INDEX_FILE,
    SCHEMA_LOCALES,
    SchemaManifestError,
    load_locale_index,
    locale_index_path,
)


logger = logging.getLogger(__name__)

def _is_ascii_identifier_char(char: str) -> bool:
    return char == "_" or "0" <= char <= "9" or "a" <= char.lower() <= "z"


def _is_whole_word(text: str, start: int, end: int) -> bool:
    """Whether ``text[start:end]`` has no identifier character on either side."""
    return (start == 0 or not _is_ascii_identifier_char(text[start - 1])) and (
        end == len(text) or not _is_ascii_identifier_char(text[end])
    )


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
        "commonAces": en.get("commonAces", {}),
    }

    for ace_type in SCHEMA_ACE_TYPES:
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

    def __init__(self, schema_dir: Path):
        self._schema_dir = Path(schema_dir)
        self._plugins: dict[str, dict] = {}
        self._behaviors: dict[str, dict] = {}
        self._name_map: dict[str, tuple[str, bool]] = {}
        # One name can belong to several effects: the zh-CN pack calls both
        # Brightness and Lighten 亮度.
        self._effect_name_map: dict[str, list[str]] = {}
        self._effect_files: dict[str, str] = {}
        self._effects: dict[str, dict] = {}
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
        index_path = self._schema_dir / SCHEMA_INDEX_FILE
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

        # The root index only lists effect ids; display names come from each
        # locale index so a query can name an effect in either language.
        for effect_id, entry in index_data.get("effects", {}).items():
            self._register_effect_name(effect_id, effect_id)
            if isinstance(entry, dict) and entry.get("file"):
                self._effect_files[effect_id] = str(entry["file"])
        for locale in SCHEMA_LOCALES:
            if not locale_index_path(self._schema_dir, locale).is_file():
                continue
            try:
                locale_sections = load_locale_index(self._schema_dir, locale)
            except SchemaManifestError as exc:
                logger.error("[SchemaIndex] Invalid %s locale index: %s", locale, exc)
                continue
            for effect_id, entry in locale_sections["effects"].items():
                self._register_effect_name(effect_id, effect_id)
                name = entry.get("name", "")
                if isinstance(name, str) and name:
                    self._register_effect_name(name, effect_id)

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

    def _register_effect_name(self, name: str, effect_id: str) -> None:
        ids = self._effect_name_map.setdefault(name.lower(), [])
        if effect_id not in ids:
            ids.append(effect_id)

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
                if registered.isascii() and not _is_whole_word(query_lower, start, end):
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

    def find_effect_in_query(
        self, query: str
    ) -> tuple[tuple[str, ...], int, int] | None:
        """Find the longest effect name in ``query``: every effect of that name, and its span."""
        self.ensure_loaded()
        query_lower = query.lower()
        candidates: list[tuple[int, int, int, tuple[str, ...]]] = []
        for registered, effect_ids in self._effect_name_map.items():
            start = query_lower.find(registered)
            if start < 0:
                continue
            end = start + len(registered)
            if registered.isascii() and not _is_whole_word(query_lower, start, end):
                continue
            candidates.append((len(registered), -start, end, tuple(effect_ids)))
        if not candidates:
            return None
        _, negative_start, end, effect_ids = max(candidates)
        return effect_ids, -negative_start, end

    def get_effect(self, effect_id: str) -> dict | None:
        """Return one effect with its parameters, English and Chinese side by side."""
        self.ensure_loaded()
        if effect_id in self._effects:
            return self._effects[effect_id]
        relative = self._effect_files.get(effect_id)
        if relative is None:
            return None
        records: dict[str, dict] = {}
        for locale in SCHEMA_LOCALES:
            path = self._schema_dir / locale / relative
            try:
                records[locale] = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("[SchemaIndex] Failed to load %s: %s", path, exc)
                return None
        en, zh = records["en-US"], records["zh-CN"]
        zh_params = {param.get("id"): param for param in zh.get("parameters", [])}
        effect = {
            "id": effect_id,
            "name_en": en.get("name", effect_id),
            "name_zh": zh.get("name", ""),
            "description_en": en.get("description", ""),
            "description_zh": zh.get("description", ""),
            "category": en.get("category", ""),
            "params": [
                {
                    "id": param.get("id", ""),
                    "type": param.get("type", ""),
                    "name_en": param.get("name", ""),
                    "name_zh": zh_params.get(param.get("id"), {}).get("name", ""),
                    "desc_en": param.get("desc", ""),
                    "desc_zh": zh_params.get(param.get("id"), {}).get("desc", ""),
                }
                for param in en.get("parameters", [])
            ],
        }
        self._effects[effect_id] = effect
        return effect

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
