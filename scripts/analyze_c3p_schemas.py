"""
Full analysis of all Construct 3 example projects.
Extracts: behaviors, effects, instanceVariables, families, timelines, flowcharts, instance effects.

Key findings about actual structure:
- Main project file is project.c3proj (not project.json)
- Non-world instances use 'singleglobal-inst' key (not instanceType: nonworld-inst)
- Layout instances have: type, properties, uid, instanceVariables, behaviors, world (or not world)
- Instance effects appear inside instance JSON under 'effects' key: {EffectName: {parameters: {...}}}
- Timeline tracks have propertyTracks with propertyKeyframes containing value/rValue/aValue/addons
- Flowchart nodes use: sid, pnSIDs, poSIDs, nodeSIDs, outputs, w, h
"""
import json
import os
import sys
from pathlib import Path
from collections import defaultdict

BASE = Path("D:/Users/Administrator/Documents/GitHub/Construct-Example-Projects/example-projects")
OUT_DIR = Path("D:/Users/Administrator/Documents/GitHub/Construct3-RAG/docs/knowledge")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Stats accumulators ──────────────────────────────────────────────────────
stats = {
    "total_projects": 0,
    "has_timelines": 0,
    "has_flowcharts": 0,
    "has_families": 0,
    "has_layouts": 0,
    "unique_behavior_ids": set(),
    "unique_effect_ids": set(),
    "object_type_variants": {
        "has_behaviorTypes": 0,
        "has_effectTypes": 0,
        "has_instanceVariables": 0,
        "has_singleglobal": 0,   # non-world plugin instances
    },
}

# ── Sample collectors ────────────────────────────────────────────────────────
samples = {
    "behavior_example": None,
    "effect_objecttype_example": None,
    "instance_vars_example": None,
    "singleglobal_example": None,       # Keyboard/Mouse/Audio style object
    "family_example": None,
    "timeline_examples": [],            # Up to 3 timelines with tracks
    "flowchart_examples": [],           # Up to 3 flowcharts with nodes
    "instance_effect_example": None,    # Instance with effects in layout
    "instance_behavior_example": None,  # Instance showing behaviors in layout
    "layout_layer_example": None,       # Layer structure
    "project_c3proj_example": None,     # project.c3proj top-level
}

# Detailed structure tracking
behavior_structures = {}   # behaviorId -> {project, file, example}
effect_structures = {}     # effectName -> {project, file, example}
effect_param_examples = {} # effectName -> instance-level example with parameters
instance_var_types_seen = set()

def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def analyze_object_type(data, project_name, ot_filename):
    if not data:
        return

    # singleglobal-inst (Keyboard, Mouse, Audio, etc.)
    if "singleglobal-inst" in data:
        stats["object_type_variants"]["has_singleglobal"] += 1
        if samples["singleglobal_example"] is None:
            samples["singleglobal_example"] = {
                "project": project_name,
                "file": ot_filename,
                "objectType": data,
            }

    # behaviorTypes
    bt = data.get("behaviorTypes")
    if bt and isinstance(bt, list) and len(bt) > 0:
        stats["object_type_variants"]["has_behaviorTypes"] += 1
        for b in bt:
            bid = b.get("behaviorId") or b.get("id") or b.get("name")
            if bid:
                stats["unique_behavior_ids"].add(bid)
                if bid not in behavior_structures:
                    behavior_structures[bid] = {
                        "project": project_name,
                        "file": ot_filename,
                        "example": b,
                    }
        if samples["behavior_example"] is None:
            samples["behavior_example"] = {
                "project": project_name,
                "file": ot_filename,
                "objectType": _trim_obj(data),
            }

    # effectTypes
    et = data.get("effectTypes")
    if et and isinstance(et, list) and len(et) > 0:
        stats["object_type_variants"]["has_effectTypes"] += 1
        for e in et:
            ename = e.get("name") or e.get("id")
            if ename:
                stats["unique_effect_ids"].add(ename)
                if ename not in effect_structures:
                    effect_structures[ename] = {
                        "project": project_name,
                        "file": ot_filename,
                        "example": e,
                    }
        if samples["effect_objecttype_example"] is None:
            samples["effect_objecttype_example"] = {
                "project": project_name,
                "file": ot_filename,
                "objectType": _trim_obj(data),
            }

    # instanceVariables
    iv = data.get("instanceVariables")
    if iv and isinstance(iv, list) and len(iv) > 0:
        stats["object_type_variants"]["has_instanceVariables"] += 1
        for v in iv:
            vtype = v.get("type")
            if vtype:
                instance_var_types_seen.add(vtype)
        if samples["instance_vars_example"] is None:
            samples["instance_vars_example"] = {
                "project": project_name,
                "file": ot_filename,
                "objectType": _trim_obj(data),
            }

