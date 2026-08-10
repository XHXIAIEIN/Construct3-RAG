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

# Heuristic suffix/prefix patterns for inferring plugin-id when objectTypes
# files are absent (newer project format). Maps lowercase pattern → plugin-id.
_NAME_PLUGIN_HINTS: list[tuple[str, str]] = [
    ("arr",   "Arr"),
    ("array", "Arr"),
    ("dict",  "Dictionary"),
    ("json",  "JSON"),
    ("ajax",  "AJAX"),
    ("xhr",   "AJAX"),
    ("ls",    "LocalStorage"),
    ("save",  "LocalStorage"),
    ("storage", "LocalStorage"),
    ("xml",   "XML"),
    ("csv",   "CSV"),
]


# ── Plugin map ──────────────────────────────────────────────────────────────────

def _build_plugin_map(proj_dir: Path) -> dict[str, str]:
    """Build {instance_name → plugin_id} map from objectTypes/*.json.

    For projects where the JSON files exist (older format), this gives exact
    mappings. For newer-format projects the directory may be sparse; a
    heuristic fallback is applied at render time for unmapped names.
    """
    name_to_plugin: dict[str, str] = {}
    ot_dir = proj_dir / "objectTypes"
    if not ot_dir.exists():
        return name_to_plugin
    for f in ot_dir.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            name = d.get("name") or f.stem
            plugin_id = d.get("plugin-id", "")
            if plugin_id:
                name_to_plugin[name] = plugin_id
        except (json.JSONDecodeError, OSError):
            pass
    return name_to_plugin


def _resolve_plugin(obj: str, plugin_map: dict[str, str]) -> str:
    """Return plugin_id for an objectClass instance name.

    Priority:
    1. Exact match in plugin_map (from objectTypes/*.json)
    2. Heuristic pattern match on the instance name
    3. Return original name unchanged
    """
    if not obj:
        return obj
    # Exact match
    if obj in plugin_map:
        return plugin_map[obj]
    # Heuristic: check if any known pattern appears in the lowercase name
    obj_lower = obj.lower()
    for pattern, plugin_id in _NAME_PLUGIN_HINTS:
        if pattern in obj_lower:
            return plugin_id
    return obj


# ── ACE rendering ──────────────────────────────────────────────────────────────

def _render_ace(ace: dict, plugin_map: Optional[dict[str, str]] = None) -> str:
    """Render a condition or action as a compact readable string.

    When plugin_map is provided, instance names are resolved to plugin IDs.
    Format: PluginId(InstanceName).ace_id(params) when name ≠ plugin_id,
    or PluginId.ace_id(params) when name = plugin_id (singleton).
    """
    obj = ace.get("objectClass", "")
    ace_id = ace.get("id", "")
    params = ace.get("parameters", {}) or {}
    if not isinstance(params, dict):
        params = {}

    # Resolve instance name → plugin id
    if plugin_map is not None:
        plugin_id = _resolve_plugin(obj, plugin_map)
        display = f"{plugin_id}({obj})" if plugin_id != obj else obj
    else:
        display = obj

    # Keep only non-trivial parameter values
    meaningful = {
        k: v for k, v in params.items()
        if v not in ("", 0, False, '""', "null", None)
    }
    if meaningful:
        kv = ", ".join(f"{k}={v}" for k, v in list(meaningful.items())[:_MAX_PARAMS])
        return f"{display}.{ace_id}({kv})"
    return f"{display}.{ace_id}"


def _render_ace_list(aces: list[dict], plugin_map: Optional[dict[str, str]] = None) -> str:
    return "; ".join(
        _render_ace(a, plugin_map) for a in aces if a.get("id") not in _LOW_INFO_ACE_IDS
    ) or "(none)"


# ── Event block extraction ─────────────────────────────────────────────────────

