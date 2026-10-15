"""Print an event sheet as the editor words it, under the editor's event numbers.

    python scripts/print_sheet.py [SHEET ...] [--events A-B] [--outline] [--show N] [--find NAME]
                                  [--limit CHARS] [--project FOLDER] [--rag FOLDER] [--locale en-US]

Conditions and actions are worded from the schema's display-text, in the
locale of --locale, at about a quarter of the JSON's length. One the editor
has deprecated ends in [deprecated], and the schema may not word it. One the
editor has disabled ends in [condition disabled] or [action disabled]: the
event runs as if that line were not there, and its other lines run. A
disabled event or group ends its first line in [event disabled], so that it
does not read as a disabled first condition. The script reads any folder
project, an official example included. An event without conditions reads
(every tick) at the top of the sheet, in a group or not, and (runs with its
parent) as a sub-event, which runs each time the event it sits in runs:
once per call in a function, once per trigger under a trigger (the manual's
project-primitives/events/sub-events).

A row's number is the count of blocks, groups, function blocks, custom
action blocks and script blocks before it in the sheet, sub-events included,
plus one: the number in the editor's margin and in its Find results. A
variable, comment or include takes no number of its own and belongs to the
next one, so a plan of edit_sheet.py names a variable by its name and a
comment by words of its text. A print that shows a variable, except
--outline, ends with the line that says how. A group's description and a
variable's comment print as // lines under it, in the column of the actions,
not of the comments. A plan changes them with "set" on the group's number
or the variable's name: {"event": 4, "set": {"description": "..."}} or
{"variable": "score", "set": {"comment": "..."}}.

--outline prints the numbering alone, with the sid of each event, which is
the string to search the sheet's JSON for, and a comment's first 30
characters. --show N prints one event as JSON, for a plan of edit_sheet.py
that puts it back changed. --find NAME prints the events that use a
variable, a function or an object, in any case, by its name in their
conditions, actions, parameters and expressions, not in quoted text or
comments, each under the events it sits in, marked [context].

--since COMMIT prints what changed in the sheets since a commit, branch or
tag of the project's git history, the files on disk included. It prints each
event added (+), removed (-), changed (the lines that changed, - before and +
after) or moved to another place. The numbers are those of the sheet on disk,
and the events a change sits in print above it, marked [context]. An event is
the same event when its content is the same: its conditions, actions and
values. If not, it is the same when its sid is. The sids alone do not decide,
because a generator run gives them anew. The old sheet is worded from the
object types the commit holds.

A harness cuts long tool output, so a sheet that does not fit --limit
characters prints the list of its groups and functions instead, each with
the event numbers it spans, then the --events and --find commands that
print a part of it. A part printed with --events starts with the events it
sits in, marked [context] and without their actions; one over the limit
stops at an event, and the last line gives the --events range that
continues. Without a sheet name, a project whose sheets do not fit the
limit prints the list of its sheets instead.
"""
import argparse
import collections
import difflib
import io
import itertools
import json
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Iterator, NamedTuple

import c3project as c3
from c3project import NUMBERED, STRING_LITERAL, describe

COMPARISONS = ("=", "≠", "<", "≤", ">", "≥")
VARIABLE_ROW = re.compile(r"\s*(?:global|local)(?: constant)?(?: static)? (?:number|string|boolean) (\S+) = (.*)")
OUTLINE_COMMENT = 30    # characters of a comment's first line --outline keeps: a CJK character is about a token
FUNCTION_BLOCKS = ("function-block", "custom-ace-block")


def cut(text: str, n: int) -> str:
    return text if len(text) <= n else text[:n].rstrip() + "…"


def printed_length(lines: Iterable[str]) -> int:
    """The characters the lines take printed, a newline after each."""
    return sum(len(line) + 1 for line in lines)


def within(number: int, first: int, last: int | None) -> bool:
    """Whether an event number lies in the range of --events; last None runs to the end."""
    return first <= number and (last is None or number <= last)


class Row(NamedTuple):
    number: int         # the editor's number; a variable, comment or include carries the next numbered row's
    head: list[str]     # the row as printed; of a block, the function line and the conditions
    body: list[str]     # the actions of a block
    above: tuple        # the rows this one sits in, outermost first
    event: dict | None = None   # the event, comment or variable printed


def outline_rows(events: list, counter: list[int], above: tuple = ()) -> Iterator[Row]:
    depth = len(above)
    for ev in events:
        et = ev.get("eventType")
        if et == "variable":
            text = f"{ev['type']} {ev['name']} = {ev.get('initialValue', '')!s}"
        elif et == "comment":
            text = "// " + cut(ev.get("text", "").split("\n")[0], OUTLINE_COMMENT)
        elif et == "group":
            text = f"group {ev.get('title', '')}"
        elif et == "include":
            text = f"include {ev.get('includeSheet', '')}"
        elif et in FUNCTION_BLOCKS:
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


