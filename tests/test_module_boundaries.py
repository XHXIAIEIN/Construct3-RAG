"""Regression tests for runtime module compatibility and dependency boundaries."""

import ast
import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.application.models import SearchCommand, SearchExecution
from src.application.search import (
    SearchStage,
    SearchWorkflow,
    UnknownCollectionError,
    detect_language,
)
from src.domain.lookup import LookupIntent as DomainLookupIntent
from src.domain.retrieval import SearchResult as DomainSearchResult
from src.interfaces.http.models import SearchRequest as HttpSearchRequest
from src.observability.trace import _trace as canonical_trace
from src.rag.lookup import LookupIntent as LegacyLookupIntent
from src.rag.retriever import SearchResult as LegacySearchResult
from src.rag.retriever import HybridRetriever as LegacyHybridRetriever
from src.rag.retriever import assign_context_tiers as legacy_assign_context_tiers
from src.rag.retriever import deduplicate_results as legacy_deduplicate_results
from src.rag.retriever import estimate_query_complexity as legacy_estimate_query_complexity
from src.rag.retriever import stable_result_id as legacy_stable_result_id
from src.rag.retriever import weighted_rrf as legacy_weighted_rrf
from src.retrieval.identity import deduplicate_results, stable_result_id
from src.retrieval.policy import assign_context_tiers, estimate_query_complexity, weighted_rrf
from src.retrieval.semantic import HybridRetriever as CanonicalHybridRetriever
from src.domain.api import SearchRequest
from src.rag._trace import _trace as legacy_trace


_SRC_ROOT = Path(__file__).parents[1] / "src"


def _source_modules() -> dict[str, Path]:
    modules: dict[str, Path] = {}
    for path in _SRC_ROOT.rglob("*.py"):
        relative = path.relative_to(_SRC_ROOT).with_suffix("")
        parts = relative.parts
        module_parts = parts[:-1] if parts[-1] == "__init__" else parts
        module = ".".join(("src", *module_parts))
        modules[module] = path
    return modules


def _absolute_import(current: str, node: ast.ImportFrom, *, is_package: bool) -> str:
    if node.level == 0:
        return node.module or ""
    package = current if is_package else current.rpartition(".")[0]
    parts = package.split(".")
    keep = max(1, len(parts) - (node.level - 1))
    prefix = ".".join(parts[:keep])
    return f"{prefix}.{node.module}" if node.module else prefix


def _module_imports(module: str, path: Path, known: set[str]) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = _absolute_import(module, node, is_package=path.name == "__init__.py")
            names = [base]
            if node.module is None:
                names.extend(f"{base}.{alias.name}" for alias in node.names)
        else:
            continue
        for name in names:
            candidates = [
                candidate
                for candidate in known
                if name == candidate or name.startswith(f"{candidate}.")
            ]
            if candidates:
                targets.add(max(candidates, key=len))
    targets.discard(module)
    return targets


def test_legacy_model_exports_point_to_domain_contracts():
    assert LegacyLookupIntent is DomainLookupIntent
    assert LegacySearchResult is DomainSearchResult
    assert LegacyHybridRetriever is CanonicalHybridRetriever
    assert legacy_assign_context_tiers is assign_context_tiers
    assert legacy_deduplicate_results is deduplicate_results
    assert legacy_estimate_query_complexity is estimate_query_complexity
    assert legacy_stable_result_id is stable_result_id
    assert legacy_weighted_rrf is weighted_rrf
    assert SearchRequest is HttpSearchRequest
    assert legacy_trace is canonical_trace


def test_semantic_runtime_does_not_depend_on_ingest_pipeline():
    import src.retrieval.semantic as semantic_module

    source = inspect.getsource(semantic_module)

    assert "src.ingest" not in source
    assert "src.config" not in source
    assert "src.collections" not in source
    assert "logging.basicConfig" not in source
    assert "print(" not in source


def test_ingest_pipeline_depends_on_canonical_adapter_not_compatibility_facade():
    import src.ingest.indexer as compatibility_module
    import src.ingest.pipeline as pipeline_module
    from src.ingest.qdrant_adapter import Indexer

    pipeline_source = inspect.getsource(pipeline_module)
    compatibility_source = inspect.getsource(compatibility_module)

    assert "src.ingest.qdrant_adapter" in pipeline_source
    assert "src.ingest.indexer" not in pipeline_source
    assert compatibility_module.Indexer is Indexer
    assert "class Indexer" not in compatibility_source


@pytest.mark.parametrize(
    ("package", "forbidden"),
    [
        ("application", ("src.rag", "src.config", "src.collections", "src.ingest")),
        ("lookup", ("src.rag", "src.config", "src.collections", "src.ingest")),
        ("retrieval", ("src.rag", "src.config", "src.collections", "src.ingest")),
        ("vector", ("src.rag", "src.config", "src.collections", "src.ingest")),
    ],
)
def test_canonical_packages_do_not_import_compatibility_or_maintenance_layers(
    package,
    forbidden,
):
    violations: list[str] = []
    for path in (_SRC_ROOT / package).rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                if any(
                    name == prefix or name.startswith(f"{prefix}.")
                    for prefix in forbidden
                ):
                    violations.append(f"{path.relative_to(_SRC_ROOT)} -> {name}")
    assert violations == []


def test_source_module_dependency_graph_is_acyclic():
    modules = _source_modules()
    known = set(modules)
    pending = {
        module: _module_imports(module, path, known)
        for module, path in modules.items()
    }

    while pending:
        leaves = {module for module, dependencies in pending.items() if not dependencies}
        if not leaves:
            break
        pending = {
            module: dependencies - leaves
            for module, dependencies in pending.items()
            if module not in leaves
        }

    assert pending == {}, "cyclic source dependencies: " + ", ".join(sorted(pending))


def test_language_detection_is_transport_independent():
    assert detect_language("Sprite actions") == "en"
    assert detect_language("精灵动作") == "zh"
    assert detect_language("スプライト") == "ja"
    assert detect_language("스프라이트") == "ko"


def test_lite_workflow_never_constructs_semantic_retriever():
    lookup = MagicMock()
    lookup.try_lookup.return_value = None
    get_retriever = MagicMock()
    workflow = SearchWorkflow(
        get_lookup_engine=lambda: lookup,
        get_retriever=get_retriever,
        lite_mode=True,
    )

    response = workflow.run(SearchRequest(query="怎么实现碰撞检测"))

    assert response.lookup is None
    assert response.semantic is None
    get_retriever.assert_not_called()


def test_search_sop_stage_names_are_stable():
    assert [stage.value for stage in SearchStage] == [
        "initialize",
        "lookup",
        "semantic",
        "deduplicate",
        "respond",
    ]


def test_internal_execution_state_contains_no_http_models():
    execution = SearchExecution(
        command=SearchCommand(query="Sprite"),
        lang="en",
    )

    assert execution.lookup_result is None
    assert execution.semantic_results == []
    assert execution.lookup_result_ids == set()


def test_workflow_does_not_reach_retriever_private_api():
    source = inspect.getsource(SearchWorkflow)

    assert "._search(" not in source
    assert "._qdrant_available" not in source


def test_collection_validation_precedes_runtime_providers():
    get_lookup = MagicMock()
    get_retriever = MagicMock()
    workflow = SearchWorkflow(
        get_lookup_engine=get_lookup,
        get_retriever=get_retriever,
        lite_mode=True,
    )

    with pytest.raises(UnknownCollectionError):
        workflow.execute(
            SearchCommand(query="test", mode="semantic", collections=("missing",))
        )

    get_lookup.assert_not_called()
    get_retriever.assert_not_called()
