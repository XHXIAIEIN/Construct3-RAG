"""Static checks for a Construct 3 folder project, run without the editor.

    python tools/check-project.py [project-root] [--rag PATH] [--locale en-US]

Reads project.c3proj and every object type, family, layout and event sheet
it lists, and checks them against the schemas in Construct3-RAG: every
condition and action exists for its plugin or behavior, parameter keys and
combo values are the schema's, layout instances only set properties their
plugin and behaviors have, and every object type, family, behavior, instance
variable, layer, layout, animation, function, custom action, image and project
file that is referenced is defined. Expressions are scanned for object,
behavior, expression and variable names. sids and uids must be unique, and
every object created at runtime needs a template instance in some layout.

It cannot run the events: picking, timing and the meaning of an expression
are the editor's and the preview's to judge.

Construct3-RAG is found from --rag, the CONSTRUCT3_RAG environment variable,
or a `Construct3-RAG: <path>` line in the project's CLAUDE.md or AGENTS.md.

Errors exit 1. Warnings (a parameter the schema lists but the file omits, a
plugin the schemas do not cover) are printed and do not fail the run.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    if msg not in warnings:
        warnings.append(msg)


def load(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# --- locate the project and the schemas -----------------------------------
def find_rag(root: Path, override: str | None) -> Path:
    candidates = [override, os.environ.get("CONSTRUCT3_RAG")]
    for name in ("CLAUDE.md", "AGENTS.md"):
        f = root / name
        if f.exists():
            m = re.search(r"Construct3-RAG:\s*(\S+)", f.read_text(encoding="utf-8"))
            if m and "<" not in m.group(1):
                candidates.append(m.group(1))
    for c in candidates:
        if c and (Path(c) / "data" / "c3-schemas" / "_index.json").exists():
            return Path(c)
    sys.exit("Construct3-RAG not found: pass --rag, set CONSTRUCT3_RAG, or put a "
             "'Construct3-RAG: <path>' line in the project's CLAUDE.md")


ap = argparse.ArgumentParser()
ap.add_argument("root", nargs="?", default=None,
                help="project folder (default: the current directory, else the parent of this script's folder)")
ap.add_argument("--rag", help="path to the Construct3-RAG checkout")
ap.add_argument("--locale", default="en-US", help="schema locale to read; ids are the same in every locale")
args = ap.parse_args()

if args.root:
    ROOT = Path(args.root).resolve()
elif (Path.cwd() / "project.c3proj").exists():
    ROOT = Path.cwd()
else:
    ROOT = Path(__file__).resolve().parent.parent
RAG = find_rag(ROOT, args.rag)
SCHEMAS = RAG / "data" / "c3-schemas" / args.locale

project = load(ROOT / "project.c3proj")
FUNCTIONS_OBJECT = project.get("functionsName", "Functions")
LOWER = str.lower  # expressions are case-insensitive: scrolly, SCROLLY and ScrollY are one name


def folder_items(folder: dict, prefix: Path = Path()) -> list[tuple[str, Path]]:
    """(name, relative folder) for every item of a project.c3proj folder tree."""
    out = [(name, prefix) for name in folder.get("items", [])]
    for sub in folder.get("subfolders", []):
        out += folder_items(sub, prefix / sub["name"] if sub.get("name") else prefix)
    return out


def project_file(kind: str, name: str, folder: Path) -> Path | None:
    """The JSON file for a listed item. Older projects keep the files flat even
    when project.c3proj has subfolders, so fall back to a search by name."""
    direct = ROOT / kind / folder / f"{name}.json"
    if direct.exists():
        return direct
    hits = [p for p in (ROOT / kind).rglob(f"{name}.json") if not p.name.endswith(".uistate.json")]
    return hits[0] if hits else None


def load_listed(kind: str) -> dict[str, dict]:
    out = {}
    for name, folder in folder_items(project.get(kind, {})):
        path = project_file(kind, name, folder)
        if path is None:
            err(f"{kind}: {name} is listed in project.c3proj but has no file")
            continue
        out[name] = load(path)
    return out


# --- schemas -----------------------------------------------------------------
_schema_cache: dict[tuple[str, str], dict | None] = {}


def schema(kind: str, addon_id: str) -> dict | None:
    key = (kind, addon_id.lower())
    if key not in _schema_cache:
        path = SCHEMAS / kind / f"{addon_id.lower()}.json"
        _schema_cache[key] = load(path) if path.exists() else None
        if _schema_cache[key] is None:
            warn(f"no schema for {kind[:-1]} {addon_id}: its ACEs and properties are not checked")
    return _schema_cache[key]


COMMON = schema("plugins", "_common")
SYSTEM = schema("plugins", "system")
SYSTEM_EXPRESSIONS = {LOWER(e["translated-name"]) for e in SYSTEM["expressions"]} | {"self", "loopindex", "infinity"}
COMMON_EXPRESSIONS = {LOWER(e["translated-name"]) for e in COMMON["expressions"]}


# --- object types and families -----------------------------------------------
types = load_listed("objectTypes")
families = load_listed("families")
plugin_of = {n: t["plugin-id"] for n, t in types.items()}
plugin_of.update({n: f["plugin-id"] for n, f in families.items()})
plugin_of["System"] = "system"
plugin_of[FUNCTIONS_OBJECT] = "system"   # the built-in Functions object: Set return value lives in the System schema
objects_lower = {LOWER(n): n for n in plugin_of}


def families_of(obj: str) -> list[str]:
    return [f for f, d in families.items() if obj in d.get("members", [])]


def ivar_types_of(obj: str) -> dict[str, str]:
    """instance variable name -> type, family variables included for member types."""
    ivars = {}
    if obj in types:
        ivars.update({v["name"]: v["type"] for v in types[obj].get("instanceVariables", [])})
        for f in families_of(obj):
            ivars.update({v["name"]: v["type"] for v in families[f].get("instanceVariables", [])})
    if obj in families:
        ivars.update({v["name"]: v["type"] for v in families[obj].get("instanceVariables", [])})
    return ivars


def ivars_of(obj: str) -> set[str]:
    return set(ivar_types_of(obj))


def behaviors_of(obj: str) -> dict[str, str]:
    """behavior name -> behavior id, family behaviors included for member types."""
    names = {}
    if obj in types:
        for b in types[obj].get("behaviorTypes", []):
            names[b["name"]] = b["behaviorId"]
        for f in families_of(obj):
            for b in families[f].get("behaviorTypes", []):
                names[b["name"]] = b["behaviorId"]
    if obj in families:
        for b in families[obj].get("behaviorTypes", []):
            names[b["name"]] = b["behaviorId"]
    return names


def animations_of(obj: str) -> set[str] | None:
    """Animation names of a Sprite type, or the union over a family's members. None: not a Sprite."""
    def walk(folder):
        out = {LOWER(a["name"]) for a in folder.get("items", [])}
        for sub in folder.get("subfolders", []):
            out |= walk(sub)
        return out
    if obj in types and "animations" in types[obj]:
        return walk(types[obj]["animations"])
    if obj in families:
        members = [m for m in families[obj].get("members", []) if m in types and "animations" in types[m]]
        return set().union(*(walk(types[m]["animations"]) for m in members)) if members else None
    return None


