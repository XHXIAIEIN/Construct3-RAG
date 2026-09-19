"""Dense and model-native sparse embedding adapter."""

from __future__ import annotations

from typing import Optional

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None  # type: ignore[assignment]

_QWEN3_QUERY_INSTRUCTION = (
    "Instruct: Retrieve relevant Construct 3 documentation for the following query\n"
    "Query: "
)


class EmbeddingModel:
    """Lazy wrapper around supported document/query embedding backends."""

    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-Embedding-0.6B",
        device: str = "cpu",
        native_sparse: bool = False,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self._model = None
        self._is_qwen3 = "qwen3-embedding" in model_name.lower()
        self._is_bge_m3_native = model_name == "BAAI/bge-m3" and native_sparse

    @property
    def model(self):
        if self._model is None:
            if self._is_bge_m3_native:
                try:
                    from FlagEmbedding import BGEM3FlagModel

                    self._model = BGEM3FlagModel(
                        self.model_name,
                        use_fp16=True,
                        device=self.device,
                    )
                except ImportError:
                    print(
                        "Warning: FlagEmbedding not installed. Falling back to "
                        "SentenceTransformer (no native sparse)."
                    )
                    self._is_bge_m3_native = False
            if self._model is None:
                if SentenceTransformer is None:
                    raise RuntimeError("sentence-transformers is not installed")
                if self._is_qwen3:
                    self._model = SentenceTransformer(
                        self.model_name,
                        device=self.device,
                        trust_remote_code=True,
                    )
                else:
                    self._model = SentenceTransformer(
                        self.model_name,
                        device=self.device,
                    )
        return self._model

    def encode(self, texts: list[str], batch_size: int = 8) -> list[list[float]]:
        """Encode document text without an asymmetric query instruction."""
        if self._is_bge_m3_native:
            output = self.model.encode(
                texts,
                batch_size=batch_size,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            return output["dense_vecs"].tolist()
        return self.model.encode(
            texts,
            show_progress_bar=False,
            batch_size=batch_size,
        ).tolist()

    def encode_single(self, text: str) -> list[float]:
        """Encode one query, applying the Qwen3 asymmetric instruction."""
        if self._is_bge_m3_native:
            output = self.model.encode(
                [text],
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            return output["dense_vecs"][0].tolist()
        if self._is_qwen3:
            return self.model.encode(
                _QWEN3_QUERY_INSTRUCTION + text,
                show_progress_bar=False,
            ).tolist()
        return self.model.encode([text], show_progress_bar=False)[0].tolist()

    def encode_sparse(self, texts: list[str]) -> Optional[list[dict]]:
        """Return BGE-M3 lexical weights when native sparse mode is enabled."""
        if not self._is_bge_m3_native:
            return None
        output = self.model.encode(
            texts,
            return_dense=False,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        return [dict(weights) for weights in output["lexical_weights"]]

    @property
    def dimension(self) -> int:
        if self._is_bge_m3_native:
            return 1024
        return self.model.get_sentence_embedding_dimension()
