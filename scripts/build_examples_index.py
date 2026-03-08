#!/usr/bin/env python3
"""Build inverted index: tag -> [example records] from examples_browser_en_r475.json"""
import json
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).parent.parent / "data"
EN_FILE = DATA_DIR / "examples_browser_en_r475.json"
OUT_FILE = DATA_DIR / "examples_index.json"


def _parse_tags(tags: list[str]) -> dict:
    """Split data-tags into categorized lists.

    Returns a dict with keys: plugins, behaviors, effects, genres, levels,
    categories, coding, misc — all list[str]. 'level' in the record is
    derived as levels[0] (str) or '' when building each record.
    """
    plugins, behaviors, effects, genres, levels, categories, coding, misc = [], [], [], [], [], [], [], []
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
        elif t in ("demo-game", "game-template", "barebones-template",
                   "gameplay-mechanic", "feature-example", "tech-demo", "guided-tour", "recommended"):
            categories.append(t)
        else:
            misc.append(t)
    return dict(plugins=plugins, behaviors=behaviors, effects=effects,
                genres=genres, levels=levels, categories=categories,
                coding=coding, misc=misc)


def build_index() -> None:
    if not EN_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {EN_FILE}")
    en_items = json.loads(EN_FILE.read_text(encoding="utf-8"))

    index = defaultdict(list)

    for item in en_items:
        slug = item.get("slug", "")
        title_en = item.get("title", "")
        parsed = _parse_tags(item.get("tags", []))

        record = {
            "title": title_en,
            "slug": slug,
            "genres": parsed["genres"],
            "behaviors": parsed["behaviors"],
            "plugins": parsed["plugins"],
            "level": parsed["levels"][0] if parsed["levels"] else "",
        }

        for tag in item.get("tags", []):
            index[tag].append(record)

    # Deduplicate by slug per tag
    deduped = {}
    for tag, records in index.items():
        seen = set()
        unique = []
        for r in records:
            key = r["slug"]
            if not key:  # skip records without slug
                continue
            if key not in seen:
                seen.add(key)
                unique.append(r)
        deduped[tag] = unique

    OUT_FILE.write_text(json.dumps(deduped, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Built index: {len(deduped)} tags, saved to {OUT_FILE}")
    top = sorted(deduped.items(), key=lambda x: len(x[1]), reverse=True)[:5]
    for tag, recs in top:
        print(f"  {tag}: {len(recs)} examples")


if __name__ == "__main__":
    build_index()