def function_line(ev: dict) -> str:
    """The first line of a function or custom action block: its name, parameters and return type."""
    name = ev.get("functionName") or f"{ev.get('objectClass')}.{ev.get('aceName')}"
    params = ", ".join(f"{fp['name']}: {fp['type']}" for fp in ev.get("functionParameters", []))
    returns = ev.get("functionReturnType", "none")
    return (f"{'function' if ev.get('eventType') == 'function-block' else 'custom action'} {name}({params})"
            + (f" -> {returns}" if returns != "none" else "")
            + (" [copy picked]" if ev.get("functionCopyPicked") else ""))


def block_name(ev: dict) -> str:
    """A function or custom action block by its name alone: the list of a long sheet's parts names it, and the
    part printed with --events gives its parameters."""
    if ev.get("eventType") == "function-block":
        return f"function {ev.get('functionName')}"
    return f"custom action {ev.get('objectClass')}.{ev.get('aceName')}"


def group_line(ev: dict) -> str:
    return (f"group {ev.get('title', '')}" + ("" if ev.get("isActiveOnStart", True) else " (inactive on start)")
            + (" [event disabled]" if ev.get("disabled") else ""))


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
            head = [f"{number}{pad}{group_line(ev)}"]
            body = remarks(ev.get("description"), pad)
        else:
            lines = [function_line(ev)] if et in FUNCTION_BLOCKS else []
            lines += [wording(p, "conditions", c) + (" [condition disabled]" if c.get("disabled") else "")
                      for c in ev.get("conditions", [])]
            lines = lines or [unconditional]
            joiner = "OR " if ev.get("isOrBlock") else ""
            # Mark the sub-events on the last line
            # Indenting alone did not tell a model that the event below belonged to this one:
            # it removed a trigger with no actions as empty, and its sub-events went with it.
            below = numbered_below(ev.get("children", [])) if et not in FUNCTION_BLOCKS else 0
            nested = (f"  [sub-event{'s' if below > 1 else ''} {span_text(counter[0] + 1, counter[0] + below)}]"
                      if below else "")
            head = [f"{number if i == 0 else '     '}{pad}{joiner if i else ''}{line}"
                    + (" [event disabled]" if ev.get("disabled") and i == 0 else "")
                    + (nested if i == len(lines) - 1 else "")
                    for i, line in enumerate(lines)]
            body = [f"     {pad}    -> {wording(p, 'actions', a)}" + (" [action disabled]" if a.get("disabled") else "")
                    for a in ev.get("actions", [])]
        row = Row(counter[0] if et in NUMBERED else counter[0] + 1, head, body, above, ev)
        yield row
        yield from sheet_rows(p, ev.get("children", []), counter, (*above, row), top and et == "group")


def with_context(row: Row, shown: set[int]) -> list[str]:
    """A row's lines under the heads of the rows it sits in that have not printed yet, marked [context].
    Adds the ids of the row and the rows it sits in to shown."""
    lines = [line + ("  [context]" if i == 0 else "") for a in row.above if id(a) not in shown
             for i, line in enumerate(a.head)] + row.head + row.body
    shown.update(id(a) for a in (*row.above, row))
    return lines


def part(rows: list[Row], first: int, last: int | None, room: int | None) -> tuple[list[str], int | None]:
    """The lines of the rows numbered first to last, the first of them under the
    heads of the rows it sits in, cut before the event that would pass room
    characters. The rows of one event number print together, the comments and
    variables above an event with it, so the number printing stopped before is
    always past the first: a continuation from it advances. Returns the lines
    and that number, None when the range was printed whole."""
    lines: list[str] = []
    shown: set[int] = set()
    used = 0
    # The rows of one event number: its comments and variables, then the event
    for number, group in itertools.groupby((row for row in rows if within(row.number, first, last)),
                                           key=lambda row: row.number):
        new = [line for row in group for line in with_context(row, shown)]
        size = printed_length(new)
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
    """The first and last event number of --events; last None runs to the end."""
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
    # A miss answers the model: on stdout, with the exit code of an error
    if not 1 <= n <= len(events):
        print(f"sheet {name} has {len(events)} events; --show {n} is not one of them")
        return 1
    text = json.dumps(events[n - 1], indent=2, ensure_ascii=False)
    if limit and len(text) > limit:
        print(f"event {n} is {len(text)} characters of JSON, over the limit of {limit} (--limit): show one of its "
              f"sub-events, or pass --limit 0 and send it to a file")
        return 1
    print(text)
    return 0


def again(args: argparse.Namespace, sheets: list[str], events: str | None, find: str | None = None) -> str:
    """The command that prints sheets, or a range of one, with the options of this run; with find, the events that
    use that name (NAME, as written, when the command is an example to fill in)."""
    find = find if find is not None else args.find
    words = ["python", c3.quoted(sys.argv[0]), *map(c3.quoted, sheets)]
    words += ["--since", c3.quoted(args.since)] if args.since else []
    words += ["--find", c3.quoted(find)] if find else []
    words += ["--events", events] if events else []
    words += ["--outline"] if args.outline and not find else []
    for flag, default in (("project", None), ("rag", None), ("locale", "en-US"), ("limit", c3.LIMIT)):
        if getattr(args, flag) != default:
            words += [f"--{flag}", c3.quoted(getattr(args, flag))]
    return " ".join(words)


