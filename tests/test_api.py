"""Tests for the FastAPI retrieval service (no external services needed)."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from src.rag.retriever import SearchResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _mock_search_results():
    return [
        SearchResult(
            text="Sprite is an object type for displaying images and animations.",
            score=0.92,
            source="c3_plugins",
            metadata={"source": "plugin-reference/sprite.md", "section_type": "overview"},
        ),
        SearchResult(
            text="Set the current animation of the Sprite.",
            score=0.85,
            source="c3_plugins",
            metadata={"source": "plugin-reference/sprite.md", "section_type": "actions"},
        ),
    ]


@pytest.fixture
def client():
    """Create test client with mocked retriever and lookup engine."""
    mock_retriever = MagicMock()
    mock_retriever.check_health.return_value = (True, "Qdrant is healthy")
    mock_retriever.health_check.return_value = {
        "status": "healthy",
        "qdrant_connected": True,
        "collections": {"c3_plugins": 100, "c3_guide": 50},
        "total_documents": 150,
        "missing_collections": [],
        "message": "2 collections, 150 documents",
    }
    mock_retriever.search_all_with_rerank.return_value = _mock_search_results()
    mock_retriever.filter_by_adaptive_threshold.side_effect = lambda r, **kw: r
    mock_retriever.search_plugin_by_name.return_value = _mock_search_results()[:1]
    mock_retriever._search.return_value = _mock_search_results()[:1]

    mock_lookup = MagicMock()
    mock_lookup.try_lookup.return_value = None  # default: no match

    import src.api
    src.api._retriever = mock_retriever
    src.api._lookup_engine = mock_lookup

    with TestClient(src.api.app) as c:
        yield c, mock_retriever, mock_lookup

    # Reset singletons
    src.api._retriever = None
    src.api._lookup_engine = None


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

def test_health_ok(client):
    c, retriever, _ = client
    resp = c.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["qdrant"] is True
    assert data["total_documents"] == 150
    assert "c3_plugins" in data["collections"]


def test_health_degraded(client):
    c, retriever, _ = client
    retriever.health_check.return_value = {
        "status": "unavailable",
        "qdrant_connected": False,
        "collections": {},
        "total_documents": 0,
        "missing_collections": [],
        "message": "Qdrant connection failed: Connection refused",
    }
    resp = c.get("/health")
    data = resp.json()
    assert data["status"] == "unavailable"
    assert data["qdrant"] is False


# ---------------------------------------------------------------------------
# /search — lookup route
# ---------------------------------------------------------------------------

def test_search_routes_to_lookup(client):
    """When lookup matches, returns lookup result with route='lookup+semantic'."""
    c, retriever, lookup = client
    from src.rag.lookup import LookupResponse as LR, LookupIntent
    intent = LookupIntent(
        intent_type="ace_list", plugin_id="sprite", ace_type="actions", tier=1,
    )
    lookup.try_lookup.return_value = LR(
        answer="| 名称 | 描述 |\n|---|---|\n| Set animation | ... |",
        query_type="lookup_ace_list",
        intent=intent,
        elapsed_ms=2.5,
    )
    resp = c.post("/search", json={"query": "列出 Sprite 的 action"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["route"] == "lookup+semantic"
    assert data["results"][0]["type"] == "lookup"
    assert "Set animation" in data["results"][0]["content"]
    # Retriever IS called (semantic search supplements lookup)
    retriever.search_all_with_rerank.assert_called_once()


def test_search_lookup_miss_falls_to_semantic(client):
    """When lookup doesn't match, falls through to semantic search."""
    c, retriever, lookup = client
    lookup.try_lookup.return_value = None
    resp = c.post("/search", json={"query": "怎么实现碰撞检测"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["route"] == "semantic"
    retriever.search_all_with_rerank.assert_called_once()


def test_search_skip_lookup(client):
    """skip_lookup=True bypasses lookup entirely."""
    c, retriever, lookup = client
    resp = c.post("/search", json={"query": "列出 Sprite 的 action", "skip_lookup": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["route"] == "semantic"
    lookup.try_lookup.assert_not_called()


# ---------------------------------------------------------------------------
# /search — semantic route
# ---------------------------------------------------------------------------

def test_search_semantic_basic(client):
    c, retriever, _ = client
    resp = c.post("/search", json={"query": "Sprite 动画", "skip_lookup": True})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 2
    assert data["results"][0]["type"] == "doc"
    assert data["results"][0]["source"] == "plugin-reference/sprite.md"
    assert data["route"] == "semantic"


def test_search_top_k(client):
    c, retriever, _ = client
    resp = c.post("/search", json={"query": "test", "top_k": 3, "skip_lookup": True})
    assert resp.status_code == 200
    retriever.search_all_with_rerank.assert_called_once_with(
        query="test", top_k_per_collection=5, final_top_k=3,
        exclude_collections={"terms"},
    )


def test_search_with_threshold(client):
    c, retriever, _ = client
    resp = c.post("/search", json={"query": "test", "apply_threshold": True, "skip_lookup": True})
    assert resp.status_code == 200
    retriever.filter_by_adaptive_threshold.assert_called_once()


def test_search_without_threshold(client):
    c, retriever, _ = client
    resp = c.post("/search", json={"query": "test", "apply_threshold": False, "skip_lookup": True})
    assert resp.status_code == 200
    retriever.filter_by_adaptive_threshold.assert_not_called()


# ---------------------------------------------------------------------------
# /search — plugin filter (skips lookup automatically)
# ---------------------------------------------------------------------------

def test_search_plugin_filter(client):
    c, retriever, lookup = client
    resp = c.post("/search", json={
        "query": "Set animation",
        "plugin": "Sprite",
        "section_types": ["actions"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["route"] == "plugin_filter"
    retriever.search_plugin_by_name.assert_called_once_with(
        query="Set animation",
        plugin_en="Sprite",
        section_types=["actions"],
        top_k=10,
    )
    # Lookup is skipped when plugin filter is set
    lookup.try_lookup.assert_not_called()


# ---------------------------------------------------------------------------
# /search — collection filter (skips lookup automatically)
# ---------------------------------------------------------------------------

def test_search_collection_filter(client):
    c, retriever, lookup = client
    resp = c.post("/search", json={
        "query": "test",
        "collections": ["plugins"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["route"] == "collection_filter"
    retriever._search.assert_called_once_with("plugins", "test", top_k=10)
    lookup.try_lookup.assert_not_called()


def test_search_invalid_collection(client):
    c, _, _ = client
    resp = c.post("/search", json={
        "query": "test",
        "collections": ["nonexistent"],
    })
    assert resp.status_code == 400
    assert "Unknown collection" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# /search — response structure
# ---------------------------------------------------------------------------

def test_search_response_structure(client):
    """Verify flat response structure with query, lang, route, latency_ms."""
    c, _, _ = client
    resp = c.post("/search", json={"query": "Sprite", "skip_lookup": True})
    assert resp.status_code == 200
    data = resp.json()
    assert "query" in data
    assert "lang" in data
    assert "route" in data
    assert "latency_ms" in data
    assert "results" in data
    assert "diagnostics" not in data  # old format removed


# ---------------------------------------------------------------------------
# /search — validation
# ---------------------------------------------------------------------------

def test_search_top_k_bounds(client):
    c, _, _ = client
    resp = c.post("/search", json={"query": "test", "top_k": 100})
    assert resp.status_code == 422  # exceeds max 50
