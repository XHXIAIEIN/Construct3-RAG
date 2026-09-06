"""Tests for the FastAPI retrieval service (no external services needed)."""
import sys
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from src.domain.retrieval import RetrievalHealth, SearchResult


def test_lookup_import_does_not_load_optional_retriever():
    """The minimal package path must not import Qdrant-backed retrieval."""
    code = (
        "import sys; import src.rag.lookup; "
        "assert 'src.rag.retriever' not in sys.modules; "
        "from src.rag import HybridRetriever; "
        "assert 'src.rag.retriever' in sys.modules; "
        "assert HybridRetriever.__name__ == 'HybridRetriever'"
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
    assert "for (const r of (data.semantic || []))" not in html
    assert "flattenLookupMatches(lk?.matches)" in html
    assert "semanticEntries(data.semantic)" in html
    assert "<span>${data.ms}ms</span>" in html


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


def _mock_ace_result(*, ace_id: str, name: str, text: str) -> SearchResult:
    """Build a semantic ACE result with the canonical identity metadata."""
    return SearchResult(
        text=text,
        score=0.88,
        source="c3_ace",
        metadata={
            "source": "construct3-schema",
            "plugin_type": "plugin",
            "plugin_name": "sprite",
            "plugin_name_en": "Sprite",
            "ace_type": "action",
            "ace_id": ace_id,
            "name_en": name,
        },
    )


@pytest.fixture
def client():
    """Create a lookup-only test client with mocked runtime dependencies."""
    mock_retriever = MagicMock()
    mock_retriever.check_health.return_value = (True, "Qdrant is healthy")
    mock_retriever.get_health.return_value = RetrievalHealth(
        status="healthy",
        qdrant_connected=True,
        collections={"c3_plugins": 100, "c3_guide": 50},
        total_documents=150,
        missing_collections=(),
        message="2 collections, 150 documents",
    )
    mock_retriever.semantic_backend_available.return_value = True
    mock_retriever.search_all_with_rerank.return_value = _mock_search_results()
    mock_retriever.filter_by_adaptive_threshold.side_effect = lambda r, **kw: r
    mock_retriever.search_plugin_by_name.return_value = _mock_search_results()[:1]
    mock_retriever.search_collections.return_value = _mock_search_results()[:1]

    mock_lookup = MagicMock()
    mock_lookup.try_lookup.return_value = None  # default: no match

    import src.api
    original_lite_mode = src.api.LITE_MODE
    original_retriever = src.api._retriever
    original_lookup_engine = src.api._lookup_engine
    src.api.LITE_MODE = True
    src.api._retriever = mock_retriever
    src.api._lookup_engine = mock_lookup

    try:
        with TestClient(src.api.app) as c:
            yield c, mock_retriever, mock_lookup
    finally:
        src.api.LITE_MODE = original_lite_mode
        src.api._retriever = original_retriever
        src.api._lookup_engine = original_lookup_engine


@pytest.fixture
def full_client(client):
    """Explicitly enable semantic retrieval for one test, then restore it."""
    import src.api
    with patch.object(src.api, "LITE_MODE", False):
        yield client


def test_retriever_provider_injects_semantic_runtime_policy(tmp_path):
    import src.api

    original_retriever = src.api._retriever
    src.api._retriever = None
    try:
        with patch("src.retrieval.semantic.HybridRetriever") as retriever_type, patch.multiple(
            src.api,
            QDRANT_HOST="vector.internal",
            QDRANT_PORT=7333,
            EMBEDDING_MODEL="example/embedding",
            BM25_ENABLED=True,
            DATA_DIR=tmp_path,
            BGE_M3_NATIVE_SPARSE=True,
            RERANKER_ENABLED=False,
            RERANKER_MODEL="example/reranker",
            RERANKER_TOP_K=37,
        ):
            result = src.api._get_retriever()

        assert result is retriever_type.return_value
        retriever_type.assert_called_once_with(
            qdrant_host="vector.internal",
            qdrant_port=7333,
            embedding_model_name="example/embedding",
            bm25_enabled=True,
            bm25_vocab_path=tmp_path / "bm25_vocab.msgpack",
            native_sparse=True,
            reranker_enabled=False,
            reranker_model="example/reranker",
            reranker_top_k=37,
        )
    finally:
        src.api._retriever = original_retriever


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

def test_health_lookup_only_default_does_not_construct_retriever(client):
    c, retriever, _ = client
    import src.api
    with patch.object(src.api, "_get_retriever") as get_retriever:
        resp = c.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "lite"
    assert data["qdrant"] is False
    assert data["embedding_model"] == ""
    get_retriever.assert_not_called()
    retriever.get_health.assert_not_called()


def test_health_full_mode_ok(full_client):
    c, _, _ = full_client
    resp = c.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["qdrant"] is True
    assert data["total_documents"] == 150
    assert "c3_plugins" in data["collections"]


def test_health_full_mode_degraded(full_client):
    c, retriever, _ = full_client
    retriever.get_health.return_value = RetrievalHealth(
        status="unavailable",
        qdrant_connected=False,
        collections={},
        total_documents=0,
        missing_collections=(),
        message="Qdrant connection failed: Connection refused",
    )
    resp = c.get("/health")
    data = resp.json()
    assert data["status"] == "unavailable"
    assert data["qdrant"] is False


# ---------------------------------------------------------------------------
# /search — lookup route
# ---------------------------------------------------------------------------

def test_search_routes_to_lookup(client):
    """Default auto mode returns lookup data without constructing a retriever."""
    c, retriever, lookup = client
    import src.api
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
    # mock schema_index on the lookup engine so plugin info resolves gracefully
    lookup.schema_index.get_schema.return_value = None

    with patch.object(src.api, "_get_retriever") as get_retriever:
        resp = c.post("/search", json={"query": "列出 Sprite 的 action"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "auto"
    assert data["lookup"] is not None
    assert len(data["lookup"]["matches"]) > 0
    assert "semantic" not in data
    get_retriever.assert_not_called()
    retriever.search_all_with_rerank.assert_not_called()


def test_search_lookup_miss_stays_offline_by_default(client):
    c, retriever, lookup = client
    import src.api
    lookup.try_lookup.return_value = None
    with patch.object(src.api, "_get_retriever") as get_retriever:
        resp = c.post("/search", json={"query": "怎么实现碰撞检测"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "auto"
    assert "lookup" not in data  # excluded when None
    assert "semantic" not in data
    get_retriever.assert_not_called()
    retriever.search_all_with_rerank.assert_not_called()


@pytest.mark.parametrize(
    "semantic_filter",
    [
        {"plugin": "Sprite"},
        {"collections": ["plugins"]},
        {"section_types": ["actions"]},
    ],
)
def test_semantic_filters_bypass_lookup_in_lookup_only_mode(client, semantic_filter):
    c, retriever, lookup = client
    import src.api

    with patch.object(src.api, "_get_retriever") as get_retriever:
        resp = c.post("/search", json={"query": "Set animation", **semantic_filter})

    assert resp.status_code == 200
    data = resp.json()
    assert "lookup" not in data
    assert "semantic" not in data
    lookup.try_lookup.assert_not_called()
    get_retriever.assert_not_called()
    retriever.search_all_with_rerank.assert_not_called()


def test_search_lookup_miss_falls_to_semantic_in_full_mode(full_client):
    c, retriever, lookup = full_client
    lookup.try_lookup.return_value = None
    resp = c.post("/search", json={"query": "怎么实现碰撞检测"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "auto"
    assert "lookup" not in data
    retriever.search_all_with_rerank.assert_called_once()


@pytest.mark.parametrize("context", ["legacy context without matches", ""])
def test_context_only_lookup_is_not_a_lookup_section(client, context):
    c, retriever, lookup = client
    import src.api
    from src.rag.lookup import LookupIntent, LookupResponse

    lookup.try_lookup.return_value = LookupResponse(
        intent=LookupIntent(intent_type="term_translate", term="Destroy", tier=1),
        matches=[],
        context=context,
        query_type="lookup_term_translate",
    )

    with patch.object(src.api, "_get_retriever") as get_retriever:
        resp = c.post("/search", json={"query": "翻译 Destroy"})

    assert resp.status_code == 200
    data = resp.json()
    assert "lookup" not in data
    assert "semantic" not in data
    get_retriever.assert_not_called()
    retriever.search_all_with_rerank.assert_not_called()


def test_lookup_dedup_removes_only_the_same_stable_ace(full_client):
    c, retriever, lookup = full_client
    from src.rag.lookup import ACELocale, LookupIntent, LookupMatch, LookupResponse

    lookup.try_lookup.return_value = LookupResponse(
        intent=LookupIntent(
            intent_type="ace_detail",
            plugin_id="sprite",
            ace_name="Set animation",
            tier=1,
            confidence=0.95,
        ),
        matches=[
            LookupMatch(
                ace_id="set-animation",
                ace_type="action",
                plugin_id="sprite",
                collection="plugins",
                en=ACELocale(name="Set animation"),
                zh=ACELocale(name="设置动画"),
            )
        ],
        context="A: Set animation",
        query_type="lookup_ace_detail",
    )
    lookup.schema_index.get_schema.return_value = None
    retriever.search_all_with_rerank.return_value = [
        _mock_ace_result(
            ace_id="set-animation",
            name="Set animation",
            text="Set the current animation of the Sprite.",
        ),
        _mock_ace_result(
            ace_id="stop-animation",
            name="Stop animation",
            text="Stop the current animation of the Sprite.",
        ),
        SearchResult(
            text="Sprite is an object type for displaying images and animations.",
            score=0.80,
            source="c3_plugins",
            metadata={
                "source": "plugin-reference/sprite.md",
                "h1_heading": "Sprite",
                "section_type": "overview",
            },
        ),
    ]

    resp = c.post("/search", json={"query": "Sprite Set animation", "debug": True})

    assert resp.status_code == 200
    data = resp.json()
    docs = data["semantic"]["docs"]
    assert "Set animation" not in {doc.get("section") for doc in docs}
    assert "Stop animation" in {doc.get("section") for doc in docs}
    assert any(doc.get("title") == "Sprite" and doc.get("collection") == "plugins" for doc in docs)
    assert all("_result_id" not in doc for doc in docs)
    assert data["debug"]["semantic"]["total_candidates"] == 3
    assert data["debug"]["semantic"]["after_dedup"] == 2


def test_search_mode_semantic_skips_lookup(full_client):
    """mode='semantic' bypasses lookup entirely."""
    c, retriever, lookup = full_client
    resp = c.post("/search", json={"query": "列出 Sprite 的 action", "mode": "semantic"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "semantic"
    lookup.try_lookup.assert_not_called()
    retriever.search_all_with_rerank.assert_called_once()


def test_semantic_mode_requires_explicit_full_opt_in(client):
    c, retriever, lookup = client
    import src.api
    with patch.object(src.api, "_get_retriever") as get_retriever:
        resp = c.post("/search", json={"query": "Sprite animation", "mode": "semantic"})
    assert resp.status_code == 200
    data = resp.json()
    assert "semantic" not in data
    lookup.try_lookup.assert_not_called()
    get_retriever.assert_not_called()
    retriever.search_all_with_rerank.assert_not_called()


# ---------------------------------------------------------------------------
# /search — semantic route
# ---------------------------------------------------------------------------

def test_search_semantic_basic(full_client):
    c, retriever, _ = full_client
    resp = c.post("/search", json={"query": "Sprite 动画", "mode": "semantic"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["semantic"]["docs"] is not None
    assert data["semantic"]["docs"][0]["content"] is not None
    assert data["mode"] == "semantic"


def test_search_top_k(full_client):
    c, retriever, _ = full_client
    # "test" is short (4 chars) → simple preset: per_coll=3, final=5
    # final_top_k = max(preset.final_top_k, req.top_k) = max(5, 3) = 5
    resp = c.post("/search", json={"query": "test", "top_k": 3, "mode": "semantic"})
    assert resp.status_code == 200
    retriever.search_all_with_rerank.assert_called_once_with(
        query="test", top_k_per_collection=3, final_top_k=5,
        exclude_collections={"terms"},
    )


def test_search_with_threshold(full_client):
    c, retriever, _ = full_client
    resp = c.post("/search", json={"query": "test", "apply_threshold": True, "mode": "semantic"})
    assert resp.status_code == 200
    retriever.filter_by_adaptive_threshold.assert_called_once()


def test_search_without_threshold(full_client):
    c, retriever, _ = full_client
    resp = c.post("/search", json={"query": "test", "apply_threshold": False, "mode": "semantic"})
    assert resp.status_code == 200
    retriever.filter_by_adaptive_threshold.assert_not_called()


# ---------------------------------------------------------------------------
# /search — plugin filter (skips lookup automatically)
# ---------------------------------------------------------------------------

def test_search_plugin_filter(full_client):
    c, retriever, lookup = full_client
    resp = c.post("/search", json={
        "query": "Set animation",
        "plugin": "Sprite",
        "section_types": ["actions"],
    })
    assert resp.status_code == 200
    data = resp.json()
    # plugin filter is a semantic-phase branch; mode reflects request default "auto"
    assert data["mode"] == "auto"
    retriever.search_plugin_by_name.assert_called_once_with(
        query="Set animation",
        plugin_en="Sprite",
        section_types=["actions"],
        top_k=10,
    )
    # Lookup is skipped when plugin filter is set
    lookup.try_lookup.assert_not_called()


def test_search_section_only_filter_is_mandatory(full_client):
    c, retriever, lookup = full_client
    retriever.search_by_section_types.return_value = _mock_search_results()[:1]

    resp = c.post("/search", json={
        "query": "Sprite animation finishes",
        "mode": "semantic",
        "section_types": ["conditions"],
        "top_k": 7,
    })

    assert resp.status_code == 200
    retriever.search_by_section_types.assert_called_once_with(
        query="Sprite animation finishes",
        section_types=["conditions"],
        top_k=7,
    )
    lookup.try_lookup.assert_not_called()


# ---------------------------------------------------------------------------
# /search — collection filter (skips lookup automatically)
# ---------------------------------------------------------------------------

def test_search_collection_filter(full_client):
    c, retriever, lookup = full_client
    resp = c.post("/search", json={
        "query": "test",
        "collections": ["plugins"],
    })
    assert resp.status_code == 200
    data = resp.json()
    # collection filter is a semantic-phase branch; mode reflects request default "auto"
    assert data["mode"] == "auto"
    # Fetch a wider candidate pool so exact stable-ID dedup can backfill.
    retriever.search_collections.assert_called_once_with(
        query="test",
        collection_keys=["plugins"],
        top_k=10,
    )
    lookup.try_lookup.assert_not_called()


def test_collection_filter_exact_dedup_backfills_with_distinct_example(full_client):
    c, retriever, _ = full_client
    # The public adapter owns candidate expansion and exact deduplication.
    retriever.search_collections.return_value = [
        SearchResult("metadata", 0.9, "c3_examples", {"slug": "lava-fall"}),
        SearchResult("metadata", 0.7, "c3_examples", {"slug": "template-platformer"}),
    ]

    resp = c.post("/search", json={
        "query": "double jump",
        "mode": "semantic",
        "collections": ["examples"],
        "top_k": 2,
        "apply_threshold": False,
    })

    assert resp.status_code == 200
    examples = resp.json()["semantic"]["examples"]
    assert [item["project"] for item in examples] == ["lava-fall", "template-platformer"]
    retriever.search_collections.assert_called_once_with(
        query="double jump",
        collection_keys=["examples"],
        top_k=2,
    )


def test_lookup_example_exact_dedup_removes_semantic_copy(full_client):
    c, retriever, lookup = full_client
    from src.rag.lookup import ACELocale, LookupIntent, LookupMatch, LookupResponse

    lookup.try_lookup.return_value = LookupResponse(
        intent=LookupIntent(intent_type="example_find", confidence=0.7),
        matches=[
            LookupMatch(
                ace_id="file-system-text-editor",
                ace_type="example",
                plugin_id="",
                collection="examples",
                en=ACELocale(name="Text editor"),
            )
        ],
        context="Text editor",
        query_type="lookup_example_find",
    )
    retriever.search_all_with_rerank.return_value = [
        SearchResult(
            "file-system-text-editor metadata",
            0.9,
            "c3_examples",
            {"slug": "file-system-text-editor"},
        )
    ]

    resp = c.post("/search", json={
        "query": "Show me a FileSystem example project",
        "debug": True,
        "apply_threshold": False,
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["lookup"] is not None
    assert "semantic" not in data
    assert data["debug"]["semantic"]["total_candidates"] == 1
    assert data["debug"]["semantic"]["after_dedup"] == 0


def test_search_invalid_collection_is_validated_before_lite_backend(client):
    c, retriever, _ = client
    resp = c.post("/search", json={
        "query": "test",
        "collections": ["nonexistent"],
    })
    assert resp.status_code == 400
    assert "Unknown collection" in resp.json()["detail"]
    retriever.semantic_backend_available.assert_not_called()


# ---------------------------------------------------------------------------
# /search — response structure
# ---------------------------------------------------------------------------

def test_search_response_structure(full_client):
    """Verify response structure with query, lang, mode, ms, lookup, semantic."""
    c, _, _ = full_client
    resp = c.post("/search", json={"query": "Sprite", "mode": "semantic"})
    assert resp.status_code == 200
    data = resp.json()
    assert "query" in data
    assert "lang" in data
    assert "mode" in data
    assert "ms" in data
    assert "semantic" in data
    # lookup excluded when None (mode=semantic skips it)
    assert "diagnostics" not in data  # old format removed
    assert "results" not in data      # old flat list removed
    assert "route" not in data        # renamed to mode
    assert data["semantic"]["docs"][0]["context_tier"] == "full"


def test_openapi_describes_typed_lookup_and_semantic_items():
    import src.api

    schemas = src.api.app.openapi()["components"]["schemas"]

    assert "LookupItemResult" in schemas
    assert "DocResult" in schemas
    assert "TermResult" in schemas
    assert "ExampleResult" in schemas


# ---------------------------------------------------------------------------
# /search — validation
# ---------------------------------------------------------------------------

def test_search_top_k_bounds(client):
    c, _, _ = client
    resp = c.post("/search", json={"query": "test", "top_k": 100})
    assert resp.status_code == 422  # exceeds max 50


@pytest.mark.parametrize(
    "payload",
    [
        {"query": "   "},
        {"query": "test", "lang": "xx"},
        {"query": "test", "mode": "lookup", "collections": ["plugins"]},
        {"query": "test", "mode": "lookup", "plugin": "Sprite"},
        {"query": "test", "mode": "list", "section_types": ["actions"]},
    ],
)
def test_search_rejects_invalid_request_combinations(client, payload):
    c, retriever, lookup = client

    resp = c.post("/search", json=payload)

    assert resp.status_code == 422
    lookup.try_lookup.assert_not_called()
    retriever.semantic_backend_available.assert_not_called()