for name, t in types.items():
    schema("plugins", t["plugin-id"])
    for b in t.get("behaviorTypes", []):
        schema("behaviors", b["behaviorId"])
for fam, f in families.items():
    schema("plugins", f["plugin-id"])
    for b in f.get("behaviorTypes", []):
        schema("behaviors", b["behaviorId"])
    for m in f.get("members", []):
        if m not in types:
            err(f"family {fam}: member {m} is not an object type")
        elif types[m]["plugin-id"] != f["plugin-id"]:
            err(f"family {fam}: member {m} is a {types[m]['plugin-id']}, the family is {f['plugin-id']}")
for c in project.get("containers", []):
    for m in c.get("members", []):
        if m not in types:
            err(f"container {c.get('members')}: member {m} is not an object type")

# images: {type}-{animation}-{frame:03d}.png per frame, {type}.png for single-image plugins
try:
    from PIL import Image
except ImportError:
    Image = None
    warn("Pillow is not installed: image sizes are not compared with the frames")


def check_image(rel: str, width: int, height: int) -> None:
    path = ROOT / "images" / rel
    if not path.exists():
        err(f"missing image {rel}")
    elif Image is not None and Image.open(path).size != (width, height):
        err(f"{rel}: the object type says {width}x{height}, the file is {Image.open(path).size}")