def _extract_blocks(
    events: list[dict],
    project_meta: dict,
    sheet_name: str,
    depth: int = 0,
    parent_comment: str = "",
    plugin_map: Optional[dict[str, str]] = None,
    event_path: tuple[int, ...] = (),
) -> list[dict]:
    """Recursively extract block/function-block events as indexable docs.

    Returns list of {id, text, metadata} dicts. Nested blocks are included
    up to depth 1 (sub-events summary appended to parent text).
    """
    docs = []
    pending_comment = parent_comment

    for idx, event in enumerate(events):
        etype = event.get("eventType", "")
        current_path = (*event_path, idx)

        if etype == "comment":
            pending_comment = event.get("text", "").replace("\n", " ").strip()[:200]
            continue

        # Groups are structural containers — recurse transparently, preserving depth
        if etype == "group":
            docs.extend(_extract_blocks(
                event.get("children", []), project_meta, sheet_name,
                depth=depth, parent_comment=pending_comment, plugin_map=plugin_map,
                event_path=current_path,
            ))
            pending_comment = ""
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

        cond_text = _render_ace_list(conditions, plugin_map)
        act_text = _render_ace_list(actions, plugin_map)
        parts.append(f"IF {cond_text}")
        parts.append(f"THEN {act_text}")

        # Summarize direct children (depth 0 only — avoid deep recursion in text)
        if depth == 0 and children:
            child_blocks = [c for c in children if c.get("eventType") in ("block", "function-block")]
            if child_blocks:
                child_summaries = []
                for cb in child_blocks[:4]:  # max 4 sub-events in summary
                    cb_cond = _render_ace_list(cb.get("conditions", []), plugin_map)
                    cb_act = _render_ace_list(cb.get("actions", []), plugin_map)
                    child_summaries.append(f"({cb_cond} → {cb_act})")
                parts.append("sub: " + "; ".join(child_summaries))

        text = " | ".join(parts)

        # ── Collect objectClasses (resolved to plugin IDs) ──
        pm = plugin_map or {}
        condition_objs = list({_resolve_plugin(c.get("objectClass", ""), pm) for c in conditions if c.get("objectClass")})
        action_objs = list({_resolve_plugin(a.get("objectClass", ""), pm) for a in actions if a.get("objectClass")})

        slug = project_meta.get("slug", "")
        # ``idx`` is only local to the current event/group list.  Using it with
        # ``depth`` alone caused blocks in separate groups (and separate parent
        # blocks) to receive the same point ID, so Qdrant upserts silently
        # replaced thousands of example blocks.  The complete ancestry path is
        # deterministic for the source snapshot and unique within an event
        # sheet, including transparent group containers.
        path_key = "_".join(str(part) for part in current_path)
        sheet_key = re.sub(r"[^a-z0-9]", "_", sheet_name.lower())
        doc_id = f"event_{slug}_{sheet_key}_{path_key}"

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
            docs.extend(_extract_blocks(
                children,
                project_meta,
                sheet_name,
                depth=1,
                plugin_map=plugin_map,
                event_path=current_path,
            ))

        pending_comment = ""

    return docs


def parse_event_sheet(
    sheet_path: Path,
    project_meta: dict,
    plugin_map: Optional[dict[str, str]] = None,
) -> list[dict]:
    """Return indexable docs extracted from a single event sheet JSON file."""
    try:
        data = json.loads(sheet_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    sheet_name = data.get("name") or sheet_path.stem
    return _extract_blocks(data.get("events", []), project_meta, sheet_name, plugin_map=plugin_map)


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

        # Build instance-name → plugin-id map from objectTypes/*.json
        plugin_map = _build_plugin_map(proj_dir)

        # Event sheets
        sheet_names = c3proj.get("eventSheets", {}).get("items", [])
        for sheet_name in sheet_names:
            sheet_path = proj_dir / "eventSheets" / f"{sheet_name}.json"
            if sheet_path.exists():
                sheet_docs = parse_event_sheet(sheet_path, project_meta, plugin_map)
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
