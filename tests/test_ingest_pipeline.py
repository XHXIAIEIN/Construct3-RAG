"""Offline tests for staged ingest orchestration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.ingest.contracts import PipelineStage, VectorDocument
from src.ingest.pipeline import prepare_documents, run_prepared_pipeline


class _FakeIndexer:
    def __init__(self):
        self.events: list[tuple] = []
        self.counts: dict[str, int] = {}
        self.client = SimpleNamespace(get_collection=self._get_collection)

    def fit_bm25(self, corpus):
        self.events.append(("fit", list(corpus)))

    def create_collection(self, collection_name, recreate=False):
        self.events.append(("create", collection_name, recreate))
        self.counts.setdefault(collection_name, 0)

    def index_documents(self, collection_name, documents):
        rows = list(documents)
        self.events.append(("index", collection_name, [row.document_id for row in rows]))
        self.counts[collection_name] = len(rows)

    def _get_collection(self, collection_name):
        self.events.append(("verify", collection_name))
        return SimpleNamespace(points_count=self.counts[collection_name])


def test_pipeline_fits_exact_final_corpus_before_first_publish():
    indexer = _FakeIndexer()
    documents = {
        "c3_guide": [VectorDocument("guide-1", "c3_guide", "Guide text")],
        "c3_ace": [VectorDocument("ace-1", "c3_ace", "ACE text")],
    }

    report = run_prepared_pipeline(indexer, documents, rebuild=True)

    assert report.completed_stages == (
        PipelineStage.PREPARE,
        PipelineStage.VALIDATE,
        PipelineStage.PUBLISH,
        PipelineStage.VERIFY,
    )
    assert indexer.events[0] == ("fit", ["Guide text", "ACE text"])
    first_publish = next(i for i, event in enumerate(indexer.events) if event[0] == "create")
    assert first_publish > 0
    assert report.stages[-1].collection_counts == {"c3_guide": 1, "c3_ace": 1}


def test_pipeline_validation_failure_never_mutates_backend():
    indexer = _FakeIndexer()
    duplicate = VectorDocument("same", "c3_guide", "body")

    with pytest.raises(ValueError, match="duplicate document_id"):
        run_prepared_pipeline(indexer, {"c3_guide": [duplicate, duplicate]})

    assert indexer.events == []


def test_pipeline_rejects_unknown_collection_before_backend_mutation():
    indexer = _FakeIndexer()
    row = VectorDocument("row", "c3_typo", "body")

    with pytest.raises(ValueError, match="unknown collections"):
        run_prepared_pipeline(indexer, {"c3_typo": [row]})

    assert indexer.events == []


def test_prepare_passes_example_projects_directory(monkeypatch, tmp_path):
    import src.config as config
    import src.ingest.event_parser as event_parser
    import src.ingest.examples_parser as examples_parser
    import src.ingest.schema_parser as schema_parser

    projects_dir = tmp_path / "examples"
    projects_dir.mkdir()
    monkeypatch.setattr(config, "MANUAL_AVAILABLE", False)
    monkeypatch.setattr(config, "EXAMPLES_AVAILABLE", True)
    monkeypatch.setattr(config, "EXAMPLE_PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(config, "ADDON_SDK_MANUAL_AVAILABLE", False)
    monkeypatch.setattr(config, "ADDON_SDK_CODE_AVAILABLE", False)
    monkeypatch.setattr(config, "CONTEXTUAL_CHUNKING_ENABLED", False)

    captured = {}

    def fake_examples(*, fetcher, projects_dir):
        captured["projects_dir"] = projects_dir
        return []

    monkeypatch.setattr(examples_parser, "load_examples_for_vectordb", fake_examples)
    monkeypatch.setattr(event_parser, "load_event_and_script_docs", lambda *args: [])

    class FakeSchemaParser:
        def __init__(self, fetcher):
            pass

        def parse_ace_entries(self):
            return []

        def export_ace_for_vectordb(self, entries):
            return []

        def export_effects_for_vectordb(self):
            return []

    monkeypatch.setattr(schema_parser, "SchemaParser", FakeSchemaParser)

    fetcher = SimpleNamespace(
        export_schemas=lambda: Path("schemas"),
        export_terms=lambda: [],
    )
    indexer = SimpleNamespace(
        _prepend_context=lambda key, text: text,
    )

    prepare_documents(indexer, fetcher)

    assert captured["projects_dir"] == projects_dir


def test_legacy_index_all_data_delegates_to_staged_pipeline(monkeypatch):
    import src.ingest.indexer as compatibility
    import src.ingest.pipeline as pipeline

    expected = object()
    run = MagicMock(return_value=expected)
    monkeypatch.setattr(pipeline, "run_index_pipeline", run)

    assert compatibility.index_all_data(rebuild=True) is expected
    run.assert_called_once_with(rebuild=True)
