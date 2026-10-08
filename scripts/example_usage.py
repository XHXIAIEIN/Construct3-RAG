#!/usr/bin/env python3
"""Index which official examples use each condition, action and expression.

    python scripts/example_usage.py                   from the Construct-Example-Projects clone beside this repository
    python scripts/example_usage.py --clone FOLDER    from a clone elsewhere

Reads the event sheets of every project in the clone's example-projects/ and
writes data/c3-example-usage/: one file per plugin and behavior that an
example uses, and _source.json with the clone's commit. For each ACE a file
gives how many examples use it and where to read up to three of them: the
example's folder, the sheet, and the first and last event of the use as
print_sheet.py numbers them, the smallest sheets first. An ACE is keyed by
the id of its plugin or behavior, not by the object's name; the ACEs every
world object shares are under _common, as in the schemas. An expression is
counted where an expression parameter writes it: Player.X, Player.Platform.Speed
or a System expression such as random(1, 5).

The index is read offline by the skill's lookup_ace.py. It is rebuilt from the
clone only, so the same commit gives the same files; scripts/init.py runs it
after the CDN export, and without a clone it keeps the committed index.

exit codes: 0 written or kept, 1 the clone was not found
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "construct3-agent-plugin" / "scripts"))
import c3project as c3  # noqa: E402

OUT = ROOT / "data" / "c3-example-usage"
KINDS = ("conditions", "actions", "expressions")
SHOWN = 3           # the uses kept per ACE, the ones lookup_ace.py prints
SPAN = 8            # the most events of one use printed: the event and its first sub-events
# Parameter types written as an expression string (lookup_ace.py, WRITING); the others are names or ids
EXPRESSION_TYPES = {"number", "string", "any", "layer", "animation", "groupname", "template", "objecteffect",
                    "layereffect", "layouteffect", "objectinsttags", "objectname", "model3d-animation-string"}
MEMBER = re.compile(r"(\w+)(?:\([^()]*\))?\s*\.\s*(\w+)(?:\s*\.\s*(\w+))?")
IDENT = re.compile(r"\w+")
NUMBER = re.compile(r"\d+(\.\d+)?(e[+-]?\d+)?", re.I)


def descendants(ev: dict) -> int:
    """The numbered events inside ev, sub-events of sub-events included."""
    return sum(1 for _ in c3.numbered_events(ev.get("children", [])))


def variables(events: list) -> set[str]:
    """The names of every variable and function parameter the events declare, lower case:
    an identifier with one of these names is the variable, not a System expression."""
    out = set()
    for ev in events:
        if ev.get("eventType") == "variable":
            out.add(c3.LOWER(ev.get("name", "")))
        out |= {c3.LOWER(param["name"]) for param in ev.get("functionParameters", [])
                if isinstance(param, dict) and param.get("name")}
        out |= variables(ev.get("children", []))
    return out


class Example:
    """One example project and the keys of the ACEs its sheets use."""

    def __init__(self, folder: Path, rag: Path) -> None:
        self.folder = folder
        self.p = c3.Project(folder, rag, "en-US", c3.Findings())
        self._written: dict[tuple[str, str], dict[str, str]] = {}

    def key(self, kind: str, ace: dict) -> tuple[str, str, str, str] | None:
        """(plugins or behaviors, addon id, kind, ACE id) of a condition or action; None when
        no schema has it: a third-party addon, or an ACE the schema left out."""
        for schema in self.p.ace_sources(ace):
            if any(it["id"] == ace.get("id") for it in schema.get(kind, [])):
                return f"{schema['type']}s", schema["id"], kind, ace["id"]
        return None

    def expression_ids(self, schema: dict, part: dict | None = None) -> dict[str, str]:
        """Written name, lower case -> ACE id of the expressions of schema, or of part of it."""
        names = self.p.expression_names(schema)
        allowed = {it["id"] for it in (part or schema).get("expressions", [])}
        return {c3.LOWER(name): ace for ace, name in names.items() if ace in allowed}

    def expressions(self, expr: str, scope: set[str]) -> set[tuple[str, str, str, str]]:
        """The keys of the expressions an expression string calls."""
        p = self.p
        text = c3.STRING_LITERAL.sub('""', expr)
        out = set()
        for m in MEMBER.finditer(text):
            obj = p.objects_lower.get(c3.LOWER(m.group(1)))
            if obj is None or obj == "System" or c3.LOWER(obj) == c3.LOWER(p.functions_object):
                continue
            member, sub = c3.LOWER(m.group(2)), c3.LOWER(m.group(3) or "")
            behaviors = {c3.LOWER(k): v for k, v in p.behaviors_of(obj).items()}
            if member in behaviors:
                schema = p.schema("behaviors", behaviors[member])
                ace = self.expression_ids(schema).get(sub) if schema else None
                if ace:
                    out.add(("behaviors", schema["id"], "expressions", ace))
                continue
            plugin = p.schema("plugins", p.plugin_of[obj])
            if plugin is None or member in {c3.LOWER(v) for v in p.ivars_of(obj)}:
                continue
            ace = self.expression_ids(plugin).get(member)
            if ace:
                out.add(("plugins", plugin["id"], "expressions", ace))
            elif p.common and (ace := self.expression_ids(p.common, p.common_of(plugin)).get(member)):
                out.add(("plugins", "_common", "expressions", ace))
        system = self.expression_ids(p.system)
        for m in IDENT.finditer(text):
            name = c3.LOWER(m.group(0))
            if NUMBER.fullmatch(name) or name in scope:
                continue
            if text[:m.start()].rstrip().endswith(".") or text[m.end():].lstrip().startswith("."):
                continue
            if name in system:
                out.add(("plugins", "system", "expressions", system[name]))
        return out

    def uses(self, events: list, scope: set[str]) -> dict[tuple[str, str, str, str], tuple[int, int]]:
        """Key -> (first, last) event of its first use in a sheet: the event and its sub-events, at most SPAN.
        scope: the variable names of the project, whose sheets see each other's global variables."""
        found: dict[tuple[str, str, str, str], tuple[int, int]] = {}
        for n, ev in enumerate(c3.numbered_events(events), 1):
            keys: set[tuple[str, str, str, str]] = set()
            for kind in ("conditions", "actions"):
                for ace in ev.get(kind, []):
                    if not isinstance(ace, dict):
                        continue
                    if "callFunction" in ace:
                        values = ace.get("parameters", [])
                    elif "id" in ace:
                        key = self.key(kind, ace)
                        if key:
                            keys.add(key)
                        entry = self.p.ace_entry(kind, ace) or {}
                        given = ace.get("parameters", {}) if isinstance(ace.get("parameters"), dict) else {}
                        values = [v for k, v in given.items()
                                  if (entry.get("params") or {}).get(k, {}).get("type") in EXPRESSION_TYPES]
                    else:
                        continue
                    for value in values:
                        if isinstance(value, str):
                            keys |= self.expressions(value, scope)
            for key in keys:
                found.setdefault(key, (n, n + min(descendants(ev), SPAN - 1)))
        return found

    def sheets(self) -> dict[str, list]:
        """Sheet name -> its events, as project.c3proj lists the sheets."""
        out = {}
        for name, path in self.p.listed_files("eventSheets").items():
            if path is not None:
                data = c3.load(path)
                if isinstance(data, dict):
                    out[name] = data.get("events", [])
        return out


