"""Typed settings regression tests."""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from src.settings import AppSettings, load_settings


def test_default_settings_are_grouped_and_immutable(tmp_path):
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
    assert settings.runtime.server_port == 8765

    with pytest.raises(FrozenInstanceError):
        settings.runtime.server_port = 1


def test_environment_overrides_are_parsed_once(tmp_path):
    cache_dir = tmp_path / "cache"
    settings = load_settings(
        environ={
            "C3_VERSION": "r999",
            "C3_CDN_BASE": "https://cdn.example.invalid",
            "C3_CACHE_DIR": str(cache_dir),
            "RAG_SERVER_PORT": "9876",
        },
        base_dir=tmp_path,
    )

    assert settings.schema.version == "r999"
    assert settings.schema.cdn_base == "https://cdn.example.invalid"
    assert settings.schema.cache_dir == cache_dir
    assert settings.schema.generated_dir == cache_dir / "r999" / "schemas"
    assert settings.runtime.server_port == 9876


def test_explicit_schema_override_always_wins(tmp_path):
    explicit = tmp_path / "external-schema"

    settings = load_settings(
        environ={"C3_SCHEMA_DIR": str(explicit)},
        base_dir=tmp_path / "repo",
    )

    assert settings.schema.directory == explicit


def test_invalid_integer_setting_fails(tmp_path):
    with pytest.raises(ValueError):
        load_settings(environ={"RAG_SERVER_PORT": "not-an-integer"}, base_dir=tmp_path)


def test_typed_settings_module_has_no_dotenv_or_external_runtime_probe():
    import src.settings as settings_module

    source = inspect.getsource(settings_module)

    assert "dotenv" not in source
    assert "urllib" not in source
    assert "socket" not in source