def _trim_obj(data, max_list=3):
    """Return dict with large arrays truncated."""
    result = {}
    for k, v in data.items():
        if isinstance(v, list) and len(v) > max_list + 1:
            result[k] = v[:max_list] + [f"... ({len(v)} total)"]
        elif isinstance(v, dict) and k == "animations":
            # animations is large, just show structure
            items = v.get("items", [])
            result[k] = {
                "items": items[:1] if items else [],
                "subfolders": v.get("subfolders", []),
                "_note": f"({len(items)} animations total)"
            }
        else:
            result[k] = v
    return result

def analyze_layout(data, project_name, layout_filename):
    if not data:
        return

    # Layout-level structure sample
    if samples["layout_layer_example"] is None:
        layers = data.get("layers", [])
        if layers:
            layer = layers[0]
            insts = layer.get("instances", [])
            samples["layout_layer_example"] = {
                "project": project_name,
                "file": layout_filename,
                "layout_keys": list(data.keys()),
                "layer_keys": list(layer.keys()),
                "instance_count": len(insts),
                "sample_layer": {k: v for k, v in layer.items() if k != "instances"},
                "sample_instance": insts[0] if insts else None,
            }

    layers = data.get("layers", [])
    for layer in layers:
        instances = layer.get("instances", [])
        for inst in instances:
            # Instance with effects
            if "effects" in inst and samples["instance_effect_example"] is None:
                samples["instance_effect_example"] = {
                    "project": project_name,
                    "file": layout_filename,
                    "instance": inst,
                }
                # Track effect parameter examples
                for ename, edata in inst["effects"].items():
                    if ename not in effect_param_examples:
                        effect_param_examples[ename] = {
                            "project": project_name,
                            "instance_type": inst.get("type"),
                            "effect_data": edata,
                        }

            # Instance with behaviors
            if inst.get("behaviors") and samples["instance_behavior_example"] is None:
                beh = inst.get("behaviors", {})
                if beh:  # not empty dict
                    samples["instance_behavior_example"] = {
                        "project": project_name,
                        "file": layout_filename,
                        "instance": inst,
                    }

def analyze_timeline(data, project_name, tl_filename):
    if not data or len(samples["timeline_examples"]) >= 3:
        return
    tracks = data.get("tracks", [])
    if not tracks:
        return
    # Only keep if tracks have propertyTracks
    has_property_tracks = any(t.get("propertyTracks") for t in tracks)
    if not has_property_tracks and len(samples["timeline_examples"]) >= 1:
        return
    samples["timeline_examples"].append({
        "project": project_name,
        "file": tl_filename,
        "timeline": _trim_timeline(data),
    })

def _trim_timeline(data):
    result = {k: v for k, v in data.items() if k not in ("tracks", "tracksRoot", "nestedData", "transitionsData")}
    tracks = data.get("tracks", [])
    result["tracks"] = [_trim_track(t) for t in tracks[:3]]
    if len(tracks) > 3:
        result["tracks"].append({"_note": f"... ({len(tracks)} total tracks)"})
    return result

