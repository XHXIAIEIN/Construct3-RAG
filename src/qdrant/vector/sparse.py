"""Deterministic BM25 sparse-vector adapter."""

from __future__ import annotations

import math
from pathlib import Path

import jieba


class BM25Vectorizer:
    """Small persisted BM25 vectorizer compatible with Qdrant sparse vectors."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.vocab: dict[str, int] = {}
        self.idf: dict[int, float] = {}
        self._avg_dl = 0.0
        self._fitted = False

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [token for token in jieba.cut(text) if len(token.strip()) > 1]

    def fit(self, corpus: list[str]) -> "BM25Vectorizer":
        tokenized = [self._tokenize(document) for document in corpus]
        document_count = len(tokenized)
        self._avg_dl = sum(len(document) for document in tokenized) / max(document_count, 1)
        all_terms = {term for document in tokenized for term in document}
        self.vocab = {term: index for index, term in enumerate(sorted(all_terms))}

        document_frequency: dict[int, int] = {}
        for document in tokenized:
            for index in {self.vocab[term] for term in document}:
                document_frequency[index] = document_frequency.get(index, 0) + 1
        self.idf = {
            index: math.log(
                1 + (document_count - frequency + 0.5) / (frequency + 0.5)
            )
            for index, frequency in document_frequency.items()
        }
        self._fitted = True
        return self

    def encode(self, text: str) -> dict[int, float]:
        if not self._fitted:
            return {}
        tokens = self._tokenize(text)
        document_length = len(tokens)
        term_frequency: dict[str, int] = {}
        for token in tokens:
            term_frequency[token] = term_frequency.get(token, 0) + 1

        vector: dict[int, float] = {}
        for term, frequency in term_frequency.items():
            if term not in self.vocab:
                continue
            index = self.vocab[term]
            normalized_frequency = (frequency * (self.k1 + 1)) / (
                frequency
                + self.k1
                * (
                    1
                    - self.b
                    + self.b * document_length / max(self._avg_dl, 1)
                )
            )
            score = self.idf.get(index, 0.0) * normalized_frequency
            if score > 0:
                vector[index] = round(score, 6)
        return vector

    def save(self, path: Path) -> None:
        import msgpack

        output_path = path.with_suffix(".msgpack")
        output_path.write_bytes(
            msgpack.packb(
                {"vocab": self.vocab, "idf": self.idf, "avg_dl": self._avg_dl},
                use_bin_type=True,
            )
        )
        print(f"[BM25] Saved vocab ({len(self.vocab)} terms) → {output_path}")

    def load(self, path: Path) -> "BM25Vectorizer":
        import msgpack

        input_path = path.with_suffix(".msgpack")
        data = msgpack.unpackb(
            input_path.read_bytes(),
            raw=False,
            strict_map_key=False,
        )
        self.vocab = data["vocab"]
        self.idf = {key: value for key, value in data["idf"].items()}
        self._avg_dl = data["avg_dl"]
        self._fitted = True
        print(f"[BM25] Loaded vocab ({len(self.vocab)} terms) from {input_path}")
        return self
