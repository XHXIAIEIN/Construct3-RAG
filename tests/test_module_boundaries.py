"""Regression tests for runtime module compatibility and dependency boundaries."""

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.application.models import SearchCommand, SearchExecution
from src.interfaces.http.models import SearchRequest
from src.application.search import (
    InvalidSearchRequestError,
    SearchStage,
    SearchWorkflow,
    detect_language,
)


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


@pytest.mark.parametrize(
    ("package", "forbidden"),
    [
        ("application", ("src.ingest",)),
        ("lookup", ("src.ingest",)),
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


def test_workflow_runs_on_the_lookup_provider_alone():
    lookup = MagicMock()
    lookup.try_lookup.return_value = None
    workflow = SearchWorkflow(get_lookup_engine=lambda: lookup)

    response = workflow.run(SearchRequest(query="怎么实现碰撞检测"))

    assert response.lookup is None
    lookup.try_lookup.assert_called_once_with("怎么实现碰撞检测")


def test_search_sop_stage_names_are_stable():
    assert [stage.value for stage in SearchStage] == [
        "initialize",
        "lookup",
        "respond",
    ]


def test_internal_execution_state_contains_no_http_models():
    execution = SearchExecution(
        command=SearchCommand(query="Sprite"),
        lang="en",
    )

    assert execution.lookup_result is None
    assert execution.timing_ms == {}


def test_validation_precedes_the_lookup_provider():
    get_lookup = MagicMock()
    workflow = SearchWorkflow(get_lookup_engine=get_lookup)

    with pytest.raises(InvalidSearchRequestError):
        workflow.execute(SearchCommand(query="   "))

    get_lookup.assert_not_called()