def stopped_line(args: argparse.Namespace, name: str, stopped: int | None, last: int | None, rest: list[str],
                 total: int | None = None) -> str:
    """The last line of a print cut at --limit: the event it stopped before, of total events when given, and the
    commands that print the rest of sheet name and then the sheets of rest."""
    more = [again(args, [name], f"{stopped}-{last or ''}")] if stopped else []
    more += [again(args, rest, None)] if rest else []
    where = (f", before event {stopped}" + (f" of {total}" if total is not None else "")) if stopped else ""
    return f"-- stopped at the limit of {args.limit} characters (--limit){where}. The rest: {'  then  '.join(more)}"


# --- a sheet over the limit: its groups and functions; --find: the events that use a name -----------------
BLOCKS = ("group", *FUNCTION_BLOCKS)


def spans(events: list) -> tuple[list[tuple[int, int, int, str]], list[tuple[int, int]]]:
    """The groups and functions of a sheet, each with its depth, the first and the last event number it spans and
    its line; and the spans of the events that sit in none of them. Groups hold groups, blocks never do."""
    entries: list[tuple[int, int, int, str]] = []
    loose: list[tuple[int, int]] = []
    counter = 0

    def walk(level: list, depth: int, inside: bool) -> None:
        nonlocal counter
        for ev in level:
            et = ev.get("eventType")
            if et not in NUMBERED:
                continue
            counter += 1
            last = counter + numbered_below(ev.get("children", []))
            if et in BLOCKS:
                entries.append((depth, counter, last, group_line(ev) if et == "group" else block_name(ev)))
                walk(ev.get("children", []), depth + 1, True)
            else:
                if not inside:
                    if loose and loose[-1][1] == counter - 1:
                        loose[-1] = (loose[-1][0], last)
                    else:
                        loose.append((counter, last))
                counter = last

    walk(events, 0, False)
    return entries, loose


def span_text(first: int, last: int) -> str:
    return f"{first}-{last}" if last > first else str(first)


def contents(args: argparse.Namespace, name: str, rows: list[Row], events: list, total: int, size: int,
             room: int) -> tuple[list[str], str]:
    """What prints instead of a sheet over the limit: one line per group and function with the events it spans,
    the deeper groups left out while the list is over room; and the span of an --events example."""
    entries, loose = spans(events)
    depth = max((e[0] for e in entries), default=0)
    tail = ["events in no group or function: " + ", ".join(span_text(a, b) for a, b in loose)] if loose else []

    def listing(deepest: int) -> list[tuple[int, str]]:
        shown = [e for e in entries if e[0] <= deepest]
        out = [(b, f"{span_text(a, b):>9}  {'  ' * d}{line}") for d, a, b, line in shown]
        if len(shown) < len(entries):
            out.append((0, f"          ({len(entries) - len(shown)} groups and functions inside these are left out "
                           f"to stay under the limit)"))
        return out

    def chars(lines: list[tuple[int, str]]) -> int:
        return printed_length(line for _, line in lines) + printed_length(tail)

    lines = listing(depth)
    while depth and chars(lines) > room:
        depth -= 1
        lines = listing(depth)
    if chars(lines) > room:         # too many top-level groups and functions for one print: the rest by number
        kept: list[tuple[int, str]] = lines[:1]
        for entry in lines[1:]:
            if chars([*kept, entry]) > room:
                break
            kept.append(entry)
        after = max(b for b, _ in kept) + 1
        outline = argparse.Namespace(**{**vars(args), "outline": True})
        lines = kept + [(0, f"          (the list stops at the limit; the numbering from event {after} on: "
                            f"{again(outline, [name], f'{after}-')})")]
    top = [(a, b) for d, a, b, _ in entries if d == 0]
    if top:
        example = span_text(*top[0])
    else:
        _, stopped = part(rows, 1, None, room)
        example = span_text(1, (stopped - 1) if stopped else total)
    head = (f"== {name}: {total} events, {size} characters {'as an outline' if args.outline else 'as events'}, "
            f"over the limit of {args.limit} (--limit). Its groups and functions, each with the events it spans:")
    return [head, *(line for _, line in lines), *tail], example


def contents_end(args: argparse.Namespace, name: str, example: str) -> str:
    return (f"-- print one part, a group or a function, by its events: {again(args, [name], example)}; "
            f"the events that use a variable, a function or an object, with the events they sit in: "
            f"{again(args, [name], None, find='NAME')}")


IDENTIFIER = r"[\w$]"
SKIPPED = {"sid", "children", "functionDescription", "functionCategory", "comment", "description"}


