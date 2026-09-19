"""Typed, side-effect-controlled application settings.

Importing this module only defines immutable data structures and parsers.
Call :func:`load_settings` explicitly to read an environment mapping and select
the local schema directory. Dotenv loading is a process entry-point concern
(``src.api``, each ``scripts/*.py``) and is intentionally absent here.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from src.lookup.schema_layout import select_schema_dir


@dataclass(frozen=True, slots=True)
class PathSettings:
    base_dir: Path
    data_dir: Path
    manual_dir: Path
    example_projects_dir: Path
    addon_sdk_manual_dir: Path
    addon_sdk_code_dir: Path

    @property
    def manual_available(self) -> bool:
        return self.manual_dir.exists()

    @property
    def examples_available(self) -> bool:
        return self.example_projects_dir.exists()

    @property
    def addon_sdk_manual_available(self) -> bool:
        return self.addon_sdk_manual_dir.exists()

    @property
    def addon_sdk_code_available(self) -> bool:
        return self.addon_sdk_code_dir.exists()


@dataclass(frozen=True, slots=True)
class SchemaSettings:
    version: str
    cdn_base: str
    cache_dir: Path
    bundled_dir: Path
    generated_dir: Path
    directory: Path


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    qdrant_host: str
    qdrant_port: int
    server_port: int


@dataclass(frozen=True, slots=True)
class VectorSettings:
    embedding_model: str
    reranker_model: str
    reranker_top_k: int
    contextual_chunking_cache: Path


@dataclass(frozen=True, slots=True)
class FeatureSettings:
    lite_mode: bool
    bge_m3_native_sparse: bool
    reranker_enabled: bool
    bm25_enabled: bool
    contextual_chunking_enabled: bool


@dataclass(frozen=True, slots=True)
class AppSettings:
    paths: PathSettings
    schema: SchemaSettings
    runtime: RuntimeSettings
    vector: VectorSettings
    features: FeatureSettings


def _string(source: Mapping[str, str], key: str, default: str) -> str:
    value = source.get(key)
    return default if value is None else value


def _boolean(source: Mapping[str, str], key: str, default: bool) -> bool:
    value = source.get(key)
    if value is None:
        return default
    return value.lower() == "true"


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
    mapping deliberately ignores it, which keeps tests and embedding callers
    deterministic. The only filesystem inspection is local schema selection and
    the dynamic availability properties on :class:`PathSettings`.
    """
    source = os.environ if environ is None else environ
    root = Path(base_dir) if base_dir is not None else Path(__file__).parent.parent.parent
    data_dir = root / "data"

    manual_repo = "Construct3-Manual"
    example_repo = "Construct-Example-Projects"
    addon_sdk_repo = "Construct-Addon-SDK"
    paths = PathSettings(
        base_dir=root,
        data_dir=data_dir,
        manual_dir=root.parent / manual_repo / "Construct3-Manual",
        example_projects_dir=root.parent / example_repo / "example-projects",
        addon_sdk_manual_dir=root.parent / manual_repo / "Construct3-Addon-SDK",
        addon_sdk_code_dir=root.parent / addon_sdk_repo,
    )

    version = _string(source, "C3_VERSION", "r495.2")
    cache_dir = _path(source, "C3_CACHE_DIR", root / ".cache" / "c3-cdn")
    bundled_dir = data_dir / "c3-schemas"
    generated_dir = cache_dir / version / "schemas"
    explicit_schema = source.get("C3_SCHEMA_DIR")
    schema = SchemaSettings(
        version=version,
        cdn_base=_string(source, "C3_CDN_BASE", "https://editor.construct.net"),
        cache_dir=cache_dir,
        bundled_dir=bundled_dir,
        generated_dir=generated_dir,
        directory=select_schema_dir(
            generated=generated_dir,
            bundled=bundled_dir,
            expected_version=version,
            explicit=Path(explicit_schema) if explicit_schema else None,
        ),
    )

    runtime = RuntimeSettings(
        qdrant_host=_string(source, "QDRANT_HOST", "localhost"),
        qdrant_port=_integer(source, "QDRANT_PORT", 6333),
        server_port=_integer(source, "RAG_SERVER_PORT", 8765),
    )
    vector = VectorSettings(
        embedding_model=_string(
            source,
            "EMBEDDING_MODEL",
            "Qwen/Qwen3-Embedding-0.6B",
        ),
        reranker_model=_string(
            source,
            "RERANKER_MODEL",
            "BAAI/bge-reranker-v2-m3",
        ),
        reranker_top_k=_integer(source, "RERANKER_TOP_K", 20),
        contextual_chunking_cache=_path(
            source,
            "CONTEXTUAL_CHUNKING_CACHE",
            data_dir / "chunk_contexts.json",
        ),
    )
    features = FeatureSettings(
        lite_mode=_boolean(source, "LITE_MODE", True),
        bge_m3_native_sparse=_boolean(source, "BGE_M3_NATIVE_SPARSE", False),
        reranker_enabled=_boolean(source, "RERANKER_ENABLED", True),
        bm25_enabled=_boolean(source, "BM25_ENABLED", False),
        contextual_chunking_enabled=_boolean(
            source,
            "CONTEXTUAL_CHUNKING_ENABLED",
            False,
        ),
    )
    return AppSettings(
        paths=paths,
        schema=schema,
        runtime=runtime,
        vector=vector,
        features=features,
    )


__all__ = [
    "AppSettings",
    "FeatureSettings",
    "PathSettings",
    "RuntimeSettings",
    "SchemaSettings",
    "VectorSettings",
    "load_settings",
]