def _trim_track(track):
    result = {}
    for k, v in track.items():
        if k == "propertyTracksRoot":
            continue
        if k == "keyframes" and isinstance(v, list):
            result[k] = v[:3]
            if len(v) > 3:
                result[k].append({"_note": f"... ({len(v)} total keyframes)"})
        elif k == "propertyTracks" and isinstance(v, list):
            trimmed_pts = []
            for pt in v[:2]:
                trimmed_pt = {kk: vv for kk, vv in pt.items() if kk != "propertyTracksRoot"}
                if "propertyKeyframes" in trimmed_pt and isinstance(trimmed_pt["propertyKeyframes"], list):
                    pks = trimmed_pt["propertyKeyframes"]
                    trimmed_pt["propertyKeyframes"] = pks[:2]
                    if len(pks) > 2:
                        trimmed_pt["propertyKeyframes"].append({"_note": f"... ({len(pks)} total)"})
                trimmed_pts.append(trimmed_pt)
            result[k] = trimmed_pts
            if len(v) > 2:
                result[k].append({"_note": f"... ({len(v)} total propertyTracks)"})
        else:
            result[k] = v
    return result

def analyze_flowchart(data, project_name, fc_filename):
    if not data or len(samples["flowchart_examples"]) >= 3:
        return
    nodes = data.get("nodes", [])
    if not nodes:
        return
    samples["flowchart_examples"].append({
        "project": project_name,
        "file": fc_filename,
        "flowchart": _trim_flowchart(data),
    })

def _trim_flowchart(data):
    result = {k: v for k, v in data.items() if k != "nodes"}
    nodes = data.get("nodes", [])
    result["nodes"] = nodes[:5]
    if len(nodes) > 5:
        result["nodes"].append({"_note": f"... ({len(nodes)} total nodes)"})
    return result

def analyze_family(data, project_name, fam_filename):
    if not data or samples["family_example"]:
        return
    samples["family_example"] = {
        "project": project_name,
        "file": fam_filename,
        "family": data,
    }

def analyze_c3proj(data, project_name):
    if not data or samples["project_c3proj_example"]:
        return
    snippet = {}
    for k, v in data.items():
        if isinstance(v, dict):
            inner = {}
            for kk, vv in list(v.items())[:5]:
                if isinstance(vv, list) and len(vv) > 2:
                    inner[kk] = vv[:1] + [f"... ({len(vv)} total)"]
                else:
                    inner[kk] = vv
            snippet[k] = inner
        elif isinstance(v, list):
            snippet[k] = v[:2] + ([f"... ({len(v)} total)"] if len(v) > 2 else [])
        else:
            snippet[k] = v
    samples["project_c3proj_example"] = {
        "project": project_name,
        "snippet": snippet,
    }

# ── Main loop ───────────────────────────────────────────────────────────────
projects = sorted([d for d in BASE.iterdir() if d.is_dir()])
stats["total_projects"] = len(projects)

print(f"Scanning {len(projects)} projects...", flush=True)

for i, proj_dir in enumerate(projects):
    if i % 50 == 0:
        print(f"  [{i}/{len(projects)}] {proj_dir.name}", flush=True)

    proj_name = proj_dir.name

    # project.c3proj
    c3proj = load_json(proj_dir / "project.c3proj")
    analyze_c3proj(c3proj, proj_name)

    # objectTypes/
    ot_dir = proj_dir / "objectTypes"
    if ot_dir.is_dir():
        for ot_file in ot_dir.glob("*.json"):
            ot_data = load_json(ot_file)
            analyze_object_type(ot_data, proj_name, ot_file.name)

    # layouts/
    layout_dir = proj_dir / "layouts"
    if layout_dir.is_dir():
        stats["has_layouts"] += 1
        for lf in layout_dir.glob("*.json"):
            ldata = load_json(lf)
            analyze_layout(ldata, proj_name, lf.name)

    # families/
    fam_dir = proj_dir / "families"
    if fam_dir.is_dir() and any(fam_dir.glob("*.json")):
        stats["has_families"] += 1
        if samples["family_example"] is None:
            for ff in fam_dir.glob("*.json"):
                fdata = load_json(ff)
                analyze_family(fdata, proj_name, ff.name)
                break

    # timelines/
    tl_dir = proj_dir / "timelines"
    if tl_dir.is_dir():
        tl_files = list(tl_dir.glob("*.json"))
        if tl_files:
            stats["has_timelines"] += 1
            for tf in tl_files:
                tdata = load_json(tf)
                analyze_timeline(tdata, proj_name, tf.name)

    # flowcharts/
    fc_dir = proj_dir / "flowcharts"
    if fc_dir.is_dir():
        fc_files = list(fc_dir.glob("*.json"))
        if fc_files:
            stats["has_flowcharts"] += 1
            for ff in fc_files:
                fdata = load_json(ff)
                analyze_flowchart(fdata, proj_name, ff.name)

