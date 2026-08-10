"""Typed settings and historical config facade regression tests."""

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
    assert settings.schema.version == "r495"
    assert settings.schema.cache_dir == tmp_path / ".cache" / "c3-cdn"
    assert settings.schema.generated_dir == (
        tmp_path / ".cache" / "c3-cdn" / "r495" / "schemas"
    )
    assert settings.schema.directory == settings.schema.generated_dir
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
            "UI_LANGUAGE": "en",
            "EMBEDDING_MODEL": "example/embedding",
            "EMBEDDING_DIMENSION": "2048",
            "BGE_M3_NATIVE_SPARSE": "TRUE",
            "LITE_MODE": "false",
            "RERANKER_ENABLED": "FALSE",
            "RERANKER_TOP_K": "37",
            "RERANKER_MODEL": "example/reranker",
            "BM25_ENABLED": "true",
            "CONTEXTUAL_CHUNKING_ENABLED": "true",
            "CONTEXTUAL_CHUNKING_CACHE": str(context_cache),
            "LLM_PROVIDER": "openai",
            "LLM_MODEL": "example/chat",
            "LLM_BASE_URL": "https://llm.example.invalid",
            "LLM_API_KEY": "secret",
            "LOOKUP_OLLAMA_MODEL": "example/lookup",
            "LOOKUP_OLLAMA_URL": "https://lookup.example.invalid",
            "EXPANDER_BACKEND": "local",
            "EXPANDER_DICT_SOURCE": "hownet",
            "EXPANDER_DICT_FILTER": "false",
            "EXPANDER_API_PROVIDER": "deepseek",
            "EXPANDER_API_KEY": "expand-secret",
            "EXPANDER_API_MODEL": "example/expand-api",
            "EXPANDER_LOCAL_MODEL": "example/expand-local",
            "EXPANDER_DEVICE": "cuda",
            "EXPANDER_TIMEOUT_S": "2.5",
            "EXPANDER_MAX_TOKENS": "91",
            "EXPANDER_TOP_K": "17",
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
    assert settings.runtime.ui_language == "en"
    assert settings.vector.embedding_model == "example/embedding"
    assert settings.vector.embedding_dimension == 2048
    assert settings.vector.reranker_model == "example/reranker"
    assert settings.vector.reranker_top_k == 37
    assert settings.vector.contextual_chunking_cache == context_cache
    assert settings.features.bge_m3_native_sparse is True
    assert settings.features.lite_mode is False
    assert settings.features.reranker_enabled is False
    assert settings.features.bm25_enabled is True
    assert settings.features.contextual_chunking_enabled is True
    assert settings.llm.provider == "openai"
    assert settings.llm.model == "example/chat"
    assert settings.llm.base_url == "https://llm.example.invalid"
    assert settings.llm.api_key == "secret"
    assert settings.lookup.ollama_model == "example/lookup"
    assert settings.lookup.ollama_url == "https://lookup.example.invalid"
    assert settings.expander.backend == "local"
    assert settings.expander.dict_source == "hownet"
    assert settings.expander.dict_filter == "false"
    assert settings.expander.api_provider == "deepseek"
    assert settings.expander.api_key == "expand-secret"
    assert settings.expander.api_model == "example/expand-api"
    assert settings.expander.local_model == "example/expand-local"
    assert settings.expander.device == "cuda"
    assert settings.expander.timeout_s == 2.5
    assert settings.expander.max_tokens == 91
    assert settings.expander.top_k == 17


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
        "EMBEDDING_DIMENSION",
        "RERANKER_TOP_K",
        "EXPANDER_MAX_TOKENS",
        "EXPANDER_TOP_K",
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


def test_config_facade_matches_typed_settings_snapshot():
    import src.config as config

    assert config.BASE_DIR == config.SETTINGS.paths.base_dir
    assert config.DATA_DIR == config.SETTINGS.paths.data_dir
    assert config.C3_VERSION == config.SETTINGS.schema.version
    assert config.SCHEMA_DIR == config.SETTINGS.schema.directory
    assert config.QDRANT_PORT == config.SETTINGS.runtime.qdrant_port
    assert config.LITE_MODE == config.SETTINGS.features.lite_mode
    assert config.EMBEDDING_MODEL == config.SETTINGS.vector.embedding_model
    assert config.EMBEDDING_DIMENSION == config.SETTINGS.vector.embedding_dimension
    assert config.MANUAL_AVAILABLE == config.SETTINGS.paths.manual_available
    assert config.LLM_PROVIDER == config.SETTINGS.llm.provider
    assert config.LOOKUP_OLLAMA_URL == config.SETTINGS.lookup.ollama_url
    assert config.EXPANDER_TIMEOUT_S == config.SETTINGS.expander.timeout_s


def test_config_facade_preserves_every_historical_constant():
    import src.config as config

    historical_names = {
        "ADDON_SDK_CODE_AVAILABLE",
        "ADDON_SDK_CODE_DIR",
        "ADDON_SDK_MANUAL_AVAILABLE",
        "ADDON_SDK_MANUAL_DIR",
        "ADDON_SDK_REPO",
        "BASE_DIR",
        "BGE_M3_NATIVE_SPARSE",
        "BM25_ENABLED",
        "C3_CACHE_DIR",
        "C3_CDN_BASE",
        "C3_VERSION",
        "CONTEXTUAL_CHUNKING_CACHE",
        "CONTEXTUAL_CHUNKING_ENABLED",
        "DATA_DIR",
        "EMBEDDING_DIMENSION",
        "EMBEDDING_MODEL",
        "EMBEDDING_MODEL_REGISTRY",
        "EXAMPLE_PROJECTS_DIR",
        "EXAMPLE_REPO",
        "EXAMPLES_AVAILABLE",
        "EXPANDER_API_KEY",
        "EXPANDER_API_MODEL",
        "EXPANDER_API_PROVIDER",
        "EXPANDER_BACKEND",
        "EXPANDER_DEVICE",
        "EXPANDER_DICT_FILTER",
        "EXPANDER_DICT_SOURCE",
        "EXPANDER_LOCAL_MODEL",
        "EXPANDER_MAX_TOKENS",
        "EXPANDER_TIMEOUT_S",
        "EXPANDER_TOP_K",
        "LITE_MODE",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "LLM_PROVIDER",
        "LOOKUP_OLLAMA_MODEL",
        "LOOKUP_OLLAMA_URL",
        "MANUAL_AVAILABLE",
        "MANUAL_DIR",
        "MANUAL_REPO",
        "MAX_CHUNK_SIZE",
        "QDRANT_HOST",
        "QDRANT_PORT",
        "RAG_SERVER_PORT",
        "RERANKER_ENABLED",
        "RERANKER_MODEL",
        "RERANKER_TOP_K",
        "SCHEMA_DIR",
        "TOP_K",
        "UI_LANGUAGE",
    }

    assert historical_names <= set(config.__all__)
    assert all(hasattr(config, name) for name in historical_names)


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
