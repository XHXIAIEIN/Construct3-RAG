"""Print an event sheet as the editor words it, under the editor's event numbers.

    python scripts/print_sheet.py [SHEET ...] [--events A-B] [--outline] [--show N] [--limit CHARS]
                                  [--project FOLDER] [--rag FOLDER] [--locale en-US]

Conditions and actions are worded from the schema's display-text, in the
locale of --locale, at about a quarter of the JSON's length. It reads any
folder project, an official example included.

A row's number is the count of blocks, groups, function blocks and custom
action blocks before it in the sheet, sub-events included, plus one: the
number in the editor's margin and in its Find results. A variable, comment
or include takes no number of its own and belongs to the next one.
--outline prints the numbering alone, with the sid of each event, which is
the string to search the sheet's JSON for. --show N prints one event as
JSON, for a plan of edit_sheet.py that puts it back changed.

A harness cuts long tool output, so printing stops at --limit characters, at
an event, and the last line gives the --events range that continues. A part
printed with --events starts with the events it sits in, marked [context]
and without their actions. Without a sheet name, a project whose sheets do
not fit the limit prints the list of its sheets instead.
"""
import json
import re
import sys
from typing import Iterator, NamedTuple

import c3project as c3
from c3project import NUMBERED, describe

COMPARISONS = ("=", "≠", "<", "≤", ">", "≥")


class Row(NamedTuple):
    number: int         # the editor's number; a variable, comment or include carries the next numbered row's
    head: list[str]     # the row as printed; of a block, the function line and the conditions
    body: list[str]     # the actions of a block
    above: tuple        # the rows this one sits in, outermost first


def outline_rows(events: list, counter: list[int], above: tuple = ()) -> Iterator[Row]:
    depth = len(above)
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
            row = Row(counter[0], [f"{counter[0]:>4} {'  ' * depth}{text}{sid}"], [], above)
        else:
            row = Row(counter[0] + 1, [f"{f'({counter[0] + 1})':>6} {'  ' * depth}{text}{sid}"], [], above)
        yield row
        yield from outline_rows(ev.get("children", []), counter, (*above, row))


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


def sheet_rows(p: c3.Project, events: list, counter: list[int], above: tuple = ()) -> Iterator[Row]:
    """The sheet as the editor shows it, with the editor's event numbers."""
    pad = "  " * len(above)
    for ev in events:
        et = ev.get("eventType")
        if et in NUMBERED:
            counter[0] += 1
        number = f"{counter[0]:>4} " if et in NUMBERED else "     "
        head, body = [], []
        if et == "variable":
            kind = ("local" if above else "global") + (" constant" if ev.get("isConstant") else "") \
                   + (" static" if ev.get("isStatic") else "")
            head = [f"{number}{pad}{kind} {ev['type']} {ev['name']} = {ev.get('initialValue', '')}"]
        elif et == "comment":
            head = [f"{number}{pad}// {line}" for line in ev.get("text", "").split("\n")]
        elif et == "include":
            head = [f"{number}{pad}include {ev.get('includeSheet', '')}"]
        elif et == "script":
            head = [f"{number}{pad}script, {len(ev.get('script', []))} lines"]
        elif et == "group":
            head = [f"{number}{pad}group {ev.get('title', '')}"
                    + ("" if ev.get("isActiveOnStart", True) else " (inactive on start)")]
        else:
            lines = []
            if et in ("function-block", "custom-ace-block"):
                name = ev.get("functionName") or f"{ev.get('objectClass')}.{ev.get('aceName')}"
                params = ", ".join(f"{fp['name']}: {fp['type']}" for fp in ev.get("functionParameters", []))
                returns = ev.get("functionReturnType", "none")
                lines.append(f"{'function' if et == 'function-block' else 'custom action'} {name}({params})"
                             + (f" -> {returns}" if returns != "none" else "")
                             + (" [copy picked]" if ev.get("functionCopyPicked") else ""))
            lines += [wording(p, "conditions", c) for c in ev.get("conditions", [])]
            joiner = "OR " if ev.get("isOrBlock") else ""
            head = [f"{number if i == 0 else '     '}{pad}{joiner if i else ''}{line}"
                    + (" [disabled]" if ev.get("disabled") and i == 0 else "")
                    for i, line in enumerate(lines or ["(every tick)"])]
            body = [f"     {pad}    -> {wording(p, 'actions', a)}" for a in ev.get("actions", [])]
        row = Row(counter[0] if et in NUMBERED else counter[0] + 1, head, body, above)
        yield row
        yield from sheet_rows(p, ev.get("children", []), counter, (*above, row))


