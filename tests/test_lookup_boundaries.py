"""Architecture checks for the split deterministic Lookup boundary."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

from src.lookup.examples_index import ExamplesIndex as CanonicalExamplesIndex
from src.lookup.schema_index import SchemaIndex as CanonicalSchemaIndex
from src.lookup.scripting_index import ScriptingIndex as CanonicalScriptingIndex
from src.lookup.service import LookupEngine as CanonicalLookupEngine
from src.lookup.term_index import TermIndex as CanonicalTermIndex
from src.lookup.indexes import (
    ExamplesIndex as IndexFacadeExamplesIndex,
    SchemaIndex as IndexFacadeSchemaIndex,
    ScriptingIndex as IndexFacadeScriptingIndex,
    TermIndex as IndexFacadeTermIndex,
)
from src.rag.lookup import (
    ExamplesIndex as LegacyExamplesIndex,
    LookupEngine as LegacyLookupEngine,
    SchemaIndex as LegacySchemaIndex,
    ScriptingIndex as LegacyScriptingIndex,
    TermIndex as LegacyTermIndex,
    SCHEMA_DIR as LegacySchemaDir,
)


ROOT = Path(__file__).resolve().parents[1]
LOOKUP_DIR = ROOT / "src" / "lookup"


def test_legacy_and_indexes_facades_export_canonical_types():
    assert LegacyLookupEngine is CanonicalLookupEngine
    assert LegacySchemaIndex is CanonicalSchemaIndex
    assert LegacyScriptingIndex is CanonicalScriptingIndex
    assert LegacyTermIndex is CanonicalTermIndex
    assert LegacyExamplesIndex is CanonicalExamplesIndex
    assert IndexFacadeSchemaIndex is CanonicalSchemaIndex
    assert IndexFacadeScriptingIndex is CanonicalScriptingIndex
    assert IndexFacadeTermIndex is CanonicalTermIndex
    assert IndexFacadeExamplesIndex is CanonicalExamplesIndex
    assert LegacySchemaIndex().schema_dir == LegacySchemaDir


def test_canonical_lookup_has_no_reverse_rag_or_config_imports():
    forbidden = ("src.rag", "src.config")
    violations = []
    for path in sorted(LOOKUP_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            else:
                continue
            for module in modules:
                if module.startswith(forbidden):
                    violations.append(f"{path.name}:{node.lineno}:{module}")
    assert violations == []


def test_direct_canonical_import_stays_free_of_runtime_modules():
    script = """
import sys
from pathlib import Path
from src.lookup.service import LookupEngine
from src.lookup.schema_index import SchemaIndex
assert 'src.rag' not in sys.modules
assert 'src.rag.lookup' not in sys.modules
assert 'src.config' not in sys.modules
try:
    SchemaIndex()
except TypeError:
    pass
else:
    raise AssertionError('canonical SchemaIndex must require an injected path')
engine = LookupEngine(schema_dir=Path('data/c3-schemas'))
assert engine.try_lookup('Sprite 有哪些 action') is not None
assert 'src.rag' not in sys.modules
assert 'src.config' not in sys.modules
"""
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_term_index_uses_schema_public_iteration_only():
    class PublicSchemaView:
        def iter_schemas(self):
            yield (
                "plugins",
                "sprite",
                {
                    "name_en": "Sprite",
                    "name_zh": "精灵",
                    "actions": [
                        {
                            "id": "destroy",
                            "name_en": "Destroy",
                            "name_zh": "销毁",
                        }
                    ],
                },
            )

    index = CanonicalTermIndex()
    index.load_from_schema(PublicSchemaView())

    assert index.search("销毁")[0]["key"] == "plugins.sprite.actions.destroy"


def test_examples_fallback_is_available_without_private_index_access(tmp_path):
    index_path = tmp_path / "examples_index.json"
    index_path.write_text(
        json.dumps(
            {
                "behavior-Tween": [
                    {
                        "title": "Tween Demo",
                        "slug": "tween-demo",
                        "genres": ["animation"],
                        "behaviors": ["Tween"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    index = CanonicalExamplesIndex(index_path=index_path)

    assert index.matching_tags("tween") == ["behavior-tween"]
    assert index.search_fallback("tween")[0]["slug"] == "tween-demo"
