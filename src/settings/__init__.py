"""Typed, side-effect-controlled application settings.

Importing this module only defines immutable data structures and parsers.
Call :func:`load_settings` explicitly to read an environment mapping. The
Construct release is the one the schema directory's ``_index.json`` records;
a data refresh asks the CDN for its target instead.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from src.lookup.schema_layout import schema_version


@dataclass(frozen=True, slots=True)
class PathSettings:
    base_dir: Path
    data_dir: Path


@dataclass(frozen=True, slots=True)
class SchemaSettings:
    version: str
    cdn_base: str
    cache_dir: Path
    directory: Path


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    server_port: int


@dataclass(frozen=True, slots=True)
class AppSettings:
    paths: PathSettings
    schema: SchemaSettings
    runtime: RuntimeSettings


def _string(source: Mapping[str, str], key: str, default: str) -> str:
    value = source.get(key)
    return default if value is None else value


def _integer(source: Mapping[str, str], key: str, default: int) -> int:
    value = source.get(key)
    return default if value is None else int(value)


def _path(source: Mapping[str, str], key: str, default: Path) -> Path:
    value = source.get(key)
    return default if value is None else Path(value)


def load_settings(
    environ: Mapping[str, str] | None = None,
    base_dir: Path | None = None,
) -> AppSettings:
    """Build an immutable settings tree from explicit inputs.

    ``environ=None`` reads the current process environment. Passing an empty
    mapping deliberately ignores it, which keeps tests and library callers
    deterministic. The only filesystem read is the schema manifest's version.
    """
    source = os.environ if environ is None else environ
    root = Path(base_dir) if base_dir is not None else Path(__file__).parent.parent.parent
    data_dir = root / "data"

    paths = PathSettings(base_dir=root, data_dir=data_dir)

    explicit_schema = source.get("C3_SCHEMA_DIR")
    directory = Path(explicit_schema) if explicit_schema else data_dir / "c3-schemas"
    schema = SchemaSettings(
        version=schema_version(directory),
        cdn_base=_string(source, "C3_CDN_BASE", "https://editor.construct.net"),
        cache_dir=_path(source, "C3_CACHE_DIR", root / ".cache" / "c3-cdn"),
        directory=directory,
    )

    runtime = RuntimeSettings(
        server_port=_integer(source, "RAG_SERVER_PORT", 8765),
    )
    return AppSettings(paths=paths, schema=schema, runtime=runtime)


__all__ = [
    "AppSettings",
    "PathSettings",
    "RuntimeSettings",
    "SchemaSettings",
    "load_settings",
]
