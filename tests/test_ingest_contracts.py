"""Unit tests for typed ingest contracts and the Qdrant adapter boundary."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.ingest.contracts import VectorDocument, VectorMode, validate_document_set


def test_vector_compatibility_imports_share_canonical_class_identity():
    from src.ingest.embedding import EmbeddingModel as LegacyEmbeddingModel
    from src.ingest.indexer import BM25Vectorizer as IndexerBM25Vectorizer
    from src.ingest.indexer import EmbeddingModel as IndexerEmbeddingModel
    from src.ingest.sparse import BM25Vectorizer as LegacyBM25Vectorizer
    from src.vector import BM25Vectorizer, EmbeddingModel

    assert LegacyEmbeddingModel is EmbeddingModel
    assert IndexerEmbeddingModel is EmbeddingModel
    assert LegacyBM25Vectorizer is BM25Vectorizer
    assert IndexerBM25Vectorizer is BM25Vectorizer


def test_indexer_facade_shares_canonical_adapter_identity():
    from src.ingest.indexer import Indexer as CompatibilityIndexer
    from src.ingest.qdrant_adapter import Indexer

    assert CompatibilityIndexer is Indexer


def test_vector_document_preserves_external_id_in_payload():
    document = VectorDocument.from_legacy(
        {"id": "ace_plugin_sprite_action_set", "text": "Set animation", "metadata": {"x": 1}},
        collection_name="c3_ace",
    )

    assert document.document_id == "ace_plugin_sprite_action_set"
    assert document.to_payload() == {
        "document_id": "ace_plugin_sprite_action_set",
        "text": "Set animation",
        "x": 1,
    }


@pytest.mark.parametrize("reserved", ["text", "document_id"])
def test_vector_document_rejects_reserved_metadata_keys(reserved):
    with pytest.raises(ValueError, match="reserved payload keys"):
        VectorDocument(
            document_id="doc",
            collection_name="c3_guide",
            text="body",
            metadata={reserved: "override"},
        )


def test_vector_document_legacy_missing_id_gets_deterministic_identity():
    first = VectorDocument.from_legacy(
        {"text": "same body", "metadata": {}}, collection_name="c3_guide"
    )
    second = VectorDocument.from_legacy(
        {"text": "same body", "metadata": {}}, collection_name="c3_guide"
    )
    assert first.document_id == second.document_id


def test_document_set_rejects_duplicate_ids_before_publication():
    row = VectorDocument("same", "c3_guide", "body")
    with pytest.raises(ValueError, match="duplicate document_id"):
        validate_document_set({"c3_guide": [row, row]})


@pytest.mark.parametrize(
    ("bm25", "native", "expected"),
    [
        (False, False, VectorMode.DENSE),
        (True, False, VectorMode.DENSE_BM25),
        (False, True, VectorMode.DENSE_NATIVE_SPARSE),
        (True, True, VectorMode.DENSE_NATIVE_SPARSE),
    ],
)
def test_vector_mode_matrix(bm25, native, expected):
    assert VectorMode.resolve(
        bm25_enabled=bm25,
        native_sparse_enabled=native,
    ) is expected


def test_indexer_dense_layout_is_named_and_payload_keeps_document_id():
    pytest.importorskip("qdrant_client")
    from src.ingest.qdrant_adapter import Indexer

    client = MagicMock()
    client.get_collections.return_value = SimpleNamespace(collections=[])
    embedder = MagicMock()
    embedder.dimension = 3
    embedder.encode.return_value = [[0.1, 0.2, 0.3]]
    indexer = Indexer(
        client=client,
        embedder=embedder,
        vector_mode=VectorMode.DENSE,
    )

    indexer.create_collection("c3_guide")
    create_kwargs = client.create_collection.call_args.kwargs
    assert set(create_kwargs["vectors_config"]) == {"dense"}
    assert "sparse_vectors_config" not in create_kwargs

    indexer.index_documents(
        "c3_guide",
        [{"id": "guide-1", "text": "Guide body", "metadata": {"source": "guide.md"}}],
    )
    point = client.upsert.call_args.kwargs["points"][0]
    assert set(point.vector) == {"dense"}
    assert point.payload["document_id"] == "guide-1"
    assert point.payload["text"] == "Guide body"


@pytest.mark.parametrize(
    "mode",
    [VectorMode.DENSE_BM25, VectorMode.DENSE_NATIVE_SPARSE],
)
def test_indexer_sparse_modes_create_named_dense_and_sparse(mode):
    pytest.importorskip("qdrant_client")
    from src.ingest.qdrant_adapter import Indexer

    client = MagicMock()
    client.get_collections.return_value = SimpleNamespace(collections=[])
    embedder = MagicMock()
    embedder.dimension = 3
    indexer = Indexer(client=client, embedder=embedder, vector_mode=mode)

    indexer.create_collection("c3_guide")

    kwargs = client.create_collection.call_args.kwargs
    assert set(kwargs["vectors_config"]) == {"dense"}
    assert set(kwargs["sparse_vectors_config"]) == {"sparse"}


@pytest.mark.parametrize(
    "mode",
    [VectorMode.DENSE_BM25, VectorMode.DENSE_NATIVE_SPARSE],
)
def test_indexer_sparse_modes_upsert_matching_named_vectors(mode):
    pytest.importorskip("qdrant_client")
    from src.ingest.qdrant_adapter import Indexer

    client = MagicMock()
    embedder = MagicMock()
    embedder.dimension = 3
    embedder.encode.return_value = [[0.1, 0.2, 0.3]]
    embedder.encode_sparse.return_value = [{7: 0.5}]
    indexer = Indexer(client=client, embedder=embedder, vector_mode=mode)
    if mode is VectorMode.DENSE_BM25:
        indexer._bm25 = MagicMock()
        indexer._bm25.encode.return_value = {3: 0.75}

    indexer.index_documents(
        "c3_guide",
        [{"id": "guide-1", "text": "Guide body", "metadata": {}}],
    )

    point = client.upsert.call_args.kwargs["points"][0]
    assert set(point.vector) == {"dense", "sparse"}