def frames_of(folder, prefix=""):
    for anim in folder.get("items", []):
        for i, fr in enumerate(anim["frames"]):
            yield f"{prefix}{anim['name'].lower()}-{i:03d}.png", fr
    for sub in folder.get("subfolders", []):
        yield from frames_of(sub, prefix)


for name, t in types.items():
    if "image" in t:
        check_image(f"{name.lower()}.png", t["image"]["width"], t["image"]["height"])
    for rel, fr in frames_of(t.get("animations", {}), f"{name.lower()}-"):
        check_image(rel, fr["width"], fr["height"])

# --- layouts -------------------------------------------------------------------
layouts = load_listed("layouts")
sheets = load_listed("eventSheets")
layers: set[str] = set()
templates: set[str] = set()      # types with an instance in some layout
uids: list[int] = []
sids: list[int] = []        # sids of events, variables, object types, instances, files
ace_sids: list[int] = []    # sids of condition and action entries; the editor tolerates repeats here
group_titles: set[str] = set()


def collect_sids(obj, in_ace: bool = False) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "sid" and isinstance(v, int):
                (ace_sids if in_ace else sids).append(v)
            # instanceFolderItem and scene-graphs-folder-root are editor references that repeat an instance's sid
            if k not in ("instanceFolderItem", "scene-graphs-folder-root"):
                collect_sids(v, in_ace or k in ("conditions", "actions"))
    elif isinstance(obj, list):
        for v in obj:
            collect_sids(v, in_ace)


def check_properties(where: str, props: dict, schema_props: dict | None) -> None:
    """A property the schema does not list is a warning: older projects keep
    keys the editor has since renamed (z-height), and the editor drops them."""
    if schema_props is None:
        return
    for k, v in props.items():
        if k not in schema_props:
            warn(f"{where}: property {k} is not in the current schema")
            continue
        items = (schema_props[k] or {}).get("items")
        if items and v not in items:
            err(f"{where}: {k}={v!r} is not one of {list(items)}")


def check_effects(effect_types: list) -> None:
    """Only whether the effect has a schema; an unknown one is warned about once."""
    for e in effect_types:
        schema("effects", e.get("effectId", e.get("id", "")))


def check_instance(where: str, inst: dict) -> None:
    uids.append(inst["uid"])
    t = inst["type"]
    templates.add(t)
    if t not in types:
        err(f"{where}: instance of unknown type {t}")
        return
    ivars = ivars_of(t)
    for iv in inst.get("instanceVariables", {}):
        if iv not in ivars:
            err(f"{where}: {t} has no instance variable {iv}")
    for iv in ivars - set(inst.get("instanceVariables", {})):
        err(f"{where}: {t} instance has no value for instance variable {iv}")
    behs = behaviors_of(t)
    for b in inst.get("behaviors", {}):
        if b not in behs:
            err(f"{where}: {t} has no behavior {b}")
    for b in set(behs) - set(inst.get("behaviors", {})):
        err(f"{where}: {t} instance has no properties block for behavior {b}")
    plugin = schema("plugins", plugin_of[t])
    check_properties(f"{where}: {t}", inst.get("properties", {}), plugin.get("properties") if plugin else None)
    for b, block in inst.get("behaviors", {}).items():
        if b in behs:
            bs = schema("behaviors", behs[b])
            check_properties(f"{where}: {t}.{b}", block.get("properties", {}), bs.get("properties") if bs else None)
    anims = animations_of(t)
    initial = inst.get("properties", {}).get("initial-animation")
    if anims is not None and initial is not None and LOWER(initial) not in anims:
        err(f"{where}: {t} has no animation {initial!r} for initial-animation")