def strings_of(value: object) -> Iterator[str]:
    """The names and expressions an event's own content holds: not its sub-events, its comments or its
    descriptions, and an expression's quoted strings left out."""
    if isinstance(value, dict):
        if value.get("type") == "comment":
            return
        for key, inner in value.items():
            if key not in SKIPPED:
                yield from strings_of(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from strings_of(inner)
    elif isinstance(value, str):
        yield STRING_LITERAL.sub('""', value) if '"' in value else value


def uses(ev: dict | None, pattern: re.Pattern) -> bool:
    """Whether an event names the variable, function or object of pattern: a group, a comment or an include
    only frames the events that do."""
    if not ev or ev.get("eventType") in ("group", "comment", "include"):
        return False
    return any(pattern.search(text) for text in strings_of(ev))


def found(rows: list[Row], pattern: re.Pattern, first: int, last: int | None,
          room: int | None) -> tuple[list[str], int, int | None]:
    """The rows that use the name, each under the heads of the rows it sits in, marked [context], within the
    numbers first to last, cut before the row that would pass room characters. Returns the lines, the number of
    rows that use it in the range, and the number printing stopped before."""
    hits = [row for row in rows if within(row.number, first, last) and uses(row.event, pattern)]
    lines: list[str] = []
    shown: set[int] = set()
    used = 0
    for row in hits:
        new = with_context(row, shown)
        size = printed_length(new)
        if room is not None and lines and used + size > room:
            return lines, len(hits), row.number
        lines += new
        used += size
    return lines, len(hits), None


def names_in(project: c3.Project, sheets: dict[str, dict]) -> set[str]:
    """The names a --find could mean: the object types, and the variables, functions and parameters of the
    sheets."""
    out = set(project.plugin_of)

    def walk(events: list) -> None:
        for ev in events:
            out.update(str(ev[k]) for k in ("name", "functionName", "aceName") if ev.get(k))
            out.update(str(fp.get("name")) for fp in ev.get("functionParameters", []))
            walk(ev.get("children", []))

    for sheet in sheets.values():
        walk(sheet.get("events", []))
    return out


def print_found(args: argparse.Namespace, project: c3.Project, sheets: dict[str, dict], names: list[str]) -> int:
    """--find: per sheet, the events that use the name, under the events they sit in."""
    pattern = re.compile(rf"(?<!{IDENTIFIER}){re.escape(args.find)}(?!{IDENTIFIER})", re.IGNORECASE)
    first, last = events_range(args.events)
    room = args.limit - 600 if args.limit else None     # the last line names a whole command
    none: list[str] = []
    for k, name in enumerate(names):
        rows = list(sheet_rows(project, sheets[name]["events"], [0]))
        lines, count, stopped = found(rows, pattern, first, last, room)
        if not count:
            none.append(name)
            continue
        print(f"== {name}: {count} event{'s' if count != 1 else ''} use{'' if count != 1 else 's'} {args.find}, "
              f"each under the events it sits in, marked [context] and printed without their actions")
        print("\n".join(lines))
        if room is not None:
            room -= printed_length(lines)
        rest = names[k + 1:]
        if stopped is not None or (rest and room is not None and room <= 0):
            print(stopped_line(args, name, stopped, last, rest))
            return 0
    if len(none) == len(names):
        # A miss answers the model: on stdout, with the names that come near.
        print(f"no event uses {args.find} in {', '.join(names)}{c3.closest(args.find, names_in(project, sheets))}; "
              f"--find takes the name of a variable, a function or an object as the sheet writes it")
        return 1
    if none:
        print(f"no event uses {args.find} in {', '.join(none)}")
    return 0


# --- --since: the events that changed since a commit ----------------------------------------------
PROJECT_PARTS = ("project.c3proj", "objectTypes", "families", "eventSheets")     # what words a sheet
SUB_EVENTS = re.compile(r"  \[sub-events? \d+(?:-\d+)?\]$")


def git(root: Path, *args: str, binary: bool = False, wait: float = 60) -> subprocess.CompletedProcess:
    """git run in the project folder, which reads paths relative to it."""
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=wait,
                              **({} if binary else {"text": True, "encoding": "utf-8", "errors": "replace"}))
    except FileNotFoundError:
        sys.exit("--since reads the project's history with git, which was not found here; install git")
    except subprocess.TimeoutExpired:
        sys.exit(f"git {args[0]} did not answer in {wait:.0f} seconds; run this again")


def commit_of(root: Path, ref: str) -> tuple[str, str]:
    """The commit ref names, in full and short."""
    if ref.startswith("-"):
        sys.exit(f"--since takes a commit, a branch or a tag, such as main or HEAD~3; got {ref!r}")
    if git(root, "rev-parse", "--git-dir").returncode:
        sys.exit(f"--since compares with a commit of the project's history, and {root} is in no git repository: "
                 f"git init and commit before the first edit")
    found = git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if found.returncode:
        recent = git(root, "log", "--oneline", "-5").stdout.strip().splitlines()
        sys.exit(f"--since {ref}: no such commit, branch or tag here"
                 + (f"; the latest commits: {'; '.join(recent)}" if recent else "; the repository has no commit yet"))
    full = found.stdout.strip()
    return full, git(root, "rev-parse", "--short", full).stdout.strip() or full[:7]


