"""Look up conditions, actions and expressions, with the JSON to write.

    python scripts/lookup_ace.py OBJECT [WORD ...] [--limit CHARS] [--project FOLDER] [--rag FOLDER]
                                 [--locale en-US]

OBJECT is an object type or family of the project, which searches its plugin,
the ACEs every world object shares and its behaviors under the names they
have on the object; `System`; or a plugin or behavior by id or display name
("8 Direction"), which needs no project. Every WORD must occur in the id, the
list name or the script name, or name where the ACE lives: the behavior, the
addon, its category (`time`, `loops`, `size-position`), `condition`, `action`
or `expression`. A word is matched as written, not by meaning: `every`,
`seconds` or the category `time` finds *Every X seconds*, `timer` does not.

The schema files run to thousands of lines, more than most tools read at
once, and an ACE below the cut looks as if it did not exist; this prints the
part that was asked for. Six matches or fewer print in full, each parameter
with the way it is written; more print one line each, and more than fit
--limit print as counts per category. When no entry has every word, the
entries that have some of them are listed.
"""
import json
import sys

import c3project as c3
from c3project import LOWER, closest, squash

KINDS = ("conditions", "actions", "expressions")

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


def sources_of(p: c3.Project, target: str) -> list[tuple[str, str | None, dict]]:
    """(objectClass to write, behaviorType, schema). Of a project object: its
    plugin, the shared world-object ACEs and its behaviors under the names they
    have on the object. Of anything else: the plugin or behavior with that id
    or display name, spelled as it is apart from case, spaces and punctuation.
    A near name is not taken for it: `Platform` would read as Platform Info."""
    obj = p.objects_lower.get(LOWER(target))
    if obj == "System" or LOWER(target) == "system":
        return [("System", None, p.system)]
    if obj:
        sources = [(obj, None, p.schema("plugins", p.plugin_of[obj]) or {})]
        if "singleglobal-inst" not in p.types.get(obj, {}):     # Keyboard, Touch, Audio: nothing of a world object
            sources.append((obj, None, p.common))
        return sources + [(obj, name, p.schema("behaviors", b) or {}) for name, b in p.behaviors_of(obj).items()]
    sources = []
    for kind in ("plugins", "behaviors"):
        addon = p.addon_names(kind).get(squash(target))
        if addon and addon != "_common":
            behavior = "<behavior name on the object>" if kind == "behaviors" else None
            sources.append(("<object>", behavior, p.schema(kind, addon) or {}))
    if not sources:
        names = [v.get("name", k) for kind in ("plugins", "behaviors")
                 for k, v in c3.load(p.schemas / "_index.json").get(kind, {}).items()]
        sys.exit(f"{target!r} is not an object of this project, System, or the id or display name of a plugin or "
                 f"behavior" + closest(target, [*p.plugin_of, *names, *p.index["plugins"], *p.index["behaviors"]]))
    return sources


def brief(owner: str, behavior: str | None, addon: str, kind: str, it: dict) -> str:
    title = it.get("list-name") or it.get("translated-name")
    via = f" [behavior {behavior}, {addon}]" if behavior else f" [{addon}]"
    params = it.get("params") or {}
    return f"{kind[:-1]:<10} {it['id']:<34} {title}{via}" + (f"  ({', '.join(params)})" if params else "")


def in_full(owner: str, behavior: str | None, addon: str, kind: str, it: dict) -> list[str]:
    title = it.get("list-name") or it.get("translated-name")
    flags = [f for f in ("isTrigger", "isLooping", "isAsync") if it.get(f)] + \
            (["not invertible"] if it.get("isInvertible") is False else [])
    via = f" [behavior {behavior}, {addon}]" if behavior else f" [{addon}]"
    params = it.get("params") or {}
    lines = [f"{kind[:-1]} {it['id']} - {title}{via}" + (f"  <{', '.join(flags)}>" if flags else ""),
             f"  {it.get('description', '')}"]
    if kind == "expressions":
        call = f"({', '.join(params)})" if params else ""
        path = f"{owner}.{behavior}." if behavior else ("" if owner == "System" else f"{owner}.")
        lines.append(f"  write: {path}{it['translated-name']}{call}  -> {it.get('returnType', 'any')}")
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
        lines.append("  write: " + head + (f', "parameters": {{{body}}}}}' if params else "}"))
    for key, spec in params.items():
        how = " | ".join(spec["items"]) if spec.get("items") \
            else WRITING.get(spec["type"], ("", "expression string"))[1]
        lines.append(f"    {key:<22} {spec['type']:<10} {how}")
    return lines


