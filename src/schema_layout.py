"""Typed conventions and validation for exported Construct 3 schema data."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


SCHEMA_LOCALES: tuple[str, ...] = ("en-US", "zh-CN")
PRIMARY_SCHEMA_LOCALE = "en-US"
SCHEMA_ADDON_TYPES: tuple[str, ...] = ("plugins", "behaviors", "effects")


class SchemaManifestError(ValueError):
    """Raised when ``_index.json`` does not satisfy the schema contract."""


@dataclass(frozen=True)
class SchemaManifestEntry:
    addon_id: str
    relative_file: PurePosixPath


@dataclass(frozen=True)
class SchemaManifest:
    """Validated language-neutral schema index."""

    version: str
    locales: tuple[str, ...]
    plugins: Mapping[str, SchemaManifestEntry]
    behaviors: Mapping[str, SchemaManifestEntry]
    effects: Mapping[str, SchemaManifestEntry]

    @property
    def sections(self) -> dict[str, Mapping[str, SchemaManifestEntry]]:
        return {
            "plugins": self.plugins,
            "behaviors": self.behaviors,
            "effects": self.effects,
        }

    @property
    def counts(self) -> dict[str, int]:
        return {name: len(entries) for name, entries in self.sections.items()}


def _required_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaManifestError(f"{location} must be a non-empty string")
    return value.strip()


def _manifest_entry(
    addon_type: str,
    addon_id: Any,
    value: Any,
) -> SchemaManifestEntry:
    addon_id = _required_string(addon_id, f"{addon_type} id")
    if not isinstance(value, dict):
        raise SchemaManifestError(f"{addon_type}.{addon_id} must be an object")
    raw_file = _required_string(value.get("file"), f"{addon_type}.{addon_id}.file")
    relative_file = PurePosixPath(raw_file.replace("\\", "/"))
    if (
        relative_file.is_absolute()
        or ".." in relative_file.parts
        or relative_file.suffix.lower() != ".json"
        or not relative_file.parts
        or relative_file.parts[0] != addon_type
    ):
        raise SchemaManifestError(
            f"{addon_type}.{addon_id}.file is not a canonical relative JSON path"
        )
    return SchemaManifestEntry(addon_id=addon_id, relative_file=relative_file)


def load_schema_manifest(root: Path) -> SchemaManifest:
    """Load and validate ``root/_index.json`` without validating data files."""
    index_path = Path(root) / "_index.json"
    try:
        raw = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SchemaManifestError(f"invalid schema manifest: {index_path}") from exc
    if not isinstance(raw, dict):
        raise SchemaManifestError("schema manifest root must be an object")

    version = _required_string(raw.get("version"), "version")
    raw_locales = raw.get("languages")
    if not isinstance(raw_locales, list):
        raise SchemaManifestError("languages must be an array")
    locales = tuple(
        _required_string(locale, f"languages[{index}]")
        for index, locale in enumerate(raw_locales)
    )
    if not set(SCHEMA_LOCALES).issubset(locales):
        raise SchemaManifestError(
            "languages must include canonical locales: " + ", ".join(SCHEMA_LOCALES)
        )

    sections: dict[str, dict[str, SchemaManifestEntry]] = {}
    for addon_type in SCHEMA_ADDON_TYPES:
        raw_section = raw.get(addon_type)
        if not isinstance(raw_section, dict) or not raw_section:
            raise SchemaManifestError(f"{addon_type} manifest must be a non-empty object")
        entries = {
            str(addon_id): _manifest_entry(addon_type, addon_id, value)
            for addon_id, value in raw_section.items()
        }
        files = [entry.relative_file for entry in entries.values()]
        if len(files) != len(set(files)):
            raise SchemaManifestError(f"{addon_type} manifest contains duplicate files")
        sections[addon_type] = entries

    return SchemaManifest(
        version=version,
        locales=locales,
        plugins=sections["plugins"],
        behaviors=sections["behaviors"],
        effects=sections["effects"],
    )


def _schema_file_is_valid(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return isinstance(value, dict)


def schema_is_complete(root: Path) -> bool:
    """Return whether *root* is a complete, parseable bilingual dataset."""
    root = Path(root)
    try:
        manifest = load_schema_manifest(root)
    except SchemaManifestError:
        return False

    for entries in manifest.sections.values():
        for entry in entries.values():
            relative_path = Path(*entry.relative_file.parts)
            for locale in SCHEMA_LOCALES:
                if not _schema_file_is_valid(root / locale / relative_path):
                    return False
    return True


def schema_version(root: Path) -> str:
    """Return the validated manifest version, or an empty string on error."""
    try:
        return load_schema_manifest(Path(root)).version
    except SchemaManifestError:
        return ""


def schema_counts(root: Path, locale: str = PRIMARY_SCHEMA_LOCALE) -> dict[str, int]:
    """Count exported JSON files by addon type for setup diagnostics."""
    return {
        addon_type: len(list((Path(root) / locale / addon_type).glob("*.json")))
        for addon_type in SCHEMA_ADDON_TYPES
    }


def select_schema_dir(
    *,
    generated: Path,
    bundled: Path,
    expected_version: str,
    explicit: Path | None = None,
) -> Path:
    """Choose a schema directory while preserving explicit override semantics."""
    if explicit is not None:
        return explicit
    if schema_is_complete(generated) and schema_version(generated) == expected_version:
        return generated
    if schema_is_complete(bundled):
        return bundled
    return generated
