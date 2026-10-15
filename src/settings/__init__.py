"""Immutable application settings, built by :func:`load_settings`.

Importing this module defines the settings types and reads nothing.
:func:`load_settings` reads an environment mapping and the Construct release
that the schema directory's ``_index.json`` records; a data refresh asks the
CDN for its target release instead.
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


def load_settings(
    environ: Mapping[str, str] | None = None,
    base_dir: Path | None = None,
) -> AppSettings:
    """Build the settings tree from an environment mapping and a repository root.

    ``environ=None`` reads the process environment; an empty mapping ignores it,
    which keeps tests and library callers deterministic. ``base_dir`` defaults
    to this checkout. The only file read is the version in the schema manifest.
    """
    source = os.environ if environ is None else environ
    root = Path(base_dir) if base_dir is not None else Path(__file__).parents[2]
    data_dir = root / "data"

    directory = Path(source.get("C3_SCHEMA_DIR") or data_dir / "c3-schemas")
    return AppSettings(
        paths=PathSettings(base_dir=root, data_dir=data_dir),
        schema=SchemaSettings(
            version=schema_version(directory),
            cdn_base=source.get("C3_CDN_BASE", "https://editor.construct.net"),
            cache_dir=Path(source.get("C3_CACHE_DIR", root / ".cache" / "c3-cdn")),
            directory=directory,
        ),
        runtime=RuntimeSettings(
            server_port=int(source.get("RAG_SERVER_PORT", 8765)),
        ),
    )


__all__ = [
    "AppSettings",
    "PathSettings",
    "RuntimeSettings",
    "SchemaSettings",
    "load_settings",
]
