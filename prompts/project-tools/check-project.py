"""Static checks for a Construct 3 folder project, run without the editor.

    python tools/check-project.py [project-root] [--rag PATH] [--locale en-US]
    python tools/check-project.py --print [SHEET]          the sheet as the editor words it
    python tools/check-project.py --outline [SHEET]        event numbers and sids
    python tools/check-project.py --ace OBJECT [WORD ...]  look an ACE up, with the JSON to write

Reads project.c3proj and every object type, family, layout and event sheet
it lists, and checks them against the schemas in Construct3-RAG: every
condition and action exists for its plugin or behavior, parameter keys and
combo values are the schema's, layout instances only set properties their
plugin and behaviors have, and every object type, family, behavior, instance
variable, layer, layout, animation, function, custom action, image and project
file that is referenced is defined. Expressions are scanned for object,
behavior, expression and variable names. sids and uids must be unique, and
every object created at runtime needs a template instance in some layout.

It also applies the rules the editor enforces when it opens or previews a
project, read from the editor's own project model: a plugin or behavior id
is spelled exactly as the editor spells it (`Arr`, `TiledBg`, `EightDir`);
an object, family, instance variable or behavior name is one the editor
keeps as written, is not reserved, and does not collide with an expression
of the object; an event branch holds one trigger, and none inside a function
or custom action; a trigger or a loop is never inverted; an Else follows a
plain event as its first condition; a key is a key code; an action does not
write a constant.

It cannot run the events: picking, timing and the meaning of an expression
are the editor's and the preview's to judge.

Findings in event sheets are placed as `sheet Game event 15 action 2`: the
event number is the one the editor prints in the margin and in Find results,
so it can be quoted to the user and read back from a screenshot. A row's
number is the count of blocks, groups, function blocks and custom action
blocks before it in the sheet, sub-events included, plus one. Those rows take
the number for themselves; a variable, comment or include takes no number of
its own and belongs to the next one, which is how the editor's Find lists it
(`Event 15: Local number srcColor`). Conditions and actions count from 1.
`--outline` prints that numbering for one sheet or all of them, with the sid
of each event, for finding the JSON behind a number. `--print` prints the
sheet itself as the editor words it, conditions and actions under each
number, in the locale of --locale; it reads any folder project, an official
example included, in a fraction of the JSON's length.

`--ace Coin tween` lists the conditions, actions and expressions whose id or
name holds every word, across the object's plugin, the shared world-object
ACEs and its behaviors; six or fewer print in full, each parameter with the
way it is written and the JSON to paste. `System`, or a plugin or behavior by
id or display name (`--ace "8 Direction" speed`), works without a project.
The schema files run to thousands of lines, more than most tools read at
once; this prints the part that was asked for.

Construct3-RAG is found from --rag, the CONSTRUCT3_RAG environment variable,
a `Construct3-RAG: <path>` line in the project's CLAUDE.md or AGENTS.md
(`<path-to>` in it is read from a `path-to = <folder>` line), or the clone
this script sits in when it is run from there.

Errors exit 1. Warnings (a parameter the schema lists but the file omits, a
plugin the schemas do not cover) are printed and do not fail the run.
"""
import argparse
import difflib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import NamedTuple

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    if msg not in errors:
        errors.append(msg)


def warn(msg: str) -> None:
    if msg not in warnings:
        warnings.append(msg)


def load(path: Path):
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"{path}: not valid JSON, line {e.lineno} column {e.colno}: {e.msg}")


def stopped(exc_type, exc, tb) -> None:
    """A file that lacks a key the editor always writes stops the run; say which
    key and where the checker was, instead of a traceback."""
    while tb.tb_next:
        tb = tb.tb_next
    what = f"missing key {exc}" if exc_type is KeyError else f"{exc_type.__name__}: {exc}"
    print(f"check-project.py stopped at line {tb.tb_lineno} ({tb.tb_frame.f_code.co_name}): {what}. "
          f"A project file lacks a key the editor always writes, or holds a value of another type than the "
          f"editor writes; compare it with a file build-project.py generates, or with an official example.")
    for w in warnings:
        print(f"warning: {w}")
    if errors:
        print("\n".join(errors))
    sys.stdout.flush()
    os._exit(2)     # sys.exit would raise inside the hook and print a second traceback


sys.excepthook = stopped


# --- locate the project and the schemas -----------------------------------
def rag_line(text: str) -> str | None:
    """The path on the `Construct3-RAG:` line of an instruction file. The line
    may spell the folder out or keep `<path-to>` and define it once above, as
    `path-to = D:\\GitHub` or `<path-to>: D:/GitHub`; a path may hold spaces."""
    m = re.search(r"^[ \t>*-]*Construct3-RAG\s*[:=][ \t]*(.+)$", text, re.M)
    if not m:
        return None
    value = m.group(1).strip().strip("`\"'")
    if "<path-to>" in value:
        base = re.search(r"^[ \t>*-]*<?path-to>?\s*[:=][ \t]*(.+)$", text, re.M)
        if not base:
            return None
        value = value.replace("<path-to>", base.group(1).strip().strip("`\"'").rstrip("\\/"))
    return None if "<" in value else value