def project_at(p: c3.Project, commit: str, into: Path) -> c3.Project | None:
    """The project as the commit holds it, as much of it as words its sheets, written into `into`;
    None when the commit holds no project.c3proj in this folder."""
    held = git(p.root, "ls-tree", "--name-only", commit, "--", *PROJECT_PARTS).stdout.split()
    if "project.c3proj" not in held:
        return None
    archive = git(p.root, "archive", "--format=tar", commit, "--", *held, binary=True)
    if archive.returncode:
        sys.exit(f"git archive {commit[:7]} failed: {archive.stderr.decode('utf-8', 'replace').strip()}")
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        for member in tar.getmembers():
            path = into.joinpath(*PurePosixPath(member.name).parts)
            if member.isfile() and ".." not in PurePosixPath(member.name).parts:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(tar.extractfile(member).read())
    try:
        return c3.Project(into, p.rag, p.locale, c3.Findings())
    except SystemExit:      # a file the commit holds is not valid JSON: its sheets read as they are worded now
        return None


def content(obj: object) -> object:
    """An event's own content, to compare: without its sub-events, and without the sids, which a generator
    run gives anew from its first changed line on."""
    if isinstance(obj, dict):
        return {k: content(v) for k, v in obj.items() if k not in ("sid", "children")}
    return [content(v) for v in obj] if isinstance(obj, list) else obj


def matched(old: list[Row], new: list[Row]) -> dict[int, int]:
    """Old row index -> new row index of the same event: the same sid and content, then the same content,
    then the same sid, then a row of the same kind in the same place with lines alike, such as an edited
    comment, which has no sid. When most events kept their content under another sid, the sids were given
    anew, as a generator run does, and a sid does not identify one event."""
    keys = {id(row): json.dumps(content(row.event), sort_keys=True, ensure_ascii=False) for row in (*old, *new)}

    def sid(row: Row) -> int | None:
        s = row.event.get("sid")
        return s if isinstance(s, int) else None

    counts = collections.Counter(sid(r) for r in (*old, *new))
    unique = {s for s, n in counts.items() if s is not None and n == 2}
    old_by_sid = {sid(r): i for i, r in enumerate(old) if sid(r) in unique}
    pairs: dict[int, int] = {}
    for j, row in enumerate(new):
        i = old_by_sid.get(sid(row))
        if i is not None and keys[id(old[i])] == keys[id(row)]:
            pairs[i] = j
    taken = set(pairs.values())
    waiting: dict[str, collections.deque] = {}
    for i, row in enumerate(old):
        if i not in pairs:
            waiting.setdefault(keys[id(row)], collections.deque()).append(i)
    for j, row in enumerate(new):
        queue = waiting.get(keys[id(row)]) if j not in taken else None
        if queue:
            pairs[queue.popleft()] = j
    taken = set(pairs.values())
    kept = [sid(old[i]) == sid(new[j]) for i, j in pairs.items() if sid(old[i]) is not None]
    if not kept or sum(kept) * 2 >= len(kept):
        for j, row in enumerate(new):
            i = old_by_sid.get(sid(row))
            if (j not in taken and i is not None and i not in pairs
                    and old[i].event.get("eventType") == row.event.get("eventType")):
                pairs[i] = j
                taken.add(j)
    # The rest by place: before the same matched row, in the same matched parent
    at_old = {id(r): k for k, r in enumerate(old)}
    at_new = {id(r): k for k, r in enumerate(new)}

    def place(rows: list[Row], k: int, at: dict[int, int], to_new: Callable[[int], int | None]) -> tuple:
        after = next((to_new(m) for m in range(k + 1, len(rows)) if to_new(m) is not None), len(new))
        parent = to_new(at[id(rows[k].above[-1])]) if rows[k].above else -1
        return after, parent, rows[k].event.get("eventType")

    spots: dict[tuple, list[int]] = {}
    for i in range(len(old)):
        if i not in pairs:
            spots.setdefault(place(old, i, at_old, pairs.get), []).append(i)
    for j in range(len(new)):
        if j in taken:
            continue
        here = spots.get(place(new, j, at_new, lambda m: m if m in taken else None), [])
        lines = compared(new[j])
        for i in here:
            was = compared(old[i])
            if difflib.SequenceMatcher(a=was, b=lines, autojunk=False).ratio() >= 0.5 \
                    or difflib.SequenceMatcher(a="\n".join(was), b="\n".join(lines), autojunk=False).ratio() >= 0.6:
                pairs[i] = j
                here.remove(i)
                break
    return pairs


