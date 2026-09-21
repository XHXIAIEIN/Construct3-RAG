"""Print an event sheet as the editor words it, under the editor's event numbers.

    python scripts/print_sheet.py [SHEET ...] [--outline] [--project FOLDER] [--rag FOLDER] [--locale en-US]

Conditions and actions are worded from the schema's display-text, in the
locale of --locale, at about a quarter of the JSON's length. It reads any
folder project, an official example included.

A row's number is the count of blocks, groups, function blocks and custom
action blocks before it in the sheet, sub-events included, plus one: the
number in the editor's margin and in its Find results. A variable, comment
or include takes no number of its own and belongs to the next one.
--outline prints the numbering alone, with the sid of each event, which is
the string to search the sheet's JSON for.
"""
import re
import sys

import c3project as c3
from c3project import NUMBERED, describe

COMPARISONS = ("=", "≠", "<", "≤", ">", "≥")


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


def wording(p: c3.Project, kind: str, ace: dict) -> str:
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
    entry = p.ace_entry(kind, ace) if obj in p.plugin_of else None
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


def print_sheet(p: c3.Project, events: list, counter: list[int], depth: int = 0, top: bool = True) -> None:
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
                params = ", ".join(f"{fp['name']}: {fp['type']}" for fp in ev.get("functionParameters", []))
                returns = ev.get("functionReturnType", "none")
                head.append(f"{'function' if et == 'function-block' else 'custom action'} {name}({params})"
                            + (f" -> {returns}" if returns != "none" else "")
                            + (" [copy picked]" if ev.get("functionCopyPicked") else ""))
            head += [wording(p, "conditions", c) for c in ev.get("conditions", [])]
            joiner = "OR " if ev.get("isOrBlock") else ""
            for i, line in enumerate(head or ["(every tick)"]):
                print(f"{number if i == 0 else '     '}{pad}{joiner if i else ''}{line}"
                      + (" [disabled]" if ev.get("disabled") and i == 0 else ""))
            for a in ev.get("actions", []):
                print(f"     {pad}    -> {wording(p, 'actions', a)}")
        print_sheet(p, ev.get("children", []), counter, depth + 1, top=False)


def main() -> int:
    ap = c3.argument_parser(
        "Print event sheets as the editor words them: numbered events, conditions, actions. Read a sheet this "
        "way before and after an edit, and read an official example this way instead of its JSON.",
        "examples:\n"
        "  python scripts/print_sheet.py Game\n"
        "  python scripts/print_sheet.py --outline Game        numbers and sids, to find the JSON behind a number\n"
        "  python scripts/print_sheet.py --project <Construct-Example-Projects>/example-projects/template-snake\n"
        "  python scripts/print_sheet.py Game --locale zh-CN   the editor's Chinese wording\n\n"
        "exit codes: 0 printed, 1 no such sheet or project/clone not found, 2 a sheet lacks a key the editor writes")
    ap.add_argument("sheets", nargs="*", metavar="SHEET", help="event sheet names (default: every sheet)")
    ap.add_argument("--outline", action="store_true",
                    help="print the event numbering with each event's sid, without conditions and actions")
    args = ap.parse_args()
    findings = c3.Findings()
    c3.stop_with_a_sentence("print_sheet.py", findings)
    project = c3.Project.open(args, findings)
    drift = c3.skill_drift(project.rag)
    if drift:
        print(f"note: {drift}", file=sys.stderr)

    sheets = project.load_listed("eventSheets")
    for name in args.sheets:
        if name not in sheets:
            sys.exit(f"no event sheet named {name!r}; sheets: {', '.join(sheets)}")
    for name in args.sheets or sheets:
        print(f"== {name}")
        if args.outline:
            outline(sheets[name]["events"], [0])
        else:
            print_sheet(project, sheets[name]["events"], [0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
