"""Parse examples_browser_en_r475.json + examples_browser.json for vector indexing."""
import json
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def _parse_tags(tags: list[str]) -> dict:
    """Categorize data-tags into typed lists.

    Returns dict with keys: plugins, behaviors, effects, genres,
    level (str), categories, coding. All values are list[str] except level.
    """
    plugins, behaviors, effects, genres, levels, categories, coding = [], [], [], [], [], [], []
    for t in tags:
        if t.startswith("plugin-"):
            plugins.append(t[7:])
        elif t.startswith("behavior-"):
            behaviors.append(t[9:])
        elif t.startswith("effect-"):
            effects.append(t[7:])
        elif t in ("beginner", "intermediate", "advanced"):
            levels.append(t)
        elif t in ("event-sheets-only", "javascript", "typescript"):
            coding.append(t)
        elif t in ("action", "adventure", "animation", "arcade", "fighting",
                   "multiplayer", "platformer", "puzzle", "rpg", "racing", "shooter", "strategy"):
            genres.append(t)
        else:
            categories.append(t)
    return dict(
        plugins=plugins, behaviors=behaviors, effects=effects,
        genres=genres, level=levels[0] if levels else "",
        categories=categories, coding=coding,
    )


def build_embed_text(title_zh: str, title_en: str, parsed: dict) -> str:
    """Build embed text for bge-m3 vector indexing."""
    parts = []
    if title_zh and title_zh != title_en:
        parts.append(f"{title_zh} | {title_en}")
    else:
        parts.append(title_en)
    if parsed["plugins"]:
        parts.append("plugins: " + ", ".join(parsed["plugins"]))
    if parsed["behaviors"]:
        parts.append("behaviors: " + ", ".join(parsed["behaviors"]))
    if parsed["genres"]:
        parts.append("genres: " + ", ".join(parsed["genres"]))
    if parsed["level"]:
        parts.append("level: " + parsed["level"])
    if parsed["coding"]:
        parts.append("coding: " + ", ".join(parsed["coding"]))
    if parsed["effects"]:
        parts.append("effects: " + ", ".join(parsed["effects"][:5]))
    return " | ".join(parts)


def load_examples_for_vectordb(
    en_path: Optional[Path] = None,
    zh_path: Optional[Path] = None,
) -> list[dict]:
    """Return list of {id, text, metadata} dicts for Qdrant indexing.

    The zh file (examples_browser.json) contains Chinese-titled items in the same
    order as the en file (examples_browser_en_r475.json). Match by index position.
    """
    en_path = en_path or DATA_DIR / "examples_browser_en_r475.json"
    zh_path = zh_path or DATA_DIR / "examples_browser.json"

    if not en_path.exists():
        raise FileNotFoundError(f"English examples file not found: {en_path}")

    en_items = json.loads(en_path.read_text(encoding="utf-8"))
    zh_items = json.loads(zh_path.read_text(encoding="utf-8")) if zh_path.exists() else []

    # zh file uses "title" for Chinese title; match by index position (same order)
    zh_titles: list[str] = [item.get("title", "") for item in zh_items]

    docs = []
    for i, item in enumerate(en_items):
        title_en = item.get("title", "")
        # Fall back to English title if zh list is shorter or title is empty
        title_zh = zh_titles[i] if i < len(zh_titles) and zh_titles[i] else title_en
        slug = item.get("slug", "")
        parsed = _parse_tags(item.get("tags", []))

        embed_text = build_embed_text(title_zh, title_en, parsed)
        docs.append({
            "id": f"example_{i}",
            "text": embed_text,
            "metadata": {
                "title_en": title_en,
                "title_zh": title_zh,
                "slug": slug,
                "example_type": item.get("exampleType", ""),
                "plugins": parsed["plugins"],
                "behaviors": parsed["behaviors"],
                "genres": parsed["genres"],
                "level": parsed["level"],
                "coding": parsed["coding"],
                "slug_derived": item.get("slug_derived", False),
            },
        })
    return docs