def walk_layers(where: str, layer_list: list) -> None:
    for layer in layer_list:
        layers.add(layer["name"])
        check_effects(layer.get("effectTypes", []))
        for inst in layer.get("instances", []):
            check_instance(f"{where} layer {layer['name']}", inst)
        walk_layers(where, layer.get("subLayers", []))


for lname, lay in layouts.items():
    collect_sids(lay)
    walk_layers(f"layout {lname}", lay["layers"])
    for inst in lay.get("nonworld-instances", []):
        check_instance(f"layout {lname}", inst)
    check_effects(lay.get("effectTypes", []))
    if lay.get("eventSheet") and lay["eventSheet"] not in sheets:
        err(f"layout {lname}: event sheet {lay['eventSheet']} does not exist")

for name, t in types.items():
    if "singleglobal-inst" in t:
        uids.append(t["singleglobal-inst"]["uid"])
        plugin = schema("plugins", t["plugin-id"])
        check_properties(f"{name}", t["singleglobal-inst"].get("properties", {}),
                         plugin.get("properties") if plugin else None)
    check_effects(t.get("effectTypes", []))
    collect_sids(t)
for f in families.values():
    collect_sids(f)
collect_sids(project.get("rootFileFolders", {}))

# --- event sheets ----------------------------------------------------------------
for sheet in sheets.values():
    collect_sids(sheet)

functions: dict[str, int] = {}                 # name -> parameter count
custom_actions: dict[tuple[str, str], int] = {}  # (owner, name) -> parameter count
pending_calls: list[tuple] = []
created: set[str] = set()
# Object and behavior names may start with a digit (3DCamera, 8Direction), so a
# token is any run of word characters and numeric literals are skipped by value.
# Sprite(2).X picks an instance by IID; the index is checked as an expression.
IDENT = re.compile(r"[A-Za-z0-9_]+")
NUMBER = re.compile(r"\d+(\.\d+)?(e[+-]?\d+)?", re.I)
MEMBER = re.compile(r"([A-Za-z0-9_]+)(?:\([^()]*\))?\s*\.\s*([A-Za-z0-9_]+)(?:\s*\.\s*([A-Za-z0-9_]+))?")
STRING_LITERAL = re.compile(r'"(?:[^"]|"")*"')


def declared_functions(events: list) -> None:
    """Functions and custom actions are visible from every sheet, so collect them first."""
    for ev in events:
        et = ev.get("eventType")
        if et == "function-block":
            functions[ev["functionName"]] = len(ev["functionParameters"])
        elif et == "custom-ace-block":
            custom_actions[(ev["objectClass"], ev["aceName"])] = len(ev["functionParameters"])
        declared_functions(ev.get("children", []))


def declared_groups(events: list) -> None:
    for ev in events:
        if ev.get("eventType") == "group":
            group_titles.add(ev["title"])
        declared_groups(ev.get("children", []))


for sheet in sheets.values():
    declared_functions(sheet["events"])
    declared_groups(sheet["events"])


def is_literal(v) -> bool:
    return isinstance(v, str) and re.fullmatch(r'"(?:[^"]|"")*"', v) is not None


def unquote(v: str) -> str:
    return v[1:-1].replace('""', '"')