def build(clone: Path, rag: Path = ROOT) -> dict[str, dict]:
    """File name under data/c3-example-usage/ -> its content, from the example projects of clone."""
    projects = clone / "example-projects"
    # key -> [(sheet size, folder, sheet, first, last)], one per example: its smallest sheet that uses it
    uses: dict[tuple[str, str, str, str], list[tuple[int, str, str, int, int]]] = {}
    examples = 0
    for folder in sorted(f for f in projects.iterdir() if (f / "project.c3proj").is_file()):
        # An example written in both languages is two folders, <id>-js and <id>-ts, with the same events.
        if folder.name.endswith("-ts") and (projects / f"{folder.name[:-3]}-js" / "project.c3proj").is_file():
            continue
        example = Example(folder, rag)
        best: dict[tuple[str, str, str, str], tuple[int, str, str, int, int]] = {}
        sheets = example.sheets()
        scope = set().union(*map(variables, sheets.values()))
        for sheet, events in sheets.items():
            size = sum(1 for _ in c3.numbered_events(events))
            for key, (first, last) in example.uses(events, scope).items():
                use = (size, folder.name, sheet, first, last)
                if key not in best or use < best[key]:
                    best[key] = use
        examples += 1
        for key, use in best.items():
            uses.setdefault(key, []).append(use)
    files: dict[str, dict] = {}
    for (addon_kind, addon, kind, ace), found in sorted(uses.items()):
        found.sort()
        entry = {"examples": len(found), "read": [list(use[1:]) for use in found[:SHOWN]]}
        files.setdefault(f"{addon_kind}/{addon}.json", {}).setdefault(kind, {})[ace] = entry
    files["_source.json"] = {"clone": c3.EXAMPLES_CLONE, "commit": commit_of(clone), "examples": examples}
    return files


