"""In-memory index over committed Construct example metadata."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


class ExamplesIndex:
    """Build and query an addon/tag index without a generated side file."""

    _EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "data" / "c3-examples" / "en-US"

    def __init__(
        self,
        index_path: Path | None = None,
        examples_dir: Path | None = None,
    ):
        self._index: dict[str, list[dict[str, Any]]] = {}
        if index_path is not None:
            self._load_legacy_index(index_path)
        else:
            self._load_examples(examples_dir or self._EXAMPLES_DIR)

    @staticmethod
    def _tag_key(tag: str) -> str:
        return tag.strip().lower()

    def _add(self, tag: str, record: dict[str, Any]) -> None:
        key = self._tag_key(tag)
        if key:
            self._index.setdefault(key, []).append(record)

    def _load_legacy_index(self, path: Path) -> None:
        """Load the retired generated-index format for caller compatibility."""
        if not path.exists():
            logger.warning("[ExamplesIndex] Index not found: %s", path)
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("[ExamplesIndex] Failed to load: %s", exc)
            return
        self._index = {
            self._tag_key(tag): records for tag, records in raw.items()
        }
        logger.info("[ExamplesIndex] Loaded %d tags", len(self._index))

    def _load_examples(self, examples_dir: Path) -> None:
        """Build the index directly from ``data/c3-examples/{locale}`` files."""
        if not examples_dir.is_dir():
            logger.warning(
                "[ExamplesIndex] Examples directory not found: %s",
                examples_dir,
            )
            return
        loaded = 0
        for path in sorted(examples_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "[ExamplesIndex] Failed to load %s: %s",
                    path.name,
                    exc,
                )
                continue
            addons = data.get("used-addons", {})
            record = {
                "title": data.get("name", path.stem),
                "slug": data.get("id", path.stem),
                "genres": data.get("tags", []),
                "behaviors": addons.get("behaviors", []),
            }
            for addon_type, prefix in (
                ("plugins", "plugin"),
                ("behaviors", "behavior"),
                ("effects", "effect"),
            ):
                for addon in addons.get(addon_type, []):
                    self._add(f"{prefix}-{addon}", record)
            for tag in data.get("tags", []):
                self._add(str(tag), record)
            loaded += 1
        logger.info(
            "[ExamplesIndex] Indexed %d examples across %d tags",
            loaded,
            len(self._index),
        )

    def matching_tags(self, text: str, max_tags: int = 3) -> list[str]:
        """Return indexed tags containing *text* for legacy fallback queries."""
        normalized = self._tag_key(text)
        if not normalized:
            return []
        return [tag for tag in self._index if normalized in tag][:max_tags]

    def search_fallback(
        self,
        text: str,
        *,
        max_tags: int = 3,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Search the limited substring-tag fallback through a public API."""
        return self.search(
            self.matching_tags(text, max_tags=max_tags),
            max_results=max_results,
        )

    def search(self, tags: list[str], max_results: int = 5) -> list[dict[str, Any]]:
        """Find examples matching any tag, ranked by overlap count."""
        if not tags:
            return []
        scores: dict[str, dict[str, Any]] = {}
        for tag in tags:
            for record in self._index.get(self._tag_key(tag), []):
                slug = record.get("slug", "")
                if not slug:
                    continue
                if slug not in scores:
                    scores[slug] = {"record": record, "score": 0}
                scores[slug]["score"] += 1
        ranked = sorted(scores.values(), key=lambda item: item["score"], reverse=True)
        return [item["record"] for item in ranked[:max_results]]

    @staticmethod
    def format_for_ace(records: list[dict[str, Any]]) -> str:
        """Compact format for appending example links to ACE results."""
        parts = [
            f"{record['title']} ({record['slug']})"
            for record in records
            if record.get("slug")
        ]
        return "Related examples: " + ", ".join(parts) if parts else ""

    @staticmethod
    def format_for_find(records: list[dict[str, Any]]) -> str:
        """Format example-find results with genre and behavior hints."""
        parts = []
        for record in records:
            if not record.get("slug"):
                continue
            tag_parts = record.get("genres", []) + record.get("behaviors", [])
            tag_text = f" [{', '.join(tag_parts[:3])}]" if tag_parts else ""
            parts.append(f"{record['title']} ({record['slug']}){tag_text}")
        return "Related examples: " + ", ".join(parts) if parts else ""