def check_expr(where: str, expr, scope: dict) -> None:
    if not isinstance(expr, str):
        return
    text = STRING_LITERAL.sub('""', expr)
    scope_lower = {LOWER(k) for k in scope}
    for m in MEMBER.finditer(text):
        obj, member, sub = m.group(1), m.group(2), m.group(3)
        if LOWER(obj) == "self" or NUMBER.fullmatch(obj):   # a decimal such as 0.5 is not a member access
            continue
        if LOWER(obj) == LOWER(FUNCTIONS_OBJECT):
            if LOWER(member) not in {LOWER(f) for f in functions}:
                err(f"{where}: {obj}.{member} is not a defined function")
            continue
        obj = objects_lower.get(LOWER(obj))
        if obj is None or obj == "System":
            err(f"{where}: unknown object {m.group(1)} in expression")
            continue
        behs = {LOWER(k): v for k, v in behaviors_of(obj).items()}
        if LOWER(member) in behs:
            bs = schema("behaviors", behs[LOWER(member)])
            if bs is None:
                continue
            if sub is None or LOWER(sub) not in {LOWER(e["translated-name"]) for e in bs["expressions"]}:
                err(f"{where}: {obj}.{member}.{sub or ''} is not an expression of behavior {behs[LOWER(member)]}")
            continue
        plugin = schema("plugins", plugin_of[obj])
        if plugin is None:
            continue
        known = {LOWER(e["translated-name"]) for e in plugin.get("expressions", [])} | COMMON_EXPRESSIONS
        known |= {LOWER(v) for v in ivars_of(obj)}
        if LOWER(member) not in known:
            err(f"{where}: {obj}.{member} is neither an expression nor an instance variable of {obj}")
    for m in IDENT.finditer(text):
        name = m.group(0)
        if NUMBER.fullmatch(name):
            continue
        if text[:m.start()].rstrip().endswith(".") or text[m.end():].lstrip().startswith("."):
            continue
        if LOWER(name) in SYSTEM_EXPRESSIONS or LOWER(name) in scope_lower:
            continue
        if LOWER(name) in objects_lower and text[m.end():].lstrip().startswith("("):
            continue
        err(f"{where}: identifier {name!r} is not a variable, parameter or system expression")


def check_param(where: str, key: str, value, ptype: str, items: dict | None, obj: str, scope: dict) -> None:
    if ptype == "cmp":
        if value not in (0, 1, 2, 3, 4, 5):
            err(f"{where}: comparison {value!r} is not an integer 0-5 (=, ≠, <, ≤, >, ≥)")
    elif ptype == "boolean":
        if not isinstance(value, bool):
            err(f"{where}: {key} should be a JSON boolean, not {value!r}")
    elif ptype in ("combo", "combo-grouped"):
        if items and value not in items:
            err(f"{where}: {key}={value!r} is not one of {list(items)}")
    elif ptype in ("ease", "keyb", "audiofile", "tilemapbrush", "function", "model3d", "template", "objecteffect"):
        return
    elif ptype == "object":
        if value not in plugin_of or value == "System":
            err(f"{where}: {key}={value!r} is not an object type or family")
    elif ptype in ("instancevar", "instancevarbool"):
        # shared ACEs name one of the object's own variables
        ivars = ivar_types_of(obj)
        if value not in ivars:
            err(f"{where}: {obj} has no instance variable {value!r}")
        elif ptype == "instancevarbool" and ivars[value] != "boolean":
            err(f"{where}: instance variable {value!r} is not a boolean")
    elif ptype == "objinstancevar":
        target, ivar = (value.get("objectClass", obj), value.get("name")) if isinstance(value, dict) else (obj, value)
        if ivar not in ivars_of(target):
            err(f"{where}: {target} has no instance variable {ivar!r}")
    elif ptype in ("eventvar", "eventvarbool", "eventvarany"):
        if value not in scope:
            err(f"{where}: variable {value!r} is not in scope")
        elif ptype == "eventvarbool" and scope[value] != "boolean":
            err(f"{where}: variable {value!r} is not a boolean")
    elif ptype == "layer":
        if is_literal(value):
            if unquote(value) not in layers:
                err(f"{where}: no layer named {unquote(value)!r} in any layout")
        else:
            check_expr(f"{where} {key}", value, scope)
    elif ptype == "layout":
        if value not in layouts:
            err(f"{where}: no layout named {value!r}")
    elif ptype == "groupname":
        if is_literal(value) and unquote(value) not in group_titles:
            err(f"{where}: no group titled {unquote(value)!r}")
    elif ptype == "animation":
        anims = animations_of(obj)
        if is_literal(value):
            if anims is not None and LOWER(unquote(value)) not in anims:
                err(f"{where}: {obj} has no animation {unquote(value)!r}")
        else:
            check_expr(f"{where} {key}", value, scope)
    elif ptype == "projectfile":
        name = value["path"] if isinstance(value, dict) else value
        if not (ROOT / "files" / name).exists() and not list((ROOT / "files").rglob(Path(name).name)):
            err(f"{where}: project file {name!r} is not in files/")
    elif ptype == "timeline":
        if value not in [n for n, _ in folder_items(project.get("timelines", {}))]:
            err(f"{where}: no timeline named {value!r}")
    elif ptype == "flowchart":
        if value not in [n for n, _ in folder_items(project.get("flowcharts", {}))]:
            err(f"{where}: no flowchart named {value!r}")
    else:
        if not isinstance(value, str):
            err(f"{where}: {key} should be an expression string, not {value!r}")
        else:
            check_expr(f"{where} {key}", value, scope)


