"""Exact TypeScript scripting API index."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path


logger = logging.getLogger(__name__)


class ScriptingIndex:
    """Search scripting API methods from ``autocomplete-data.json``."""

    _DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "c3-ts-defs"

    def __init__(self, data_dir: Path | None = None):
        self._data: dict[str, list[str]] = {}
        self._loaded = False
        self._data_dir = data_dir or self._DEFAULT_DATA_DIR

    def ensure_loaded(self) -> None:
        """Load the local scripting index once."""
        if self._loaded:
            return
        self._loaded = True
        autocomplete_path = self._data_dir / "autocomplete-data.json"
        if not autocomplete_path.exists():
            logger.warning("[ScriptingIndex] Not found: %s", autocomplete_path)
            return
        try:
            data = json.loads(autocomplete_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("[ScriptingIndex] Failed to load: %s", exc)
            return
        self._data = data.get("properties", {})
        logger.info("[ScriptingIndex] Loaded %d classes", len(self._data))

    # Compatibility for callers that used the historical private loader.
    _load = ensure_loaded

    def search(self, query: str, max_results: int = 20) -> list[dict]:
        """Search exact TypeScript identifiers only.

        Natural-language overlap is deliberately excluded: scripting lookup is
        authoritative only for a qualified ``Class.member`` or a standalone
        class/member identifier. Everything else falls back to semantic search.
        """
        self.ensure_loaded()
        identifier = query.strip()
        qualified = re.fullmatch(
            r"(?P<class>[A-Za-z_][A-Za-z0-9_]*)\."
            r"(?P<method>[A-Za-z_][A-Za-z0-9_]*)",
            identifier,
        )
        if qualified:
            class_lower = qualified.group("class").lower()
            method_lower = qualified.group("method").lower()
            for class_name, methods in self._data.items():
                if class_name.lower() != class_lower:
                    continue
                for method in methods:
                    if method.lower() == method_lower:
                        return [{"class": class_name, "method": method}]
            return []

        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
            return []

        identifier_lower = identifier.lower()
        for class_name, methods in self._data.items():
            if class_name.lower() == identifier_lower:
                return [
                    {"class": class_name, "method": method}
                    for method in methods[:max_results]
                ]

        results = []
        for class_name, methods in self._data.items():
            for method in methods:
                if method.lower() == identifier_lower:
                    results.append({"class": class_name, "method": method})
                    if len(results) >= max_results:
                        return results
        return results