print("Scan complete. Writing output...", flush=True)

# ── Finalize stats ──────────────────────────────────────────────────────────
stats_out = {
    "total_projects": stats["total_projects"],
    "has_layouts": stats["has_layouts"],
    "has_timelines": stats["has_timelines"],
    "has_flowcharts": stats["has_flowcharts"],
    "has_families": stats["has_families"],
    "object_type_variants": stats["object_type_variants"],
    "instance_variable_types_seen": sorted(list(instance_var_types_seen)),
    "unique_behavior_ids": sorted(list(stats["unique_behavior_ids"])),
    "unique_effect_ids": sorted(list(stats["unique_effect_ids"])),
    "behavior_count": len(stats["unique_behavior_ids"]),
    "effect_count": len(stats["unique_effect_ids"]),
    "behavior_structures_sample": {
        k: v for k, v in list(behavior_structures.items())[:15]
    },
    "effect_structures_sample": {
        k: v for k, v in list(effect_structures.items())[:15]
    },
}

stats_path = OUT_DIR / "c3p-stats.json"
with open(stats_path, "w", encoding="utf-8") as f:
    json.dump(stats_out, f, ensure_ascii=False, indent=2)
print(f"Stats written to {stats_path}", flush=True)

# ── Build Markdown ───────────────────────────────────────────────────────────
def jblock(obj):
    return "```json\n" + json.dumps(obj, ensure_ascii=False, indent=2) + "\n```"

md_lines = [
    "# Construct 3 Project Schemas — Discovered Structures",
    "",
    "> Auto-generated by `scripts/analyze_c3p_schemas.py` from "
    f"{stats['total_projects']} example projects.",
    "",
    "## Table of Contents",
    "1. [Project Overview Statistics](#1-project-overview-statistics)",
    "2. [project.c3proj Top-Level Structure](#2-projectc3proj-top-level-structure)",
    "3. [ObjectType — With Behaviors](#3-objecttype--with-behaviors)",
    "4. [ObjectType — With Effects (effectTypes)](#4-objecttype--with-effects-effecttypes)",
    "5. [ObjectType — With Instance Variables](#5-objecttype--with-instance-variables)",
    "6. [ObjectType — Single-Global (Non-World Plugins)](#6-objecttype--single-global-non-world-plugins)",
    "7. [Families](#7-families)",
    "8. [Layouts — Layer and Instance Structure](#8-layouts--layer-and-instance-structure)",
    "9. [Layout Instance — With Effects](#9-layout-instance--with-effects)",
    "10. [Layout Instance — With Behaviors](#10-layout-instance--with-behaviors)",
    "11. [Timelines](#11-timelines)",
    "12. [Flowcharts](#12-flowcharts)",
    "13. [Unique Behavior IDs](#13-unique-behavior-ids)",
    "14. [Unique Effect IDs](#14-unique-effect-ids)",
    "",
]

