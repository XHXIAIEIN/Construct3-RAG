"""Canonical Qdrant adapter for validated ingest vector documents."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Distance, PointStruct, VectorParams
except ImportError:  # pragma: no cover - exercised only in minimal installs
    QdrantClient = None  # type: ignore[assignment]
    Distance = PointStruct = VectorParams = None  # type: ignore[assignment]

from src.ingest.contracts import VectorDocument, VectorMode
from src.vector import BM25Vectorizer, EmbeddingModel

__all__ = ["Indexer"]


class Indexer:
    """Validate vector documents and publish them to Qdrant."""

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        embedding_model: str = "Qwen/Qwen3-Embedding-0.6B",
        *,
        client: Any | None = None,
        embedder: EmbeddingModel | None = None,
        vector_mode: VectorMode | None = None,
    ) -> None:
        from src.config import BGE_M3_NATIVE_SPARSE

        try:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"

        if client is None:
            if QdrantClient is None:
                raise RuntimeError("qdrant-client is required to construct Indexer")
            client = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.client = client
        self.embedder = embedder or EmbeddingModel(
            embedding_model,
            device=device,
            native_sparse=BGE_M3_NATIVE_SPARSE,
        )
        self._vector_mode_override = vector_mode
        self._bm25: BM25Vectorizer | None = None

    @property
    def vector_mode(self) -> VectorMode:
        """Resolve one consistent collection/upsert vector layout.

        Accessing the embedding dimension initializes the backend first. This is
        important when native sparse was requested but FlagEmbedding is missing:
        the embedder can fall back before the collection layout is selected.
        """
        if self._vector_mode_override is not None:
            return self._vector_mode_override
        _ = self.embedder.dimension
        from src.config import BM25_ENABLED

        return VectorMode.resolve(
            bm25_enabled=BM25_ENABLED,
            native_sparse_enabled=bool(self.embedder._is_bge_m3_native),
        )

    @staticmethod
    def _generate_id(text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _point_id(document_id: str) -> int:
        """Map a stable external ID to a Qdrant-compatible positive integer."""
        return int(hashlib.md5(document_id.encode("utf-8")).hexdigest()[:15], 16)

    @staticmethod
    def _coerce_document(
        collection_name: str,
        value: VectorDocument | Mapping[str, Any],
    ) -> VectorDocument:
        return VectorDocument.from_legacy(value, collection_name=collection_name)

    def fit_bm25(self, corpus: list[str], vocab_path: Path | None = None) -> None:
        """Fit BM25 only when the resolved vector mode requires it."""
        if not self.vector_mode.uses_bm25:
            return
        from src.config import DATA_DIR

        print(f"[BM25] Fitting on {len(corpus)} documents...")
        self._bm25 = BM25Vectorizer().fit(corpus)
        path = vocab_path or (DATA_DIR / "bm25_vocab.msgpack")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._bm25.save(path)

    def create_collection(self, collection_name: str, recreate: bool = False) -> None:
        """Create a collection matching the resolved :class:`VectorMode`."""
        if VectorParams is None or Distance is None:
            raise RuntimeError("qdrant-client is required to create collections")

        collections = [item.name for item in self.client.get_collections().collections]
        if collection_name in collections:
            if recreate:
                print(f"Deleting existing collection: {collection_name}")
                self.client.delete_collection(collection_name)
            else:
                print(f"Collection already exists: {collection_name}")
                return

        mode = self.vector_mode
        dense_config = VectorParams(
            size=self.embedder.dimension,
            distance=Distance.COSINE,
        )
        kwargs: dict[str, Any] = {
            "collection_name": collection_name,
            # Dense vectors are always named. Runtime retrieval therefore has
            # one stable query contract in every vector mode.
            "vectors_config": {"dense": dense_config},
        }
        if mode.uses_sparse:
            from qdrant_client.http.models import SparseIndexParams, SparseVectorParams

            kwargs["sparse_vectors_config"] = {
                "sparse": SparseVectorParams(index=SparseIndexParams())
            }
        print(f"Creating collection: {collection_name} [{mode.value}]")
        self.client.create_collection(**kwargs)

    def index_documents(
        self,
        collection_name: str,
        documents: Iterable[VectorDocument | Mapping[str, Any]],
        batch_size: int = 100,
    ) -> None:
        """Validate and upsert documents using the collection's vector layout."""
        if PointStruct is None:
            raise RuntimeError("qdrant-client is required to index documents")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")

        validated = [self._coerce_document(collection_name, value) for value in documents]
        mode = self.vector_mode
        if mode.uses_bm25 and self._bm25 is None:
            raise RuntimeError("BM25 vector mode requires fit_bm25() before publication")

        print(
            f"Indexing {len(validated)} documents to {collection_name} "
            f"[{mode.value}]"
        )
        for start in range(0, len(validated), batch_size):
            batch = validated[start:start + batch_size]
            texts = [document.text for document in batch]
            dense_vectors = self.embedder.encode(texts)
            if len(dense_vectors) != len(batch):
                raise RuntimeError("embedding backend returned an unexpected vector count")

            native_sparse_vectors = None
            if mode is VectorMode.DENSE_NATIVE_SPARSE:
                native_sparse_vectors = self.embedder.encode_sparse(texts)
                if native_sparse_vectors is None or len(native_sparse_vectors) != len(batch):
                    raise RuntimeError(
                        "native sparse mode requires one sparse vector per document"
                    )

            points = []
            for index, (document, dense_vector) in enumerate(zip(batch, dense_vectors)):
                vector: dict[str, Any] = {"dense": dense_vector}
                if mode.uses_sparse:
                    from qdrant_client.http.models import SparseVector

                    if mode is VectorMode.DENSE_NATIVE_SPARSE:
                        sparse_values = native_sparse_vectors[index]
                    else:
                        sparse_values = self._bm25.encode(document.text)  # type: ignore[union-attr]
                    vector["sparse"] = SparseVector(
                        indices=list(sparse_values.keys()),
                        values=list(sparse_values.values()),
                    )

                points.append(
                    PointStruct(
                        id=self._point_id(document.document_id),
                        vector=vector,
                        payload=document.to_payload(),
                    )
                )

            self.client.upsert(collection_name=collection_name, points=points)
            completed = min(start + batch_size, len(validated))
            if completed % 500 == 0:
                print(f"  Indexed {completed}/{len(validated)}")
        print(f"  Completed indexing {len(validated)} documents")

    def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Small dense-only diagnostic search over the named dense vector."""
        response = self.client.query_points(
            collection_name=collection_name,
            query=self.embedder.encode_single(query),
            using="dense",
            limit=top_k,
        )
        return [
            {
                "score": result.score,
                "text": result.payload.get("text", ""),
                "metadata": {
                    key: value
                    for key, value in result.payload.items()
                    if key != "text"
                },
            }
            for result in response.points
        ]

    def _load_chunk_contexts(self, cache_path: Path | str | None = None) -> None:
        """Load pre-generated contextual chunk summaries from JSON cache."""
        from src.config import CONTEXTUAL_CHUNKING_CACHE

        path = Path(cache_path or CONTEXTUAL_CHUNKING_CACHE)
        if path.exists():
            self._chunk_contexts = json.loads(path.read_text(encoding="utf-8"))
            print(
                f"[ContextualChunking] Loaded {len(self._chunk_contexts)} "
                f"contexts from {path}"
            )
        else:
            self._chunk_contexts = {}
            print(f"[ContextualChunking] Cache not found at {path}, using raw chunks")

    def _prepend_context(self, chunk_key: str, chunk_text: str) -> str:
        ctx = getattr(self, "_chunk_contexts", {}).get(chunk_key, "")
        return ctx + chunk_text if ctx else chunk_text
