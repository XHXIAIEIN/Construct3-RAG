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
RESERVED_NAMES = {"self", "true", "false", "system", "con", "prn", "aux", "nul",
                  *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}

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

    def __init__(self, p: c3.Project, limit: int = 0) -> None:
        self.p = p
        self.limit = limit
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

    def run(self) -> int:
        self.check_names()
        self.check_images()
        self.check_layouts()
        for obj in list(self.p.types) + list(self.p.families):
            self.check_namespace(obj)
        self.check_sheets()
        self.check_calls()
        self.check_uniqueness()
        self.check_files_and_addons()
        return self.report()

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
        for iv in inst.get("instanceVariables", {}):
            if iv not in ivars:
                self.err(f"{where}: {t} has no instance variable {iv}")
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
        self.sheets = p.load_listed("eventSheets")
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
        expressions = {LOWER(e["translated-name"]) for e in (plugin or {}).get("expressions", [])}
        members = p.families[obj].get("members", []) if obj in p.families else [obj]
        if any(m in self.world_types for m in members):
            expressions |= p.common_expressions
        for key, label in declared.items():
            if key in expressions and " of family " not in label:
                self.err(f"{obj}: {label} collides with the expression {obj}.{key}; rename it")

    # --- event sheets: expressions and parameters -------------------------------------------
    def check_expr(self, where: str, expr, scope: dict) -> None:
        p = self.p
        if not isinstance(expr, str):
            return
        text = STRING_LITERAL.sub('""', expr)
        scope_lower = {LOWER(k) for k in scope}
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
                if sub is None or LOWER(sub) not in {LOWER(e["translated-name"]) for e in bs["expressions"]}:
                    self.err(f"{where}: {obj}.{member}.{sub or ''} is not an expression of behavior "
                             f"{behs[LOWER(member)]}")
                continue
            plugin = p.schema("plugins", p.plugin_of[obj])
            if plugin is None:
                continue
            known = {LOWER(e["translated-name"]) for e in plugin.get("expressions", [])} | p.common_expressions
            known |= {LOWER(v) for v in p.ivars_of(obj)}
            if LOWER(member) not in known:
                # Platform.Speed is reached as Player.Platform.Speed, through the behavior's name on the object.
                owner = next((name for name, b in p.behaviors_of(obj).items() if LOWER(member) in
                              {LOWER(e["translated-name"]) for e in (p.schema("behaviors", b) or {}).get("expressions", [])}),
                             None)
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
                    writes: bool = False) -> None:
        """writes: the parameter belongs to an action, which assigns the variable it names."""
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
                self.check_expr(f"{where} {key}", value, scope)
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
                self.check_expr(f"{where} {key}", value, scope)
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
                self.check_expr(f"{where} {key}", value, scope)

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
        for k, v in params.items():
            if k not in schema_params:
                continue
            self.check_param(where, k, v, schema_params[k]["type"], schema_params[k].get("items"), obj, scope,
                             writes=kind == "actions")
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
            if c.get("isInverted") and (e.get("isTrigger") or e.get("isLooping") or e.get("isInvertible") is False):
                kind = "a trigger" if e.get("isTrigger") else "a loop" if e.get("isLooping") else "this condition"
                self.err(f"{where}: {describe(c)} is inverted, and {kind} cannot be; "
                         f"the editor stops with 'condition not invertible'")
            # Trigger once, Every X seconds: the editor keeps them out of a triggered branch, where they
            # are tested only in the tick the trigger fires. Else has its own rule below.
            if e.get("isCompatibleWithTriggers") is False and c["id"] != "else" \
                    and (triggers or (above and above.fires)):
                self.warn(f"{where}: {describe(c)} is in a branch run by the trigger "
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

    def walk(self, events: list, scope: dict, where: str, counter: list[int], above: Holder | None = None) -> None:
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
                label = ev.get("functionName") or f"{ev['objectClass']}.{ev['aceName']}"
                if et == "custom-ace-block" and ev["objectClass"] not in self.p.plugin_of:
                    self.err(f"{w}: custom action {label} belongs to unknown object {ev['objectClass']}")
                self.check_block(ev, fscope, f"{w} {label}")
                self.walk(ev.get("children", []), fscope, where, counter,
                          self.check_structure(ev, f"{w} {label}", above, previous))
            elif et == "block":
                self.check_block(ev, scope, w)
                self.walk(ev.get("children", []), scope, where, counter, self.check_structure(ev, w, above, previous))
            elif et != "script":
                self.err(f"{w}: unknown eventType {et!r}; the editor knows block, group, variable, comment, include, "
                         f"function-block, custom-ace-block and script")
            if et != "comment":
                previous = ev

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
        print(f"ok: {len(p.types)} object types, {len(p.families)} families, {len(self.layouts)} layouts, "
              f"{len(self.sheets)} sheets, {len(self.sids) + len(self.ace_sids)} sids, {len(self.uids)} uids, "
              f"{len(self.functions)} functions, {len(self.custom_actions)} custom actions")
        return 0


def main() -> int:
    ap = c3.argument_parser(
        "Check a Construct 3 folder project against the Construct3-RAG schemas and the rules the editor applies "
        "when it opens or previews a project. Every finding names its place, as 'sheet Game event 15 action 2' "
        "with the editor's event number, and says what to write where it can.",
        "examples:\n"
        "  python scripts/check_project.py\n"
        "  python scripts/check_project.py --project ../OtherGame\n\n"
        "exit codes: 0 no errors (warnings do not fail the run), 1 findings or project/clone not found,\n"
        "2 a project file lacks a key the editor always writes and the run stopped there")
    args = ap.parse_args()
    c3.utf8_output()
    findings = c3.Findings()
    c3.stop_with_a_sentence("check_project.py", findings)
    project = c3.Project.open(args, findings)
    drift = c3.skill_drift(project.rag)
    if drift:
        findings.warn(drift)
    return Checker(project, args.limit).run()


if __name__ == "__main__":
    sys.exit(main())
