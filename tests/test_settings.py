"""Typed settings regression tests."""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from src.settings import AppSettings, load_settings


def test_default_settings_are_grouped_immutable_and_lookup_only(tmp_path):
    settings = load_settings(environ={}, base_dir=tmp_path)

    assert isinstance(settings, AppSettings)
    assert settings.paths.base_dir == tmp_path
    assert settings.paths.data_dir == tmp_path / "data"
    assert settings.schema.version == "r495.2"
    assert settings.schema.cache_dir == tmp_path / ".cache" / "c3-cdn"
    assert settings.schema.generated_dir == (
        tmp_path / ".cache" / "c3-cdn" / "r495.2" / "schemas"
    )
    assert settings.schema.directory == settings.schema.bundled_dir
    assert settings.runtime.qdrant_host == "localhost"
    assert settings.runtime.qdrant_port == 6333
    assert settings.runtime.server_port == 8765
    assert settings.features.lite_mode is True
    assert settings.features.reranker_enabled is True
    assert settings.features.bm25_enabled is False

    with pytest.raises(FrozenInstanceError):
        settings.features.lite_mode = False


def test_environment_overrides_are_parsed_once(tmp_path):
    cache_dir = tmp_path / "cache"
    context_cache = tmp_path / "context.json"
    settings = load_settings(
        environ={
            "C3_VERSION": "r999",
            "C3_CDN_BASE": "https://cdn.example.invalid",
            "C3_CACHE_DIR": str(cache_dir),
            "QDRANT_HOST": "vector.internal",
            "QDRANT_PORT": "7333",
            "RAG_SERVER_PORT": "9876",
            "EMBEDDING_MODEL": "example/embedding",
            "BGE_M3_NATIVE_SPARSE": "TRUE",
            "LITE_MODE": "false",
            "RERANKER_ENABLED": "FALSE",
            "RERANKER_TOP_K": "37",
            "RERANKER_MODEL": "example/reranker",
            "BM25_ENABLED": "true",
            "CONTEXTUAL_CHUNKING_ENABLED": "true",
            "CONTEXTUAL_CHUNKING_CACHE": str(context_cache),
        },
        base_dir=tmp_path,
    )

    assert settings.schema.version == "r999"
    assert settings.schema.cdn_base == "https://cdn.example.invalid"
    assert settings.schema.cache_dir == cache_dir
    assert settings.schema.generated_dir == cache_dir / "r999" / "schemas"
    assert settings.runtime.qdrant_host == "vector.internal"
    assert settings.runtime.qdrant_port == 7333
    assert settings.runtime.server_port == 9876
    assert settings.vector.embedding_model == "example/embedding"
    assert settings.vector.reranker_model == "example/reranker"
    assert settings.vector.reranker_top_k == 37
    assert settings.vector.contextual_chunking_cache == context_cache
    assert settings.features.bge_m3_native_sparse is True
    assert settings.features.lite_mode is False
    assert settings.features.reranker_enabled is False
    assert settings.features.bm25_enabled is True
    assert settings.features.contextual_chunking_enabled is True


def test_explicit_schema_override_always_wins(tmp_path):
    explicit = tmp_path / "external-schema"

    settings = load_settings(
        environ={"C3_SCHEMA_DIR": str(explicit)},
        base_dir=tmp_path / "repo",
    )

    assert settings.schema.directory == explicit


def test_external_repository_availability_is_dynamic(tmp_path):
    root = tmp_path / "Construct3-RAG"
    settings = load_settings(environ={}, base_dir=root)

    assert settings.paths.manual_available is False
    assert settings.paths.examples_available is False

    settings.paths.manual_dir.mkdir(parents=True)
    settings.paths.example_projects_dir.mkdir(parents=True)

    assert settings.paths.manual_available is True
    assert settings.paths.examples_available is True


@pytest.mark.parametrize(
    "key",
    [
        "QDRANT_PORT",
        "RAG_SERVER_PORT",
        "RERANKER_TOP_K",
    ],
)
def test_invalid_integer_setting_fails_with_source_key_context(tmp_path, key):
    with pytest.raises(ValueError):
        load_settings(environ={key: "not-an-integer"}, base_dir=tmp_path)


def test_typed_settings_module_has_no_dotenv_or_external_runtime_probe():
    import src.settings as settings_module

    source = inspect.getsource(settings_module)

    assert "dotenv" not in source
    assert "qdrant_client" not in source
    assert "sentence_transformers" not in source


def test_default_path_derivation_matches_historical_layout(tmp_path):
    root = tmp_path / "Construct3-RAG"
    settings = load_settings(environ={}, base_dir=root)

    assert settings.paths.manual_dir == (
        tmp_path / "Construct3-Manual" / "Construct3-Manual"
    )
    assert settings.paths.example_projects_dir == (
        tmp_path / "Construct-Example-Projects" / "example-projects"
    )
    assert settings.paths.addon_sdk_manual_dir == (
        tmp_path / "Construct3-Manual" / "Construct3-Addon-SDK"
    )
    assert settings.paths.addon_sdk_code_dir == tmp_path / "Construct-Addon-SDK"
