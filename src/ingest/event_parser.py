"""Parse Construct 3 example project content for vector indexing.

Handles eventSheets (block events), scripts (JS/TS), and project metadata
enrichment from families, layouts, timelines, and flowcharts.

All output docs share the same {id, text, metadata} format for c3_examples.
"""
import json
import re
from pathlib import Path
from typing import Optional

# ACE ids that convey little meaning on their own (e.g. pure flow control)
_LOW_INFO_ACE_IDS = frozenset({
    "else", "end", "stop", "noop", "comment",
})

# Max parameters to include per ACE in embed text
_MAX_PARAMS = 3


# ── ACE rendering ──────────────────────────────────────────────────────────────

def _render_ace(ace: dict) -> str:
    """Render a condition or action as a compact readable string."""
    obj = ace.get("objectClass", "")
    ace_id = ace.get("id", "")
    params = ace.get("parameters", {}) or {}
    if not isinstance(params, dict):
        params = {}

    # Keep only non-trivial parameter values
    meaningful = {
        k: v for k, v in params.items()
        if v not in ("", 0, False, '""', "null", None)
    }
    if meaningful:
        kv = ", ".join(f"{k}={v}" for k, v in list(meaningful.items())[:_MAX_PARAMS])
        return f"{obj}.{ace_id}({kv})"
    return f"{obj}.{ace_id}"


def _render_ace_list(aces: list[dict]) -> str:
    return "; ".join(_render_ace(a) for a in aces if a.get("id") not in _LOW_INFO_ACE_IDS) or "(none)"


# ── Event block extraction ─────────────────────────────────────────────────────

def _extract_blocks(
    events: list[dict],
    project_meta: dict,
    sheet_name: str,
    depth: int = 0,
    parent_comment: str = "",
) -> list[dict]:
    """Recursively extract block/function-block events as indexable docs.

    Returns list of {id, text, metadata} dicts. Nested blocks are included
    up to depth 1 (sub-events summary appended to parent text).
    """
    docs = []
    pending_comment = parent_comment

    for idx, event in enumerate(events):
        etype = event.get("eventType", "")

        if etype == "comment":
            pending_comment = event.get("text", "").replace("\n", " ").strip()[:200]
            continue

        if etype not in ("block", "function-block"):
            pending_comment = ""
            continue

        conditions = event.get("conditions", [])
        actions = event.get("actions", [])
        children = event.get("children", [])
        is_func = etype == "function-block"
        func_name = event.get("functionName", "")

        # ── Build embed text ──
        title_zh = project_meta.get("title_zh", "")
        title_en = project_meta.get("title_en", "")
        header = f"{title_zh} | {title_en}" if title_zh and title_zh != title_en else title_en
        parts = [f"{header} | sheet:{sheet_name}"]

        if is_func and func_name:
            parts.append(f"function:{func_name}")
        if pending_comment:
            parts.append(f"[{pending_comment}]")

        cond_text = _render_ace_list(conditions)
        act_text = _render_ace_list(actions)
        parts.append(f"IF {cond_text}")
        parts.append(f"THEN {act_text}")

        # Summarize direct children (depth 0 only — avoid deep recursion in text)
        if depth == 0 and children:
            child_blocks = [c for c in children if c.get("eventType") in ("block", "function-block")]
            if child_blocks:
                child_summaries = []
                for cb in child_blocks[:4]:  # max 4 sub-events in summary
                    cb_cond = _render_ace_list(cb.get("conditions", []))
                    cb_act = _render_ace_list(cb.get("actions", []))
                    child_summaries.append(f"({cb_cond} → {cb_act})")
                parts.append("sub: " + "; ".join(child_summaries))

        text = " | ".join(parts)

        # ── Collect objectClasses ──
        condition_objs = list({c.get("objectClass", "") for c in conditions if c.get("objectClass")})
        action_objs = list({a.get("objectClass", "") for a in actions if a.get("objectClass")})

        slug = project_meta.get("slug", "")
        doc_id = f"event_{slug}_{re.sub(r'[^a-z0-9]', '_', sheet_name.lower())}_{depth}_{idx}"

        docs.append({
            "id": doc_id,
            "text": text,
            "metadata": {
                "source": "event_block",
                "slug": slug,
                "title_en": title_en,
                "title_zh": title_zh,
                "sheet_name": sheet_name,
                "is_function": is_func,
                "function_name": func_name,
                "condition_objs": condition_objs,
                "action_objs": action_objs,
                "depth": depth,
            },
        })

        # Recurse into children (depth + 1, no deeper than 1 to limit volume)
        if depth == 0 and children:
            docs.extend(_extract_blocks(children, project_meta, sheet_name, depth=1))

        pending_comment = ""

    return docs


