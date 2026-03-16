"""Tests for examples_parser CDN path — C3Fetcher + c3proj enrichment."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.ingest.examples_parser import load_examples_for_vectordb


@pytest.fixture
def mock_fetcher():
    f = MagicMock()
    f.fetch_examples.return_value = [
        {
            "id": "platformer-basics",
            "tags": ["beginner", "game-template", "platformer"],
            "used-addons": {
                "plugins": ["Sprite", "Keyboard"],
                "behaviors": ["Platform", "Solid"],
                "effects": [],
            },
        },
        {
            "id": "particle-demo",
            "tags": ["intermediate", "effect-blur"],
            "used-addons": {
                "plugins": ["Particles"],
                "behaviors": [],
                "effects": ["blur"],
            },
        },
    ]
    return f


@pytest.fixture
def fake_projects(tmp_path):
    proj = tmp_path / "platformer-basics"
    proj.mkdir()
    (proj / "project.c3proj").write_text(json.dumps({
        "name": "Platformer Basics",
        "savedWithRelease": 47600,
        "usedAddons": [
            {"type": "plugin", "id": "Sprite", "name": "Sprite"},
            {"type": "plugin", "id": "Keyboard", "name": "Keyboard"},
            {"type": "behavior", "id": "Platform", "name": "Platform"},
        ],
        "layouts": {"items": ["Game"]},
        "eventSheets": {"items": ["Events"]},
    }), encoding="utf-8")
    return tmp_path


def test_loads_from_cdn_plus_c3proj(mock_fetcher, fake_projects):
    """CDN metadata + c3proj enrichment produces correct docs."""
    docs = load_examples_for_vectordb(fetcher=mock_fetcher, projects_dir=fake_projects)
    assert len(docs) == 2

    d = docs[0]
    assert d["metadata"]["slug"] == "platformer-basics"
    # c3proj provides authoritative plugin/behavior lists
    assert "Sprite" in d["metadata"]["plugins"]
    assert "Platform" in d["metadata"]["behaviors"]
    # Title from c3proj "name" field
    assert "Platformer Basics" in d["text"]
    # c3proj enrichment: layouts and event sheets
    assert d["metadata"]["layouts"] == ["Game"]
    assert d["metadata"]["event_sheets"] == ["Events"]
    assert d["metadata"]["c3_version"] == 47600


def test_falls_back_without_fetcher():
    """Without fetcher, uses old browser JSON path (backward compat)."""
    docs = load_examples_for_vectordb()
    assert isinstance(docs, list)
    assert len(docs) > 0
    assert "id" in docs[0]
    assert "text" in docs[0]
    assert "metadata" in docs[0]
    assert "slug" in docs[0]["metadata"]


def test_skips_missing_c3proj(mock_fetcher, tmp_path):
    """Examples without matching c3proj still load using CDN data."""
    # tmp_path has no project directories at all
    docs = load_examples_for_vectordb(fetcher=mock_fetcher, projects_dir=tmp_path)
    assert len(docs) == 2

    d = docs[0]
    assert d["metadata"]["slug"] == "platformer-basics"
    # Falls back to CDN used-addons when no c3proj
    assert "Sprite" in d["metadata"]["plugins"]
    assert "Keyboard" in d["metadata"]["plugins"]
    assert "Platform" in d["metadata"]["behaviors"]
    # Title falls back to slug when no c3proj
    assert "platformer-basics" in d["text"]
    # No c3proj enrichment
    assert d["metadata"]["layouts"] == []
    assert d["metadata"]["c3_version"] == ""
