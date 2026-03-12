"""Parse examples_browser_en_rXXX.json + examples_browser_cn_rXXX.json for vector indexing.

Also enriches each entry with project.c3proj metadata (layouts, event sheets, usedAddons)
when the corresponding example project directory is available.
"""
import json
import re
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def _find_latest_browser_json(prefix: str) -> Optional[Path]:
    """Return the highest-versioned examples_browser_{prefix}_rXXX.json in DATA_DIR."""
    candidates = list(DATA_DIR.glob(f"examples_browser_{prefix}_r*.json"))
    if not candidates:
        return None
    def _version(p: Path) -> int:
        m = re.search(r"_r(\d+)", p.name)
        return int(m.group(1)) if m else 0
    return max(candidates, key=_version)


def _load_c3proj_metadata(projects_dir: Path, slug: str) -> Optional[dict]:
    """Load metadata from project.c3proj for the given slug.

    Returns dict with keys: layouts, event_sheets, plugins, behaviors, c3_version.
    Returns None if the project directory or file does not exist.
    """
    c3proj_path = projects_dir / slug / "project.c3proj"
    if not c3proj_path.exists():
        return None
    try:
        data = json.loads(c3proj_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    addons = data.get("usedAddons", [])
    return {
        "layouts": data.get("layouts", {}).get("items", []),
        "event_sheets": data.get("eventSheets", {}).get("items", []),
        "plugins": [a["id"] for a in addons if a.get("type") == "plugin"],
        "behaviors": [a["id"] for a in addons if a.get("type") == "behavior"],
        "c3_version": data.get("savedWithRelease", ""),
    }


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


def build_embed_text(
    title_zh: str,
    title_en: str,
    parsed: dict,
    c3proj: Optional[dict] = None,
    extra: Optional[dict] = None,
) -> str:
    """Build embed text for bge-m3 vector indexing."""
    parts = []
    if title_zh and title_zh != title_en:
        parts.append(f"{title_zh} | {title_en}")
    else:
        parts.append(title_en)

    # Prefer c3proj addon lists (authoritative) over browser tag parsing
    plugins = c3proj["plugins"] if c3proj else parsed["plugins"]
    behaviors = c3proj["behaviors"] if c3proj else parsed["behaviors"]

    if plugins:
        parts.append("plugins: " + ", ".join(plugins))
    if behaviors:
        parts.append("behaviors: " + ", ".join(behaviors))
    if parsed["genres"]:
        parts.append("genres: " + ", ".join(parsed["genres"]))
    if parsed["level"]:
        parts.append("level: " + parsed["level"])
    if parsed["coding"]:
        parts.append("coding: " + ", ".join(parsed["coding"]))
    if parsed["effects"]:
        parts.append("effects: " + ", ".join(parsed["effects"][:5]))

    # Enrich with project structure from c3proj
    if c3proj:
        if c3proj["layouts"]:
            parts.append("layouts: " + ", ".join(c3proj["layouts"]))
        if c3proj["event_sheets"]:
            parts.append("event-sheets: " + ", ".join(c3proj["event_sheets"]))

    # Extra structure from project directories
    if extra:
        if extra.get("timeline_names"):
            parts.append("timelines: " + ", ".join(extra["timeline_names"]))
        if extra.get("families"):
            fnames = [f["name"] for f in extra["families"]]
            parts.append("families: " + ", ".join(fnames))
        if extra.get("flowchart_names"):
            parts.append("flowcharts: " + ", ".join(extra["flowchart_names"]))
        if extra.get("script_languages"):
            parts.append("scripts: " + ", ".join(extra["script_languages"]))

    return " | ".join(parts)


def load_examples_for_vectordb(
    en_path: Optional[Path] = None,
    zh_path: Optional[Path] = None,
    projects_dir: Optional[Path] = None,
) -> list[dict]:
    """Return list of {id, text, metadata} dicts for Qdrant indexing.

    Auto-detects the latest versioned examples_browser_en_rXXX.json and
    examples_browser_cn_rXXX.json files. Explicit paths override auto-detection.
    Match zh titles to en items by index position (same order).

    When projects_dir is provided (or auto-detected via EXAMPLE_PROJECTS_DIR config),
    each entry is enriched with project.c3proj metadata: layouts, event sheets,
    and authoritative plugin/behavior lists.
    """
    en_path = en_path or _find_latest_browser_json("en") or DATA_DIR / "examples_browser_en_r475.json"
    zh_path = zh_path or _find_latest_browser_json("cn")

    if projects_dir is None:
        try:
            from src.config import EXAMPLE_PROJECTS_DIR
            projects_dir = Path(EXAMPLE_PROJECTS_DIR) if EXAMPLE_PROJECTS_DIR.exists() else None
        except (ImportError, AttributeError):
            projects_dir = None

    if not en_path.exists():
        raise FileNotFoundError(f"English examples file not found: {en_path}")

    en_items = json.loads(en_path.read_text(encoding="utf-8"))
    zh_items = json.loads(zh_path.read_text(encoding="utf-8")) if zh_path and zh_path.exists() else []

    # zh file uses "title" for Chinese title; match by index position (same order)
    zh_titles: list[str] = [item.get("title", "") for item in zh_items]

    # Lazy import to avoid circular deps
    try:
        from src.ingest.event_parser import load_project_extra_metadata
        _extra_meta_fn = load_project_extra_metadata
    except ImportError:
        _extra_meta_fn = None

    c3proj_hits = 0
    docs = []
    for i, item in enumerate(en_items):
        title_en = item.get("title", "")
        title_zh = zh_titles[i] if i < len(zh_titles) and zh_titles[i] else title_en
        slug = item.get("slug", "")
        parsed = _parse_tags(item.get("tags", []))

        proj_dir = (projects_dir / slug) if projects_dir and slug else None
        c3proj = _load_c3proj_metadata(projects_dir, slug) if projects_dir and slug else None
        extra = _extra_meta_fn(proj_dir) if (_extra_meta_fn and proj_dir and proj_dir.exists()) else None
        if c3proj:
            c3proj_hits += 1

        embed_text = build_embed_text(title_zh, title_en, parsed, c3proj, extra)
        docs.append({
            "id": f"example_{i}",
            "text": embed_text,
            "metadata": {
                "source": "example",
                "title_en": title_en,
                "title_zh": title_zh,
                "slug": slug,
                "example_type": item.get("exampleType", ""),
                "plugins": c3proj["plugins"] if c3proj else parsed["plugins"],
                "behaviors": c3proj["behaviors"] if c3proj else parsed["behaviors"],
                "genres": parsed["genres"],
                "level": parsed["level"],
                "coding": parsed["coding"],
                "layouts": c3proj["layouts"] if c3proj else [],
                "event_sheets": c3proj["event_sheets"] if c3proj else [],
                "c3_version": c3proj["c3_version"] if c3proj else "",
                "families": [f["name"] for f in extra["families"]] if extra else [],
                "timeline_names": extra["timeline_names"] if extra else [],
                "flowchart_names": extra["flowchart_names"] if extra else [],
                "has_scripts": extra["has_scripts"] if extra else False,
                "script_languages": extra["script_languages"] if extra else [],
                "slug_derived": item.get("slug_derived", False),
            },
        })

    if projects_dir:
        print(f"  c3proj enrichment: {c3proj_hits}/{len(docs)} examples")
    return docs