def parse_event_sheet(sheet_path: Path, project_meta: dict) -> list[dict]:
    """Return indexable docs extracted from a single event sheet JSON file."""
    try:
        data = json.loads(sheet_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    sheet_name = data.get("name") or sheet_path.stem
    return _extract_blocks(data.get("events", []), project_meta, sheet_name)


# ── Script parsing ─────────────────────────────────────────────────────────────

def _split_script_chunks(source: str, max_chars: int = 1200) -> list[str]:
    """Split JS/TS source into chunks at function/class boundaries."""
    # Split on top-level function/class declarations
    pattern = re.compile(
        r'(?=(?:^|\n)(?:export\s+)?(?:function|class|async\s+function)\s)',
        re.MULTILINE,
    )
    raw_parts = pattern.split(source)

    chunks = []
    current = ""
    for part in raw_parts:
        if len(current) + len(part) <= max_chars:
            current += part
        else:
            if current.strip():
                chunks.append(current.strip())
            current = part
    if current.strip():
        chunks.append(current.strip())

    # If no natural split found, chunk by max_chars
    if not chunks:
        for i in range(0, len(source), max_chars):
            chunk = source[i:i + max_chars].strip()
            if chunk:
                chunks.append(chunk)

    return chunks


def parse_script_file(script_path: Path, project_meta: dict) -> list[dict]:
    """Return indexable docs from a JS/TS script file."""
    try:
        source = script_path.read_text(encoding="utf-8")
    except OSError:
        return []

    slug = project_meta.get("slug", "")
    title_zh = project_meta.get("title_zh", "")
    title_en = project_meta.get("title_en", "")
    header = f"{title_zh} | {title_en}" if title_zh and title_zh != title_en else title_en
    lang = "typescript" if script_path.suffix == ".ts" else "javascript"
    fname = script_path.stem

    chunks = _split_script_chunks(source)
    docs = []
    for i, chunk in enumerate(chunks):
        text = f"{header} | script:{fname} | {lang}\n{chunk[:1000]}"
        doc_id = f"script_{slug}_{re.sub(r'[^a-z0-9]', '_', fname.lower())}_{i}"
        docs.append({
            "id": doc_id,
            "text": text,
            "metadata": {
                "source": "script_code",
                "slug": slug,
                "title_en": title_en,
                "title_zh": title_zh,
                "script_name": fname,
                "language": lang,
                "chunk_index": i,
            },
        })
    return docs


# ── Project-level metadata enrichment ─────────────────────────────────────────

def load_project_extra_metadata(proj_dir: Path) -> dict:
    """Extract metadata from families, timelines, layouts, flowcharts.

    Returns dict with keys: families, timelines, layout_names, flowcharts,
    has_scripts, script_languages.
    """
    families, timeline_names, layout_names, flowchart_names = [], [], [], []
    has_scripts = False
    script_languages: set[str] = set()

    # families
    for f in (proj_dir / "families").glob("*.json") if (proj_dir / "families").exists() else []:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            families.append({
                "name": d.get("name", f.stem),
                "plugin_id": d.get("plugin-id", ""),
                "behaviors": [b.get("behaviorId", "") for b in d.get("behaviorTypes", [])],
            })
        except (json.JSONDecodeError, OSError):
            pass

    # timelines
    for f in (proj_dir / "timelines").glob("*.json") if (proj_dir / "timelines").exists() else []:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            timeline_names.append(d.get("name", f.stem))
        except (json.JSONDecodeError, OSError):
            pass

    # layouts
    for f in (proj_dir / "layouts").glob("*.json") if (proj_dir / "layouts").exists() else []:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            layout_names.append(d.get("name", f.stem))
        except (json.JSONDecodeError, OSError):
            pass

    # flowcharts
    for f in (proj_dir / "flowcharts").glob("*.json") if (proj_dir / "flowcharts").exists() else []:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            flowchart_names.append(d.get("name", f.stem))
        except (json.JSONDecodeError, OSError):
            pass

    # scripts
    scripts_dir = proj_dir / "scripts"
    if scripts_dir.exists():
        for f in scripts_dir.iterdir():
            if f.suffix in (".js", ".ts"):
                has_scripts = True
                script_languages.add("typescript" if f.suffix == ".ts" else "javascript")

    return {
        "families": families,
        "timeline_names": timeline_names,
        "layout_names": layout_names,
        "flowchart_names": flowchart_names,
        "has_scripts": has_scripts,
        "script_languages": sorted(script_languages),
    }


# ── Top-level loader ───────────────────────────────────────────────────────────

def load_event_and_script_docs(
    projects_dir: Path,
    slug_title_map: Optional[dict[str, dict]] = None,
) -> list[dict]:
    """Return all event block and script docs from all example projects.

    slug_title_map: optional {slug -> {title_en, title_zh}} for display titles.
    Falls back to slug-based title if not provided.
    """
    docs = []
    project_count = 0
    event_count = 0
    script_count = 0

    for proj_dir in sorted(projects_dir.iterdir()):
        if not proj_dir.is_dir():
            continue
        c3proj_path = proj_dir / "project.c3proj"
        if not c3proj_path.exists():
            continue

        slug = proj_dir.name
        if slug_title_map and slug in slug_title_map:
            title_en = slug_title_map[slug].get("title_en", slug)
            title_zh = slug_title_map[slug].get("title_zh", title_en)
        else:
            title_en = slug.replace("-", " ").title()
            title_zh = title_en

        project_meta = {"slug": slug, "title_en": title_en, "title_zh": title_zh}

        try:
            c3proj = json.loads(c3proj_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        # Event sheets
        sheet_names = c3proj.get("eventSheets", {}).get("items", [])
        for sheet_name in sheet_names:
            sheet_path = proj_dir / "eventSheets" / f"{sheet_name}.json"
            if sheet_path.exists():
                sheet_docs = parse_event_sheet(sheet_path, project_meta)
                docs.extend(sheet_docs)
                event_count += len(sheet_docs)

        # Scripts
        scripts_dir = proj_dir / "scripts"
        if scripts_dir.exists():
            for script_path in scripts_dir.iterdir():
                if script_path.suffix in (".js", ".ts"):
                    script_docs = parse_script_file(script_path, project_meta)
                    docs.extend(script_docs)
                    script_count += len(script_docs)

        project_count += 1

    print(f"  Parsed {project_count} projects: {event_count} event blocks, {script_count} script chunks")
    return docs
