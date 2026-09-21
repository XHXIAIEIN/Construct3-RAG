"""Tests for the FastAPI lookup service (no external services needed)."""
import dataclasses
import sys
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient


def test_service_import_loads_no_model_or_vector_package():
    """The service is offline: importing it must not pull a model or vector stack."""
    code = (
        "import sys; import src.api; "
        "heavy = {'torch', 'numpy', 'qdrant_client', 'sentence_transformers', 'FlagEmbedding'}; "
        "loaded = sorted(heavy & set(sys.modules)); "
        "assert not loaded, loaded"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_playground_uses_current_nested_search_contract():
    html = (Path(__file__).parent.parent / "src" / "interfaces" / "http" / "playground.html").read_text(encoding="utf-8")

    assert "data.lookup?.hit" not in html
    assert "data.latency_ms" not in html
    assert "data.semantic" not in html
    assert "flattenLookupMatches(lk?.matches)" in html
    assert "<span>${data.ms}ms</span>" in html


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Create a test client with a mocked lookup engine."""
    mock_lookup = MagicMock()
    mock_lookup.try_lookup.return_value = None  # default: no match

    import src.api
    original_lookup_engine = src.api._lookup_engine
    src.api._lookup_engine = mock_lookup

    try:
        with TestClient(src.api.app) as c:
            yield c, mock_lookup
    finally:
        src.api._lookup_engine = original_lookup_engine


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

def test_health_reports_the_committed_schema_as_ready(client):
    c, _ = client
    resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "schema_ready": True, "message": "Lookup ready"}


def test_health_says_how_to_get_missing_schema_data(client, tmp_path):
    c, _ = client
    import src.api
    original_settings = src.api.SETTINGS
    src.api.SETTINGS = dataclasses.replace(
        src.api.SETTINGS,
        schema=dataclasses.replace(src.api.SETTINGS.schema, directory=tmp_path),
    )
    try:
        data = c.get("/health").json()
    finally:
        src.api.SETTINGS = original_settings

    assert data["status"] == "unavailable"
    assert data["schema_ready"] is False
    assert "scripts/init.py" in data["message"]


# ---------------------------------------------------------------------------
# /search — lookup route
# ---------------------------------------------------------------------------

def test_search_routes_to_lookup(client):
    c, lookup = client
    from src.rag.lookup import LookupResponse as LR, LookupIntent, LookupMatch, ACELocale
    intent = LookupIntent(
        intent_type="ace_list", plugin_id="sprite", ace_type="actions", tier=1,
        confidence=0.85,
    )
    lookup.try_lookup.return_value = LR(
        context="| 名称 | 描述 |\n|---|---|\n| Set animation | ... |",
        query_type="lookup_ace_list",
        intent=intent,
        elapsed_ms=2.5,
        matches=[
            LookupMatch(
                ace_id="set-animation",
                ace_type="action",
                plugin_id="sprite",
                collection="plugins",
                en=ACELocale(name="Set animation", desc="Set the current animation."),
                zh=ACELocale(name="设置动画", desc="设置当前动画。"),
            )
        ],
    )

    resp = c.post("/search", json={"query": "列出 Sprite 的 action"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "auto"
    assert data["lookup"] is not None
    assert len(data["lookup"]["matches"]) > 0
    lookup.try_lookup.assert_called_once_with("列出 Sprite 的 action")


def test_search_lookup_miss_returns_no_lookup_section(client):
    c, lookup = client
    lookup.try_lookup.return_value = None
    resp = c.post("/search", json={"query": "怎么实现碰撞检测"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "auto"
    assert "lookup" not in data  # excluded when None


@pytest.mark.parametrize("context", ["legacy context without matches", ""])
def test_context_only_lookup_is_not_a_lookup_section(client, context):
    c, lookup = client
    from src.rag.lookup import LookupIntent, LookupResponse

    lookup.try_lookup.return_value = LookupResponse(
        intent=LookupIntent(intent_type="term_translate", term="Destroy", tier=1),
        matches=[],
        context=context,
        query_type="lookup_term_translate",
    )

    resp = c.post("/search", json={"query": "翻译 Destroy"})

    assert resp.status_code == 200
    assert "lookup" not in resp.json()


def test_debug_reports_the_lookup_intent_and_timing(client):
    c, lookup = client
    from src.rag.lookup import ACELocale, LookupIntent, LookupMatch, LookupResponse

    lookup.try_lookup.return_value = LookupResponse(
        intent=LookupIntent(
            intent_type="ace_search",
            plugin_id="sprite",
            filter_term="animation speed",
            tier=1,
            confidence=0.85,
        ),
        matches=[
            LookupMatch(
                ace_id="set-animation-speed",
                ace_type="action",
                plugin_id="sprite",
                collection="plugins",
                en=ACELocale(name="Set speed"),
            )
        ],
        context="A: Set speed",
        query_type="lookup_ace_search",
    )

    data = c.post("/search", json={"query": "Sprite animation speed", "debug": True}).json()

    assert set(data["debug"]) == {"lookup_ms", "lookup"}
    assert data["debug"]["lookup"] == {
        "plugin": "sprite",
        "tier": 1,
        "confidence": 0.85,
        "intent": "ace_search",
        "keywords": ["animation", "speed"],
    }


# ---------------------------------------------------------------------------
# /search — response structure
# ---------------------------------------------------------------------------

def test_search_response_structure(client):
    c, _ = client
    resp = c.post("/search", json={"query": "Sprite"})
    assert resp.status_code == 200
    assert set(resp.json()) == {"query", "lang", "mode", "ms"}


def test_openapi_describes_typed_lookup_items_only():
    import src.api

    schemas = src.api.app.openapi()["components"]["schemas"]

    assert "LookupItemResult" in schemas
    assert set(schemas["SearchRequest"]["properties"]) == {
        "query", "lang", "debug", "context", "mode", "scope",
    }
    assert set(schemas["SearchResponse"]["properties"]) == {
        "query", "lang", "mode", "ms", "lookup", "debug",
    }
    assert set(schemas["HealthResponse"]["properties"]) == {"status", "schema_ready", "message"}


# ---------------------------------------------------------------------------
# /search — validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "payload",
    [
        {"query": "   "},
        {"query": "test", "lang": "xx"},
        {"query": "test", "mode": "semantic"},
        {"query": "test", "top_k": 5},
        {"query": "test", "collections": ["ace"]},
        {"query": "test", "mode": "lookup", "plugin": "Sprite"},
    ],
)
def test_search_rejects_what_it_cannot_honor(client, payload):
    """A filter or mode the service does not have is an error, not a silent drop."""
    c, lookup = client

    resp = c.post("/search", json=payload)

    assert resp.status_code == 422
    lookup.try_lookup.assert_not_called()