def moved(old: list[Row], new: list[Row], pairs: dict[int, int]) -> set[int]:
    """The new rows of matched events that moved: into another event, or to another place among the events
    beside them. Among siblings, the longest run that kept its old order stays, and the rest moved."""
    index = {id(r): k for rows in (old, new) for k, r in enumerate(rows)}
    parent_old = [index[id(r.above[-1])] if r.above else None for r in old]
    parent_new = [index[id(r.above[-1])] if r.above else None for r in new]
    out, siblings = set(), {}
    for i, j in sorted(pairs.items(), key=lambda pair: pair[1]):
        po, pn = parent_old[i], parent_new[j]
        if pairs.get(po) != pn or (po is None) != (pn is None):
            out.add(j)
        else:
            siblings.setdefault(pn, []).append((i, j))
    for kids in siblings.values():
        # The longest increasing run of old indexes, in new order
        best: list[list[tuple[int, int]]] = []
        for pair in kids:
            longest = max((run for run in best if run[-1][0] < pair[0]), key=len, default=[])
            best.append([*longest, pair])
        keep = set(max(best, key=len, default=[]))
        out.update(j for i, j in kids if (i, j) not in keep)
    return out


def compared(row: Row) -> list[str]:
    """A row's lines without its number and its sub-event numbers, which an edit elsewhere changes."""
    return [SUB_EVENTS.sub("", line)[5:] for line in (*row.head, *row.body)]


def unnumbered(line: str) -> str:
    """A line of the old sheet, without its numbers, which would read as those of the sheet on disk."""
    return "     " + SUB_EVENTS.sub("", line)[5:]


def changes(old: list[Row], new: list[Row], since: str) -> tuple[list[tuple[int, list[str]]], collections.Counter]:
    """The changes of one sheet in the order of the sheet on disk, each with the number of the event it prints
    at, and how many rows were added, changed, moved and removed. An added or changed row prints at its own
    number, a removed one before the next event that stayed, or at the end, under the events it sat in."""
    pairs = matched(old, new)
    back = {j: i for i, j in pairs.items()}
    shifted = moved(old, new, pairs)
    at_old = {id(r): k for k, r in enumerate(old)}
    at_new = {id(r): k for k, r in enumerate(new)}
    added = {j for j in range(len(new)) if j not in back}
    edited = {j for j, i in back.items() if content(old[i].event) != content(new[j].event)}
    counts = collections.Counter(added=len(added), changed=len(edited), moved=len(shifted - edited),
                                 removed=len(old) - len(pairs))
    shown: set[int] = set()     # new rows whose first line is printed, as a change or as context

    def context(chain: Iterable[Row]) -> list[str]:
        lines = []
        for above in chain:
            if at_new[id(above)] not in shown:
                shown.add(at_new[id(above)])
                lines.append(f" {above.head[0]}  [context]")
        return lines

    def numbered(row: Row) -> bool:
        return row.event.get("eventType") in NUMBERED

    def removal(i: int) -> list[str]:
        row = old[i]
        top = not row.above or at_old[id(row.above[-1])] in pairs
        where = f"removed; event {row.number} in {since}" if numbered(row) else "removed"
        chain = [new[pairs[at_old[id(a)]]] for a in row.above if at_old[id(a)] in pairs] if top else []
        return context(chain) + [f"-{unnumbered(line)}" + (f"  [{where}]" if n == 0 and top else "")
                                 for n, line in enumerate((*row.head, *row.body))]

    def addition(j: int) -> list[str]:
        row = new[j]
        top = not row.above or at_new[id(row.above[-1])] not in added
        shown.add(j)
        return (context(row.above) if top else []) + [
            f"+{line}" + ("  [added]" if n == 0 and top else "") for n, line in enumerate((*row.head, *row.body))]

    def change(j: int) -> list[str]:
        row, was = new[j], old[back[j]]
        shown.add(j)
        notes = ["changed"] if j in edited else []
        if j in shifted:
            notes.append(f"moved from event {was.number} in {since}" if numbered(was) else "moved")
        note = ", ".join(notes)
        a, b = compared(was), compared(row)
        if a == b:
            if j in edited:
                old_keys, new_keys = content(was.event), content(row.event)
                keys = sorted(k for k in {*old_keys, *new_keys} if old_keys.get(k) != new_keys.get(k))
                note += f" in {', '.join(keys)}, which the print does not show"
            return context(row.above) + [f" {row.head[0]}  [{note}]"]
        old_lines, new_lines = [*was.head, *was.body], [*row.head, *row.body]
        ops = difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes()
        # Each changed line with the line before and after it, and the event's first line
        wanted = {("new", 0)}
        for tag, i1, i2, j1, j2 in ops:
            if tag != "equal":
                wanted.update(("old", k) for k in range(i1, i2))
                wanted.update(("new", k) for k in range(j1 - 1, j2 + 1) if 0 <= k < len(b))
        out, gap = [], False
        for tag, i1, i2, j1, j2 in ops:
            sides = [("old", k) for k in range(i1, i2) if tag != "equal"] + [("new", k) for k in range(j1, j2)]
            for side, k in sides:
                if (side, k) not in wanted:
                    gap = True
                    continue
                if gap and out:
                    out.append("             ...")
                gap = False
                out.append(f"-{unnumbered(old_lines[k])}" if side == "old"
                           else f"{' ' if tag == 'equal' else '+'}{new_lines[k]}")
        out[0] += f"  [{note}]"
        return context(row.above) + out

    removed_at: dict[int, list[int]] = {}
    for i in range(len(old)):
        if i not in pairs:
            after = next((pairs[k] for k in range(i + 1, len(old)) if k in pairs), len(new))
            removed_at.setdefault(after, []).append(i)
    end = (new[-1].number + 1) if new else 1
    chunks: list[tuple[int, list[str]]] = []
    for j, row in enumerate(new):
        chunks += [(row.number, removal(i)) for i in removed_at.get(j, [])]
        if j in added:
            chunks.append((row.number, addition(j)))
        elif j in edited or j in shifted:
            chunks.append((row.number, change(j)))
    chunks += [(end, removal(i)) for i in removed_at.get(len(new), [])]
    return chunks, counts