def part(rows: list[Row], first: int, last: int | None, room: int | None) -> tuple[list[str], int | None]:
    """The lines of the rows numbered first to last, the first of them under the
    heads of the rows it sits in, cut before the row that would pass room
    characters. Returns the lines and the number printing stopped before."""
    lines: list[str] = []
    shown: set[int] = set()
    used = 0
    for row in rows:
        if row.number < first or (last is not None and row.number > last):
            continue
        new = [line + ("  [context]" if i == 0 else "") for a in row.above if id(a) not in shown
               for i, line in enumerate(a.head)] + row.head + row.body
        used += sum(len(line) + 1 for line in new)
        if room is not None and lines and used > room:
            return lines, row.number
        shown.update(id(a) for a in (*row.above, row))
        lines += new
    return lines, None


def events_range(spec: str | None) -> tuple[int, int | None]:
    if spec is None:
        return 1, None
    m = re.fullmatch(r"(\d*)(-?)(\d*)", spec.strip())
    if not m or not (m.group(1) or m.group(3)):
        sys.exit(f"--events takes the editor's event numbers as a range: 40-80, 40- or 40; got {spec!r}")
    first = int(m.group(1) or 1)
    last = int(m.group(3)) if m.group(3) else (None if m.group(2) else first)
    if last is not None and last < first:
        sys.exit(f"--events {spec}: the range ends before it starts")
    return first, last


def show(sheet: dict, name: str, n: int, limit: int) -> int:
    """Event n as JSON, two spaces deep: what edit_sheet.py takes back under "replace"."""
    def numbered(events: list) -> Iterator[dict]:
        for ev in events:
            if ev.get("eventType") in NUMBERED:
                yield ev
            yield from numbered(ev.get("children", []))
    events = list(numbered(sheet["events"]))
    if not 1 <= n <= len(events):
        sys.exit(f"sheet {name} has {len(events)} events; --show {n} is not one of them")
    text = json.dumps(events[n - 1], indent=2, ensure_ascii=False)
    if limit and len(text) > limit:
        sys.exit(f"event {n} is {len(text)} characters of JSON, over the limit of {limit} (--limit): show one of its "
                 f"sub-events, or pass --limit 0 and send it to a file")
    print(text)
    return 0


def again(args, sheets: list[str], events: str | None) -> str:
    """The command that prints sheets, or a range of one, with the options of this run."""
    def quoted(value) -> str:
        return str(value) if re.fullmatch(r"[\w./\\:-]+", str(value)) else f'"{value}"'
    words = ["python", quoted(sys.argv[0]), *map(quoted, sheets)]
    words += ["--events", events] if events else []
    words += ["--outline"] if args.outline else []
    for flag, default in (("project", None), ("rag", None), ("locale", "en-US"), ("limit", c3.LIMIT)):
        if getattr(args, flag) != default:
            words += [f"--{flag}", quoted(getattr(args, flag))]
    return " ".join(words)


