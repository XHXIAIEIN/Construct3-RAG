"""Static checks for a Construct 3 folder project, run without the editor.

    python scripts/check_project.py [--project FOLDER] [--rag FOLDER] [--locale en-US]

Reads project.c3proj and every object type, family, layout and event sheet it
lists, and checks them against the schemas in Construct3-RAG and against the
rules the editor applies when it opens or previews a project. What is
checked, and where each rule comes from: references/checker-rules.md.

It cannot run the events: picking, timing and the meaning of an expression
are the editor's and the preview's to judge.

Findings in event sheets are placed as `sheet Game event 15 action 2`, the
number the editor prints in the margin; print_sheet.py prints that numbering.
Under --limit the findings that fit are printed and the rest counted; the
last line, `ok:` or the number of problems, always prints.

Exit 0: no errors; warnings do not fail the run. Exit 1: findings, or the
project or the clone was not found. Exit 2: a project file lacks a key the
editor always writes, and the run stopped there.
"""
import difflib
import json
import math
import re
import sys
import unicodedata
from pathlib import Path
from typing import NamedTuple

import c3project as c3
from c3project import LOWER, NUMBERED, closest, describe, folder_items, squash

try:
    from PIL import Image
except ImportError:
    Image = None

# Names. The editor passes every name through a filter when it opens the
# project and keeps the result, so a name the filter changes no longer matches
# the events that use it; and it refuses a name that is reserved or already
# taken in the object's namespace, where instance variables, behaviors, effects
# and the plugin's expressions live side by side, compared without case.
NAME_DROPS = set(".。,，\"“”(（)）?？:：\\/;*|'-`!¬£$%^&+=<>{}[]@#~­​")
VARIABLE_TYPES = ("number", "string", "boolean")
# how a layout instance writes the value of an instance variable of each type
JSON_TYPES = {"number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
              "string": lambda v: isinstance(v, str), "boolean": lambda v: isinstance(v, bool)}
JSON_EXAMPLES = {"number": "a number such as 1", "string": "text such as \"a\"", "boolean": "true or false"}
FULL_TURN = 2 * math.pi + 1e-6      # the largest world angle the official examples hold is 2π
RESERVED_NAMES = {"self", "true", "false", "system", "con", "prn", "aux", "nul",
                  *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}

# project.c3proj. Opening a project reads the whole properties block before it
# reads a single file of the project, and each of these is asserted as it is
# read: a missing one throws "TypeError: expected string" and a wrong one names
# the property. The value sets are the editor's; the defaults are what it
# writes into a new project.
PROJECT_TEXT = {"description": "", "version": "1.0.0.0", "author": "", "authorEmail": "",
                "authorWebsite": "", "appId": ""}
PROJECT_OPTIONS = {"fullscreenMode": ("letterbox-scale", "letterbox-integer-scale", "scale-inner",
                                      "integer-scale-inner", "scale-outer", "integer-scale-outer", "off"),
                   "fullscreenQuality": ("high", "low"),
                   "orientations": ("any", "portrait", "landscape"),
                   "sampling": ("trilinear", "bilinear", "nearest"),
                   "downscaling": ("medium", "low", "high"),
                   "loaderStyle": ("splash", "progress-logo", "progress", "percent", "none")}
PROJECT_ALSO = {"sampling": ("linear", "point")}    # older ids the editor maps as it reads them
# Below this release the editor reads an object type from objectTypes\<name in
# lower case>.json, the layout of a project from 2016, and finds nothing.
FOLDER_PROJECT_RELEASE = 30900

# Object and behavior names may start with a digit (3DCamera, 8Direction), so a
# token is any run of word characters and numeric literals are skipped by value.
# Sprite(2).X picks an instance by IID; the index is checked as an expression.
IDENT = re.compile(r"[A-Za-z0-9_]+")
NUMBER = re.compile(r"\d+(\.\d+)?(e[+-]?\d+)?", re.I)
MEMBER = re.compile(r"([A-Za-z0-9_]+)(?:\([^()]*\))?\s*\.\s*([A-Za-z0-9_]+)(?:\s*\.\s*([A-Za-z0-9_]+))?")
STRING_LITERAL = re.compile(r'"(?:[^"]|"")*"')


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


def is_literal(v) -> bool:
    return isinstance(v, str) and re.fullmatch(r'"(?:[^"]|"")*"', v) is not None


def unquote(v: str) -> str:
    return v[1:-1].replace('""', '"')


def bare(value, options) -> str:
    """A combo item, a layout, an object and a variable are written bare; only an
    expression carries quotes. Says so when stripping the quotes gives a match."""
    if isinstance(value, str) and len(value) > 1 and value[0] == value[-1] == '"' and value[1:-1] in options:
        return f"; write it bare, \"{value[1:-1]}\": only an expression parameter carries inner quotes"
    return ""


def frames_of(folder, prefix=""):
    for anim in folder.get("items", []):
        for i, fr in enumerate(anim["frames"]):
            yield f"{prefix}{anim['name'].lower()}-{i:03d}.png", fr
    for sub in folder.get("subfolders", []):
        yield from frames_of(sub, prefix)


STYLE_RUN = 8      # actions in a row without a comment action
STYLE_TREE = 3     # sub-event levels below an event, when every leaf calls the same function
STYLE_LADDER = 5   # sibling events of one shape, their conditions and actions the same, only the values differ


class Holder(NamedTuple):
    """What holds the trigger of an event branch."""
    name: str       # "Touch:on-touched-object", or "the function AddScore"
    fires: bool     # a trigger condition, as opposed to a function standing in for one

    @property
    def text(self) -> str:
        return f"an event that already has the trigger {self.name}" if self.fires \
            else f"{self.name}, which counts as a trigger"


