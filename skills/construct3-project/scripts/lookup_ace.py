"""Look up conditions, actions and expressions, with the JSON to write.

    python scripts/lookup_ace.py OBJECT [WORD ...] [--project FOLDER] [--rag FOLDER] [--locale en-US]

OBJECT is an object type or family of the project, which searches its plugin,
the ACEs every world object shares and its behaviors under the names they
have on the object; `System`; or a plugin or behavior by id or display name
("8 Direction"), which needs no project. Every WORD must occur in the id, the
list name or the script name, or name where the ACE lives: the behavior, the
addon, `condition`, `action` or `expression`.

The schema files run to thousands of lines, more than most tools read at
once, and an ACE below the cut looks as if it did not exist; this prints the
part that was asked for. Six matches or fewer print in full, each parameter
with the way it is written; more print one line each.
"""
import json
import sys

import c3project as c3
from c3project import LOWER, closest, squash

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


def ace_lookup(p: c3.Project, target: str, words: list[str]) -> None:
    """Sources of a project object are its plugin, the shared world-object ACEs
    and its behaviors under the names they have on the object; of anything
    else, the plugin or behavior with that id or display name."""
    sources: list[tuple[str, str | None, dict]] = []      # (objectClass to write, behaviorType, schema)
    obj = p.objects_lower.get(LOWER(target))
    if obj == "System" or LOWER(target) == "system":
        sources.append(("System", None, p.system))
    elif obj:
        sources.append((obj, None, p.schema("plugins", p.plugin_of[obj]) or {}))
        if "singleglobal-inst" not in p.types.get(obj, {}):     # Keyboard, Touch, Audio: nothing of a world object
            sources.append((obj, None, p.common))
        sources += [(obj, name, p.schema("behaviors", b) or {}) for name, b in p.behaviors_of(obj).items()]
    else:
        for kind in ("plugins", "behaviors"):
            addon = target if LOWER(target) in p.index.get(kind, {}) else p.addon_hint(kind, target)
            if addon and LOWER(addon) != "_common":
                behavior = "<behavior name on the object>" if kind == "behaviors" else None
                sources.append(("<object>", behavior, p.schema(kind, addon) or {}))
                break
    if not sources:
        sys.exit(f"{target!r} is not an object of this project, System, or a plugin or behavior"
                 + closest(target, list(p.plugin_of) + list(p.index["plugins"]) + list(p.index["behaviors"])))

    kinds = ("conditions", "actions", "expressions")
    found = []
    for owner, behavior, s in sources:
        for kind in kinds:
            for it in s.get(kind, []):
                # A word may also name where the ACE lives: the behavior, the addon, "condition".
                hay = squash(" ".join([*(str(it.get(k, "")) for k in ("id", "list-name", "translated-name", "scriptName")),
                                       behavior or "", s.get("id", ""), s.get("name", ""), kind]))
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


def main() -> int:
    ap = c3.argument_parser(
        "Look up conditions, actions and expressions of an object of the project, of System, or of a plugin or "
        "behavior by id or display name, and print each with its parameters and the JSON to write. Use it "
        "instead of reading plugins/system.json or plugins/_common.json, which are longer than most tools read.",
        "examples:\n"
        "  python scripts/lookup_ace.py Coin tween two         an object of the project: plugin, shared ACEs, behaviors\n"
        "  python scripts/lookup_ace.py System wait\n"
        "  python scripts/lookup_ace.py \"8 Direction\" speed    a plugin or behavior by id or display name\n"
        "  python scripts/lookup_ace.py Coin tween condition   a word may be condition, action or expression\n\n"
        "exit codes: 0 found, 1 nothing matches (the nearest ids are listed) or the clone was not found")
    ap.add_argument("object", metavar="OBJECT",
                    help="an object type or family of the project, System, or a plugin or behavior id or display name")
    ap.add_argument("words", nargs="*", metavar="WORD",
                    help="every word must occur in the id, the list name or the script name, or name the "
                         "behavior, the addon, or the kind: condition, action, expression")
    args = ap.parse_args()
    findings = c3.Findings()
    c3.stop_with_a_sentence("lookup_ace.py", findings)
    project = c3.Project.open(args, findings, needs_project=False)
    drift = c3.skill_drift(project.rag)
    if drift:
        print(f"note: {drift}", file=sys.stderr)
    ace_lookup(project, args.object, args.words)
    return 0


if __name__ == "__main__":
    sys.exit(main())