def check_ace(kind: str, ace: dict, scope: dict, where: str) -> None:
    obj = ace["objectClass"]
    ace_id = ace["id"]
    params = ace.get("parameters", {})
    where = f"{where} {obj}:{ace_id}"
    if obj not in plugin_of:
        err(f"{where}: unknown object {obj}")
        return
    if "behaviorType" in ace:
        behs = behaviors_of(obj)
        if ace["behaviorType"] not in behs:
            err(f"{where}: {obj} has no behavior {ace['behaviorType']}")
            return
        addon_kind, addon_id = "behaviors", behs[ace["behaviorType"]]
        src = schema(addon_kind, addon_id)
        if src is None:
            return
        entry = next((it for it in src.get(kind, []) if it["id"] == ace_id), None)
    else:
        addon_kind, addon_id = "plugins", plugin_of[obj]
        src = schema(addon_kind, addon_id)
        if src is None:
            return
        entry = next((it for it in src.get(kind, []) if it["id"] == ace_id), None)
        if entry is None and obj != "System":
            entry = next((it for it in COMMON.get(kind, []) if it["id"] == ace_id), None)
            addon_id = "_common"
    if entry is None:
        err(f"{where}: {plugin_of[obj] if addon_id == '_common' else addon_id} has no {kind[:-1]} {ace_id}"
            + (" (not in _common either)" if addon_id == "_common" else ""))
        return
    schema_params = entry.get("params") or {}
    for k in params:
        if k not in schema_params:
            err(f"{where}: unknown parameter {k}")
    for k in schema_params:
        if k not in params:
            warn(f"{where}: parameter {k} is omitted; the editor fills its default")
    for k, v in params.items():
        if k not in schema_params:
            continue
        check_param(where, k, v, schema_params[k]["type"], schema_params[k].get("items"), obj, scope)
    if ace_id == "create-object" and obj == "System":
        created.add(params.get("object-to-create"))
    if ace_id == "set-eventvar-value" and scope.get(params.get("variable")) == "boolean":
        err(f"{where}: Set value on boolean {params['variable']}; use Set boolean")


def check_block(ev: dict, scope: dict, where: str) -> None:
    for i, c in enumerate(ev.get("conditions", [])):
        check_ace("conditions", c, scope, f"{where} cond#{i}")
    for i, a in enumerate(ev.get("actions", [])):
        w = f"{where} act#{i}"
        if a.get("type") in ("comment", "script"):
            continue
        if "callFunction" in a:
            pending_calls.append(("function", a["callFunction"], None, len(a.get("parameters", [])), w))
            for p in a.get("parameters", []):
                check_expr(w, p, scope)
            continue
        if "customAction" in a:
            owner = a.get("customActionObjectClass", a["objectClass"])
            pending_calls.append(("custom", a["customAction"], owner, len(a.get("parameters", [])), w))
            for p in a.get("parameters", []):
                check_expr(w, p, scope)
            continue
        check_ace("actions", a, scope, w)


def walk(events: list, scope: dict, where: str) -> None:
    """A local declared in a list of sibling events is visible to every event of
    that list, whatever the order, and to their sub-events; not to the parent's
    own actions. So the list's variables enter the scope first, and a block is
    checked before its children are walked."""
    scope = dict(scope)
    for ev in events:
        if ev.get("eventType") == "variable":
            scope[ev["name"]] = ev["type"]
    for ev in events:
        et = ev.get("eventType")
        w = f"{where} {ev.get('sid', '?')}"
        if et == "variable":
            continue
        elif et in ("comment", "include"):
            if et == "include" and ev["includeSheet"] not in sheets:
                err(f"{w}: included sheet {ev['includeSheet']} does not exist")
        elif et == "group":
            walk(ev["children"], scope, w)
        elif et in ("function-block", "custom-ace-block"):
            fscope = dict(scope)
            for p in ev["functionParameters"]:
                fscope[p["name"]] = p["type"]
            label = ev.get("functionName") or f"{ev['objectClass']}.{ev['aceName']}"
            if et == "custom-ace-block" and ev["objectClass"] not in plugin_of:
                err(f"{w}: custom action {label} belongs to unknown object {ev['objectClass']}")
            check_block(ev, fscope, f"{w} {label}")
            walk(ev.get("children", []), fscope, w)
        elif et == "block":
            check_block(ev, scope, w)
            walk(ev.get("children", []), scope, w)
        else:
            err(f"{w}: unknown eventType {et!r}")