class Checker:
    """The checks in the order run() calls them. A later one reads what an
    earlier one collected: the layers and template instances of the layouts,
    the functions and groups of every sheet."""

    def __init__(self, p: c3.Project, limit: int = 0, sheets: dict[str, dict] | None = None,
                 style: bool = False) -> None:
        self.p = p
        self.limit = limit
        self.unsaved = sheets or {}     # edit_sheet.py checks a sheet before it writes it
        self.style = style              # the three readability warnings of check_style, off unless asked
        self.err, self.warn = p.err, p.warn
        self.layouts: dict[str, dict] = {}
        self.sheets: dict[str, dict] = {}
        self.layers: set[str] = set()
        self.templates: set[str] = set()      # types with an instance in some layout
        self.world_types: set[str] = set()    # types with an instance on a layer: they have X, Width, Angle ...
        self.uids: list[int] = []
        self.sids: list[int] = []        # sids of events, variables, object types, instances, files
        self.ace_sids: list[int] = []    # sids of condition and action entries; the editor tolerates repeats here
        self.group_titles: set[str] = set()
        self.functions: dict[str, int] = {}                     # name -> parameter count
        self.custom_actions: dict[tuple[str, str], int] = {}    # (owner, name) -> parameter count
        self.pending_calls: list[tuple] = []
        self.created: set[str] = set()
        self._eases: set[str] = set()

    def check(self) -> None:
        self.check_project_file()
        self.check_names()
        self.check_images()
        self.check_layouts()
        for obj in list(self.p.types) + list(self.p.families):
            self.check_namespace(obj)
        self.check_sheets()
        self.check_calls()
        self.check_uniqueness()
        self.check_files_and_addons()

    def run(self) -> int:
        self.check()
        return self.report()

    # --- project.c3proj -----------------------------------------------------------------
    def check_project_file(self) -> None:
        """What the editor reads before it opens a single file of the project. A
        hand-written project.c3proj that keeps only the keys the tools read opens
        as `TypeError: expected string`, a message that names neither the key nor
        the file; the editor writes all of these into every project it saves."""
        data = self.p.data
        props = data.get("properties")
        if not isinstance(props, dict):
            self.err("project.c3proj: no \"properties\" block; copy the one from a project the editor saved, "
                     "or from an empty project of the Construct3-New-project clone")
            props = {}
        missing = [k for k in PROJECT_TEXT if not isinstance(props.get(k), str)]
        if missing:
            written = ", ".join(f'"{k}": {json.dumps(PROJECT_TEXT[k])}' for k in missing)
            self.err(f"project.c3proj properties: {', '.join(missing)} "
                     f"{'is' if len(missing) == 1 else 'are'} missing or not text; the editor reads every "
                     f"property as it opens the project and stops with \"TypeError: expected string\" before "
                     f"it names a file. Write {written}")
        for key, options in PROJECT_OPTIONS.items():
            value = props.get(key)
            if value is None:
                rest = ", ".join(options[1:])
                self.err(f"project.c3proj properties: no \"{key}\"; the editor reads it on open and stops. "
                         f"Write \"{key}\": \"{options[0]}\", or "
                         f"{rest if len(options) == 2 else 'one of ' + rest}")
            elif value not in options and value not in PROJECT_ALSO.get(key, ()):
                self.err(f"project.c3proj properties: {key} {value!r} is not one of "
                         f"{', '.join(options)}; the editor stops with \"invalid {key}\"")
        for key in ("viewportWidth", "viewportHeight"):
            value = data.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 2:
                self.err(f"project.c3proj: {key} is {value!r}; the editor reads it as a number of at least 2 "
                         f"and stops with \"invalid {'viewport width' if key.endswith('Width') else 'viewport height'}\"")
        self.check_project_index()
        fmt = data.get("projectFormatVersion")
        if fmt is not None and (not isinstance(fmt, int) or fmt > 1):
            self.err(f"project.c3proj: projectFormatVersion is {fmt!r}; the editor refuses anything above 1 with "
                     f"\"project from a future version of C3\". Write \"projectFormatVersion\": 1")
        self.check_saved_with_release()

    def check_project_index(self) -> None:
        """The lists project.c3proj keeps of what the project holds. The editor
        walks each one's items and subfolders as it opens, and reads containers as
        an array before it has read a file, so a list that is missing rather than
        empty stops the open with a type and nothing else."""
        data = self.p.data
        for key in ("objectTypes", "families", "layouts", "eventSheets"):
            block = data.get(key)
            if not isinstance(block, dict):
                folder = self.p.root / key
                found = sorted(f.stem for f in folder.glob("*.json")) if folder.is_dir() else []
                self.err(f"project.c3proj: no \"{key}\"; the editor reads the list before it reads a file and "
                         f"stops with \"TypeError: expected object\". Write \"{key}\": "
                         f"{{\"items\": {json.dumps(found)}, \"subfolders\": []}}")
                continue
            for part in ("items", "subfolders"):
                if not isinstance(block.get(part), list):
                    self.err(f"project.c3proj {key}: {part} is {block.get(part)!r}; the editor walks both lists "
                             f"as it opens the project. Write \"{part}\": []")
        if not isinstance(data.get("containers"), list):
            self.err(f"project.c3proj: containers is {data.get('containers')!r}; the editor reads it as an array "
                     f"before it has read a file and stops with \"TypeError: expected array\". A project with no "
                     f"container writes \"containers\": []")

    def check_saved_with_release(self) -> None:
        """The release decides where the editor looks for an object type: under
        r309 it reads objectTypes\\<name in lower case>.json, the layout of a
        project from 2016, and a project without the key is read as r86."""
        release = self.p.data.get("savedWithRelease")
        if not isinstance(release, int) or isinstance(release, bool):
            self.err(f"project.c3proj: savedWithRelease is {release!r}; without the release the editor reads the "
                     f"project as r86 and looks for objectTypes\\{'coin' if 'Coin' in self.p.types else 'name'}"
                     f".json in lower case. Write \"savedWithRelease\": 49502, or the release the editor that "
                     f"saved the project shows; a release newer than the editor opening it asks the user first")
            return
        if release < FOLDER_PROJECT_RELEASE:
            # by the name the folder holds, not by Path.exists(): a Windows file
            # system answers for Coin.json when the editor asks for coin.json
            folder = self.p.root / "objectTypes"
            have = {f.name for f in folder.glob("*.json")} if folder.is_dir() else set()
            wrong = [n for n in self.p.types if f"{n.lower()}.json" not in have]
            if wrong:
                self.err(f"project.c3proj: savedWithRelease {release} is below r309, so the editor reads an object "
                         f"type from objectTypes/<name in lower case>.json; {', '.join(sorted(wrong)[:3])} "
                         f"{'has' if len(wrong) == 1 else 'have'} no such file. Write the release that saved the "
                         f"project, for example \"savedWithRelease\": 49502")

    # --- names, addon ids, families -----------------------------------------------------
    def check_name(self, where: str, what: str, name: str, is_object: bool) -> None:
        kept = editor_name(name, is_object)
        if kept != name:
            self.err(f"{where}: the editor does not keep the {what} name {name!r} as written"
                     + (f", it becomes {kept!r}" if kept else "")
                     + "; use letters, digits and underscores, starting with a letter")

    def check_addon_id(self, kind: str, addon_id: str, where: str) -> None:
        """The editor looks an addon up by its exact id, so 'sprite' or 'Tiledbg'
        fails to open even though the schema file is found case-insensitively."""
        exact = self.p.index.get(kind, {}).get(addon_id.lower(), {}).get("originalId")
        if exact and exact != addon_id:
            self.err(f"{where}: {kind[:-1]} id {addon_id!r} must be written {exact!r}; addon ids are case-sensitive")

    def check_names(self) -> None:
        p = self.p
        for kind, listed in (("object type", p.types), ("family", p.families)):
            for name, t in listed.items():
                if t.get("name") != name:
                    self.err(f"{kind} {name}: the file says \"name\": {t.get('name')!r}; "
                             f"it must be the name listed in project.c3proj")
                self.check_name(f"{kind} {name}", kind, name, True)
                if LOWER(name) in RESERVED_NAMES or LOWER(name) in p.system_expression_names:
                    self.err(f"{kind} {name}: the name is reserved ({LOWER(name)} is a keyword or a system "
                             f"expression); rename it, for example {name}Object")
                self.check_addon_id("plugins", t["plugin-id"], f"{kind} {name}")
                for b in t.get("behaviorTypes", []):
                    self.check_addon_id("behaviors", b["behaviorId"], f"{kind} {name} behavior {b['name']}")
                    self.check_name(f"{kind} {name}", "behavior", b["name"], True)
                for v in t.get("instanceVariables", []):
                    self.check_name(f"{kind} {name}", "instance variable", v["name"], False)
                    if v.get("type") not in VARIABLE_TYPES:
                        self.err(f"{kind} {name}: instance variable {v['name']}: type {v.get('type')!r} is not "
                                 f"number, string or boolean; the editor's Text type is written \"string\"")
        for a in p.data.get("usedAddons", []):
            if a.get("type") in ("plugin", "behavior"):
                self.check_addon_id(a["type"] + "s", a["id"], "project.c3proj usedAddons")

        for name, t in p.types.items():
            p.schema("plugins", t["plugin-id"])
            for b in t.get("behaviorTypes", []):
                p.schema("behaviors", b["behaviorId"])
        for fam, f in p.families.items():
            p.schema("plugins", f["plugin-id"])
            for b in f.get("behaviorTypes", []):
                p.schema("behaviors", b["behaviorId"])
            for m in f.get("members", []):
                if m not in p.types:
                    self.err(f"family {fam}: member {m} is not an object type")
                elif p.types[m]["plugin-id"] != f["plugin-id"]:
                    self.err(f"family {fam}: member {m} is a {p.types[m]['plugin-id']}, the family is {f['plugin-id']}")
        for c in p.data.get("containers", []):
            for m in c.get("members", []):
                if m not in p.types:
                    self.err(f"container {c.get('members')}: member {m} is not an object type")

    # --- images: {type}-{animation}-{frame:03d}.png per frame, {type}.png for single-image plugins ---
    def check_image(self, rel: str, width: int, height: int) -> None:
        path = self.p.root / "images" / rel
        if not path.exists():
            self.err(f"missing image {rel}")
        elif Image is not None and Image.open(path).size != (width, height):
            self.err(f"{rel}: the object type says {width}x{height}, the file is {Image.open(path).size}")

    def check_images(self) -> None:
        if Image is None:
            self.warn("Pillow is not installed: image sizes are not compared with the frames")
        for name, t in self.p.types.items():
            if "image" in t:
                self.check_image(f"{name.lower()}.png", t["image"]["width"], t["image"]["height"])
            for rel, fr in frames_of(t.get("animations", {}), f"{name.lower()}-"):
                self.check_image(rel, fr["width"], fr["height"])

    # --- layouts ----------------------------------------------------------------------------
    def collect_sids(self, obj, in_ace: bool = False) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "sid" and isinstance(v, int):
                    (self.ace_sids if in_ace else self.sids).append(v)
                # instanceFolderItem and scene-graphs-folder-root are editor references that repeat an instance's sid
                if k not in ("instanceFolderItem", "scene-graphs-folder-root"):
                    self.collect_sids(v, in_ace or k in ("conditions", "actions"))
        elif isinstance(obj, list):
            for v in obj:
                self.collect_sids(v, in_ace)

    def check_properties(self, where: str, props: dict, schema_props: dict | None) -> None:
        """A property the schema does not list is a warning: older projects keep
        keys the editor has since renamed (z-height), and the editor drops them."""
        if schema_props is None:
            return
        for k, v in props.items():
            if k not in schema_props:
                self.warn(f"{where}: property {k} is not in the current schema")
                continue
            items = (schema_props[k] or {}).get("items")
            if items and v not in items:
                self.err(f"{where}: {k}={v!r} is not one of {list(items)}")

    def check_effects(self, effect_types: list) -> None:
        """Only whether the effect has a schema; an unknown one is warned about once."""
        for e in effect_types:
            self.p.schema("effects", e.get("effectId", e.get("id", "")))

    def check_instance(self, where: str, inst: dict) -> None:
        p = self.p
        t = inst.get("type")
        if not isinstance(inst.get("uid"), int):
            self.err(f"{where}: instance of {t} has no integer uid")
        else:
            self.uids.append(inst["uid"])
        self.templates.add(t)
        if t not in p.types:
            self.err(f"{where}: instance of unknown type {t}{closest(t or '', p.types)}")
            return
        ivars = p.ivars_of(t)
        ivar_types = p.ivar_types_of(t)
        for iv, value in inst.get("instanceVariables", {}).items():
            if iv not in ivars:
                self.err(f"{where}: {t} has no instance variable {iv}")
            elif ivar_types[iv] in JSON_TYPES and not JSON_TYPES[ivar_types[iv]](value):
                self.err(f"{where}: {t} instance variable {iv} = {value!r}; a {ivar_types[iv]} is written as "
                         f"{JSON_EXAMPLES[ivar_types[iv]]} here, a JSON value, not text")
        angle = inst.get("world", {}).get("angle", 0)
        if isinstance(angle, (int, float)) and abs(angle) > FULL_TURN:
            self.err(f"{where}: {t} world angle {angle} is more than a full turn; the file stores radians, "
                     f"{angle} degrees is {math.radians(angle):.4f}")
        for iv in ivars - set(inst.get("instanceVariables", {})):
            self.err(f"{where}: {t} instance has no value for instance variable {iv}")
        behs = p.behaviors_of(t)
        for b in inst.get("behaviors", {}):
            if b not in behs:
                self.err(f"{where}: {t} has no behavior {b}")
        for b in set(behs) - set(inst.get("behaviors", {})):
            self.err(f"{where}: {t} instance has no properties block for behavior {b}")
        plugin = p.schema("plugins", p.plugin_of[t])
        self.check_properties(f"{where}: {t}", inst.get("properties", {}), plugin.get("properties") if plugin else None)
        for b, block in inst.get("behaviors", {}).items():
            if b in behs:
                bs = p.schema("behaviors", behs[b])
                self.check_properties(f"{where}: {t}.{b}", block.get("properties", {}),
                                      bs.get("properties") if bs else None)
        anims = p.animations_of(t)
        initial = inst.get("properties", {}).get("initial-animation")
        if anims is not None and initial is not None and LOWER(initial) not in anims:
            self.err(f"{where}: {t} has no animation {initial!r} for initial-animation")

    def walk_layers(self, where: str, layer_list: list) -> None:
        for layer in layer_list:
            self.layers.add(layer["name"])
            self.check_effects(layer.get("effectTypes", []))
            for inst in layer.get("instances", []):
                self.world_types.add(inst.get("type"))
                self.check_instance(f"{where} layer {layer['name']}", inst)
            self.walk_layers(where, layer.get("subLayers", []))

    def check_layouts(self) -> None:
        p = self.p
        self.layouts = p.load_listed("layouts")
        self.sheets = {**p.load_listed("eventSheets"), **self.unsaved}
        for lname, lay in self.layouts.items():
            self.collect_sids(lay)
            self.walk_layers(f"layout {lname}", lay["layers"])
            for inst in lay.get("nonworld-instances", []):
                self.check_instance(f"layout {lname}", inst)
            self.check_effects(lay.get("effectTypes", []))
            if lay.get("eventSheet") and lay["eventSheet"] not in self.sheets:
                self.err(f"layout {lname}: event sheet {lay['eventSheet']} does not exist")

        for name, t in p.types.items():
            if "singleglobal-inst" in t:
                self.uids.append(t["singleglobal-inst"]["uid"])
                plugin = p.schema("plugins", t["plugin-id"])
                self.check_properties(f"{name}", t["singleglobal-inst"].get("properties", {}),
                                      plugin.get("properties") if plugin else None)
            self.check_effects(t.get("effectTypes", []))
            self.collect_sids(t)
        for f in p.families.values():
            self.collect_sids(f)
        self.collect_sids(p.data.get("rootFileFolders", {}))

    def check_namespace(self, obj: str) -> None:
        """`Enemy.Angle` has to mean one thing, so the editor refuses an instance
        variable, behavior or effect named like another one on the object or its
        families, or like an expression of the plugin. Names compare without case."""
        p = self.p
        declared: dict[str, str] = {}
        for owner in [obj] + p.families_of(obj):
            d = p.types.get(owner) or p.families.get(owner) or {}
            entries = ([("instance variable", v["name"]) for v in d.get("instanceVariables", [])]
                       + [("behavior", b["name"]) for b in d.get("behaviorTypes", [])]
                       + [("effect", e["name"]) for e in d.get("effectTypes", []) if "name" in e])
            for what, name in entries:
                label = f"{what} {name}" + (f" of family {owner}" if owner != obj else "")
                if LOWER(name) in declared:
                    self.err(f"{obj}: {label} has the same name as {declared[LOWER(name)]}")
                declared[LOWER(name)] = label
        plugin = p.schema("plugins", p.plugin_of[obj])
        expressions = p.expressions_of(plugin)
        members = p.families[obj].get("members", []) if obj in p.families else [obj]
        if any(m in self.world_types for m in members):
            expressions |= p.common_expressions
        for key, label in declared.items():
            if key in expressions and " of family " not in label:
                self.err(f"{obj}: {label} collides with the expression {obj}.{key}; rename it")

    # --- event sheets: expressions and parameters -------------------------------------------
    def check_expr(self, where: str, expr, scope: dict, owner: str | None = None,
                   stand_in: str | None = None) -> None:
        """owner: the object of the condition or action the expression belongs to;
        Self names it, so Self in a System parameter names nothing, and the editor
        stops with 'Invalid use of self'. stand_in: the object a System parameter
        of the same ACE names, the one to write instead of Self."""
        p = self.p
        if not isinstance(expr, str):
            return
        text = STRING_LITERAL.sub('""', expr)
        scope_lower = {LOWER(k) for k in scope}
        if owner == "System" and any(LOWER(m.group(0)) == "self" for m in IDENT.finditer(text)):
            fixed = re.sub(r"\bself\b", stand_in, expr, flags=re.I) if stand_in else None
            hint = f"; write {fixed!r}" if fixed else "; name the object instead"
            self.err(f"{where}: Self names the object of the condition or action, and here that is System; "
                     f"the editor stops with \"Invalid use of 'self'\"{hint}")
        for m in MEMBER.finditer(text):
            obj, member, sub = m.group(1), m.group(2), m.group(3)
            if LOWER(obj) == "self" or NUMBER.fullmatch(obj):   # a decimal such as 0.5 is not a member access
                continue
            if LOWER(obj) == LOWER(p.functions_object):
                if LOWER(member) not in {LOWER(f) for f in self.functions}:
                    self.err(f"{where}: {obj}.{member} is not a defined function")
                continue
            obj = p.objects_lower.get(LOWER(obj))
            if obj is None or obj == "System":
                # JSON.Get names the plugin; an expression is reached through the project's object of it.
                users = [n for n, pl in p.plugin_of.items() if squash(pl) == squash(m.group(1)) and pl != "system"]
                hint = f"; {m.group(1)} is the plugin, the object of it here is {', '.join(users)}" if users \
                    else closest(m.group(1), p.plugin_of)
                self.err(f"{where}: unknown object {m.group(1)} in expression{hint}")
                continue
            behs = {LOWER(k): v for k, v in p.behaviors_of(obj).items()}
            if LOWER(member) in behs:
                bs = p.schema("behaviors", behs[LOWER(member)])
                if bs is None:
                    continue
                if sub is None or LOWER(sub) not in p.expressions_of(bs):
                    self.err(f"{where}: {obj}.{member}.{sub or ''} is not an expression of behavior "
                             f"{behs[LOWER(member)]}")
                continue
            plugin = p.schema("plugins", p.plugin_of[obj])
            if plugin is None:
                continue
            known = p.expressions_of(plugin) | p.common_expressions
            known |= {LOWER(v) for v in p.ivars_of(obj)}
            if LOWER(member) not in known:
                # Platform.Speed is reached as Player.Platform.Speed, through the behavior's name on the object.
                owner = next((name for name, b in p.behaviors_of(obj).items()
                              if LOWER(member) in p.expressions_of(p.schema("behaviors", b))), None)
                hint = f"; it is an expression of a behavior: {obj}.{owner}.{member}" if owner \
                    else closest(member, known)
                self.err(f"{where}: {obj}.{member} is neither an expression nor an instance variable of {obj}{hint}")
        for m in IDENT.finditer(text):
            name = m.group(0)
            if NUMBER.fullmatch(name):
                continue
            if text[:m.start()].rstrip().endswith(".") or text[m.end():].lstrip().startswith("."):
                continue
            if LOWER(name) in p.system_expressions or LOWER(name) in scope_lower:
                continue
            if LOWER(name) in p.objects_lower and text[m.end():].lstrip().startswith("("):
                continue
            hint = closest(name, list(scope) + list(p.plugin_of))
            if LOWER(name) in p.objects_lower:
                hint = f"; {p.objects_lower[LOWER(name)]} is an object, write {p.objects_lower[LOWER(name)]}.<expression>"
            elif text.strip() == name:
                hint += f"; a text value carries inner quotes: \"\\\"{name}\\\"\""
            self.err(f"{where}: identifier {name!r} is not a variable, parameter or system expression{hint}")

    def builtin_eases(self) -> set[str]:
        """Ids of the built-in eases, the keys the editor's language pack labels."""
        if not self._eases:
            pack = self.p.rag / "data" / "c3-lang" / "en-US.json"
            if pack.exists():
                self._eases.update(c3.load(pack)["text"]["ui"]["bars"]["timeline"]["eases"])
        return self._eases

    def check_param(self, where: str, key: str, value, ptype: str, items: dict | None, obj: str, scope: dict,
                    writes: bool = False, stand_in: str | None = None) -> None:
        """writes: the parameter belongs to an action, which assigns the variable it names.
        stand_in: the object an "object" parameter of the same ACE names."""
        p = self.p
        if ptype == "cmp":
            if value not in (0, 1, 2, 3, 4, 5) or isinstance(value, bool):
                self.err(f"{where}: comparison {value!r} is not an integer 0-5 (=, ≠, <, ≤, >, ≥)")
        elif ptype == "boolean":
            if not isinstance(value, bool):
                self.err(f"{where}: {key} should be a JSON boolean, not {value!r}")
        elif ptype in ("combo", "combo-grouped"):
            if items and value not in items:
                self.err(f"{where}: {key}={value!r} is not one of {list(items)}{bare(value, items)}")
        elif ptype == "keyb":
            if not isinstance(value, int) or isinstance(value, bool):
                self.err(f"{where}: {key}={value!r} should be a key code, a JSON number such as 32 for Space or "
                         f"37-40 for the arrows; the editor stops with 'expected finite number'")
        elif ptype == "ease":
            eases = self.builtin_eases()
            if isinstance(value, str) and eases and value not in eases and not p.data.get("eases"):
                self.err(f"{where}: {key}={value!r} is not a built-in ease{closest(value, eases)}")
        elif ptype in ("audiofile", "tilemapbrush", "function", "model3d", "template", "objecteffect"):
            return
        elif ptype == "object":
            if value not in p.plugin_of or value == "System":
                self.err(f"{where}: {key}={value!r} is not an object type or family"
                         + (bare(value, p.plugin_of) or closest(value, p.plugin_of)))
        elif ptype in ("instancevar", "instancevarbool"):
            # shared ACEs name one of the object's own variables
            ivars = p.ivar_types_of(obj)
            if value not in ivars:
                self.err(f"{where}: {obj} has no instance variable {value!r}{bare(value, ivars) or closest(value, ivars)}")
            elif ptype == "instancevarbool" and ivars[value] != "boolean":
                self.err(f"{where}: instance variable {value!r} is not a boolean")
        elif ptype == "objinstancevar":
            target, ivar = (value.get("objectClass", obj), value.get("name")) if isinstance(value, dict) else (obj, value)
            if ivar not in p.ivars_of(target):
                self.err(f"{where}: {target} has no instance variable {ivar!r}{closest(ivar or '', p.ivars_of(target))}")
        elif ptype in ("eventvar", "eventvarbool", "eventvarany"):
            if value not in scope:
                self.err(f"{where}: variable {value!r} is not in scope{bare(value, scope) or closest(value, scope)}")
            elif ptype == "eventvarbool" and scope[value]["type"] != "boolean":
                self.err(f"{where}: variable {value!r} is not a boolean")
            elif writes and scope[value].get("isConstant"):
                self.err(f"{where}: {value} is a constant and an action cannot change it; "
                         f"the editor stops with 'event variable {value} is constant'")
        elif ptype == "layer":
            if is_literal(value):
                if unquote(value) not in self.layers:
                    self.err(f"{where}: no layer named {unquote(value)!r} in any layout")
            else:
                self.check_expr(f"{where} {key}", value, scope, obj, stand_in)
        elif ptype == "layout":
            if value not in self.layouts:
                self.err(f"{where}: no layout named {value!r}{bare(value, self.layouts) or closest(value, self.layouts)}")
        elif ptype == "groupname":
            if is_literal(value) and unquote(value) not in self.group_titles:
                self.err(f"{where}: no group titled {unquote(value)!r}")
        elif ptype == "animation":
            anims = p.animations_of(obj)
            if is_literal(value):
                if anims is not None and LOWER(unquote(value)) not in anims:
                    self.err(f"{where}: {obj} has no animation {unquote(value)!r}")
            else:
                self.check_expr(f"{where} {key}", value, scope, obj, stand_in)
        elif ptype == "projectfile":
            name = value["path"] if isinstance(value, dict) else value
            if not (p.root / "files" / name).exists() and not list((p.root / "files").rglob(Path(name).name)):
                self.err(f"{where}: project file {name!r} is not in files/")
        elif ptype == "timeline":
            if value not in [n for n, _ in folder_items(p.data.get("timelines", {}))]:
                self.err(f"{where}: no timeline named {value!r}")
        elif ptype == "flowchart":
            if value not in [n for n, _ in folder_items(p.data.get("flowcharts", {}))]:
                self.err(f"{where}: no flowchart named {value!r}")
        else:
            if not isinstance(value, str):
                self.err(f"{where}: {key} should be an expression string, not {value!r}")
            else:
                self.check_expr(f"{where} {key}", value, scope, obj, stand_in)

    # --- event sheets: conditions and actions -------------------------------------------------
    def ace_hint(self, kind: str, ace: dict) -> str:
        """Where an id the schema does not have under this object does exist: on one
        of its behaviors, on the object itself, as the other kind, or under a near
        spelling (the script name and the list name are tried as well as the id)."""
        p = self.p
        obj, ace_id = ace["objectClass"], ace["id"]
        if "behaviorType" not in ace:
            for name, behavior_id in p.behaviors_of(obj).items():
                s = p.schema("behaviors", behavior_id)
                if s and any(it["id"] == ace_id for it in s.get(kind, [])):
                    return f"; it belongs to the behavior {name}: add \"behaviorType\": \"{name}\""
        elif any(it["id"] == ace_id for s in p.ace_sources({"objectClass": obj}) for it in s.get(kind, [])):
            return "; it belongs to the object itself: remove \"behaviorType\""
        sources = p.ace_sources(ace)
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

    def check_ace(self, kind: str, ace: dict, scope: dict, where: str) -> None:
        p = self.p
        obj = ace.get("objectClass")
        ace_id = ace.get("id")
        params = ace.get("parameters", {})
        where = f"{where} {obj}:{ace_id}"
        if obj is None or ace_id is None:
            self.err(f"{where}: a {kind[:-1]} needs \"objectClass\" and \"id\"")
            return
        if obj not in p.plugin_of:
            self.err(f"{where}: unknown object {obj}{closest(obj, p.plugin_of)}")
            return
        if "behaviorType" in ace and ace["behaviorType"] not in p.behaviors_of(obj):
            self.err(f"{where}: {obj} has no behavior {ace['behaviorType']}"
                     f"{closest(ace['behaviorType'], p.behaviors_of(obj))}; "
                     f"\"behaviorType\" is the name the behavior has on the object, not its id")
            return
        if not p.ace_sources(ace):
            return      # no schema for this addon: warned about once, nothing to check against
        entry = p.ace_entry(kind, ace)
        if entry is None:
            owner = p.behaviors_of(obj)[ace["behaviorType"]] if "behaviorType" in ace else p.plugin_of[obj]
            self.err(f"{where}: {owner} has no {kind[:-1]} {ace_id}"
                     + ("" if "behaviorType" in ace or obj == "System" else " (not in _common either)")
                     + self.ace_hint(kind, ace))
            return
        schema_params = entry.get("params") or {}
        if not isinstance(params, dict):
            self.err(f"{where}: \"parameters\" should be an object keyed by parameter id: "
                     f"{', '.join(schema_params) or 'none here'}")
            return
        for k in params:
            if k not in schema_params:
                self.err(f"{where}: unknown parameter {k}; the parameters are: {', '.join(schema_params) or 'none'}")
        for k in schema_params:
            if k not in params:
                self.warn(f"{where}: parameter {k} is omitted; the editor fills its default")
        named = [v for k, v in params.items() if schema_params.get(k, {}).get("type") == "object"]
        stand_in = named[0] if len(named) == 1 and named[0] in p.plugin_of else None
        for k, v in params.items():
            if k not in schema_params:
                continue
            self.check_param(where, k, v, schema_params[k]["type"], schema_params[k].get("items"), obj, scope,
                             writes=kind == "actions", stand_in=stand_in)
        if ace_id == "create-object" and obj == "System":
            self.created.add(params.get("object-to-create"))
        if ace_id == "set-eventvar-value" and (scope.get(params.get("variable")) or {}).get("type") == "boolean":
            self.err(f"{where}: Set value on boolean {params['variable']}; use Set boolean")

    def check_structure(self, ev: dict, where: str, above: Holder | None, previous: dict | None) -> Holder | None:
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
        p = self.p
        conds = [c for c in ev.get("conditions", []) if "id" in c]
        entries = [p.ace_entry("conditions", c) or {} for c in conds]
        is_function = ev.get("eventType") != "block"
        triggers = [c for c, e in zip(conds, entries) if e.get("isTrigger")]
        if is_function and ev.get("isOrBlock"):
            self.err(f"{where}: a function or custom action cannot be an OR block")
        if triggers and (above or is_function):
            holder = above.text if above else "a function or custom action, which counts as a trigger"
            self.err(f"{where}: {describe(triggers[0])} is a trigger inside {holder}; the editor stops with 'cannot "
                     f"add another trigger to event branch'. Move it to an event of its own, outside, and test the "
                     f"rest in sub-events")
        elif len(triggers) > 1 and not ev.get("isOrBlock"):
            self.err(f"{where}: {' and '.join(describe(c) for c in triggers)} are two triggers in one event; the "
                     f"editor stops with 'cannot add another trigger to event branch'. One event per trigger, or an "
                     f"OR block")
        for c, e in zip(conds, entries):
            # Both are mended in the one condition, so they name it, as check_ace does.
            its = f"{where} condition {next(i for i, x in enumerate(ev['conditions'], 1) if x is c)}"
            if c.get("isInverted") and (e.get("isTrigger") or e.get("isLooping") or e.get("isInvertible") is False):
                kind = "a trigger" if e.get("isTrigger") else "a loop" if e.get("isLooping") else "this condition"
                self.err(f"{its}: {describe(c)} is inverted, and {kind} cannot be; "
                         f"the editor stops with 'condition not invertible'")
            # Trigger once, Every X seconds: the editor keeps them out of a triggered branch, where they
            # are tested only in the tick the trigger fires. Else has its own rule below.
            if e.get("isCompatibleWithTriggers") is False and c["id"] != "else" \
                    and (triggers or (above and above.fires)):
                self.warn(f"{its}: {describe(c)} is in a branch run by the trigger "
                          f"{describe(triggers[0]) if triggers else above.name}; the editor does not offer it there, "
                          f"since it is only tested when the trigger fires")
        for i, c in enumerate(conds):
            if c.get("objectClass") != "System" or c["id"] != "else":
                continue
            problem = None
            before = [b for b in (previous or {}).get("conditions", []) if "id" in b]
            flags = [p.ace_entry("conditions", b) or {} for b in before]
            if ev.get("isOrBlock") or is_function:
                problem = "its event is " + ("an OR block" if ev.get("isOrBlock") else "a function")
            elif triggers:
                problem = f"its event has the trigger {describe(triggers[0])}"
            elif i != 0:
                problem = "it is not the first condition of its event"
            elif previous is None or previous.get("eventType") != "block":
                problem = "it is the first event of its list" if previous is None else \
                    f"it follows a {previous.get('eventType')}, and only comments may stand between it and the " \
                    f"event it answers"
            elif len(before) == 1 and describe(before[0]) == "System:else":
                problem = "it follows an event whose only condition is Else"
            elif any(f.get("isTrigger") for f in flags):
                problem = "it follows a triggered event"
            elif any(f.get("isLooping") for f in flags):
                problem = "it follows a loop"
            if problem:
                self.err(f"{where}: Else cannot stand here, {problem}; the editor refuses to preview ('An Else "
                         f"condition cannot be placed here'). Use a second event with the inverted condition")
        if above:
            return above
        if is_function:
            kind = "function" if ev.get("eventType") == "function-block" else "custom action"
            return Holder(f"the {kind} {ev.get('functionName') or ev.get('aceName')}", False)
        return Holder(describe(triggers[0]), True) if triggers else None

    def check_variable(self, var: dict, where: str, what: str) -> None:
        """An event variable or a function parameter: its type is one of three and its
        initialValue is text, as the editor writes it. The editor reads a boolean by
        comparing the text to "true", in the editor and again on export, so a JSON
        true or a "True" reads as false; a function parameter may also carry a
        number, anything else stops the load with 'invalid type of initialValue'."""
        name, vtype, value = var.get("name"), var.get("type"), var.get("initialValue")
        w = f"{where}: {what} {name}"
        if vtype not in VARIABLE_TYPES:
            self.err(f"{w}: type {vtype!r} is not number, string or boolean")
            return
        if what == "parameter" and isinstance(value, (int, float)) and not isinstance(value, bool):
            value = str(value)
        if not isinstance(value, str):
            if vtype == "boolean":
                self.err(f"{w}: initialValue should be the text \"true\" or \"false\", not {value!r}; "
                         f"the editor compares the text to \"true\", so a JSON boolean reads as false")
            else:
                self.err(f"{w}: initialValue should be text, {json.dumps(str(value if value is not None else ''))}, "
                         f"not {value!r}; the editor stores every initial value as text")
        elif vtype == "boolean" and value not in ("true", "false"):
            self.err(f"{w}: initialValue {value!r} should be \"true\" or \"false\", lowercase; "
                     f"the editor compares the text to \"true\" and reads anything else as false")
        elif vtype == "number":
            try:
                finite = math.isfinite(float(value))
            except ValueError:
                finite = False
            if not finite:
                self.err(f"{w}: initialValue {value!r} is not a number; the editor reads it as 0")

    def check_block(self, ev: dict, scope: dict, where: str) -> None:
        for i, c in enumerate(ev.get("conditions", []), 1):
            self.check_ace("conditions", c, scope, f"{where} condition {i}")
        for i, a in enumerate(ev.get("actions", []), 1):
            w = f"{where} action {i}"
            if a.get("type") in ("comment", "script"):
                continue
            if "callFunction" in a:
                self.pending_calls.append(("function", a["callFunction"], None, len(a.get("parameters", [])), w))
                for param in a.get("parameters", []):
                    self.check_expr(w, param, scope)
                continue
            if "customAction" in a:
                owner = a.get("customActionObjectClass", a["objectClass"])
                self.pending_calls.append(("custom", a["customAction"], owner, len(a.get("parameters", [])), w))
                for param in a.get("parameters", []):
                    self.check_expr(w, param, scope)
                continue
            self.check_ace("actions", a, scope, w)

    def walk(self, events: list, scope: dict, where: str, counter: list[int], above: Holder | None = None,
             depth: int = 0) -> None:
        """A local declared in a list of sibling events is visible to every event of
        that list, whatever the order, and to their sub-events; not to the parent's
        own actions. So the list's variables enter the scope first, and a block is
        checked before its children are walked. scope maps a name to the variable
        event or function parameter that declares it. counter holds the sheet's
        running event number, above what holds the trigger of this branch, depth
        how many sub-event levels down this list is (a group's children are 0)."""
        scope = dict(scope)
        for ev in events:
            if ev.get("eventType") == "variable":
                scope[ev["name"]] = ev
        ladders = self.ladders(events) if self.style else {}
        numbered: dict[int, list[tuple[int, str]]] = {}
        previous = None
        for i, ev in enumerate(events):
            et = ev.get("eventType")
            if et in NUMBERED:
                counter[0] += 1
            w = f"{where} event {counter[0] + (et not in NUMBERED)} (sid {ev.get('sid', '?')})"
            if self.style and et in ("block", "function-block", "custom-ace-block"):
                self.check_style(ev, w, events, i, depth)
            if id(ev) in ladders:
                rungs = numbered.setdefault(ladders[id(ev)][0], [])
                rungs.append((counter[0], w))
                if len(rungs) == ladders[id(ev)][1]:
                    self.check_ladder(rungs)
            if et == "variable":
                self.check_variable(ev, w, "variable")
            elif et in ("comment", "include"):
                if et == "include" and ev["includeSheet"] not in self.sheets:
                    self.err(f"{w}: included sheet {ev['includeSheet']} does not exist"
                             f"{closest(ev['includeSheet'], self.sheets)}")
                elif et == "include" and where == f"sheet {ev['includeSheet']}":
                    self.err(f"{w}: a sheet cannot include itself")
            elif et == "group":
                self.walk(ev["children"], scope, where, counter, above)
            elif et in ("function-block", "custom-ace-block"):
                fscope = dict(scope)
                for param in ev["functionParameters"]:
                    fscope[param["name"]] = param
                    self.check_variable(param, w, "parameter")
                label = ev.get("functionName") or f"{ev['objectClass']}.{ev['aceName']}"
                if et == "custom-ace-block" and ev["objectClass"] not in self.p.plugin_of:
                    self.err(f"{w}: custom action {label} belongs to unknown object {ev['objectClass']}")
                self.check_block(ev, fscope, f"{w} {label}")
                self.walk(ev.get("children", []), fscope, where, counter,
                          self.check_structure(ev, f"{w} {label}", above, previous), depth + 1)
            elif et == "block":
                self.check_block(ev, scope, w)
                self.walk(ev.get("children", []), scope, where, counter, self.check_structure(ev, w, above, previous),
                          depth + 1)
            elif et != "script":
                self.err(f"{w}: unknown eventType {et!r}; the editor knows block, group, variable, comment, include, "
                         f"function-block, custom-ace-block and script")
            if et != "comment":
                previous = ev

    # --- style, with --style ------------------------------------------------------------
    def check_style(self, ev: dict, where: str, siblings: list, i: int, depth: int) -> None:
        """Habits of sheets written by small models, each with the shape the
        official examples give it instead. Warnings, never errors: the editor
        accepts them all. The thresholds sit past the 90th percentile of the
        studio examples, where a run of actions without a comment is 3 at the
        median and 6 at the 90th percentile, branches go two sub-events deep in
        93% of events, 93% of top-level events have a comment above them, and
        of the events with two or more case sub-events 84% have a comment above
        at least one case (docs/decisions/event-sheet-design-guidance.md,
        2026-09-22). edit_sheet.py refuses a plan whose new events raise the
        ones whose fix is one comment, and prints the others; check_project.py
        reports them all over the whole project when asked, which suits a
        project the agent wrote. A ladder of sibling events is check_ladder."""
        actions = ev.get("actions", [])
        run = longest = 0
        for a in actions:
            run = 0 if a.get("type") == "comment" else run + 1
            longest = max(longest, run)
        style = self.p.findings.style_finding
        if longest >= STYLE_RUN:
            style("run", f"{where}: {longest} actions in a row without a comment action; the official examples step a "
                         f"long block with a comment action every three to five actions, "
                         '{"type": "comment", "text": "What the next actions do."}')
        if depth == 0 and (actions or ev.get("children")):
            j = i - 1
            while j >= 0 and siblings[j].get("eventType") == "variable":     # locals declared above the event
                j -= 1
            if j < 0 or siblings[j].get("eventType") != "comment":
                style("comment", f"{where}: no comment above it; the official examples put a one-sentence comment "
                                 f"above every top-level event, saying what it does or which case it is, "
                                 '{"eventType": "comment", "text": "..."} as the event before it')
        cases = [j for j, k in enumerate(ev.get("children", []))
                 if k.get("eventType") == "block" and (k.get("actions") or k.get("children"))]
        if len(cases) >= 2 and not any(j > 0 and ev["children"][j - 1].get("eventType") == "comment" for j in cases):
            style("cases", f"{where}: none of its {len(cases)} case sub-events has a comment above it; the official "
                           f"examples put a one-sentence comment above each case, saying which case it is, "
                           '{"eventType": "comment", "text": "..."} as the event before each')
        if depth == 0 and self.tree_depth(ev) >= STYLE_TREE:
            leaves = self.leaves(ev)
            called = {a["callFunction"] for leaf in leaves for a in leaf.get("actions", []) if "callFunction" in a}
            if len(leaves) >= 3 and len(called) == 1 and \
                    all(any("callFunction" in a for a in leaf.get("actions", [])) for leaf in leaves):
                style("tree", f"{where}: sub-events {self.tree_depth(ev)} levels deep, every leaf calling "
                              f"{called.pop()}; the official examples write the cases as sibling sub-events with a "
                              f"comment each, or compute the value in one expression")

    @staticmethod
    def shape(ev: dict) -> tuple:
        """An event's conditions and actions by their ACE, without their values."""
        return (ev.get("isOrBlock", False),
                tuple((c.get("objectClass"), c.get("id"), c.get("isInverted", False)) for c in ev.get("conditions", [])),
                tuple((a.get("objectClass"), a.get("id")) for a in ev.get("actions", [])),
                len([k for k in ev.get("children", []) if k.get("eventType") == "block"]))

    def ladders(self, events: list) -> dict[int, tuple[int, int]]:
        """The sibling blocks that share their shape with STYLE_LADDER or more others, by
        id, each mapped to its ladder's number and size. One event per option,
        building or state, only the numbers changed, is a table transcribed into
        events; the studio examples reach five such siblings in 32 places of 20 of their 219
        projects, input ladders (a key per action) and else-if chains among them."""
        of_shape: dict[tuple, list[dict]] = {}
        for ev in events:
            if ev.get("eventType") == "block" and (ev.get("actions") or ev.get("children")):
                of_shape.setdefault(self.shape(ev), []).append(ev)
        return {id(ev): (n, len(evs)) for n, evs in enumerate(of_shape.values()) if len(evs) >= STYLE_LADDER
                for ev in evs}

    def check_ladder(self, rungs: list[tuple[int, str]]) -> None:
        others = ", ".join(str(n) for n, _ in rungs[1:])
        self.p.findings.style_finding(
            "ladder", f"{rungs[0][1]}: with events {others}, the same conditions and actions {len(rungs)} times over, "
                      f"differing only in their values; the official examples write such cases once, over what "
                      f"differs: an instance variable of the object touched, a family, a Dictionary loaded from a "
                      f"project file, or the value in one expression")

    @staticmethod
    def tree_depth(ev: dict) -> int:
        kids = [k for k in ev.get("children", []) if k.get("eventType") == "block"]
        return 1 + max((Checker.tree_depth(k) for k in kids), default=0) if kids else 0

    @staticmethod
    def leaves(ev: dict) -> list[dict]:
        kids = [k for k in ev.get("children", []) if k.get("eventType") == "block"]
        return [leaf for k in kids for leaf in Checker.leaves(k)] if kids else [ev]

    def declared_functions(self, events: list) -> None:
        """Functions and custom actions are visible from every sheet, so collect them first."""
        for ev in events:
            et = ev.get("eventType")
            if et == "function-block":
                self.functions[ev["functionName"]] = len(ev["functionParameters"])
            elif et == "custom-ace-block":
                self.custom_actions[(ev["objectClass"], ev["aceName"])] = len(ev["functionParameters"])
            self.declared_functions(ev.get("children", []))

    def declared_groups(self, events: list) -> None:
        for ev in events:
            if ev.get("eventType") == "group":
                self.group_titles.add(ev["title"])
            self.declared_groups(ev.get("children", []))

    def check_sheets(self) -> None:
        for sheet in self.sheets.values():
            self.collect_sids(sheet)
        for sheet in self.sheets.values():
            self.declared_functions(sheet["events"])
            self.declared_groups(sheet["events"])
        # A global declared at the top level of any sheet is visible from every sheet.
        globals_ = {ev["name"]: ev for s in self.sheets.values() for ev in s["events"]
                    if ev.get("eventType") == "variable"}
        for sname, sheet in self.sheets.items():
            self.walk(sheet["events"], globals_, f"sheet {sname}", [0])

    def check_calls(self) -> None:
        p = self.p
        for kind, name, owner, nparams, where in self.pending_calls:
            if kind == "function":
                if name not in self.functions:
                    self.err(f"{where}: call to undefined function {name}{closest(name, self.functions)}")
                elif self.functions[name] != nparams:
                    self.err(f"{where}: {name} called with {nparams} parameters, defined with {self.functions[name]}")
            else:
                owners = [owner] + p.families_of(owner)
                hit = next(((o, name) for o in owners if (o, name) in self.custom_actions), None)
                if hit is None:
                    self.err(f"{where}: {owner} has no custom action {name!r}"
                             + closest(name, [n for o, n in self.custom_actions if o in owners]))
                elif self.custom_actions[hit] != nparams:
                    self.err(f"{where}: {owner}.{name} called with {nparams} parameters, "
                             f"defined with {self.custom_actions[hit]}")
        for t in self.created:
            if t in p.types and t not in self.templates:
                self.warn(f"{t} is created at runtime but has no instance in any layout: "
                          f"it is created with default properties")

    # --- uniqueness, project files, addons ----------------------------------------------------
    def check_uniqueness(self) -> None:
        sids, ace_sids, uids = self.sids, self.ace_sids, self.uids
        dup_sids = sorted({s for s in sids if sids.count(s) > 1} | (set(sids) & set(ace_sids)))
        if dup_sids:
            self.err(f"duplicate sids: {dup_sids[:5]}{' ...' if len(dup_sids) > 5 else ''}")
        dup_ace_sids = sorted({s for s in ace_sids if ace_sids.count(s) > 1})
        if dup_ace_sids:
            self.warn(f"conditions or actions sharing a sid (pasted in the editor?): "
                      f"{dup_ace_sids[:5]}{' ...' if len(dup_ace_sids) > 5 else ''}")
        dup_uids = sorted({u for u in uids if uids.count(u) > 1})
        if dup_uids:
            self.err(f"duplicate uids: {dup_uids[:5]}{' ...' if len(dup_uids) > 5 else ''}")

    def check_files_and_addons(self) -> None:
        p = self.p
        for name, folder in folder_items(p.data.get("rootFileFolders", {}).get("general", {})):
            fname = name["name"] if isinstance(name, dict) else name
            if not (p.root / "files" / folder / fname).exists():
                self.err(f"project file {fname} is listed in project.c3proj but missing from files/{folder}")

        addon_ids = {a["id"] for a in p.data.get("usedAddons", [])}

        def need_addon(addon_id: str, where: str) -> None:
            if addon_id not in addon_ids:
                self.err(f"{where}: {addon_id} is not listed in usedAddons")

        for name, t in p.types.items():
            need_addon(t["plugin-id"], f"object type {name}")
            for b in t.get("behaviorTypes", []):
                need_addon(b["behaviorId"], f"object type {name}")
            for e in t.get("effectTypes", []):
                need_addon(e.get("effectId", e.get("id", "")), f"object type {name}")
        for name, f in p.families.items():
            for b in f.get("behaviorTypes", []):
                need_addon(b["behaviorId"], f"family {name}")
            for e in f.get("effectTypes", []):
                need_addon(e.get("effectId", e.get("id", "")), f"family {name}")

    def report(self) -> int:
        """Warnings, then problems, then the line that says how it went. A report
        longer than --limit prints what fits of each, warnings in a third of it
        when there are problems too, and says how many it left out."""
        p = self.p
        warnings, errors = [f"warning: {w}" for w in p.findings.warnings], p.findings.errors
        room = max(self.limit - 300, 3)                                         # less the closing lines
        cut = self.limit and c3.fitting(warnings + errors, room) < len(warnings + errors)
        shares = (room // 3 if errors else room, room - room // 3) if cut else (0, 0)       # 0 is no limit
        for lines, share, rest in ((warnings, shares[0], "warnings"),
                                   (errors, shares[1], "problems; fix these and run again")):
            fit = max(c3.fitting(lines, share), 1)
            if lines:
                print("\n".join(lines[:fit]))
            if fit < len(lines):
                print(f"... and {len(lines) - fit} more {rest} (--limit 0 prints all)")
        if errors:
            print(f"{len(errors)} problem(s)")
            return 1
        print(self.ok_line())
        return 0

    def ok_line(self) -> str:
        p = self.p
        return (f"ok: {len(p.types)} object types, {len(p.families)} families, {len(self.layouts)} layouts, "
                f"{len(self.sheets)} sheets, {len(self.sids) + len(self.ace_sids)} sids, {len(self.uids)} uids, "
                f"{len(self.functions)} functions, {len(self.custom_actions)} custom actions")


def main() -> int:
    ap = c3.argument_parser(
        "Check a Construct 3 folder project against the Construct3-RAG schemas and the rules the editor applies "
        "when it opens or previews a project. Every finding names its place, as 'sheet Game event 15 action 2' "
        "with the editor's event number, and says what to write where it can.",
        "examples:\n"
        "  python scripts/check_project.py\n"
        "  python scripts/check_project.py --project ../OtherGame\n\n"
        "  python scripts/check_project.py --style        # a project the agent wrote\n\n"
        "exit codes: 0 no errors (warnings do not fail the run), 1 findings or project/clone not found,\n"
        "2 a project file lacks a key the editor always writes and the run stopped there")
    ap.add_argument("--style", action="store_true",
                    help="also warn where a sheet departs from the authoring style of the official examples: "
                         f"{STYLE_RUN} or more actions in a row without a comment action, a top-level event with "
                         f"no comment above it, an event none of whose case sub-events has a comment above it, "
                         f"sub-events {STYLE_TREE} levels deep whose leaves all call one function, and "
                         f"{STYLE_LADDER} or more sibling events of the same conditions and actions with other "
                         "values. For a project the agent wrote; edit_sheet.py refuses a plan whose new events "
                         "raise the first three and warns on the other two")
    args = ap.parse_args()
    c3.utf8_output()
    findings = c3.Findings()
    c3.stop_with_a_sentence("check_project.py", findings)
    project = c3.Project.open(args, findings)
    drift = c3.skill_drift(project.rag)
    if drift:
        findings.warn(drift)
    return Checker(project, args.limit, style=args.style).run()


if __name__ == "__main__":
    sys.exit(main())
