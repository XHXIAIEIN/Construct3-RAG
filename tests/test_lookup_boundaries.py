"""Architecture checks for the split deterministic Lookup boundary."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.lookup.examples_index import ExamplesIndex as CanonicalExamplesIndex
from src.lookup.term_index import TermIndex as CanonicalTermIndex


ROOT = Path(__file__).resolve().parents[1]


def test_lookup_runs_from_an_injected_schema_dir_without_settings():
    script = """
import sys
from pathlib import Path
from src.lookup.service import LookupEngine
from src.lookup.schema_index import SchemaIndex
try:
    SchemaIndex()
except TypeError:
    pass
else:
    raise AssertionError('canonical SchemaIndex must require an injected path')
engine = LookupEngine(schema_dir=Path('data/c3-schemas'))
assert engine.try_lookup('Sprite 有哪些 action') is not None
assert 'src.settings' not in sys.modules
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