def main() -> int:
    ap = c3.argument_parser(
        "Print event sheets as the editor words them: numbered events, conditions, actions. Read a sheet this "
        "way before and after an edit, and read an official example this way instead of its JSON.",
        "examples:\n"
        "  python scripts/print_sheet.py Game\n"
        "  python scripts/print_sheet.py Game --events 40-80   a part; the last line of a cut print names the next one\n"
        "  python scripts/print_sheet.py --outline Game        numbers and sids, to find the JSON behind a number\n"
        "  python scripts/print_sheet.py Game --show 5         event 5 as JSON\n"
        "  python scripts/print_sheet.py --project <Construct-Example-Projects>/example-projects/template-snake\n"
        "  python scripts/print_sheet.py Game --locale zh-CN   the editor's Chinese wording\n\n"
        "exit codes: 0 printed, whole or the part that fits; 1 no such sheet, a range past the sheet's end, or\n"
        "project/clone not found; 2 a sheet lacks a key the editor writes")
    ap.add_argument("sheets", nargs="*", metavar="SHEET", help="event sheet names (default: every sheet)")
    ap.add_argument("--events", metavar="A-B",
                    help="print only the events numbered A to B of one sheet; 40- runs to the end, 40 is one event")
    ap.add_argument("--outline", action="store_true",
                    help="print the event numbering with each event's sid, without conditions and actions")
    ap.add_argument("--show", type=int, metavar="N",
                    help="print event N of one sheet as JSON, to change and put back with edit_sheet.py's replace")
    args = ap.parse_args()
    c3.utf8_output()
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
    names = args.sheets or list(sheets)
    if (args.events or args.show is not None) and len(names) != 1:
        sys.exit(f"--events and --show read one sheet; name it: {', '.join(sheets)}")
    if args.show is not None:
        return show(sheets[names[0]], names[0], args.show, args.limit)
    first, last = events_range(args.events)

    rows, totals = {}, {}
    for name in names:
        counter = [0]
        events = sheets[name]["events"]
        rows[name] = list(outline_rows(events, counter) if args.outline else sheet_rows(project, events, counter))
        totals[name] = counter[0]
    if args.events and first > totals[names[0]]:
        sys.exit(f"sheet {names[0]} has {totals[names[0]]} events; --events {args.events} starts past its end")

    size = {name: sum(len(line) + 1 for line in [f"== {name}", *part(rows[name], first, last, None)[0]]) for name in names}
    fits = not args.limit or sum(size.values()) <= args.limit
    if not fits and not args.sheets and len(names) > 1:
        print(f"{len(names)} event sheets, {sum(size.values())} characters as events, over the limit of "
              f"{args.limit} (--limit). Name the ones to read:")
        for name in names:
            includes = [ev.get("includeSheet", "") for ev in sheets[name]["events"] if ev.get("eventType") == "include"]
            print(f"  {name:<28} {totals[name]:>4} events {size[name]:>7} characters"
                  + (f"   includes {', '.join(includes)}" if includes else ""))
        print(f"for example: {again(args, names[:1], None)}\n"
              f"A sheet over the limit prints in parts; the last line of a part names the next.")
        return 0

    room = None if fits else args.limit - 600   # the title, and a whole command to close
    for i, name in enumerate(names):
        lines, stopped = part(rows[name], first, last, room)
        whole = stopped is None and not args.events
        until = min(stopped - 1 if stopped else last or totals[name], totals[name])
        print(f"== {name}" if whole else f"== {name}: events {first}-{until} of {totals[name]}"
              + ("; a [context] row is an event these sit in, without its actions" if first > 1 else ""))
        if lines:
            print("\n".join(lines))
        if room is not None:
            room -= sum(len(line) + 1 for line in lines)
        rest = names[i + 1:]
        if stopped is not None or (rest and room is not None and room <= 0):
            more = [again(args, [name], f"{stopped}-{last or ''}")] if stopped else []
            more += [again(args, rest, None)] if rest else []
            print(f"-- stopped at the limit of {args.limit} characters (--limit)"
                  + (f", before event {stopped} of {totals[name]}" if stopped else "")
                  + f". The rest: {'  then  '.join(more)}")
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