# ── Section 1: Statistics ────────────────────────────────────────────────────
md_lines += [
    "## 1. Project Overview Statistics",
    "",
    "| Metric | Count |",
    "|--------|-------|",
    f"| Total projects scanned | {stats['total_projects']} |",
    f"| Projects with layouts/ | {stats['has_layouts']} |",
    f"| Projects with timelines/ | {stats['has_timelines']} |",
    f"| Projects with flowcharts/ | {stats['has_flowcharts']} |",
    f"| Projects with families/ | {stats['has_families']} |",
    f"| ObjectTypes with behaviorTypes | {stats['object_type_variants']['has_behaviorTypes']} |",
    f"| ObjectTypes with effectTypes | {stats['object_type_variants']['has_effectTypes']} |",
    f"| ObjectTypes with instanceVariables | {stats['object_type_variants']['has_instanceVariables']} |",
    f"| ObjectTypes with singleglobal-inst | {stats['object_type_variants']['has_singleglobal']} |",
    f"| Unique behavior IDs | {len(stats['unique_behavior_ids'])} |",
    f"| Unique effect IDs | {len(stats['unique_effect_ids'])} |",
    f"| Instance variable types | `{', '.join(sorted(instance_var_types_seen))}` |",
    "",
]

# ── Section 2: project.c3proj ─────────────────────────────────────────────
md_lines += [
    "## 2. project.c3proj Top-Level Structure",
    "",
    "The main project file is `project.c3proj` (JSON format). It contains project metadata and references to all objects, layouts, event sheets, and timelines.",
    "",
]
if samples["project_c3proj_example"]:
    ex = samples["project_c3proj_example"]
    md_lines += [
        f"Source: `{ex['project']}/project.c3proj`",
        "",
        jblock(ex["snippet"]),
        "",
        "**Key top-level fields:**",
        "| Field | Type | Description |",
        "|-------|------|-------------|",
        "| `projectFormatVersion` | number | Always `1` |",
        "| `savedWithRelease` | number | Construct release number |",
        "| `name` | string | Project display name |",
        "| `runtime` | string | Always `\"c3\"` |",
        "| `usedAddons` | array | List of used plugin/behavior addon IDs |",
        "| `uniqueId` | string | Project unique identifier |",
        "| `objectTypes` | object | `{items: [...], subfolders: [...]}` |",
        "| `families` | object | `{items: [...], subfolders: [...]}` |",
        "| `layouts` | object | `{items: [...], subfolders: [...]}` |",
        "| `eventSheets` | object | `{items: [...], subfolders: [...]}` |",
        "| `timelines` | object | `{items: [...], subfolders: [...]}` |",
        "| `properties` | object | description, version, author, etc. |",
        "| `viewportWidth` / `viewportHeight` | number | Canvas size |",
        "| `firstLayout` | string \\| null | Name of first layout to play |",
        "",
    ]

# ── Section 3: Behavior ObjectType ──────────────────────────────────────────
md_lines += [
    "## 3. ObjectType — With Behaviors",
    "",
    "ObjectType files live in `objectTypes/` and contain a `behaviorTypes` array. Each entry has `behaviorId`, `name`, and `sid`.",
    "",
]
if samples["behavior_example"]:
    ex = samples["behavior_example"]
    md_lines += [
        f"Source: `{ex['project']}/objectTypes/{ex['file']}`",
        "",
        jblock(ex["objectType"]),
        "",
        "### Behavior entry structure",
        "",
        "Each entry in `behaviorTypes` is minimal — the actual behavior parameters appear in the **layout instance** `behaviors` field:",
        "",
        "```json",
        '{ "behaviorId": "Tween", "name": "Tween", "sid": 191632034691493 }',
        "```",
        "",
        "### All discovered behaviorId values with their display names:",
        "",
        "| behaviorId | Display Name | Source Project |",
        "|------------|--------------|----------------|",
    ]
    for bid, binfo in sorted(behavior_structures.items()):
        display = binfo["example"].get("name", bid)
        md_lines.append(f"| `{bid}` | {display} | {binfo['project']} |")
    md_lines.append("")

