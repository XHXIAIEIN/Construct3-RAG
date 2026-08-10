"""Typed, side-effect-controlled application settings.

Importing this module only defines immutable data structures and parsers.
Call :func:`load_settings` explicitly to read an environment mapping and select
the local schema directory. Dotenv loading remains a compatibility concern of
``src.config`` and is intentionally absent here.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from src.schema_layout import select_schema_dir


@dataclass(frozen=True, slots=True)
class PathSettings:
    base_dir: Path
    data_dir: Path
    manual_repo: str
    example_repo: str
    addon_sdk_repo: str
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
    ui_language: str


@dataclass(frozen=True, slots=True)
class VectorSettings:
    embedding_model_registry: tuple[tuple[str, int], ...]
    embedding_model: str
    embedding_dimension: int
    max_chunk_size: int
    top_k: int
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
class LLMSettings:
    provider: str
    model: str
    base_url: str
    api_key: str


@dataclass(frozen=True, slots=True)
class LookupSettings:
    ollama_model: str
    ollama_url: str


@dataclass(frozen=True, slots=True)
class ExpanderSettings:
    backend: str
    dict_source: str
    dict_filter: str
    api_provider: str
    api_key: str
    api_model: str
    local_model: str
    device: str
    timeout_s: float
    max_tokens: int
    top_k: int


@dataclass(frozen=True, slots=True)
class AppSettings:
    paths: PathSettings
    schema: SchemaSettings
    runtime: RuntimeSettings
    vector: VectorSettings
    features: FeatureSettings
    llm: LLMSettings
    lookup: LookupSettings
    expander: ExpanderSettings


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


def _float(source: Mapping[str, str], key: str, default: float) -> float:
    value = source.get(key)
    return default if value is None else float(value)


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
    root = Path(base_dir) if base_dir is not None else Path(__file__).parent.parent
    data_dir = root / "data"

    manual_repo = "Construct3-Manual"
    example_repo = "Construct-Example-Projects"
    addon_sdk_repo = "Construct-Addon-SDK"
    paths = PathSettings(
        base_dir=root,
        data_dir=data_dir,
        manual_repo=manual_repo,
        example_repo=example_repo,
        addon_sdk_repo=addon_sdk_repo,
        manual_dir=root.parent / manual_repo / "Construct3-Manual",
        example_projects_dir=root.parent / example_repo / "example-projects",
        addon_sdk_manual_dir=root.parent / manual_repo / "Construct3-Addon-SDK",
        addon_sdk_code_dir=root.parent / addon_sdk_repo,
    )

    version = _string(source, "C3_VERSION", "r495")
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
        ui_language=_string(source, "UI_LANGUAGE", "zh"),
    )
    vector = VectorSettings(
        embedding_model_registry=(
            ("BAAI/bge-m3", 1024),
            ("Qwen/Qwen3-Embedding-0.6B", 1024),
            ("Qwen/Qwen3-Embedding-4B", 2560),
            ("Qwen/Qwen3-Embedding-8B", 4096),
        ),
        embedding_model=_string(
            source,
            "EMBEDDING_MODEL",
            "Qwen/Qwen3-Embedding-0.6B",
        ),
        embedding_dimension=_integer(source, "EMBEDDING_DIMENSION", 1024),
        max_chunk_size=2000,
        top_k=5,
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
    llm = LLMSettings(
        provider=_string(source, "LLM_PROVIDER", "ollama"),
        model=_string(source, "LLM_MODEL", "qwen2.5:7b"),
        base_url=_string(source, "LLM_BASE_URL", "http://localhost:11434"),
        api_key=_string(source, "LLM_API_KEY", ""),
    )
    lookup = LookupSettings(
        ollama_model=_string(source, "LOOKUP_OLLAMA_MODEL", "qwen2.5:7b"),
        ollama_url=_string(
            source,
            "LOOKUP_OLLAMA_URL",
            "http://localhost:11434",
        ),
    )
    expander = ExpanderSettings(
        backend=_string(source, "EXPANDER_BACKEND", "dict"),
        dict_source=_string(source, "EXPANDER_DICT_SOURCE", "cilin"),
        dict_filter=_string(source, "EXPANDER_DICT_FILTER", "true"),
        api_provider=_string(source, "EXPANDER_API_PROVIDER", "dashscope"),
        api_key=_string(source, "EXPANDER_API_KEY", ""),
        api_model=_string(source, "EXPANDER_API_MODEL", "qwen-turbo"),
        local_model=_string(
            source,
            "EXPANDER_LOCAL_MODEL",
            "Qwen/Qwen3-0.5B",
        ),
        device=_string(source, "EXPANDER_DEVICE", "cpu"),
        timeout_s=_float(source, "EXPANDER_TIMEOUT_S", 5.0),
        max_tokens=_integer(source, "EXPANDER_MAX_TOKENS", 80),
        top_k=_integer(source, "EXPANDER_TOP_K", 12),
    )
    return AppSettings(
        paths=paths,
        schema=schema,
        runtime=runtime,
        vector=vector,
        features=features,
        llm=llm,
        lookup=lookup,
        expander=expander,
    )


__all__ = [
    "AppSettings",
    "FeatureSettings",
    "ExpanderSettings",
    "LLMSettings",
    "LookupSettings",
    "PathSettings",
    "RuntimeSettings",
    "SchemaSettings",
    "VectorSettings",
    "load_settings",
]
