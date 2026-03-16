"""Parse example project metadata for vector indexing.

Data source: C3Fetcher CDN data (media/example-project-data.json) + local c3proj enrichment.
"""
import json
from pathlib import Path
from typing import Optional


def _load_c3proj_metadata(projects_dir: Path, slug: str) -> Optional[dict]:
    """Load metadata from project.c3proj for the given slug.

    Returns dict with keys: layouts, event_sheets, plugins, behaviors, c3_version, name.
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
        "name": data.get("name", ""),
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


def _load_from_cdn(fetcher, projects_dir: Optional[Path]) -> list[dict]:
    """Load examples using C3Fetcher CDN data + optional c3proj enrichment."""
    cdn_items = fetcher.fetch_examples()

    # Lazy import to avoid circular deps
    try:
        from src.ingest.event_parser import load_project_extra_metadata
        _extra_meta_fn = load_project_extra_metadata
    except ImportError:
        _extra_meta_fn = None

    c3proj_hits = 0
    docs = []
    for i, item in enumerate(cdn_items):
        slug = item.get("id", "")
        tags = item.get("tags", [])
        parsed = _parse_tags(tags)

        # used-addons from CDN provide authoritative plugin/behavior lists
        used_addons = item.get("used-addons", {})
        cdn_plugins = used_addons.get("plugins", [])
        cdn_behaviors = used_addons.get("behaviors", [])

        # Try c3proj enrichment for layouts, event sheets, version, and title
        c3proj = None
        if projects_dir and slug:
            c3proj = _load_c3proj_metadata(projects_dir, slug)
        if c3proj:
            c3proj_hits += 1

        # Title: prefer c3proj "name", fallback to slug
        title_en = (c3proj["name"] if c3proj and c3proj.get("name") else "") or slug

        # Use CDN addons as authoritative; c3proj addons override if available
        plugins = c3proj["plugins"] if c3proj else cdn_plugins
        behaviors = c3proj["behaviors"] if c3proj else cdn_behaviors

        proj_dir = (projects_dir / slug) if projects_dir and slug else None
        extra = _extra_meta_fn(proj_dir) if (_extra_meta_fn and proj_dir and proj_dir.exists()) else None

        # Build parsed dict with CDN data merged in for build_embed_text
        merged_parsed = dict(parsed)
        # If CDN provides addon lists directly, use them as fallback plugins/behaviors
        if not merged_parsed["plugins"] and cdn_plugins:
            merged_parsed["plugins"] = cdn_plugins
        if not merged_parsed["behaviors"] and cdn_behaviors:
            merged_parsed["behaviors"] = cdn_behaviors

        embed_text = build_embed_text(title_en, title_en, merged_parsed, c3proj, extra)
        docs.append({
            "id": f"example_{i}",
            "text": embed_text,
            "metadata": {
                "source": "example",
                "title_en": title_en,
                "title_zh": title_en,  # CDN has no Chinese titles
                "slug": slug,
                "example_type": item.get("exampleType", ""),
                "plugins": plugins,
                "behaviors": behaviors,
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
                "slug_derived": False,
            },
        })

    if projects_dir:
        print(f"  c3proj enrichment: {c3proj_hits}/{len(docs)} examples")
    return docs


def load_examples_for_vectordb(
    fetcher,
    projects_dir: Optional[Path] = None,
) -> list[dict]:
    """Return list of {id, text, metadata} dicts for Qdrant indexing.

    Uses CDN example-project-data.json for metadata (tags, used-addons).
    Enriches with local project.c3proj when projects_dir is available.
    Title comes from c3proj "name" field, falling back to slug.

    Args:
        fetcher: C3Fetcher instance (required).
        projects_dir: optional path to local example project directories.
    """
    return _load_from_cdn(fetcher, projects_dir)