# ── Section 4: Effect ObjectType ────────────────────────────────────────────
md_lines += [
    "## 4. ObjectType — With Effects (effectTypes)",
    "",
    "ObjectType files can have an `effectTypes` array. Each entry has `effectId` (the shader ID) and `name` (display name). The `name` is used as the key in layout instance `effects` dictionaries.",
    "",
]
if samples["effect_objecttype_example"]:
    ex = samples["effect_objecttype_example"]
    md_lines += [
        f"Source: `{ex['project']}/objectTypes/{ex['file']}`",
        "",
        jblock(ex["objectType"]),
        "",
        "**Note:** `effectId` is the internal shader identifier (lowercase), `name` is the display name used as key in instance-level effects.",
        "",
        "### Discovered effectId → name mappings:",
        "",
        "| name (instance key) | effectId (shader) | Source |",
        "|---------------------|-------------------|--------|",
    ]
    for ename, einfo in sorted(effect_structures.items()):
        eid = einfo["example"].get("effectId", "?")
        md_lines.append(f"| `{ename}` | `{eid}` | {einfo['project']} |")
    md_lines.append("")

# ── Section 5: InstanceVariables ────────────────────────────────────────────
md_lines += [
    "## 5. ObjectType — With Instance Variables",
    "",
    f"Instance variable types: `{', '.join(sorted(instance_var_types_seen))}`",
    "",
    "Each variable in `instanceVariables` array has: `name`, `type`, `desc`, `sid`. No `show` field observed in examples.",
    "",
]
if samples["instance_vars_example"]:
    ex = samples["instance_vars_example"]
    md_lines += [
        f"Source: `{ex['project']}/objectTypes/{ex['file']}`",
        "",
        jblock(ex["objectType"]),
        "",
    ]

# ── Section 6: Single-Global Non-World ───────────────────────────────────────
md_lines += [
    "## 6. ObjectType — Single-Global (Non-World Plugins)",
    "",
    "Plugins like Keyboard, Mouse, Audio, Touch have a `singleglobal-inst` field instead of world position data.",
    "These objects have no spatial representation in layouts.",
    "",
]
if samples["singleglobal_example"]:
    ex = samples["singleglobal_example"]
    md_lines += [
        f"Source: `{ex['project']}/objectTypes/{ex['file']}`",
        "",
        jblock(ex["objectType"]),
        "",
        "**Structure:** `singleglobal-inst` contains `type`, `properties` (plugin-specific), and `uid`.",
        "",
    ]

# ── Section 7: Families ──────────────────────────────────────────────────────
md_lines += [
    "## 7. Families",
    "",
    "Family files live in `families/`. They group multiple object types sharing common instance variables and behaviors.",
    "",
]
if samples["family_example"]:
    ex = samples["family_example"]
    md_lines += [
        f"Source: `{ex['project']}/families/{ex['file']}`",
        "",
        jblock(ex["family"]),
        "",
    ]
else:
    md_lines += ["*No family examples captured.*", ""]

# ── Section 8: Layout Structure ──────────────────────────────────────────────
md_lines += [
    "## 8. Layouts — Layer and Instance Structure",
    "",
    "Layout files live in `layouts/`. Each layout has layers, each layer has instances.",
    "",
]
if samples["layout_layer_example"]:
    ex = samples["layout_layer_example"]
    md_lines += [
        f"Source: `{ex['project']}/layouts/{ex['file']}`",
        "",
        f"**Layout top-level keys:** `{', '.join(ex['layout_keys'])}`",
        "",
        f"**Layer keys:** `{', '.join(ex['layer_keys'])}`",
        "",
        "**Layer (without instances):**",
        "",
        jblock(ex["sample_layer"]),
        "",
        "**Sample Instance (world object):**",
        "",
    ]
    if ex["sample_instance"]:
        md_lines.append(jblock(ex["sample_instance"]))
    md_lines += [
        "",
        "**Instance field reference:**",
        "| Field | Description |",
        "|-------|-------------|",
        "| `type` | Object type name (matches objectType filename) |",
        "| `properties` | Plugin-specific initial properties |",
        "| `uid` | Unique instance ID within the project |",
        "| `instanceVariables` | `{varName: value}` dict |",
        "| `behaviors` | `{behaviorName: {properties: {...}}}` dict |",
        "| `world` | Position/size/angle/color (world objects only) |",
        "| `effects` | `{effectName: {parameters: {...}}}` (if effects applied) |",
        "",
    ]