# A global declared at the top level of any sheet is visible from every sheet.
globals_ = {ev["name"]: ev["type"] for s in sheets.values() for ev in s["events"] if ev.get("eventType") == "variable"}
for sname, sheet in sheets.items():
    walk(sheet["events"], globals_, f"sheet {sname}")

for kind, name, owner, nparams, where in pending_calls:
    if kind == "function":
        if name not in functions:
            err(f"{where}: call to undefined function {name}")
        elif functions[name] != nparams:
            err(f"{where}: {name} called with {nparams} parameters, defined with {functions[name]}")
    else:
        owners = [owner] + families_of(owner)
        hit = next(((o, name) for o in owners if (o, name) in custom_actions), None)
        if hit is None:
            err(f"{where}: {owner} has no custom action {name!r}")
        elif custom_actions[hit] != nparams:
            err(f"{where}: {owner}.{name} called with {nparams} parameters, defined with {custom_actions[hit]}")

for t in created:
    if t in types and t not in templates:
        warn(f"{t} is created at runtime but has no instance in any layout: it is created with default properties")

# --- uniqueness, project files, addons --------------------------------------------
dup_sids = sorted({s for s in sids if sids.count(s) > 1} | (set(sids) & set(ace_sids)))
if dup_sids:
    err(f"duplicate sids: {dup_sids[:5]}{' ...' if len(dup_sids) > 5 else ''}")
dup_ace_sids = sorted({s for s in ace_sids if ace_sids.count(s) > 1})
if dup_ace_sids:
    warn(f"conditions or actions sharing a sid (pasted in the editor?): {dup_ace_sids[:5]}{' ...' if len(dup_ace_sids) > 5 else ''}")
dup_uids = sorted({u for u in uids if uids.count(u) > 1})
if dup_uids:
    err(f"duplicate uids: {dup_uids[:5]}{' ...' if len(dup_uids) > 5 else ''}")

for name, folder in folder_items(project.get("rootFileFolders", {}).get("general", {})):
    fname = name["name"] if isinstance(name, dict) else name
    if not (ROOT / "files" / folder / fname).exists():
        err(f"project file {fname} is listed in project.c3proj but missing from files/{folder}")

addon_ids = {a["id"] for a in project.get("usedAddons", [])}


def need_addon(addon_id: str, where: str) -> None:
    if addon_id not in addon_ids:
        err(f"{where}: {addon_id} is not listed in usedAddons")


for name, t in types.items():
    need_addon(t["plugin-id"], f"object type {name}")
    for b in t.get("behaviorTypes", []):
        need_addon(b["behaviorId"], f"object type {name}")
    for e in t.get("effectTypes", []):
        need_addon(e.get("effectId", e.get("id", "")), f"object type {name}")
for name, f in families.items():
    for b in f.get("behaviorTypes", []):
        need_addon(b["behaviorId"], f"family {name}")
    for e in f.get("effectTypes", []):
        need_addon(e.get("effectId", e.get("id", "")), f"family {name}")

for w in warnings:
    print(f"warning: {w}")
if errors:
    print("\n".join(errors))
    print(f"{len(errors)} problem(s)")
    sys.exit(1)
print(f"ok: {len(types)} object types, {len(families)} families, {len(layouts)} layouts, {len(sheets)} sheets, "
      f"{len(sids) + len(ace_sids)} sids, {len(uids)} uids, {len(functions)} functions, {len(custom_actions)} custom actions")