def print_since(args: argparse.Namespace, project: c3.Project, sheets: dict[str, dict]) -> int:
    """The events added, changed, moved and removed since --since, sheet by sheet, as the editor words them."""
    commit, short = commit_of(project.root, args.since)
    since = short if short.startswith(args.since) else f"{args.since} ({short})"
    first, last = events_range(args.events)
    with tempfile.TemporaryDirectory(prefix="print-sheet-since-") as tmp:
        then = project_at(project, commit, Path(tmp))
        old_sheets = then.load_listed("eventSheets") if then else {}
        for name in args.sheets:
            if name not in sheets and name not in old_sheets:
                print(f"no event sheet named {name!r} on disk or in {since}; sheets: {', '.join(sheets)}")
                return 1        # an answer: on stdout
        names = args.sheets or [*sheets, *(n for n in old_sheets if n not in sheets)]
        if args.events and len(names) != 1:
            sys.exit(f"--events reads one sheet; name it: {', '.join(names)}")
        room = args.limit - 600 if args.limit else None     # the last line names a whole command
        same: list[str] = []
        for k, name in enumerate(names):
            if room is not None and room <= 0:
                print(stopped_line(args, name, None, last, names[k:]))
                return 0
            if name not in sheets:
                line = f"== {name}: removed since {since}, with its {numbered_below(old_sheets[name]['events'])} events"
                print(line)
                room = room and room - len(line) - 1
                continue
            new = list(sheet_rows(project, sheets[name]["events"], [0]))
            total = numbered_below(sheets[name]["events"])
            if name in old_sheets:
                chunks, counts = changes(list(sheet_rows(then, old_sheets[name]["events"], [0])), new, args.since)
                if not chunks:
                    same.append(name)
                    continue
                head = (f"== {name} since {since}: "
                        + ", ".join(f"{counts[kind]} {kind}" for kind in ("added", "changed", "moved", "removed")
                                    if counts[kind])
                        + "; event numbers as the sheet is on disk")
            else:
                chunks = [(r.number, [f"+{line}" for line in (*r.head, *r.body)]) for r in new]
                head = f"== {name}: new since {since}, {total} events"
            print(head)
            used = len(head) + 1
            for n, lines in chunks:
                if not within(n, first, last):
                    continue
                size = printed_length(lines)
                if room is not None and used + size > room and used > len(head) + 1:
                    print(stopped_line(args, name, n, last, names[k + 1:], total))
                    return 0
                print("\n".join(lines))
                used += size
            room = room and room - used
        if same:
            print(f"no event changed since {since} in {', '.join(same)}")
    return 0


