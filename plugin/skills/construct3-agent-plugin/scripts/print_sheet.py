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

--since COMMIT prints what changed in the sheets since a commit, branch or
tag of the project's git history, the files on disk included: each event
added (+), removed (-) or changed (its lines that changed, - before and +
after), and each one moved to another place, under the numbers of the sheet
now and the events it sits in, marked [context]. An event is the same event
when its content is, conditions, actions and values, or else when its sid is;
the sids alone do not say it, because a generator run gives them anew. The old
sheet is worded from the object types the commit holds.

A harness cuts long tool output, so printing stops at --limit characters, at
an event, and the last line gives the --events range that continues. A part
printed with --events starts with the events it sits in, marked [context]
and without their actions. Without a sheet name, a project whose sheets do
not fit the limit prints the list of its sheets instead.
"""
import collections
import difflib
import io
import json
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
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
    event: dict | None = None   # the event, comment or variable printed


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
        row = Row(counter[0] if et in NUMBERED else counter[0] + 1, head, body, above, ev)
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
    words += ["--since", quoted(args.since)] if args.since else []
    words += ["--events", events] if events else []
    words += ["--outline"] if args.outline else []
    for flag, default in (("project", None), ("rag", None), ("locale", "en-US"), ("limit", c3.LIMIT)):
        if getattr(args, flag) != default:
            words += [f"--{flag}", quoted(getattr(args, flag))]
    return " ".join(words)


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


def content(obj):
    """An event's own content, to compare: without its sub-events, and without the sids, which a generator
    run gives anew from its first changed line on."""
    if isinstance(obj, dict):
        return {k: content(v) for k, v in obj.items() if k not in ("sid", "children")}
    return [content(v) for v in obj] if isinstance(obj, list) else obj


def matched(old: list[Row], new: list[Row]) -> dict[int, int]:
    """Old row index -> new row index of the same event: the same sid and content, then the same content,
    then the same sid, then a row of the same kind in the same place with lines alike, such as an edited
    comment, which has no sid. When most events kept their content under another sid, the sids were given
    anew, as a generator run does, and a sid no longer names one event."""
    keys = {id(row): json.dumps(content(row.event), sort_keys=True, ensure_ascii=False) for row in (*old, *new)}

    def sid(row: Row):
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

    def place(rows: list[Row], k: int, at: dict, to_new) -> tuple:
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
            if difflib.SequenceMatcher(a=compared(old[i]), b=lines, autojunk=False).ratio() >= 0.5 \
                    or difflib.SequenceMatcher(a="\n".join(compared(old[i])), b="\n".join(lines),
                                               autojunk=False).ratio() >= 0.6:
                pairs[i] = j
                here.remove(i)
                break
    return pairs


def moved(old: list[Row], new: list[Row], pairs: dict[int, int]) -> set[int]:
    """The new rows of matched events that sit in another event, or in another order among the events that
    stayed beside them: out of the longest run of them that kept its order."""
    index = {id(r): k for rows in (old, new) for k, r in enumerate(rows)}
    parent_old = [index[id(r.above[-1])] if r.above else None for r in old]
    parent_new = [index[id(r.above[-1])] if r.above else None for r in new]
    out, siblings = set(), {}
    for i, j in sorted(pairs.items(), key=lambda pair: pair[1]):
        po, pn = parent_old[i], parent_new[j]
        if (pairs.get(po) if po is not None else None) != pn or (po is None) != (pn is None):
            out.add(j)
        else:
            siblings.setdefault(pn, []).append((i, j))
    for kids in siblings.values():
        # the longest increasing run of old indexes, in new order
        best: list[list[tuple[int, int]]] = []
        for pair in kids:
            longest = max((run for run in best if run[-1][0] < pair[0]), key=len, default=[])
            best.append([*longest, pair])
        keep = set(max(best, key=len, default=[]))
        out.update(j for pair in kids if pair not in keep for _, j in [pair])
    return out


def compared(row: Row) -> list[str]:
    """A row's lines without its number and its sub-event numbers, which an edit elsewhere changes."""
    return [SUB_EVENTS.sub("", line)[5:] for line in (*row.head, *row.body)]


def unnumbered(line: str) -> str:
    """A line of the old sheet, whose numbers would read as the sheet's now."""
    return "     " + SUB_EVENTS.sub("", line)[5:]


