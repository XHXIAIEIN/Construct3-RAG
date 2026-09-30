"""The study's game list, kept in the ignored workspace and never committed.

``catalog.json`` there is a list of ``{"source", "folder", "author"}`` objects: a
``<kind>:<id>`` source, the output folder, and the author group.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORKSPACE = REPO / ".local" / "docs" / "evidence" / "c3-reference-games"
CATALOG = WORKSPACE / "catalog.json"


def load_catalog(path: Path = CATALOG) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"No game list at {path}; create it locally, it is not part of the repository.")
    return json.loads(path.read_text(encoding="utf-8"))