def main() -> int:
    ap = c3.argument_parser(
        "Print event sheets as the editor words them: numbered events, conditions, actions. Read a sheet this "
        "way before and after an edit, and read an official example this way instead of its JSON.",
        "examples:\n"
        "  python scripts/print_sheet.py Game\n"
        "  python scripts/print_sheet.py Game --events 40-80   a part; the last line of a cut print names the next one\n"
        "  python scripts/print_sheet.py --outline Game        numbers and sids, to find the JSON behind a number\n"
        "  python scripts/print_sheet.py Game --show 5         event 5 as JSON\n"
        "  python scripts/print_sheet.py --find score          the events that use score, under the events they sit in\n"
        "  python scripts/print_sheet.py --project <Construct-Example-Projects>/example-projects/template-snake\n"
        "  python scripts/print_sheet.py Game --locale zh-CN   the editor's Chinese wording\n"
        "  python scripts/print_sheet.py --review              a project someone asked about\n"
        "  python scripts/print_sheet.py --since main          what changed since main, for a review or a hand-over\n\n"
        "exit codes: 0 printed, whole, the part that fits, or a long sheet's groups; 1 no such sheet, a range past\n"
        "the sheet's end, no event that uses the name of --find, project/clone not found, or a --since the\n"
        "project's history does not hold; 2 a sheet lacks a key the editor writes")
    ap.add_argument("sheets", nargs="*", metavar="SHEET", help="event sheet names (default: every sheet)")
    ap.add_argument("--events", metavar="A-B",
                    help="print only the events numbered A to B of one sheet; 40- runs to the end, 40 is one event")
    ap.add_argument("--outline", action="store_true",
                    help="print the event numbering with each event's sid, without conditions and actions")
    ap.add_argument("--show", type=int, metavar="N",
                    help="print event N of one sheet as JSON, to change and put back with edit_sheet.py's replace")
    ap.add_argument("--review", action="store_true",
                    help="for a project someone else wrote and asked about: end with what a review reports")
    ap.add_argument("--since", metavar="COMMIT",
                    help="print only the events added, changed, moved and removed since this commit, branch or tag "
                         "of the project's git history, the files on disk included")
    ap.add_argument("--find", metavar="NAME",
                    help="print only the events that use this variable, function or object, each under the events "
                         "it sits in; with --events, only those in the range")
    args = ap.parse_args()
    if args.find is not None and (args.outline or args.show is not None or args.since is not None):
        ap.error("--find prints events as the sheet words them; it does not take --outline, --show or --since")
    if args.find is not None and not args.find.strip():
        ap.error("--find takes the name of a variable, a function or an object")
    c3.utf8_output()
    findings = c3.Findings()
    c3.stop_with_a_sentence("print_sheet.py", findings)
    project = c3.Project.open(args, findings)
    c3.note_drift(project.rag)

    sheets = project.load_listed("eventSheets")
    files = project.listed_files("eventSheets")
    if args.since is not None:
        if args.outline or args.show is not None:
            sys.exit("--since prints what changed, as events; --outline and --show read the sheet as it is on disk")
        for name, path in files.items():
            if path and name in (args.sheets or sheets):
                c3.stamp(path)
        return print_since(args, project, sheets)
    if not sheets:
        scripts = project.scripts_summary()
        print((f"no event sheets: the project's logic is in its scripts, read them as code: {scripts}" if scripts
               else "no event sheets and no scripts: the project holds no logic yet")
              + "; events go into a new sheet with edit_sheet.py SHEET PLAN.json --new")
        return 0
    for name in args.sheets:
        if name not in sheets:
            print(f"no event sheet named {name!r}; sheets: {', '.join(sheets)}")      # an answer: on stdout
            return 1
    names = args.sheets or list(sheets)
    if (args.events or args.show is not None) and len(names) != 1:
        sys.exit(f"--events and --show read one sheet; name it: {', '.join(sheets)}")
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
    if args.find is not None:
        return print_found(args, project, sheets, names)

    rows, totals = {}, {}
    for name in names:
        counter = [0]
        events = sheets[name]["events"]
        rows[name] = list(outline_rows(events, counter) if args.outline else sheet_rows(project, events, counter))
        totals[name] = counter[0]
    if args.events and first > totals[names[0]]:
        print(f"sheet {names[0]} has {totals[names[0]]} events; --events {args.events} starts past its end")
        return 1        # an answer: on stdout

    whole = {name: part(rows[name], first, last, None)[0] for name in names}
    size = {name: printed_length([f"== {name}", *whole[name]]) for name in names}
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
    if not fits and not args.events and len(names) == 1:
        # The first 10 000 characters of a long sheet name nothing of the rest, and a model that wants one event
        # then prints the whole sheet with --limit 0; the list of its groups says which part to print.
        name = names[0]
        # The size counts what a whole print adds, the note on naming a variable and the review's line, as fits does
        lines, example = contents(args, name, rows[name], sheets[name]["events"], totals[name], size[name] + reserved,
                                  args.limit - 600 - (len(c3.REVIEW) + 1 if args.review else 0))
        print("\n".join(lines))
        if args.review:
            print(c3.REVIEW)        # above the line that says how to read on, which stays the last
        print(contents_end(args, name, example))
        return 0
    shown: list[str] = []
    for i, name in enumerate(names):
        lines, stopped = (whole[name], None) if room is None else part(rows[name], first, last, room)
        until = min(stopped - 1 if stopped else last or totals[name], totals[name])
        print(f"== {name}" if stopped is None and not args.events
              else f"== {name}: events {first}-{until} of {totals[name]}"
              + ("; a [context] row is an event these sit in, without its actions" if first > 1 else ""))
        if lines:
            print("\n".join(lines))
        if room is not None:
            room -= printed_length(lines)
        rest = names[i + 1:]
        shown += lines
        said = note and (not rest or stopped is not None or (room is not None and room <= 0)) and naming_note(shown)
        if said:
            print(said)
        if stopped is not None or (rest and room is not None and room <= 0):
            if args.review:
                print(c3.REVIEW)        # above the line that names the rest, which stays the last
            print(stopped_line(args, name, stopped, last, rest, totals[name]))
            break
    else:
        if args.review:
            print(c3.REVIEW)
    return 0


if __name__ == "__main__":
    sys.exit(main())
