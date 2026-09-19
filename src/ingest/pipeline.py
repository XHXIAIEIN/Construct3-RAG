"""Explicit prepare -> validate -> publish -> verify ingest pipeline."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from typing import Any

from src.ingest.contracts import (
    PipelineReport,
    PipelineStage,
    VectorDocument,
    validate_document_set,
)
from src.qdrant.adapter import Indexer


DocumentsByCollection = dict[str, list[VectorDocument]]


def _append_legacy(
    documents: DocumentsByCollection,
    collection_name: str,
    value: VectorDocument | Mapping[str, Any],
) -> None:
    documents.setdefault(collection_name, []).append(
        VectorDocument.from_legacy(value, collection_name=collection_name)
    )


def _collection_counts(documents: Mapping[str, Iterable[VectorDocument]]) -> dict[str, int]:
    return {collection: len(list(rows)) for collection, rows in documents.items()}


def prepare_documents(indexer: Any, fetcher: Any) -> DocumentsByCollection:
    """Materialize every final vector document without mutating Qdrant."""
    from src.qdrant.collections import ALL_COLLECTIONS, COLLECTIONS, DOC_COLLECTIONS
    from src.settings import load_settings
    from src.ingest.markdown_parser import MarkdownParser

    settings = load_settings()
    documents: DocumentsByCollection = {
        collection_name: [] for collection_name in ALL_COLLECTIONS
    }

    schemas_dir = fetcher.export_schemas()
    print(f"[prepare] Schemas exported to {schemas_dir}")
    if settings.features.contextual_chunking_enabled:
        indexer._load_chunk_contexts()

    # Manual documentation.
    if settings.paths.manual_available:
        all_chunks = MarkdownParser().parse_directory()
    else:
        print("[prepare] Construct3-Manual not found; skipping manual documents")
        all_chunks = []
    chunks_by_collection = {collection: [] for collection in DOC_COLLECTIONS}
    for chunk in all_chunks:
        collection = chunk.metadata.get("collection")
        if collection in chunks_by_collection:
            chunks_by_collection[collection].append(chunk)
    for collection_name in DOC_COLLECTIONS:
        for index, chunk in enumerate(chunks_by_collection[collection_name]):
            chunk_key = hashlib.md5(chunk.text[:500].encode("utf-8")).hexdigest()
            _append_legacy(
                documents,
                collection_name,
                {
                    "id": f"{collection_name}_{index}",
                    "text": indexer._prepend_context(chunk_key, chunk.text),
                    "metadata": dict(chunk.metadata),
                },
            )

    # Translation terms.
    for index, term in enumerate(fetcher.export_terms()):
        _append_legacy(
            documents,
            COLLECTIONS["terms"],
            {
                "id": f"term_{index}",
                "text": term["full_text"],
                "metadata": {
                    "term_key": term["term_key"],
                    "category": term["category"],
                    "term_type": term["term_type"],
                    "zh": term["zh"],
                    "en": term["en"],
                    "path": "/".join(term["path"]),
                },
            },
        )

    # Example metadata, event blocks, and scripts.
    from src.ingest.event_parser import load_event_and_script_docs
    from src.ingest.examples_parser import load_examples_for_vectordb

    projects_dir = settings.paths.example_projects_dir if settings.paths.examples_available else None
    try:
        example_rows = load_examples_for_vectordb(
            fetcher=fetcher,
            projects_dir=projects_dir,
        )
    except FileNotFoundError as exc:
        print(f"[prepare] Skipping examples: {exc}")
        example_rows = []
    for row in example_rows:
        _append_legacy(documents, COLLECTIONS["examples"], row)

    if projects_dir is not None:
        slug_title_map = {
            row["metadata"]["slug"]: {
                "title_en": row["metadata"]["title_en"],
                "title_zh": row["metadata"]["title_zh"],
            }
            for row in example_rows
            if row.get("metadata", {}).get("slug")
        }
        for row in load_event_and_script_docs(projects_dir, slug_title_map):
            _append_legacy(documents, COLLECTIONS["examples"], row)

    # ACEs and effects.
    from src.ingest.schema_parser import SchemaParser

    schema_parser = SchemaParser(fetcher=fetcher)
    ace_entries = schema_parser.parse_ace_entries()
    for row in schema_parser.export_ace_for_vectordb(ace_entries):
        _append_legacy(documents, COLLECTIONS["ace"], row)
    for row in schema_parser.export_effects_for_vectordb():
        _append_legacy(documents, COLLECTIONS["effects"], row)

    # Addon SDK manual and code sources share one collection.
    sdk_collection = COLLECTIONS["addon_sdk"]
    if settings.paths.addon_sdk_manual_available:
        sdk_chunks = MarkdownParser(base_dir=settings.paths.addon_sdk_manual_dir).parse_directory()
        for index, chunk in enumerate(sdk_chunks):
            metadata = {**chunk.metadata, "collection": sdk_collection}
            chunk_key = hashlib.md5(chunk.text[:500].encode("utf-8")).hexdigest()
            _append_legacy(
                documents,
                sdk_collection,
                {
                    "id": f"addon_sdk_doc_{index}",
                    "text": indexer._prepend_context(chunk_key, chunk.text),
                    "metadata": metadata,
                },
            )
    else:
        print("[prepare] Addon SDK manual not found; skipping manual source")

    if settings.paths.addon_sdk_code_available:
        from src.ingest.sdk_parser import load_sdk_for_vectordb

        for row in load_sdk_for_vectordb(settings.paths.addon_sdk_code_dir):
            _append_legacy(documents, sdk_collection, row)
    else:
        print("[prepare] Addon SDK code repository not found; skipping code source")

    return documents


def publish_documents(
    indexer: Any,
    documents: Mapping[str, list[VectorDocument]],
    *,
    rebuild: bool,
) -> None:
    """Publish a previously validated, fully materialized document set."""
    for collection_name, rows in documents.items():
        indexer.create_collection(collection_name, recreate=rebuild)
        if rows:
            indexer.index_documents(collection_name, rows)


def verify_collections(
    indexer: Any,
    expected_counts: Mapping[str, int],
) -> dict[str, int]:
    """Verify every managed collection exists and contains prepared points."""
    actual_counts: dict[str, int] = {}
    for collection_name, expected in expected_counts.items():
        info = indexer.client.get_collection(collection_name)
        actual = int(info.points_count or 0)
        if actual < expected:
            raise RuntimeError(
                f"collection {collection_name} contains {actual} points; "
                f"expected at least {expected}"
            )
        actual_counts[collection_name] = actual
    return actual_counts


def run_prepared_pipeline(
    indexer: Any,
    documents: Mapping[str, Iterable[VectorDocument]],
    *,
    rebuild: bool = False,
) -> PipelineReport:
    """Run all non-source stages; useful for deterministic offline tests."""
    materialized = {
        collection_name: list(rows)
        for collection_name, rows in documents.items()
    }
    report = PipelineReport(rebuild=rebuild)
    report.add(PipelineStage.PREPARE, _collection_counts(materialized))

    from src.qdrant.collections import ALL_COLLECTIONS

    unknown_collections = sorted(set(materialized).difference(ALL_COLLECTIONS))
    if unknown_collections:
        raise ValueError(
            "pipeline contains unknown collections: " + ", ".join(unknown_collections)
        )
    validated = validate_document_set(materialized)
    expected_counts = _collection_counts(validated)
    report.add(PipelineStage.VALIDATE, expected_counts)

    # The exact final text corpus is fitted before the first Qdrant mutation.
    corpus = [
        document.text
        for rows in validated.values()
        for document in rows
    ]
    indexer.fit_bm25(corpus)
    publish_documents(indexer, validated, rebuild=rebuild)
    report.add(PipelineStage.PUBLISH, expected_counts)

    actual_counts = verify_collections(indexer, expected_counts)
    report.add(PipelineStage.VERIFY, actual_counts)
    return report


def run_index_pipeline(
    rebuild: bool = False,
    *,
    indexer: Any | None = None,
    fetcher: Any | None = None,
) -> PipelineReport:
    """Prepare every source and execute the explicit indexing SOP."""
    from src.settings import load_settings
    from src.ingest.c3_fetcher import C3Fetcher
    settings = load_settings()
    source = fetcher or C3Fetcher(
        version=settings.schema.version,
        base_url=settings.schema.cdn_base,
        cache_dir=settings.schema.cache_dir,
    )
    adapter = indexer or Indexer(
        qdrant_host=settings.runtime.qdrant_host,
        qdrant_port=settings.runtime.qdrant_port,
        embedding_model=settings.vector.embedding_model,
    )
    print(f"[pipeline] Construct 3 version: {settings.schema.version}")
    documents = prepare_documents(adapter, source)
    report = run_prepared_pipeline(adapter, documents, rebuild=rebuild)
    print("[pipeline] Indexing complete")
    for collection_name, count in report.stages[-1].collection_counts.items():
        print(f"  {collection_name}: {count} vectors")
    return report