# ── Section 9: Instance Effects ───────────────────────────────────────────────
md_lines += [
    "## 9. Layout Instance — With Effects",
    "",
    "Instances in layouts can carry an `effects` field overriding effect parameters.",
    "",
]
if samples["instance_effect_example"]:
    ex = samples["instance_effect_example"]
    md_lines += [
        f"Source: `{ex['project']}/layouts/{ex['file']}`",
        "",
        jblock(ex["instance"]),
        "",
        "**Effects field structure:** `{ \"EffectName\": { \"parameters\": { \"param-name\": value, ... } } }`",
        "",
    ]
    if effect_param_examples:
        md_lines += ["**Effect parameter examples from instance level:**", ""]
        for ename, epex in list(effect_param_examples.items())[:5]:
            md_lines += [
                f"**`{ename}`** (on `{epex['instance_type']}` in `{epex['project']}`):",
                "",
                jblock(epex["effect_data"]),
                "",
            ]

# ── Section 10: Instance with Behaviors ──────────────────────────────────────
md_lines += [
    "## 10. Layout Instance — With Behaviors",
    "",
    "The `behaviors` field in a layout instance holds per-instance behavior property overrides.",
    "",
]
if samples["instance_behavior_example"]:
    ex = samples["instance_behavior_example"]
    md_lines += [
        f"Source: `{ex['project']}/layouts/{ex['file']}`",
        "",
        jblock(ex["instance"]),
        "",
        "**Behaviors field structure:** `{ \"BehaviorName\": { \"properties\": { \"enabled\": bool, ... } } }`",
        "",
    ]

# ── Section 11: Timelines ────────────────────────────────────────────────────
md_lines += [
    "## 11. Timelines",
    "",
    "Timeline files live in `timelines/`. Each timeline defines keyframe animations for object instances.",
    "",
    "**Timeline top-level fields:**",
    "| Field | Description |",
    "|-------|-------------|",
    "| `name` | Timeline display name |",
    "| `enabled` | Whether the timeline is active |",
    "| `interpolationMode` | Default interpolation (e.g. `\"default\"`, `\"step\"`) |",
    "| `resultMode` | How values are applied |",
    "| `ease` | Default easing function |",
    "| `totalTime` | Duration in seconds |",
    "| `loop` | Whether timeline loops |",
    "| `pingPong` | Whether timeline ping-pongs |",
    "| `repeatCount` | Number of repeats |",
    "| `tracks` | Array of instance-track objects |",
    "",
    "**Track fields (instance-track):**",
    "| Field | Description |",
    "|-------|-------------|",
    "| `type` | Always `\"instance-track\"` |",
    "| `worldInstance` | UID of the target instance |",
    "| `objectType` | Name of the object type |",
    "| `project` | Project unique ID |",
    "| `enabled` | Track enabled flag |",
    "| `interpolationMode` / `ease` / `pathMode` | Per-track overrides |",
    "| `initialVisibility` | Initial visible state |",
    "| `keyframes` | Array of `{time, tags, enabled, ease, pathMode}` — position keyframes |",
    "| `propertyTracks` | Array of property-specific sub-tracks |",
    "| `virtualPosition` | Initial offset and color settings |",
    "",
    "**PropertyKeyframe fields:**",
    "| Field | Description |",
    "|-------|-------------|",
    "| `time` | Time in seconds |",
    "| `enabled` | Keyframe active |",
    "| `ease` | Easing override |",
    "| `value` | Current computed value |",
    "| `rValue` | Raw/relative value |",
    "| `aValue` | Absolute value |",
    "| `addons` | Array of addon data (e.g. cubic-bezier handles) |",
    "",
]
if samples["timeline_examples"]:
    for tlex in samples["timeline_examples"]:
        md_lines += [
            f"### Example: `{tlex['project']}/timelines/{tlex['file']}`",
            "",
            jblock(tlex["timeline"]),
            "",
        ]