def ace_lookup(p: c3.Project, target: str, words: list[str], limit: int) -> int:
    sources = sources_of(p, target)
    entries = []        # (its names, its names and category, owner, behavior, addon, kind, entry)
    for owner, behavior, s in sources:
        for kind in KINDS:
            for it in s.get(kind, []):
                # A word may also name where the ACE lives: the behavior, the addon, "condition".
                names = squash(" ".join([*(str(it.get(k, "")) for k in ("id", "list-name", "translated-name", "scriptName")),
                                         behavior or "", s.get("id", ""), s.get("name", ""), kind]))
                entries.append((names, names + " " + squash(it.get("category", "")), owner, behavior, s.get("id", ""), kind, it))
    if not entries:
        sys.exit(f"the clone has no schema for {target}, a third-party addon: nothing to look up")
    # By name first, so that a category which shares a word with a name does not
    # turn six entries printed in full into a list: `Physics force` is the three
    # Apply force actions, and the rest of the category `forces` is named below them.
    named = [all(squash(w) in e[0] for w in words) for e in entries]
    wider = [all(squash(w) in e[1] for w in words) for e in entries]
    found = [e[2:] for e, n in zip(entries, named) if n]
    by_category = [e[2:] for e, n, w in zip(entries, named, wider) if w and not n]
    if not found or len(found) > 6:
        found, by_category = [e[2:] for e, w in zip(entries, wider) if w], []

    if not found:
        # The most words first, a word in a name before a word in a category.
        some = sorted(((sum(squash(w) in e[0] for w in words), sum(squash(w) in e[1] for w in words), e[2:])
                       for e in entries), key=lambda x: (-x[0], -x[1]))
        some = [e for _, n, e in some if n]
        entries = [e[1:] for e in entries]
        print(f"nothing under {target} has every word of {' '.join(words)!r}", file=sys.stderr)
        if some:
            print("entries with some of them, the most first:", file=sys.stderr)
            for e in some[:12]:
                print("  " + brief(*e), file=sys.stderr)
            if len(some) > 12:
                print(f"  ... and {len(some) - 12} more", file=sys.stderr)
        else:
            near = closest(" ".join(words), [e[5]["id"] for e in entries], n=6)
            categories = sorted({e[5].get("category", "") for e in entries} - {""})
            print((near.lstrip("; ") + "\n" if near else "") + f"categories, each a word too: {', '.join(categories)}",
                  file=sys.stderr)
        return 1

    if len(found) <= 6:
        for e in found:
            print("\n".join(in_full(*e)))
        if by_category:
            print(f"by category, not by name: {', '.join(e[4]['id'] for e in by_category[:20])}"
                  + (" ..." if len(by_category) > 20 else ""))
        return 0
    lines = [brief(*e) for e in found]
    if c3.fitting(lines, limit) == len(lines):
        print("\n".join(lines))
        print(f"{len(found)} entries; add a word to narrow them, six or fewer print with the JSON to write")
        return 0
    print(f"{len(found)} entries, more than fit {limit} characters (--limit). Entries per category:")
    for kind in KINDS:
        counts: dict[str, int] = {}
        for _, behavior, addon, its_kind, it in found:
            if its_kind == kind:
                where = it.get("category") or behavior or addon     # a behavior's own ACEs carry no category
                counts[where] = counts.get(where, 0) + 1
        if counts:
            print(f"  {kind:<12} " + ", ".join(f"{name} {n}" for name, n in counts.items()))
    behaviors = list(dict.fromkeys(b for _, b, _ in sources if b and not b.startswith("<")))
    if behaviors:
        print(f"  behaviors    {', '.join(behaviors)}")
    print("add a word: a category, a behavior, condition, action or expression, or part of a name; "
          "six entries or fewer print with the JSON to write")
    return 0


def main() -> int:
    ap = c3.argument_parser(
        "Look up conditions, actions and expressions of an object of the project, of System, or of a plugin or "
        "behavior by id or display name, and print each with its parameters and the JSON to write. Use it "
        "instead of reading plugins/system.json or plugins/_common.json, which are longer than most tools read.",
        "examples:\n"
        "  python scripts/lookup_ace.py Coin tween two         an object of the project: plugin, shared ACEs, behaviors\n"
        "  python scripts/lookup_ace.py System wait\n"
        "  python scripts/lookup_ace.py System time            a category: Every X seconds, Wait, dt, time ...\n"
        "  python scripts/lookup_ace.py \"8 Direction\" speed    a plugin or behavior by id or display name\n"
        "  python scripts/lookup_ace.py Coin tween condition   a word may be condition, action or expression\n\n"
        "exit codes: 0 found, 1 no entry has every word (those with some are listed), OBJECT is unknown (the\n"
        "nearest names are listed), or the clone was not found")
    ap.add_argument("object", metavar="OBJECT",
                    help="an object type or family of the project, System, or a plugin or behavior id or display name")
    ap.add_argument("words", nargs="*", metavar="WORD",
                    help="every word must occur in the id, the list name or the script name, or name the "
                         "behavior, the addon, the category, or the kind: condition, action, expression")
    args = ap.parse_args()
    c3.utf8_output()
    findings = c3.Findings()
    c3.stop_with_a_sentence("lookup_ace.py", findings)
    project = c3.Project.open(args, findings, needs_project=False)
    drift = c3.skill_drift(project.rag)
    if drift:
        print(f"note: {drift}", file=sys.stderr)
    return ace_lookup(project, args.object, args.words, args.limit)


if __name__ == "__main__":
    sys.exit(main())