def find_rag(root: Path, override: str | None) -> Path:
    tried = []
    candidates = [("--rag", override), ("CONSTRUCT3_RAG", os.environ.get("CONSTRUCT3_RAG"))]
    # The project being checked, then the one this copy of the script belongs to:
    # an official example printed from a game project has no instruction file of its own.
    for folder in dict.fromkeys((root, Path.cwd(), Path(__file__).resolve().parent.parent)):
        for name in ("CLAUDE.md", "AGENTS.md"):
            f = folder / name
            if f.exists():
                candidates.append((str(f), rag_line(f.read_text(encoding="utf-8"))))
    for source, c in candidates:
        if not c:
            continue
        if (Path(c) / "data" / "c3-schemas" / "_index.json").exists():
            return Path(c)
        tried.append(f"{source}: {c}")
    # Run in place, from <Construct3-RAG>/prompts/project-tools/, the clone is the script's own.
    own = Path(__file__).resolve().parents[2]
    if (own / "data" / "c3-schemas" / "_index.json").exists():
        return own
    sys.exit("Construct3-RAG not found. Pass --rag <folder>, set CONSTRUCT3_RAG, or write the line "
             "'- Construct3-RAG: <folder>' in the project's AGENTS.md or CLAUDE.md; the folder is the "
             "one that holds data/c3-schemas/_index.json."
             + ("\nTried " + "; ".join(tried) if tried else ""))


ap = argparse.ArgumentParser()
ap.add_argument("root", nargs="?", default=None,
                help="project folder (default: the current directory, else the parent of this script's folder)")
ap.add_argument("--rag", help="path to the Construct3-RAG checkout")
ap.add_argument("--locale", default="en-US", help="schema locale to read; ids are the same in every locale")
ap.add_argument("--outline", nargs="?", const="*", metavar="SHEET",
                help="print the event numbering of one sheet, or of every sheet, instead of checking")
ap.add_argument("--print", nargs="?", const="*", metavar="SHEET",
                help="print one sheet, or every sheet, as the editor words it: numbered events, conditions, actions")
ap.add_argument("--ace", nargs="+", metavar=("OBJECT", "WORD"),
                help="look up conditions, actions and expressions instead of checking: an object of the project "
                     "(its plugin, the shared ACEs and its behaviors), System, or a plugin or behavior by id or "
                     "name; the words narrow the list, and a short list prints each entry with the JSON to write")
args = ap.parse_args()

if args.root:
    ROOT = Path(args.root).resolve()
elif (Path.cwd() / "project.c3proj").exists():
    ROOT = Path.cwd()
else:
    ROOT = Path(__file__).resolve().parent.parent
RAG = find_rag(ROOT, args.rag)
SCHEMAS = RAG / "data" / "c3-schemas" / args.locale

# A lookup by plugin or behavior needs no project: --ace works from the clone alone.
project = load(ROOT / "project.c3proj") if (ROOT / "project.c3proj").exists() or not args.ace else {}
used_addons = {a["id"]: a for a in project.get("usedAddons", [])}
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
INDEX = load(RAG / "data" / "c3-schemas" / "_index.json")


def squash(s: str) -> str:
    """Letters and digits only, lowercased: 'Set animation', 'SetAnimation' and 'set-animation' are one key."""
    return re.sub(r"[\W_]+", "", str(s).lower())


def closest(word: str, options, n: int = 3) -> str:
    """'; closest: a, b' for an error message, or '' when nothing is near."""
    table = {squash(o): o for o in options}
    hits = difflib.get_close_matches(squash(word), list(table), n=n, cutoff=0.6)
    return "; closest: " + ", ".join(table[h] for h in hits) if hits else ""


def addon_hint(kind: str, addon_id: str) -> str | None:
    """The id the editor uses for what the project calls addon_id, found through
    the display name ('Array' is Arr, '8 Direction' is EightDir) or a near id."""
    ids = INDEX.get(kind, {})
    by_name = {}
    for locale in {args.locale, "en-US"}:
        names_file = RAG / "data" / "c3-schemas" / locale / "_index.json"
        if names_file.exists():
            for k, v in load(names_file).get(kind, {}).items():
                by_name[squash(v.get("name", k))] = k
    table = {**by_name, **{squash(k): k for k in ids}}
    hit = table.get(squash(addon_id))
    if hit is None:
        near = difflib.get_close_matches(squash(addon_id), list(table), n=1, cutoff=0.75)
        hit = table[near[0]] if near else None
    if hit is None or hit not in ids or hit == "_common":
        return None
    return ids[hit].get("originalId", hit)


def schema(kind: str, addon_id: str) -> dict | None:
    key = (kind, addon_id.lower())
    if key not in _schema_cache:
        path = SCHEMAS / kind / f"{addon_id.lower()}.json"
        _schema_cache[key] = load(path) if path.exists() else None
        if _schema_cache[key] is None:
            # An addon the project lists under another author is a third-party one: no schema, no hint.
            third_party = used_addons.get(addon_id, {}).get("author", "Scirra") != "Scirra"
            hint = None if third_party else addon_hint(kind, addon_id)
            if hint:
                err(f"{kind[:-1]} id {addon_id!r} does not exist: the editor's id is {hint!r}")
            else:
                warn(f"no schema for {kind[:-1]} {addon_id}: its ACEs and properties are not checked")
    return _schema_cache[key]


def check_addon_id(kind: str, addon_id: str, where: str) -> None:
    """The editor looks an addon up by its exact id, so 'sprite' or 'Tiledbg'
    fails to open even though the schema file is found case-insensitively."""
    exact = INDEX.get(kind, {}).get(addon_id.lower(), {}).get("originalId")
    if exact and exact != addon_id:
        err(f"{where}: {kind[:-1]} id {addon_id!r} must be written {exact!r}; addon ids are case-sensitive")


COMMON = schema("plugins", "_common")
SYSTEM = schema("plugins", "system")
SYSTEM_EXPRESSION_NAMES = {LOWER(e["translated-name"]) for e in SYSTEM["expressions"]}
SYSTEM_EXPRESSIONS = SYSTEM_EXPRESSION_NAMES | {"self", "loopindex", "infinity"}
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


