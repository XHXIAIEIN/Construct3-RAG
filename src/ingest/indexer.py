"""Compatibility facade and CLI for the staged ingest pipeline."""

from __future__ import annotations

from src.ingest.contracts import VectorDocument, VectorMode
from src.ingest.qdrant_adapter import Indexer
from src.vector import BM25Vectorizer, EmbeddingModel

__all__ = [
    "BM25Vectorizer",
    "EmbeddingModel",
    "Indexer",
    "VectorDocument",
    "VectorMode",
    "index_all_data",
]


def index_all_data(rebuild: bool = False):
    """Compatibility wrapper for the staged ingest pipeline."""
    from src.ingest.pipeline import run_index_pipeline

    return run_index_pipeline(rebuild=rebuild)


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Index Construct 3 data into Qdrant")
    parser.add_argument("--rebuild", action="store_true", help="Recreate collections")
    args = parser.parse_args()
    index_all_data(rebuild=args.rebuild)


if __name__ == "__main__":
    _main()
