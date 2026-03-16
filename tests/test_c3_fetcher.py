"""Tests for C3Fetcher — CDN access layer with weekly cache expiry."""
import json
import os
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.ingest.c3_fetcher import C3Fetcher, _cache_expired


@pytest.fixture
def fetcher(tmp_path):
    return C3Fetcher(version="r476", cache_dir=tmp_path)


def test_fetch_caches_locally(fetcher):
    """Fetched data is cached to disk."""
    mock_data = {"pluginList": {"Sprite": {"path": "general/sprite"}}}
    with patch.object(fetcher, "_http_get", return_value=json.dumps(mock_data).encode()):
        result = fetcher.fetch("plugins/pluginList.json")
        assert result == mock_data
        # Second call should use cache, not HTTP
        fetcher._http_get = MagicMock(side_effect=Exception("should not be called"))
        result2 = fetcher.fetch("plugins/pluginList.json")
        assert result2 == mock_data


def test_fetch_force_bypasses_cache(fetcher):
    """force=True always hits HTTP even if cache exists."""
    data_v1 = {"v": 1}
    data_v2 = {"v": 2}
    with patch.object(fetcher, "_http_get", return_value=json.dumps(data_v1).encode()):
        fetcher.fetch("test.json")
    with patch.object(fetcher, "_http_get", return_value=json.dumps(data_v2).encode()):
        result = fetcher.fetch("test.json", force=True)
        assert result == data_v2


def test_handles_bom(fetcher):
    """UTF-8 BOM in response is stripped."""
    mock_data = {"ok": True}
    bom_bytes = b"\xef\xbb\xbf" + json.dumps(mock_data).encode()
    with patch.object(fetcher, "_http_get", return_value=bom_bytes):
        result = fetcher.fetch("bom_test.json")
        assert result == mock_data


def test_get_latest_version(fetcher):
    """Detect latest stable version from versions.json."""
    mock_versions = [
        {"branchName": "Beta", "releaseName": "r477"},
        {"branchName": "Stable", "releaseName": "r476"},
        {"branchName": "LTS", "releaseName": "r449.3"},
    ]
    with patch.object(fetcher, "_http_get", return_value=json.dumps(mock_versions).encode()):
        assert fetcher.get_latest_stable_version() == "r476"


def test_cache_expired_old_file(tmp_path):
    """Cache files older than 10 days are always expired (crosses a Wednesday)."""
    cache_file = tmp_path / "test_cache"
    cache_file.write_text("old")
    old_time = time.time() - 10 * 86400
    os.utime(cache_file, (old_time, old_time))
    assert _cache_expired(cache_file) is True


def test_cache_fresh_file(tmp_path):
    """Cache files written just now should not be expired."""
    cache_file = tmp_path / "test_cache"
    cache_file.write_text("fresh")
    assert _cache_expired(cache_file) is False


def test_cache_nonexistent_file(tmp_path):
    """Non-existent file counts as expired."""
    assert _cache_expired(tmp_path / "nope") is True


def test_fetch_all_aces(fetcher):
    """Convenience method returns joined plugin + behavior ACEs."""
    mock_plugin_aces = {"Sprite": {"": {"conditions": [{"id": "c1"}]}}}
    mock_behavior_aces = {"Platform": {"": {"actions": [{"id": "a1"}]}}}
    with patch.object(fetcher, "fetch", side_effect=[mock_plugin_aces, mock_behavior_aces]):
        result = fetcher.fetch_all_aces()
        assert "Sprite" in result["plugins"]
        assert "Platform" in result["behaviors"]


def test_fetch_examples(fetcher):
    """fetch_examples unwraps the 'projects' key."""
    mock = {"projects": [{"id": "demo"}]}
    with patch.object(fetcher, "fetch", return_value=mock):
        result = fetcher.fetch_examples()
        assert result == [{"id": "demo"}]


def test_fetch_effects(fetcher):
    """fetch_effects unwraps the 'all' key."""
    mock = {"all": [{"json": {"id": "blur"}}]}
    with patch.object(fetcher, "fetch", return_value=mock):
        result = fetcher.fetch_effects()
        assert result == [{"json": {"id": "blur"}}]