def commit_of(clone: Path) -> str | None:
    try:
        p = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"], capture_output=True, text=True,
                           timeout=30, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout.strip() or None


def dump(content: dict) -> str:
    """One ACE per line: a diff between two clones shows the ACEs whose uses changed."""
    if "examples" in content and "clone" in content:
        return json.dumps(content, indent=2) + "\n"
    lines = ["{"]
    kinds = [k for k in KINDS if k in content]
    for i, kind in enumerate(kinds):
        lines.append(f'  "{kind}": {{')
        aces = content[kind]
        for j, (ace, entry) in enumerate(aces.items()):
            lines.append(f"    {json.dumps(ace)}: {json.dumps(entry, ensure_ascii=False)}"
                         + ("," if j < len(aces) - 1 else ""))
        lines.append("  }" + ("," if i < len(kinds) - 1 else ""))
    lines.append("}")
    return "\n".join(lines) + "\n"


def write(files: dict[str, dict], out: Path = OUT) -> None:
    """Replace out with files: an addon no example uses any more leaves the index."""
    stage = out.with_name(f".{out.name}-staging")
    shutil.rmtree(stage, ignore_errors=True)
    for name, content in files.items():
        path = stage / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(dump(content).encode("utf-8"))
    shutil.rmtree(out, ignore_errors=True)
    stage.rename(out)


def refresh(clone: Path | None = None, out: Path = OUT) -> str:
    """Rebuild the index from clone, the sibling clone by default; what happened, in a sentence."""
    clone = clone or c3.siblings_folder(ROOT) / c3.EXAMPLES_CLONE
    if not (clone / "example-projects").is_dir():
        return (f"no {c3.EXAMPLES_CLONE} clone at {clone}: kept the committed index; "
                f"{c3.examples_clone_command(ROOT)} clones it")
    files = build(clone)
    write(files, out)
    source = files["_source.json"]
    return (f"{source['examples']} examples at {str(source['commit'])[:12]}, "
            f"{sum(len(f.get(k, {})) for f in files.values() for k in KINDS)} ACEs in {len(files) - 1} files")


def main() -> int:
    ap = argparse.ArgumentParser(description="Index which official examples use each condition, action and "
                                             "expression, into data/c3-example-usage/")
    ap.add_argument("--clone", type=Path, help=f"the {c3.EXAMPLES_CLONE} clone (default: beside this repository)")
    args = ap.parse_args()
    if args.clone and not (args.clone / "example-projects").is_dir():
        sys.exit(f"no example-projects folder in {args.clone}")
    print(f"data/c3-example-usage/: {refresh(args.clone)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
