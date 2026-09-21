"""What the scripts of this skill share: finding the project and the
Construct3-RAG clone, reading the files project.c3proj lists, the schemas,
the object model (types, families, behaviors, instance variables) and the
schema entry behind a condition or an action.

Not a command. check_project.py, print_sheet.py and lookup_ace.py import it
from the folder they sit in.
"""
import argparse
import difflib
import json
import os
import re
import sys
from pathlib import Path

SKILL = "construct3-project"
SKILL_DIR = Path(__file__).resolve().parent.parent
LOWER = str.lower  # expressions are case-insensitive: scrolly, SCROLLY and ScrollY are one name

# The editor numbers these in document order, sub-events included, one
# sequence per sheet. A variable, comment or include takes no number of its
# own: the margin leaves it blank and Find files it under the next numbered
# event, so every row's number is the count of numbered rows before it plus one.
NUMBERED = ("block", "group", "function-block", "custom-ace-block", "script")


class Findings:
    """Errors fail the run; warnings are printed and do not. Each is kept once."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, msg: str) -> None:
        if msg not in self.errors:
            self.errors.append(msg)

    def warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)


def stop_with_a_sentence(script: str, findings: Findings) -> None:
    """A file that lacks a key the editor always writes stops the run; say which
    key and where the script was, instead of a traceback."""
    def stopped(exc_type, exc, tb) -> None:
        while tb.tb_next:
            tb = tb.tb_next
        what = f"missing key {exc}" if exc_type is KeyError else f"{exc_type.__name__}: {exc}"
        code = tb.tb_frame.f_code
        print(f"{script} stopped at {Path(code.co_filename).name} line {tb.tb_lineno} ({code.co_name}): {what}. "
              f"A project file lacks a key the editor always writes, or holds a value of another type than the "
              f"editor writes; compare it with a file assets/build_project.py generates, or with an official example.")
        for w in findings.warnings:
            print(f"warning: {w}")
        if findings.errors:
            print("\n".join(findings.errors))
        sys.stdout.flush()
        os._exit(2)     # sys.exit would raise inside the hook and print a second traceback

    sys.excepthook = stopped


def load(path: Path):
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"{path}: not valid JSON, line {e.lineno} column {e.colno}: {e.msg}")


def squash(s: str) -> str:
    """Letters and digits only, lowercased: 'Set animation', 'SetAnimation' and 'set-animation' are one key."""
    return re.sub(r"[\W_]+", "", str(s).lower())


def closest(word: str, options, n: int = 3) -> str:
    """'; closest: a, b' for an error message, or '' when nothing is near."""
    table = {squash(o): o for o in options}
    hits = difflib.get_close_matches(squash(word), list(table), n=n, cutoff=0.6)
    return "; closest: " + ", ".join(table[h] for h in hits) if hits else ""


def describe(cond: dict) -> str:
    return f"{cond.get('objectClass')}:{cond.get('id')}"


def folder_items(folder: dict, prefix: Path = Path()) -> list[tuple[str, Path]]:
    """(name, relative folder) for every item of a project.c3proj folder tree."""
    out = [(name, prefix) for name in folder.get("items", [])]
    for sub in folder.get("subfolders", []):
        out += folder_items(sub, prefix / sub["name"] if sub.get("name") else prefix)
    return out


# --- locate the project and the clone ---------------------------------------------
def above(start: Path, marker: str) -> Path | None:
    """The nearest folder at or above start that holds marker."""
    for folder in (start, *start.parents):
        if (folder / marker).exists():
            return folder
    return None


def find_project(given: str | None) -> Path | None:
    """--project, else the project the current directory is in, else the one
    this copy of the skill is installed in."""
    if given:
        return Path(given).resolve()
    return above(Path.cwd(), "project.c3proj") or above(SKILL_DIR, "project.c3proj")


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


def is_clone(folder: Path) -> bool:
    return (folder / "data" / "c3-schemas" / "_index.json").exists()


def find_rag(root: Path | None, override: str | None) -> Path:
    tried = []
    candidates = [("--rag", override), ("CONSTRUCT3_RAG", os.environ.get("CONSTRUCT3_RAG"))]
    # The project being read, then the one this copy of the skill is installed in:
    # an official example printed from a game project has no instruction file of its own.
    folders = (root, Path.cwd(), above(SKILL_DIR, "project.c3proj"))
    for folder in dict.fromkeys(f for f in folders if f):
        for name in ("CLAUDE.md", "AGENTS.md"):
            f = folder / name
            if f.exists():
                candidates.append((str(f), rag_line(f.read_text(encoding="utf-8"))))
    for source, c in candidates:
        if not c:
            continue
        if is_clone(Path(c)):
            return Path(c)
        tried.append(f"{source}: {c}")
    # Run in place, from <Construct3-RAG>/skills/, the clone is the script's own.
    own = above(SKILL_DIR, "data/c3-schemas/_index.json")
    if own:
        return own
    sys.exit("Construct3-RAG not found. Pass --rag <folder>, set CONSTRUCT3_RAG, or write the line "
             "'- Construct3-RAG: <folder>' in the project's AGENTS.md or CLAUDE.md; the folder is the "
             "one that holds data/c3-schemas/_index.json."
             + ("\nTried " + "; ".join(tried) if tried else ""))


def skill_files(skill_dir: Path) -> dict[str, Path]:
    """The files a copy of the skill consists of, by their path inside it."""
    return {p.relative_to(skill_dir).as_posix(): p for p in sorted(skill_dir.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


def same_text(a: Path, b: Path) -> bool:
    """Line endings aside: a checkout may convert them."""
    return a.read_bytes().replace(b"\r\n", b"\n") == b.read_bytes().replace(b"\r\n", b"\n")


def skill_drift(rag: Path) -> str | None:
    """A sentence when this copy of the skill, installed in a game project, is
    not what the clone holds. The clone is the source; install.py refreshes the copy."""
    source = rag / "skills" / SKILL
    if not (source / "SKILL.md").exists() or source.resolve() == SKILL_DIR:
        return None
    wanted, have = skill_files(source), skill_files(SKILL_DIR)
    changed = [rel for rel, path in wanted.items() if rel not in have or not same_text(path, have[rel])]
    changed += [rel for rel in have if rel not in wanted]
    if not changed:
        return None
    return (f"this copy of the {SKILL} skill differs from the clone's ({', '.join(changed[:4])}"
            f"{' ...' if len(changed) > 4 else ''}); refresh it: "
            f"python \"{source / 'scripts' / 'install.py'}\" --into \"{SKILL_DIR.parent}\"")


def argument_parser(description: str, epilog: str) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=description, epilog=epilog,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", metavar="FOLDER",
                    help="the folder that holds project.c3proj (default: found from the current directory upward)")
    ap.add_argument("--rag", metavar="FOLDER",
                    help="the Construct3-RAG clone (default: CONSTRUCT3_RAG, else the 'Construct3-RAG:' line "
                         "of the project's AGENTS.md or CLAUDE.md)")
    ap.add_argument("--locale", default="en-US",
                    help="schema locale, one of `languages` in data/c3-schemas/_index.json; ids are the same in "
                         "every locale, names and wording differ (default: en-US)")
    return ap


# --- the project ----------------------------------------------------------------------
class Project:
    """project.c3proj, the object types and families it lists, and the schemas
    of the clone. Loading reports what it cannot find to `findings`."""

    def __init__(self, root: Path | None, rag: Path, locale: str, findings: Findings) -> None:
        self.root = root or Path.cwd()
        self.rag = rag
        self.locale = locale
        self.findings = findings
        self.err, self.warn = findings.err, findings.warn
        self.schemas = rag / "data" / "c3-schemas" / locale
        self.data: dict = load(root / "project.c3proj") if root else {}
        self.used_addons = {a["id"]: a for a in self.data.get("usedAddons", [])}
        self.functions_object: str = self.data.get("functionsName", "Functions")

        self._schema_cache: dict[tuple[str, str], dict | None] = {}
        self.index = load(rag / "data" / "c3-schemas" / "_index.json")
        if not self.schemas.is_dir():
            sys.exit(f"no schemas for --locale {locale}; the clone has: {', '.join(self.index.get('languages', []))}")
        self.common = self.schema("plugins", "_common")
        self.system = self.schema("plugins", "system")
        self.system_expression_names = {LOWER(e["translated-name"]) for e in self.system["expressions"]}
        self.system_expressions = self.system_expression_names | {"self", "loopindex", "infinity"}
        self.common_expressions = {LOWER(e["translated-name"]) for e in self.common["expressions"]}

        self.types = self.load_listed("objectTypes")
        self.families = self.load_listed("families")
        self.plugin_of = {n: t["plugin-id"] for n, t in self.types.items()}
        self.plugin_of.update({n: f["plugin-id"] for n, f in self.families.items()})
        self.plugin_of["System"] = "system"
        # the built-in Functions object: Set return value lives in the System schema
        self.plugin_of[self.functions_object] = "system"
        self.objects_lower = {LOWER(n): n for n in self.plugin_of}

    @classmethod
    def open(cls, args: argparse.Namespace, findings: Findings, needs_project: bool = True) -> "Project":
        root = find_project(args.project)
        if root and not (root / "project.c3proj").exists():
            sys.exit(f"no project.c3proj in {root}: --project is the folder the editor saved the project into")
        if root is None and needs_project:
            sys.exit(f"no project.c3proj in {Path.cwd()} or above it; run this from the project folder "
                     f"or pass --project <folder>")
        return cls(root, find_rag(root, args.rag), args.locale, findings)

    # --- files ------------------------------------------------------------------------
    def project_file(self, kind: str, name: str, folder: Path) -> Path | None:
        """The JSON file for a listed item. Older projects keep the files flat even
        when project.c3proj has subfolders, so fall back to a search by name."""
        direct = self.root / kind / folder / f"{name}.json"
        if direct.exists():
            return direct
        hits = [p for p in (self.root / kind).rglob(f"{name}.json") if not p.name.endswith(".uistate.json")]
        return hits[0] if hits else None

    def load_listed(self, kind: str) -> dict[str, dict]:
        out = {}
        for name, folder in folder_items(self.data.get(kind, {})):
            path = self.project_file(kind, name, folder)
            if path is None:
                self.err(f"{kind}: {name} is listed in project.c3proj but has no file")
                continue
            out[name] = load(path)
        return out

    # --- schemas ----------------------------------------------------------------------
    def addon_hint(self, kind: str, addon_id: str) -> str | None:
        """The id the editor uses for what the project calls addon_id, found through
        the display name ('Array' is Arr, '8 Direction' is EightDir) or a near id."""
        ids = self.index.get(kind, {})
        by_name = {}
        for locale in {self.locale, "en-US"}:
            names_file = self.rag / "data" / "c3-schemas" / locale / "_index.json"
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

    def schema(self, kind: str, addon_id: str) -> dict | None:
        key = (kind, addon_id.lower())
        if key not in self._schema_cache:
            path = self.schemas / kind / f"{addon_id.lower()}.json"
            self._schema_cache[key] = load(path) if path.exists() else None
            if self._schema_cache[key] is None:
                # An addon the project lists under another author is a third-party one: no schema, no hint.
                third_party = self.used_addons.get(addon_id, {}).get("author", "Scirra") != "Scirra"
                hint = None if third_party else self.addon_hint(kind, addon_id)
                if hint:
                    self.err(f"{kind[:-1]} id {addon_id!r} does not exist: the editor's id is {hint!r}")
                else:
                    self.warn(f"no schema for {kind[:-1]} {addon_id}: its ACEs and properties are not checked")
        return self._schema_cache[key]

    # --- object types and families ----------------------------------------------------
    def families_of(self, obj: str) -> list[str]:
        return [f for f, d in self.families.items() if obj in d.get("members", [])]

    def ivar_types_of(self, obj: str) -> dict[str, str]:
        """instance variable name -> type, family variables included for member types."""
        ivars = {}
        if obj in self.types:
            ivars.update({v["name"]: v["type"] for v in self.types[obj].get("instanceVariables", [])})
            for f in self.families_of(obj):
                ivars.update({v["name"]: v["type"] for v in self.families[f].get("instanceVariables", [])})
        if obj in self.families:
            ivars.update({v["name"]: v["type"] for v in self.families[obj].get("instanceVariables", [])})
        return ivars

    def ivars_of(self, obj: str) -> set[str]:
        return set(self.ivar_types_of(obj))

    def behaviors_of(self, obj: str) -> dict[str, str]:
        """behavior name -> behavior id, family behaviors included for member types."""
        names = {}
        if obj in self.types:
            for b in self.types[obj].get("behaviorTypes", []):
                names[b["name"]] = b["behaviorId"]
            for f in self.families_of(obj):
                for b in self.families[f].get("behaviorTypes", []):
                    names[b["name"]] = b["behaviorId"]
        if obj in self.families:
            for b in self.families[obj].get("behaviorTypes", []):
                names[b["name"]] = b["behaviorId"]
        return names

    def animations_of(self, obj: str) -> set[str] | None:
        """Animation names of a Sprite type, or the union over a family's members. None: not a Sprite."""
        def walk(folder):
            out = {LOWER(a["name"]) for a in folder.get("items", [])}
            for sub in folder.get("subfolders", []):
                out |= walk(sub)
            return out
        if obj in self.types and "animations" in self.types[obj]:
            return walk(self.types[obj]["animations"])
        if obj in self.families:
            members = [m for m in self.families[obj].get("members", [])
                       if m in self.types and "animations" in self.types[m]]
            return set().union(*(walk(self.types[m]["animations"]) for m in members)) if members else None
        return None

    # --- conditions and actions -------------------------------------------------------
    def ace_sources(self, ace: dict) -> list[dict]:
        """The schemas an ACE is looked up in: the named behavior's, or the plugin's
        and then the shared world-object one. Empty when the object, the behavior or
        its schema is unknown."""
        obj = ace.get("objectClass")
        if obj not in self.plugin_of:
            return []
        if "behaviorType" in ace:
            behavior_id = self.behaviors_of(obj).get(ace["behaviorType"])
            own = self.schema("behaviors", behavior_id) if behavior_id else None
            return [own] if own else []
        own = self.schema("plugins", self.plugin_of[obj])
        if own is None:
            return []       # a third-party plugin: its own ACEs cannot be told from a wrong id
        return [own] if obj == "System" else [own, self.common]

    def ace_entry(self, kind: str, ace: dict) -> dict | None:
        return next((it for s in self.ace_sources(ace) for it in s.get(kind, []) if it["id"] == ace.get("id")), None)
