"""Print an event sheet as the editor words it, under the editor's event numbers.

    python scripts/print_sheet.py [SHEET ...] [--events A-B] [--outline] [--show N] [--limit CHARS]
                                  [--project FOLDER] [--rag FOLDER] [--locale en-US]

Conditions and actions are worded from the schema's display-text, in the
locale of --locale, at about a quarter of the JSON's length; one the editor
has deprecated ends in [deprecated], and the schema may not word it. One the
editor has disabled ends in [condition disabled] or [action disabled]: the
event runs as if that line were not there, and its other lines run. A disabled event or group ends its first line in [event disabled],
so that it does not read as a disabled first condition. It reads any
folder project, an official example included. An event without conditions
reads (every tick) at the top of the sheet, in a group or not, and (runs
with its parent) as a sub-event, which runs each time the event it sits in
runs: once per call in a function, once per trigger under a trigger (the
manual's project-primitives/events/sub-events).

A row's number is the count of blocks, groups, function blocks, custom
action blocks and script blocks before it in the sheet, sub-events included,
plus one: the number in the editor's margin and in its Find results. A variable, comment
or include takes no number of its own and belongs to the next one, so a
plan of edit_sheet.py names a variable by its name and a comment by words of
its text. A print that shows a variable, except --outline, ends with the
line that says how. A group's description and a variable's comment print
as // lines under it, in the column of the actions, not of the comments: a
plan changes them with "set" on the group's number or the variable's name,
{"event": 4, "set": {"description": "..."}} or
{"variable": "score", "set": {"comment": "..."}}.
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
VARIABLE_ROW = re.compile(r"\s*(?:global|local)(?: constant)?(?: static)? (?:number|string|boolean) (\S+) = (.*)")


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


def script_head(script: list | str) -> str:
    """A script as one row: the editor stores its lines as a list or as one string with newlines."""
    n = len(script.splitlines()) if isinstance(script, str) else len(script)
    return f"script, {n} line{'' if n == 1 else 's'}"


def wording(p: c3.Project, kind: str, ace: dict) -> str:
    """A condition or action as the event sheet words it: the schema's
    display-text with the parameters in place, in the locale of --locale."""
    obj = ace.get("objectClass", "?")
    args_ = ace.get("parameters", [])
    if "callFunction" in ace:
        return f"{p.functions_object}: Call {ace['callFunction']}({', '.join(map(str, args_))})"
    if "customAction" in ace:
        return f"{obj}: {ace['customAction']}({', '.join(map(str, args_))})"
    if ace.get("type") == "comment":
        return "// " + str(ace.get("text", "")).split("\n")[0]
    if ace.get("type") == "script":
        return script_head(ace.get("script", []))
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
    if obj in p.plugin_of and p.deprecated_entry(kind, ace):
        text += " [deprecated]"
    return f"{obj}: {'NOT ' if ace.get('isInverted') else ''}{text}"


def numbered_below(events: list) -> int:
    """How many numbered events these are, with everything below them."""
    return sum((ev.get("eventType") in NUMBERED) + numbered_below(ev.get("children", [])) for ev in events)


def remarks(text: object, pad: str) -> list[str]:
    """A group's description or a variable's comment, as // lines under it in the column of the actions: a
    comment event sits in the column of the events."""
    return [f"     {pad}    // {line}" for line in text.split("\n")] if isinstance(text, str) and text.strip() else []


def sheet_rows(p: c3.Project, events: list, counter: list[int], above: tuple = (),
               top: bool = True) -> Iterator[Row]:
    """The sheet as the editor shows it, with the editor's event numbers. top: every
    row above these is a group, so an event without conditions runs every tick."""
    pad = "  " * len(above)
    unconditional = "(every tick)" if top else "(runs with its parent)"
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
            body = remarks(ev.get("comment"), pad)
        elif et == "comment":
            head = [f"{number}{pad}// {line}" for line in ev.get("text", "").split("\n")]
        elif et == "include":
            head = [f"{number}{pad}include {ev.get('includeSheet', '')}"]
        elif et == "script":
            head = [f"{number}{pad}{script_head(ev.get('script', []))}"]
        elif et == "group":
            head = [f"{number}{pad}group {ev.get('title', '')}"
                    + ("" if ev.get("isActiveOnStart", True) else " (inactive on start)")
                    + (" [event disabled]" if ev.get("disabled") else "")]
            body = remarks(ev.get("description"), pad)
        else:
            lines = []
            if et in ("function-block", "custom-ace-block"):
                name = ev.get("functionName") or f"{ev.get('objectClass')}.{ev.get('aceName')}"
                params = ", ".join(f"{fp['name']}: {fp['type']}" for fp in ev.get("functionParameters", []))
                returns = ev.get("functionReturnType", "none")
                lines.append(f"{'function' if et == 'function-block' else 'custom action'} {name}({params})"
                             + (f" -> {returns}" if returns != "none" else "")
                             + (" [copy picked]" if ev.get("functionCopyPicked") else ""))
            lines += [wording(p, "conditions", c) + (" [condition disabled]" if c.get("disabled") else "")
                      for c in ev.get("conditions", [])]
            joiner = "OR " if ev.get("isOrBlock") else ""
            # Indenting alone did not tell a model that the event below belonged to this one:
            # it removed a trigger with no actions as empty, and its sub-events went with it.
            below = numbered_below(ev.get("children", [])) if et not in ("function-block", "custom-ace-block") else 0
            nested = f"  [sub-event{'s' if below > 1 else ''} {counter[0] + 1}" \
                + (f"-{counter[0] + below}]" if below > 1 else "]") if below else ""
            head = [f"{number if i == 0 else '     '}{pad}{joiner if i else ''}{line}"
                    + (" [event disabled]" if ev.get("disabled") and i == 0 else "")
                    + (nested if i == len(lines or [unconditional]) - 1 else "")
                    for i, line in enumerate(lines or [unconditional])]
            body = [f"     {pad}    -> {wording(p, 'actions', a)}" + (" [action disabled]" if a.get("disabled") else "")
                    for a in ev.get("actions", [])]
        row = Row(counter[0] if et in NUMBERED else counter[0] + 1, head, body, above)
        yield row
        yield from sheet_rows(p, ev.get("children", []), counter, (*above, row), top and et == "group")


def part(rows: list[Row], first: int, last: int | None, room: int | None) -> tuple[list[str], int | None]:
    """The lines of the rows numbered first to last, the first of them under the
    heads of the rows it sits in, cut before the event that would pass room
    characters. The rows of one event number print together, the comments and
    variables above an event with it, so the number printing stopped before is
    always past the first: a continuation from it advances. Returns the lines
    and that number, None when the range was printed whole."""
    # The rows of one event number, its comments and variables and then the event.
    groups: list[tuple[int, list[Row]]] = []
    for row in rows:
        if row.number < first or (last is not None and row.number > last):
            continue
        if groups and groups[-1][0] == row.number:
            groups[-1][1].append(row)
        else:
            groups.append((row.number, [row]))
    lines: list[str] = []
    shown: set[int] = set()
    used = 0
    for number, group in groups:
        new: list[str] = []
        for row in group:
            new += [line + ("  [context]" if i == 0 else "") for a in row.above if id(a) not in shown
                    for i, line in enumerate(a.head)] + row.head + row.body
            shown.update(id(a) for a in (*row.above, row))
        size = sum(len(line) + 1 for line in new)
        if room is not None and lines and used + size > room:
            return lines, number
        lines += new
        used += size
    return lines, None


def naming_note(lines: list[str]) -> str | None:
    """How a plan names the first variable the lines show: a variable has no number to address."""
    found = [m for m in map(VARIABLE_ROW.fullmatch, (line[5:] for line in lines)) if m]
    if not found:
        return None
    m = next((m for m in found if len(m.group(2)) <= 30), found[0])     # a short value keeps the line short
    value = m.group(2) if len(m.group(2)) <= 30 else "..."
    plan = json.dumps({"variable": m.group(1)[:40], "set": {"initialValue": value}}, ensure_ascii=False)
    return (f"-- a variable or comment has no number, so a plan of edit_sheet.py names it. A variable: {plan}; "
            f"a value a constant holds is changed there, not in the formulas that read it. A comment, by words "
            f'of its text: {{"comment": "...", "set": {{"text": "..."}}}}')


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
    events = list(c3.numbered_events(sheet["events"]))
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
        "  python scripts/print_sheet.py Game --locale zh-CN   the editor's Chinese wording\n"
        "  python scripts/print_sheet.py --review              a project someone asked about\n\n"
        "exit codes: 0 printed, whole or the part that fits; 1 no such sheet, a range past the sheet's end, or\n"
        "project/clone not found; 2 a sheet lacks a key the editor writes")
    ap.add_argument("sheets", nargs="*", metavar="SHEET", help="event sheet names (default: every sheet)")
    ap.add_argument("--events", metavar="A-B",
                    help="print only the events numbered A to B of one sheet; 40- runs to the end, 40 is one event")
    ap.add_argument("--outline", action="store_true",
                    help="print the event numbering with each event's sid, without conditions and actions")
    ap.add_argument("--show", type=int, metavar="N",
                    help="print event N of one sheet as JSON, to change and put back with edit_sheet.py's replace")
    ap.add_argument("--review", action="store_true",
                    help="for a project someone else wrote and asked about: end with what a review reports")
    args = ap.parse_args()
    c3.utf8_output()
    findings = c3.Findings()
    c3.stop_with_a_sentence("print_sheet.py", findings)
    project = c3.Project.open(args, findings)
    c3.note_drift(project.rag)

    sheets = project.load_listed("eventSheets")
    if not sheets:
        scripts = project.scripts_summary()
        print((f"no event sheets: the project's logic is in its scripts, read them as code: {scripts}" if scripts
               else "no event sheets and no scripts: the project holds no logic yet")
              + "; events go into a new sheet with edit_sheet.py SHEET PLAN.json --new")
        return 0
    for name in args.sheets:
        if name not in sheets:
            sys.exit(f"no event sheet named {name!r}; sheets: {', '.join(sheets)}")
    names = args.sheets or list(sheets)
    if (args.events or args.show is not None) and len(names) != 1:
        sys.exit(f"--events and --show read one sheet; name it: {', '.join(sheets)}")
    files = project.listed_files("eventSheets")
    for name in names:
        c3.stamp(files[name])
    if args.show is not None:
        return show(sheets[names[0]], names[0], args.show, args.limit)
    first, last = events_range(args.events)
    if project.functions_object != "Functions":
        # A model read 活着.Potion as a function named 活着 that returned its own name.
        f = project.functions_object
        print(f"note: {f} is this project's name for the built-in Functions object (functionsName in "
              f"project.c3proj), not a function: {f}.Name(...) calls the function Name")

    rows, totals = {}, {}
    for name in names:
        counter = [0]
        events = sheets[name]["events"]
        rows[name] = list(outline_rows(events, counter) if args.outline else sheet_rows(project, events, counter))
        totals[name] = counter[0]
    if args.events and first > totals[names[0]]:
        sys.exit(f"sheet {names[0]} has {totals[names[0]]} events; --events {args.events} starts past its end")

    whole = {name: part(rows[name], first, last, None)[0] for name in names}
    size = {name: sum(len(line) + 1 for line in [f"== {name}", *whole[name]]) for name in names}
    # The line on naming a variable, with room for a longer name or value than this one's in a part.
    note = None if args.outline else naming_note([line for name in names for line in whole[name]])
    reserved = (len(note) + 70 if note else 0) + (len(c3.REVIEW) + 1 if args.review else 0)
    fits = not args.limit or sum(size.values()) + reserved <= args.limit
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

    room = None if fits else args.limit - 600 - reserved   # the title, the note and a whole command to close
    shown: list[str] = []
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
        shown += lines
        said = note and (not rest or stopped is not None or (room is not None and room <= 0)) and naming_note(shown)
        if said:
            print(said)
        if stopped is not None or (rest and room is not None and room <= 0):
            if args.review:
                print(c3.REVIEW)        # above the line that names the rest, which stays the last
            more = [again(args, [name], f"{stopped}-{last or ''}")] if stopped else []
            more += [again(args, rest, None)] if rest else []
            print(f"-- stopped at the limit of {args.limit} characters (--limit)"
                  + (f", before event {stopped} of {totals[name]}" if stopped else "")
                  + f". The rest: {'  then  '.join(more)}")
            break
    else:
        if args.review:
            print(c3.REVIEW)
    return 0


if __name__ == "__main__":
    sys.exit(main())