# Names. The editor passes every name through a filter when it opens the
# project and keeps the result, so a name the filter changes no longer matches
# the events that use it; and it refuses a name that is reserved or already
# taken in the object's namespace, where instance variables, behaviors, effects
# and the plugin's expressions live side by side, compared without case.
NAME_DROPS = set(".。,，\"“”(（)）?？:：\\/;*|'-`!¬£$%^&+=<>{}[]@#~­​")
RESERVED_NAMES = {"self", "true", "false", "system", "con", "prn", "aux", "nul",
                  *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def editor_name(name: str, is_object: bool) -> str:
    """What the editor keeps of a name: the letter after a space is capitalised,
    spaces and punctuation go, leading underscores go. An object or behavior
    name may start with a digit but not be all digits; an instance variable
    name loses its leading digits too."""
    chars = list(unicodedata.normalize("NFC", name))
    for i in range(len(chars) - 1):
        if chars[i] == " ":
            chars[i + 1] = chars[i + 1].upper()
    chars = [c for c in chars if c not in NAME_DROPS and not c.isspace()]
    if is_object:
        while chars and chars[0] == "_":
            chars.pop(0)
        if all(c.isdigit() for c in chars):
            chars = []
    else:
        while chars and (chars[0].isdigit() or chars[0] == "_"):
            chars.pop(0)
    return "".join(chars)


def check_name(where: str, what: str, name: str, is_object: bool) -> None:
    kept = editor_name(name, is_object)
    if kept != name:
        err(f"{where}: the editor does not keep the {what} name {name!r} as written"
            + (f", it becomes {kept!r}" if kept else "") + "; use letters, digits and underscores, starting with a letter")


for kind, listed in (("object type", types), ("family", families)):
    for name, t in listed.items():
        if t.get("name") != name:
            err(f"{kind} {name}: the file says \"name\": {t.get('name')!r}; it must be the name listed in project.c3proj")
        check_name(f"{kind} {name}", kind, name, True)
        if LOWER(name) in RESERVED_NAMES or LOWER(name) in SYSTEM_EXPRESSION_NAMES:
            err(f"{kind} {name}: the name is reserved ({LOWER(name)} is a keyword or a system expression); "
                f"rename it, for example {name}Object")
        check_addon_id("plugins", t["plugin-id"], f"{kind} {name}")
        for b in t.get("behaviorTypes", []):
            check_addon_id("behaviors", b["behaviorId"], f"{kind} {name} behavior {b['name']}")
            check_name(f"{kind} {name}", "behavior", b["name"], True)
        for v in t.get("instanceVariables", []):
            check_name(f"{kind} {name}", "instance variable", v["name"], False)
for a in project.get("usedAddons", []):
    if a.get("type") in ("plugin", "behavior"):
        check_addon_id(a["type"] + "s", a["id"], "project.c3proj usedAddons")

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

# --- --ace: look an ACE up and print the JSON to write ---------------------------------
# How each parameter type is written in an event sheet file, and a value that loads.
WRITING = {
    "number": ('"0"', "expression string: \"100\", \"Self.X + 50\""),
    "string": ('"\\"\\""', "expression string, text in inner quotes: \"\\\"hello\\\"\""),
    "any": ('"0"', "expression string, a number or a text in inner quotes"),
    "boolean": ("false", "JSON true or false"),
    "cmp": ("0", "JSON number: 0 =, 1 ≠, 2 <, 3 ≤, 4 >, 5 ≥"),
    "object": ('"<object>"', "bare name of an object type or family"),
    "layer": ('"0"', "expression string: an index \"0\" or a name in inner quotes \"\\\"HUD\\\"\""),
    "layout": ('"<layout>"', "bare layout name"),
    "keyb": ("32", "key code as a JSON number: 32 Space, 13 Enter, 37-40 arrows, 65-90 A-Z"),
    "instancevar": ('"<variable>"', "bare name of an instance variable of the object"),
    "instancevarbool": ('"<variable>"', "bare name of a boolean instance variable of the object"),
    "objinstancevar": ('{"name": "<variable>", "objectClass": "<object>"}', "an instance variable of another object"),
    "eventvar": ('"<variable>"', "bare name of a global or local variable in scope"),
    "eventvarbool": ('"<variable>"', "bare name of a boolean variable in scope"),
    "eventvarany": ('"<variable>"', "bare name of a variable in scope"),
    "animation": ('"\\"\\""', "expression string, the animation name in inner quotes"),
    "groupname": ('"\\"\\""', "expression string, the group title in inner quotes"),
    "ease": ('"easeinoutsine"', "bare id of a built-in ease: noease, easeinoutsine, easeoutback ..."),
    "projectfile": ('"<file>"', "bare file name under files/"),
    "timeline": ('"<timeline>"', "bare timeline name"),
    "flowchart": ('"<flowchart>"', "bare flowchart name"),
    "template": ('"\\"\\""', "expression string, the template name in inner quotes, \"\\\"\\\"\" for none"),
}


def ace_lookup(target: str, words: list[str]) -> None:
    """Sources of a project object are its plugin, the shared world-object ACEs
    and its behaviors under the names they have on the object; of anything
    else, the plugin or behavior with that id or display name."""
    sources: list[tuple[str, str | None, dict]] = []      # (objectClass to write, behaviorType, schema)
    obj = objects_lower.get(LOWER(target))
    if obj == "System" or LOWER(target) == "system":
        sources.append(("System", None, SYSTEM))
    elif obj:
        sources.append((obj, None, schema("plugins", plugin_of[obj]) or {}))
        if "singleglobal-inst" not in types.get(obj, {}):     # Keyboard, Touch, Audio: nothing of a world object
            sources.append((obj, None, COMMON))
        sources += [(obj, name, schema("behaviors", b) or {}) for name, b in behaviors_of(obj).items()]
    else:
        for kind in ("plugins", "behaviors"):
            addon = target if LOWER(target) in INDEX.get(kind, {}) else addon_hint(kind, target)
            if addon and LOWER(addon) != "_common":
                behavior = "<behavior name on the object>" if kind == "behaviors" else None
                sources.append(("<object>", behavior, schema(kind, addon) or {}))
                break
    if not sources:
        sys.exit(f"{target!r} is not an object of this project, System, or a plugin or behavior"
                 + closest(target, list(plugin_of) + list(INDEX["plugins"]) + list(INDEX["behaviors"])))

    kinds = ("conditions", "actions", "expressions")
    found = []
    for owner, behavior, s in sources:
        for kind in kinds:
            for it in s.get(kind, []):
                hay = squash(" ".join(str(it.get(k, "")) for k in ("id", "list-name", "translated-name", "scriptName")))
                if all(squash(w) in hay for w in words):
                    found.append((owner, behavior, s.get("id", ""), kind, it))
    if not found:
        ids = [it["id"] for _, _, s in sources for kind in kinds for it in s.get(kind, [])]
        sys.exit(f"nothing under {target} matches {' '.join(words)!r}{closest(' '.join(words), ids, n=6)}")

    brief = len(found) > 6
    for owner, behavior, addon, kind, it in found:
        title = it.get("list-name") or it.get("translated-name")
        flags = [f for f in ("isTrigger", "isLooping", "isAsync") if it.get(f)] + \
                (["not invertible"] if it.get("isInvertible") is False else [])
        via = f" [behavior {behavior}, {addon}]" if behavior else f" [{addon}]"
        params = it.get("params") or {}
        if brief:
            print(f"{kind[:-1]:<10} {it['id']:<34} {title}{via}" + (f"  ({', '.join(params)})" if params else ""))
            continue
        print(f"{kind[:-1]} {it['id']} - {title}{via}" + (f"  <{', '.join(flags)}>" if flags else ""))
        print(f"  {it.get('description', '')}")
        if kind == "expressions":
            call = f"({', '.join(params)})" if params else ""
            path = f"{owner}.{behavior}." if behavior else ("" if owner == "System" else f"{owner}.")
            print(f"  write: {path}{it['translated-name']}{call}  -> {it.get('returnType', 'any')}")
        else:
            values = {}
            for key, spec in params.items():
                items = spec.get("items")
                if items:
                    first = spec.get("initialValue") if spec.get("initialValue") in items else next(iter(items))
                    values[key] = json.dumps(first)
                else:
                    values[key] = WRITING.get(spec["type"], ('"0"', ""))[0]
            head = f'{{"id": "{it["id"]}", "objectClass": "{owner}"' \
                   + (f', "behaviorType": "{behavior}"' if behavior else "") + ', "sid": <new sid>'
            body = ", ".join(f'"{k}": {v}' for k, v in values.items())
            print("  write: " + head + (f', "parameters": {{{body}}}}}' if params else "}"))
        for key, spec in params.items():
            how = " | ".join(spec["items"]) if spec.get("items") \
                else WRITING.get(spec["type"], ("", "expression string"))[1]
            print(f"    {key:<22} {spec['type']:<10} {how}")
    if brief:
        print(f"{len(found)} entries; add a word to narrow them, six or fewer print with the JSON to write")
    sys.exit(0)


if args.ace:
    ace_lookup(args.ace[0], args.ace[1:])

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
world_types: set[str] = set()    # types with an instance on a layer: they have X, Width, Angle ...
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
    t = inst.get("type")
    if not isinstance(inst.get("uid"), int):
        err(f"{where}: instance of {t} has no integer uid")
    else:
        uids.append(inst["uid"])
    templates.add(t)
    if t not in types:
        err(f"{where}: instance of unknown type {t}{closest(t or '', types)}")
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
            world_types.add(inst.get("type"))
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


def check_namespace(obj: str) -> None:
    """`Enemy.Angle` has to mean one thing, so the editor refuses an instance
    variable, behavior or effect named like another one on the object or its
    families, or like an expression of the plugin. Names compare without case."""
    declared: dict[str, str] = {}
    for owner in [obj] + families_of(obj):
        d = types.get(owner) or families.get(owner) or {}
        entries = ([("instance variable", v["name"]) for v in d.get("instanceVariables", [])]
                   + [("behavior", b["name"]) for b in d.get("behaviorTypes", [])]
                   + [("effect", e["name"]) for e in d.get("effectTypes", []) if "name" in e])
        for what, name in entries:
            label = f"{what} {name}" + (f" of family {owner}" if owner != obj else "")
            if LOWER(name) in declared:
                err(f"{obj}: {label} has the same name as {declared[LOWER(name)]}")
            declared[LOWER(name)] = label
    plugin = schema("plugins", plugin_of[obj])
    expressions = {LOWER(e["translated-name"]) for e in (plugin or {}).get("expressions", [])}
    members = families[obj].get("members", []) if obj in families else [obj]
    if any(m in world_types for m in members):
        expressions |= COMMON_EXPRESSIONS
    for key, label in declared.items():
        if key in expressions and " of family " not in label:
            err(f"{obj}: {label} collides with the expression {obj}.{key}; rename it")


for obj in list(types) + list(families):
    check_namespace(obj)

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
            # JSON.Get names the plugin; an expression is reached through the project's object of it.
            users = [n for n, p in plugin_of.items() if squash(p) == squash(m.group(1)) and p != "system"]
            hint = f"; {m.group(1)} is the plugin, the object of it here is {', '.join(users)}" if users \
                else closest(m.group(1), plugin_of)
            err(f"{where}: unknown object {m.group(1)} in expression{hint}")
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
            # Platform.Speed is reached as Player.Platform.Speed, through the behavior's name on the object.
            owner = next((name for name, b in behaviors_of(obj).items() if LOWER(member) in
                          {LOWER(e["translated-name"]) for e in (schema("behaviors", b) or {}).get("expressions", [])}), None)
            hint = f"; it is an expression of a behavior: {obj}.{owner}.{member}" if owner else closest(member, known)
            err(f"{where}: {obj}.{member} is neither an expression nor an instance variable of {obj}{hint}")
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
        hint = closest(name, list(scope) + list(plugin_of))
        if LOWER(name) in objects_lower:
            hint = f"; {objects_lower[LOWER(name)]} is an object, write {objects_lower[LOWER(name)]}.<expression>"
        elif text.strip() == name:
            hint += f"; a text value carries inner quotes: \"\\\"{name}\\\"\""
        err(f"{where}: identifier {name!r} is not a variable, parameter or system expression{hint}")


def bare(value, options) -> str:
    """A combo item, a layout, an object and a variable are written bare; only an
    expression carries quotes. Says so when stripping the quotes gives a match."""
    if isinstance(value, str) and len(value) > 1 and value[0] == value[-1] == '"' and value[1:-1] in options:
        return f"; write it bare, \"{value[1:-1]}\": only an expression parameter carries inner quotes"
    return ""


_eases: set[str] = set()


def builtin_eases() -> set[str]:
    """Ids of the built-in eases, the keys the editor's language pack labels."""
    if not _eases:
        pack = RAG / "data" / "c3-lang" / "en-US.json"
        if pack.exists():
            _eases.update(load(pack)["text"]["ui"]["bars"]["timeline"]["eases"])
    return _eases


def check_param(where: str, key: str, value, ptype: str, items: dict | None, obj: str, scope: dict,
                writes: bool = False) -> None:
    """writes: the parameter belongs to an action, which assigns the variable it names."""
    if ptype == "cmp":
        if value not in (0, 1, 2, 3, 4, 5) or isinstance(value, bool):
            err(f"{where}: comparison {value!r} is not an integer 0-5 (=, ≠, <, ≤, >, ≥)")
    elif ptype == "boolean":
        if not isinstance(value, bool):
            err(f"{where}: {key} should be a JSON boolean, not {value!r}")
    elif ptype in ("combo", "combo-grouped"):
        if items and value not in items:
            err(f"{where}: {key}={value!r} is not one of {list(items)}{bare(value, items)}")
    elif ptype == "keyb":
        if not isinstance(value, int) or isinstance(value, bool):
            err(f"{where}: {key}={value!r} should be a key code, a JSON number such as 32 for Space or 37-40 "
                f"for the arrows; the editor stops with 'expected finite number'")
    elif ptype == "ease":
        eases = builtin_eases()
        if isinstance(value, str) and eases and value not in eases and not project.get("eases"):
            err(f"{where}: {key}={value!r} is not a built-in ease{closest(value, eases)}")
    elif ptype in ("audiofile", "tilemapbrush", "function", "model3d", "template", "objecteffect"):
        return
    elif ptype == "object":
        if value not in plugin_of or value == "System":
            err(f"{where}: {key}={value!r} is not an object type or family"
                + (bare(value, plugin_of) or closest(value, plugin_of)))
    elif ptype in ("instancevar", "instancevarbool"):
        # shared ACEs name one of the object's own variables
        ivars = ivar_types_of(obj)
        if value not in ivars:
            err(f"{where}: {obj} has no instance variable {value!r}{bare(value, ivars) or closest(value, ivars)}")
        elif ptype == "instancevarbool" and ivars[value] != "boolean":
            err(f"{where}: instance variable {value!r} is not a boolean")
    elif ptype == "objinstancevar":
        target, ivar = (value.get("objectClass", obj), value.get("name")) if isinstance(value, dict) else (obj, value)
        if ivar not in ivars_of(target):
            err(f"{where}: {target} has no instance variable {ivar!r}{closest(ivar or '', ivars_of(target))}")
    elif ptype in ("eventvar", "eventvarbool", "eventvarany"):
        if value not in scope:
            err(f"{where}: variable {value!r} is not in scope{bare(value, scope) or closest(value, scope)}")
        elif ptype == "eventvarbool" and scope[value]["type"] != "boolean":
            err(f"{where}: variable {value!r} is not a boolean")
        elif writes and scope[value].get("isConstant"):
            err(f"{where}: {value} is a constant and an action cannot change it; "
                f"the editor stops with 'event variable {value} is constant'")
    elif ptype == "layer":
        if is_literal(value):
            if unquote(value) not in layers:
                err(f"{where}: no layer named {unquote(value)!r} in any layout")
        else:
            check_expr(f"{where} {key}", value, scope)
    elif ptype == "layout":
        if value not in layouts:
            err(f"{where}: no layout named {value!r}{bare(value, layouts) or closest(value, layouts)}")
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


def ace_sources(ace: dict) -> list[dict]:
    """The schemas an ACE is looked up in: the named behavior's, or the plugin's
    and then the shared world-object one. Empty when the object, the behavior or
    its schema is unknown."""
    obj = ace.get("objectClass")
    if obj not in plugin_of:
        return []
    if "behaviorType" in ace:
        behavior_id = behaviors_of(obj).get(ace["behaviorType"])
        own = schema("behaviors", behavior_id) if behavior_id else None
        return [own] if own else []
    own = schema("plugins", plugin_of[obj])
    if own is None:
        return []       # a third-party plugin: its own ACEs cannot be told from a wrong id
    return [own] if obj == "System" else [own, COMMON]


def ace_entry(kind: str, ace: dict) -> dict | None:
    return next((it for s in ace_sources(ace) for it in s.get(kind, []) if it["id"] == ace.get("id")), None)


def ace_hint(kind: str, ace: dict) -> str:
    """Where an id the schema does not have under this object does exist: on one
    of its behaviors, on the object itself, as the other kind, or under a near
    spelling (the script name and the list name are tried as well as the id)."""
    obj, ace_id = ace["objectClass"], ace["id"]
    if "behaviorType" not in ace:
        for name, behavior_id in behaviors_of(obj).items():
            s = schema("behaviors", behavior_id)
            if s and any(it["id"] == ace_id for it in s.get(kind, [])):
                return f"; it belongs to the behavior {name}: add \"behaviorType\": \"{name}\""
    elif any(it["id"] == ace_id for s in ace_sources({"objectClass": obj}) for it in s.get(kind, [])):
        return "; it belongs to the object itself: remove \"behaviorType\""
    sources = ace_sources(ace)
    other = "actions" if kind == "conditions" else "conditions"
    if any(it["id"] == ace_id for s in sources for it in s.get(other, [])):
        return f"; {ace_id} is one of its {other}, not its {kind}"
    spellings = {}
    for s in sources:
        for it in s.get(kind, []):
            for text in (it["id"], it.get("scriptName", ""), it.get("list-name", "")):
                spellings.setdefault(squash(text), it["id"])
    if squash(ace_id) in spellings:
        return f"; the id is {spellings[squash(ace_id)]!r}"
    near = difflib.get_close_matches(squash(ace_id), list(spellings), n=4, cutoff=0.6)
    ids = list(dict.fromkeys(spellings[n] for n in near))[:3]
    return "; closest: " + ", ".join(ids) if ids else ""


def check_ace(kind: str, ace: dict, scope: dict, where: str) -> None:
    obj = ace.get("objectClass")
    ace_id = ace.get("id")
    params = ace.get("parameters", {})
    where = f"{where} {obj}:{ace_id}"
    if obj is None or ace_id is None:
        err(f"{where}: a {kind[:-1]} needs \"objectClass\" and \"id\"")
        return
    if obj not in plugin_of:
        err(f"{where}: unknown object {obj}{closest(obj, plugin_of)}")
        return
    if "behaviorType" in ace and ace["behaviorType"] not in behaviors_of(obj):
        err(f"{where}: {obj} has no behavior {ace['behaviorType']}{closest(ace['behaviorType'], behaviors_of(obj))}; "
            f"\"behaviorType\" is the name the behavior has on the object, not its id")
        return
    if not ace_sources(ace):
        return      # no schema for this addon: warned about once, nothing to check against
    entry = ace_entry(kind, ace)
    if entry is None:
        owner = behaviors_of(obj)[ace["behaviorType"]] if "behaviorType" in ace else plugin_of[obj]
        err(f"{where}: {owner} has no {kind[:-1]} {ace_id}"
            + ("" if "behaviorType" in ace or obj == "System" else " (not in _common either)") + ace_hint(kind, ace))
        return
    schema_params = entry.get("params") or {}
    if not isinstance(params, dict):
        err(f"{where}: \"parameters\" should be an object keyed by parameter id: {', '.join(schema_params) or 'none here'}")
        return
    for k in params:
        if k not in schema_params:
            err(f"{where}: unknown parameter {k}; the parameters are: {', '.join(schema_params) or 'none'}")
    for k in schema_params:
        if k not in params:
            warn(f"{where}: parameter {k} is omitted; the editor fills its default")
    for k, v in params.items():
        if k not in schema_params:
            continue
        check_param(where, k, v, schema_params[k]["type"], schema_params[k].get("items"), obj, scope,
                    writes=kind == "actions")
    if ace_id == "create-object" and obj == "System":
        created.add(params.get("object-to-create"))
    if ace_id == "set-eventvar-value" and (scope.get(params.get("variable")) or {}).get("type") == "boolean":
        err(f"{where}: Set value on boolean {params['variable']}; use Set boolean")


def describe(cond: dict) -> str:
    return f"{cond.get('objectClass')}:{cond.get('id')}"


class Holder(NamedTuple):
    """What holds the trigger of an event branch."""
    name: str       # "Touch:on-touched-object", or "the function AddScore"
    fires: bool     # a trigger condition, as opposed to a function standing in for one

    @property
    def text(self) -> str:
        return f"an event that already has the trigger {self.name}" if self.fires \
            else f"{self.name}, which counts as a trigger"


def check_structure(ev: dict, where: str, above: Holder | None, previous: dict | None) -> Holder | None:
    """Where a condition may stand. These are the editor's own rules, the first
    three applied as it opens the project and the fourth before every preview:
    an event branch, from the top-level event down to a leaf, holds one trigger,
    and a function or a custom action counts as one (only an OR block lists
    several); a trigger, a loop and a condition the schema marks
    isInvertible: false cannot be inverted; a function cannot be an OR block;
    Else is the first condition of an event that directly follows a plain event.

    above is the holder of the branch's trigger so far, previous the sibling
    before this event with comments skipped. Returns the holder for the
    sub-events: above, or this event if it brings the trigger."""
    conds = [c for c in ev.get("conditions", []) if "id" in c]
    entries = [ace_entry("conditions", c) or {} for c in conds]
    is_function = ev.get("eventType") != "block"
    triggers = [c for c, e in zip(conds, entries) if e.get("isTrigger")]
    if is_function and ev.get("isOrBlock"):
        err(f"{where}: a function or custom action cannot be an OR block")
    if triggers and (above or is_function):
        holder = above.text if above else "a function or custom action, which counts as a trigger"
        err(f"{where}: {describe(triggers[0])} is a trigger inside {holder}; the editor stops with 'cannot add "
            f"another trigger to event branch'. Move it to an event of its own, outside, and test the rest in sub-events")
    elif len(triggers) > 1 and not ev.get("isOrBlock"):
        err(f"{where}: {' and '.join(describe(c) for c in triggers)} are two triggers in one event; the editor "
            f"stops with 'cannot add another trigger to event branch'. One event per trigger, or an OR block")
    for c, e in zip(conds, entries):
        if c.get("isInverted") and (e.get("isTrigger") or e.get("isLooping") or e.get("isInvertible") is False):
            kind = "a trigger" if e.get("isTrigger") else "a loop" if e.get("isLooping") else "this condition"
            err(f"{where}: {describe(c)} is inverted, and {kind} cannot be; "
                f"the editor stops with 'condition not invertible'")
        # Trigger once, Every X seconds: the editor keeps them out of a triggered branch, where they
        # are tested only in the tick the trigger fires. Else has its own rule below.
        if e.get("isCompatibleWithTriggers") is False and c["id"] != "else" and (triggers or (above and above.fires)):
            warn(f"{where}: {describe(c)} is in a branch run by the trigger "
                 f"{describe(triggers[0]) if triggers else above.name}; the editor does not offer it there, "
                 f"since it is only tested when the trigger fires")
    for i, c in enumerate(conds):
        if c.get("objectClass") != "System" or c["id"] != "else":
            continue
        problem = None
        before = [p for p in (previous or {}).get("conditions", []) if "id" in p]
        flags = [ace_entry("conditions", p) or {} for p in before]
        if ev.get("isOrBlock") or is_function:
            problem = "its event is " + ("an OR block" if ev.get("isOrBlock") else "a function")
        elif triggers:
            problem = f"its event has the trigger {describe(triggers[0])}"
        elif i != 0:
            problem = "it is not the first condition of its event"
        elif previous is None or previous.get("eventType") != "block":
            problem = "it is the first event of its list" if previous is None else \
                f"it follows a {previous.get('eventType')}, and only comments may stand between it and the event it answers"
        elif len(before) == 1 and describe(before[0]) == "System:else":
            problem = "it follows an event whose only condition is Else"
        elif any(f.get("isTrigger") for f in flags):
            problem = "it follows a triggered event"
        elif any(f.get("isLooping") for f in flags):
            problem = "it follows a loop"
        if problem:
            err(f"{where}: Else cannot stand here, {problem}; the editor refuses to preview ('An Else condition "
                f"cannot be placed here'). Use a second event with the inverted condition")
    if above:
        return above
    if is_function:
        kind = "function" if ev.get("eventType") == "function-block" else "custom action"
        return Holder(f"the {kind} {ev.get('functionName') or ev.get('aceName')}", False)
    return Holder(describe(triggers[0]), True) if triggers else None


def check_block(ev: dict, scope: dict, where: str) -> None:
    for i, c in enumerate(ev.get("conditions", []), 1):
        check_ace("conditions", c, scope, f"{where} condition {i}")
    for i, a in enumerate(ev.get("actions", []), 1):
        w = f"{where} action {i}"
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


# The editor numbers these in document order, sub-events included, one
# sequence per sheet. A variable, comment or include takes no number of its
# own: the margin leaves it blank and Find files it under the next numbered
# event, so every row's number is the count of numbered rows before it plus one.
NUMBERED = ("block", "group", "function-block", "custom-ace-block", "script")


def walk(events: list, scope: dict, where: str, counter: list[int], above: Holder | None = None) -> None:
    """A local declared in a list of sibling events is visible to every event of
    that list, whatever the order, and to their sub-events; not to the parent's
    own actions. So the list's variables enter the scope first, and a block is
    checked before its children are walked. scope maps a name to the variable
    event or function parameter that declares it. counter holds the sheet's
    running event number, above what holds the trigger of this branch."""
    scope = dict(scope)
    for ev in events:
        if ev.get("eventType") == "variable":
            scope[ev["name"]] = ev
    previous = None
    for ev in events:
        et = ev.get("eventType")
        if et in NUMBERED:
            counter[0] += 1
        w = f"{where} event {counter[0] + (et not in NUMBERED)} (sid {ev.get('sid', '?')})"
        if et == "variable":
            pass
        elif et in ("comment", "include"):
            if et == "include" and ev["includeSheet"] not in sheets:
                err(f"{w}: included sheet {ev['includeSheet']} does not exist{closest(ev['includeSheet'], sheets)}")
            elif et == "include" and where == f"sheet {ev['includeSheet']}":
                err(f"{w}: a sheet cannot include itself")
        elif et == "group":
            walk(ev["children"], scope, where, counter, above)
        elif et in ("function-block", "custom-ace-block"):
            fscope = dict(scope)
            for p in ev["functionParameters"]:
                fscope[p["name"]] = p
            label = ev.get("functionName") or f"{ev['objectClass']}.{ev['aceName']}"
            if et == "custom-ace-block" and ev["objectClass"] not in plugin_of:
                err(f"{w}: custom action {label} belongs to unknown object {ev['objectClass']}")
            check_block(ev, fscope, f"{w} {label}")
            walk(ev.get("children", []), fscope, where, counter, check_structure(ev, f"{w} {label}", above, previous))
        elif et == "block":
            check_block(ev, scope, w)
            walk(ev.get("children", []), scope, where, counter, check_structure(ev, w, above, previous))
        elif et != "script":
            err(f"{w}: unknown eventType {et!r}; the editor knows block, group, variable, comment, include, "
                f"function-block, custom-ace-block and script")
        if et != "comment":
            previous = ev


def outline(events: list, counter: list[int], depth: int = 0) -> None:
    for ev in events:
        et = ev.get("eventType")
        if et == "variable":
            text = f"{ev['type']} {ev['name']} = {ev.get('initialValue', '')!s}"
        elif et == "comment":
            text = "// " + ev.get("text", "").split("\n")[0]
        elif et == "group":
            text = f"group {ev.get('title', '')}"
        elif et == "include":
            text = f"include {ev.get('includeSheet', '')}"
        elif et in ("function-block", "custom-ace-block"):
            text = "function " + (ev.get("functionName") or f"{ev['objectClass']}.{ev['aceName']}")
        elif et == "script":
            text = "script"
        else:
            conds = ev.get("conditions", [])
            text = "; ".join(describe(c) for c in conds) or "(no condition)"
        sid = f"  [sid {ev['sid']}]" if "sid" in ev else ""
        if et in NUMBERED:
            counter[0] += 1
            print(f"{counter[0]:>4} {'  ' * depth}{text}{sid}")
        else:
            print(f"{f'({counter[0] + 1})':>6} {'  ' * depth}{text}{sid}")
        outline(ev.get("children", []), counter, depth + 1)


COMPARISONS = ("=", "≠", "<", "≤", ">", "≥")


def wording(kind: str, ace: dict) -> str:
    """A condition or action as the event sheet words it: the schema's
    display-text with the parameters in place, in the locale of --locale."""
    obj = ace.get("objectClass", "?")
    args_ = ace.get("parameters", [])
    if "callFunction" in ace:
        return f"Functions: Call {ace['callFunction']}({', '.join(map(str, args_))})"
    if "customAction" in ace:
        return f"{obj}: {ace['customAction']}({', '.join(map(str, args_))})"
    if ace.get("type") == "comment":
        return "// " + str(ace.get("text", "")).split("\n")[0]
    if ace.get("type") == "script":
        return f"script, {len(ace.get('script', []))} lines"
    params = args_ if isinstance(args_, dict) else {}
    entry = ace_entry(kind, ace) if obj in plugin_of else None
    if not entry or not entry.get("display-text"):
        text = f"{ace.get('id')} ({', '.join(f'{k}: {v}' for k, v in params.items())})"
    else:
        shown = []
        for key, spec in (entry.get("params") or {}).items():
            value = params.get(key, "…")
            if spec["type"] == "cmp" and value in range(6):
                value = COMPARISONS[value]
            elif spec.get("items") and value in spec["items"]:
                value = spec["items"][value]
            shown.append(str(value))
        text = re.sub(r"\[/?[bi]\]", "", entry["display-text"]).replace("{my}", ace.get("behaviorType", ""))
        text = re.sub(r"\{(\d+)\}", lambda m: shown[int(m.group(1))] if int(m.group(1)) < len(shown) else "…", text)
    return f"{obj}: {'NOT ' if ace.get('isInverted') else ''}{text}"


def print_sheet(events: list, counter: list[int], depth: int = 0, top: bool = True) -> None:
    """The sheet as the editor shows it, with the editor's event numbers."""
    for ev in events:
        et = ev.get("eventType")
        pad = "  " * depth
        if et in NUMBERED:
            counter[0] += 1
        number = f"{counter[0]:>4} " if et in NUMBERED else "     "
        if et == "variable":
            kind = ("global" if top else "local") + (" constant" if ev.get("isConstant") else "") \
                   + (" static" if ev.get("isStatic") else "")
            print(f"{number}{pad}{kind} {ev['type']} {ev['name']} = {ev.get('initialValue', '')}")
        elif et == "comment":
            print(f"{number}{pad}// " + ev.get("text", "").replace("\n", f"\n{number}{pad}// "))
        elif et == "include":
            print(f"{number}{pad}include {ev.get('includeSheet', '')}")
        elif et == "script":
            print(f"{number}{pad}script, {len(ev.get('script', []))} lines")
        elif et == "group":
            print(f"{number}{pad}group {ev.get('title', '')}"
                  + ("" if ev.get("isActiveOnStart", True) else " (inactive on start)"))
        else:
            head = []
            if et in ("function-block", "custom-ace-block"):
                name = ev.get("functionName") or f"{ev.get('objectClass')}.{ev.get('aceName')}"
                params = ", ".join(f"{p['name']}: {p['type']}" for p in ev.get("functionParameters", []))
                returns = ev.get("functionReturnType", "none")
                head.append(f"{'function' if et == 'function-block' else 'custom action'} {name}({params})"
                            + (f" -> {returns}" if returns != "none" else "")
                            + (" [copy picked]" if ev.get("functionCopyPicked") else ""))
            head += [wording("conditions", c) for c in ev.get("conditions", [])]
            joiner = "OR " if ev.get("isOrBlock") else ""
            for i, line in enumerate(head or ["(every tick)"]):
                print(f"{number if i == 0 else '     '}{pad}{joiner if i else ''}{line}"
                      + (" [disabled]" if ev.get("disabled") and i == 0 else ""))
            for a in ev.get("actions", []):
                print(f"     {pad}    -> {wording('actions', a)}")
        print_sheet(ev.get("children", []), counter, depth + 1, top=False)


for flag, printer in ((args.outline, outline), (args.print, print_sheet)):
    if flag:
        wanted = sheets if flag == "*" else {flag: sheets.get(flag)}
        for sname, sheet in wanted.items():
            if sheet is None:
                sys.exit(f"no event sheet named {flag!r}; sheets: {', '.join(sheets)}")
            print(f"== {sname}")
            printer(sheet["events"], [0])
        sys.exit(0)

# A global declared at the top level of any sheet is visible from every sheet.
globals_ = {ev["name"]: ev for s in sheets.values() for ev in s["events"] if ev.get("eventType") == "variable"}
for sname, sheet in sheets.items():
    walk(sheet["events"], globals_, f"sheet {sname}", [0])

for kind, name, owner, nparams, where in pending_calls:
    if kind == "function":
        if name not in functions:
            err(f"{where}: call to undefined function {name}{closest(name, functions)}")
        elif functions[name] != nparams:
            err(f"{where}: {name} called with {nparams} parameters, defined with {functions[name]}")
    else:
        owners = [owner] + families_of(owner)
        hit = next(((o, name) for o in owners if (o, name) in custom_actions), None)
        if hit is None:
            err(f"{where}: {owner} has no custom action {name!r}"
                + closest(name, [n for o, n in custom_actions if o in owners]))
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