else:
    md_lines += ["*No timelines with tracks found.*", ""]

# ── Section 12: Flowcharts ────────────────────────────────────────────────────
md_lines += [
    "## 12. Flowcharts",
    "",
    "Flowchart files live in `flowcharts/`. They define node-based narrative/logic graphs.",
    f"Found in 10 projects: `chess-checkmate`, `flowchart-questionnaire`, `quest-flowcharts`, `text-based-adventure`, `visual-novel-sniff-and-fetch`, and others.",
    "",
    "**Flowchart top-level fields:**",
    "| Field | Description |",
    "|-------|-------------|",
    "| `name` | Flowchart display name |",
    "| `sid` | Stable ID (if present) |",
    "| `w`, `h` | Canvas dimensions |",
    "| `nodes` | Array of node objects |",
    "| `preset-nodes` | Predefined node templates (optional) |",
    "",
    "**Node fields:**",
    "| Field | Description |",
    "|-------|-------------|",
    "| `sid` | Unique stable ID for this node |",
    "| `pnSIDs` | Array of **previous node** SIDs (incoming connections) |",
    "| `poSIDs` | Array of **previous output** SIDs (which output port connects here) |",
    "| `nodeSIDs` | Array of **child node** SIDs (outgoing connections) |",
    "| `outputs` | Array of output port objects |",
    "| `x`, `y` | Canvas position |",
    "| `w`, `h` | Node width/height (if explicit) |",
    "| `t` | Node type string (observed: none in examples — type inferred from structure) |",
    "| `s` | Display string/label |",
    "| `c` | Comment text |",
    "| `pi` | Plugin/behavior reference index |",
    "",
    "**Output port fields:**",
    "| Field | Description |",
    "|-------|-------------|",
    "| `sid` | Stable ID for this output port |",
    "| `cnSID` | Connected next node SID (null if unconnected) |",
    "| `name` | Port label (e.g. `\"Message\"`, `\"Option1\"`, `\"Yes\"`) |",
    "| `value` | Content/value associated with this output |",
    "",
]
if samples["flowchart_examples"]:
    for fcex in samples["flowchart_examples"]:
        md_lines += [
            f"### Example: `{fcex['project']}/flowcharts/{fcex['file']}`",
            "",
            jblock(fcex["flowchart"]),
            "",
        ]
else:
    md_lines += ["*No flowcharts with nodes found.*", ""]

# ── Section 13: Unique Behavior IDs ─────────────────────────────────────────
md_lines += [
    "## 13. Unique Behavior IDs",
    "",
    f"Total: **{len(stats['unique_behavior_ids'])}** unique behavior IDs found across all 490 projects.",
    "",
    "```",
]
for bid in sorted(stats["unique_behavior_ids"]):
    md_lines.append(bid)
md_lines += ["```", ""]

# ── Section 14: Unique Effect IDs ────────────────────────────────────────────
md_lines += [
    "## 14. Unique Effect IDs",
    "",
    f"Total: **{len(stats['unique_effect_ids'])}** unique effect names found.",
    "Note: `effectId` (shader ID) and `name` (display) differ — see Section 4 for the mapping.",
    "",
    "```",
]
for eid in sorted(stats["unique_effect_ids"]):
    md_lines.append(eid)
md_lines += ["```", ""]

# Write Markdown
md_path = OUT_DIR / "c3p-schemas-discovered.md"
with open(md_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md_lines))
print(f"Markdown written to {md_path}", flush=True)
print("Done.", flush=True)