def changes(old: list[Row], new: list[Row], since: str) -> tuple[list[tuple[int, list[str]]], collections.Counter]:
    """The changes of one sheet in the order of the sheet now, each with the number of the event it prints
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

    def context(chain) -> list[str]:
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


def print_since(args, project: c3.Project, sheets: dict[str, dict]) -> int:
    """The events added, changed, moved and removed since --since, sheet by sheet, as the editor words them."""
    commit, short = commit_of(project.root, args.since)
    since = short if short.startswith(args.since) else f"{args.since} ({short})"
    first, last = events_range(args.events)
    with tempfile.TemporaryDirectory(prefix="print-sheet-since-") as tmp:
        then = project_at(project, commit, Path(tmp))
        old_sheets = then.load_listed("eventSheets") if then else {}
        for name in args.sheets:
            if name not in sheets and name not in old_sheets:
                sys.exit(f"no event sheet named {name!r} now or in {since}; sheets: {', '.join(sheets)}")
        names = args.sheets or [*sheets, *(n for n in old_sheets if n not in sheets)]
        if args.events and len(names) != 1:
            sys.exit(f"--events reads one sheet; name it: {', '.join(names)}")
        room = args.limit - 600 if args.limit else None     # the last line names a whole command
        same: list[str] = []
        for k, name in enumerate(names):
            if room is not None and room <= 0:
                print(f"-- stopped at the limit of {args.limit} characters (--limit). The rest: "
                      f"{again(args, names[k:], None)}")
                return 0
            if name not in sheets:
                line = (f"== {name}: removed since {since}, with its "
                        f"{sum(1 for _ in c3.numbered_events(old_sheets[name]['events']))} events")
                print(line)
                room = room and room - len(line) - 1
                continue
            new = list(sheet_rows(project, sheets[name]["events"], [0]))
            total = sum(1 for _ in c3.numbered_events(sheets[name]["events"]))
            if name in old_sheets:
                chunks, counts = changes(list(sheet_rows(then, old_sheets[name]["events"], [0])), new, args.since)
                if not chunks:
                    same.append(name)
                    continue
                head = (f"== {name} since {since}: "
                        + ", ".join(f"{counts[kind]} {kind}" for kind in ("added", "changed", "moved", "removed")
                                    if counts[kind])
                        + "; event numbers are the sheet's now")
            else:
                chunks = [(r.number, [f"+{line}" for line in (*r.head, *r.body)]) for r in new]
                head = f"== {name}: new since {since}, {total} events"
            print(head)
            used = len(head) + 1
            for n, lines in chunks:
                if n < first or (last is not None and n > last):
                    continue
                size = sum(len(line) + 1 for line in lines)
                if room is not None and used + size > room and used > len(head) + 1:
                    more = [again(args, [name], f"{n}-{last or ''}")] + (
                        [again(args, names[k + 1:], None)] if names[k + 1:] else [])
                    print(f"-- stopped at the limit of {args.limit} characters (--limit), before event {n} of "
                          f"{total}. The rest: {'  then  '.join(more)}")
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
        "  python scripts/print_sheet.py --project <Construct-Example-Projects>/example-projects/template-snake\n"
        "  python scripts/print_sheet.py Game --locale zh-CN   the editor's Chinese wording\n"
        "  python scripts/print_sheet.py --review              a project someone asked about\n"
        "  python scripts/print_sheet.py --since main          what changed since main, for a review or a hand-over\n\n"
        "exit codes: 0 printed, whole or the part that fits; 1 no such sheet, a range past the sheet's end,\n"
        "project/clone not found, or a --since the project's history does not hold; 2 a sheet lacks a key the\n"
        "editor writes")
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
                         "of the project's git history, the files as they are now included")
    args = ap.parse_args()
    c3.utf8_output()
    findings = c3.Findings()
    c3.stop_with_a_sentence("print_sheet.py", findings)
    project = c3.Project.open(args, findings)
    c3.note_drift(project.rag)

    sheets = project.load_listed("eventSheets")
    if args.since is not None:
        if args.outline or args.show is not None:
            sys.exit("--since prints what changed, as events; --outline and --show read the sheet as it is now")
        for name, path in project.listed_files("eventSheets").items():
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
