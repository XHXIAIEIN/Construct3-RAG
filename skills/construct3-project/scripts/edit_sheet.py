"""Change an event sheet from a plan: events put in, moved, replaced or taken out by the editor's numbers.

    python scripts/edit_sheet.py SHEET PLAN.json [--dry-run] [--project FOLDER] [--rag FOLDER] [--locale en-US]

PLAN.json is a list of operations. A number is an event number of the sheet
as it is on disk, the one print_sheet.py prints and check_project.py names,
whatever the operations before it do:

    {"after": 8, "events": [...]}          beside event 8, below it and its sub-events
    {"before": 3, "events": [...]}         above event 3 and the comments directly above it
    {"into": 3, "events": [...]}           as the last sub-events of event 3; 0 is the sheet itself
    {"replace": 5, "events": [...]}        in the place of event 5 and its sub-events; one event keeps its sid
                                           and the number 5 for the operations below
    {"remove": 5}                          event 5, its sub-events and the comments directly above it
    {"move": 7, "after": 6}                or "before" or "into"; the comments directly above go with it
    {"event": 2, "add-actions": [...]}     after its last action; "position": 1 makes the first new one the first
    {"event": 2, "add-conditions": [...]}
    {"event": 5, "condition": 1, "set": {"parameters": {"type": "start"}}}
    {"event": 8, "action": 2, "set": {"id": "set-text"}}       the place is the one a finding of the checker names
    {"event": 2, "condition": 1, "set": {"isInverted": null}}  null takes a key out; parameters are set one by one
    {"event": 4, "set": {"title": "Input", "disabled": true}}  the event's own values
    {"event": 6, "action": 3, "remove": true}

An event is written as the sheet's JSON holds it, and may leave out what the
editor always writes the same way: {"eventType": "variable", "name": "lives"}
becomes a number 0 with its comment, isStatic, isConstant and sid. Leave
`sid` out of what is new: each event, condition, action and function
parameter gets one the project does not use. A condition or action is the
`write:` line of lookup_ace.py with its values filled in.

Nothing is written unless the whole plan holds: the sheet it makes is checked
like check_project.py checks the project, and a problem the plan would add is
printed instead, with the file left as it was. A problem that was there
before does not stop it. It ends with the changed events as the editor words
them, under their new numbers, and the checker's last line.

print_sheet.py SHEET --show N prints event N as JSON, to change and put back
with "replace". The file is written as the editor writes it: tabs, LF, no
newline at the end.

exit codes: 0 written, or a dry run that would be; 1 nothing written: the plan
cannot be read, names an event the sheet does not have, or adds a problem; or
the project or the clone was not found; 2 a project file lacks a key the
editor always writes
"""
import copy
import json
import os
import random
import re
import sys
from pathlib import Path

import c3project as c3
import check_project
import print_sheet
from c3project import NUMBERED

NEEDED, SID, IF_GIVEN = "needed", "sid", "if given"
INITIAL = {"number": "0", "string": "", "boolean": "false"}
FUNCTION = [("functionDescription", ""), ("functionCategory", ""), ("functionReturnType", "none"),
            ("functionCopyPicked", False), ("functionIsAsync", False), ("functionParameters", list),
            ("eventType", NEEDED), ("conditions", list), ("actions", list), ("sid", SID), ("children", IF_GIVEN)]
# The keys the editor writes for each kind of event, in its order, with the
# value it writes when nothing else is said: read from the 46 000 events of the
# official examples, saved by 126 releases.
EVENTS = {
    "block": [("eventType", NEEDED), ("conditions", list), ("actions", list), ("sid", SID), ("disabled", IF_GIVEN),
              ("children", IF_GIVEN), ("isOrBlock", IF_GIVEN)],
    "group": [("eventType", NEEDED), ("disabled", False), ("title", NEEDED), ("description", ""),
              ("isActiveOnStart", True), ("children", list), ("sid", SID)],
    "variable": [("eventType", NEEDED), ("name", NEEDED), ("type", "number"), ("initialValue", None), ("comment", ""),
                 ("isStatic", False), ("isConstant", False), ("sid", SID)],
    "comment": [("eventType", NEEDED), ("text", NEEDED)],
    "include": [("eventType", NEEDED), ("includeSheet", NEEDED)],
    "function-block": [("functionName", NEEDED), *FUNCTION],
    "custom-ace-block": [("aceType", "action"), ("aceName", NEEDED), ("objectClass", NEEDED), *FUNCTION],
}
PARAMETER = [("name", NEEDED), ("type", "number"), ("initialValue", None), ("comment", ""), ("sid", SID)]
ACES = {"id": [("id", NEEDED), ("objectClass", NEEDED), ("sid", SID), ("behaviorType", IF_GIVEN), ("disabled", IF_GIVEN),
               ("parameters", IF_GIVEN), ("isInverted", IF_GIVEN)],
        "callFunction": [("callFunction", NEEDED), ("sid", SID), ("parameters", IF_GIVEN)],
        "customAction": [("customAction", NEEDED), ("objectClass", NEEDED), ("customActionObjectClass", IF_GIVEN),
                         ("sid", SID), ("disabled", IF_GIVEN), ("parameters", IF_GIVEN)]}
HOLDS_EVENTS = ("block", "group", "function-block", "custom-ace-block")
PLACES = ("after", "before", "into")


class PlanError(Exception):
    pass


# --- what the plan holds, written the way the editor writes it ----------------------------------
def filled(given: dict, keys: list, where: str) -> dict:
    """given with the editor's keys in the editor's order, then whatever else it holds."""
    out = {}
    for key, default in keys:
        if key in given:
            out[key] = given[key]
        elif default == NEEDED:
            raise PlanError(f"{where} needs {key!r}")
        elif default == SID:
            out[key] = None
        elif default != IF_GIVEN:
            out[key] = default() if callable(default) else default
    if "initialValue" in out:
        if out["type"] not in INITIAL:
            raise PlanError(f"{where}: type is 'number', 'string' or 'boolean', not {out['type']!r}")
        value = given.get("initialValue", INITIAL[out["type"]])
        out["initialValue"] = str(value).lower() if isinstance(value, bool) else str(value)   # the editor keeps a string
    return {**out, **{k: v for k, v in given.items() if k not in out}}


def in_order(entry: dict) -> None:
    """The keys of an event, condition or action that is already in the sheet, as the editor orders them; none added."""
    template = EVENTS.get(entry.get("eventType")) or next((keys for kind, keys in ACES.items() if kind in entry), [])
    kept = {**{key: entry[key] for key, _ in template if key in entry}, **entry}
    entry.clear()
    entry.update(kept)


def assign(entry: dict, values: dict, name: str, fixed: tuple[str, ...]) -> None:
    """values into entry: a parameter at a time, null to take a key out. Only
    keys the editor writes for this kind of entry, or that it already has: a
    key of the plan's own making would stay in the file and mean nothing."""
    template = EVENTS.get(entry.get("eventType")) or next((keys for kind, keys in ACES.items() if kind in entry), [])
    known = [key for key in dict.fromkeys([*(key for key, _ in template), *entry]) if key not in fixed]
    what = f"a {entry['eventType']}" if "eventType" in entry else "a condition or action"
    for key, value in values.items():
        if key in fixed:
            raise PlanError(f"{name}: \"set\" changes values, not {key!r}; put the event back whole with \"replace\", "
                            f"or use \"add-actions\", \"add-conditions\" and \"remove\"")
        if key not in known:
            raise PlanError(f"{name}: {key!r} is not a value of {what}, which has: {', '.join(known)}"
                            + c3.closest(key, known, n=1)
                            + ("; a condition or an action of the event is changed by its number, "
                               '{"event": N, "condition": 1, "set": {"isInverted": null}}' if "conditions" in entry else ""))
        if key == "parameters" and isinstance(value, dict) and isinstance(entry.get("parameters"), dict):
            entry["parameters"].update(value)
            for k in [k for k, v in value.items() if v is None]:
                del entry["parameters"][k]
        elif value is None or (key == "isInverted" and value is False):     # the editor writes isInverted only when true
            entry.pop(key, None)
        else:
            entry[key] = value
    in_order(entry)


def new_ace(ace, where: str) -> dict:
    if not isinstance(ace, dict):
        raise PlanError(f"{where} is {json.dumps(ace)[:60]}, not an object")
    if ace.get("type") in ("comment", "script"):
        return dict(ace)
    kind = next((k for k in ACES if k in ace), None)
    if kind is None:
        raise PlanError(f"{where} has no 'id': write it as the write: line of lookup_ace.py gives it, "
                        f'{{"id": ..., "objectClass": ..., "parameters": {{...}}}}; a function call is '
                        f'{{"callFunction": "name", "parameters": ["expression", ...]}}')
    return filled(ace, ACES[kind], where)


def new_event(ev, where: str) -> dict:
    if not isinstance(ev, dict):
        raise PlanError(f"{where} is {json.dumps(ev)[:60]}, not an object")
    kind = ev.get("eventType")
    if kind == "script":
        return copy.deepcopy(ev)
    if kind not in EVENTS:
        raise PlanError(f"{where}: eventType is {kind!r}; it is one of {', '.join(EVENTS)}. An event with conditions "
                        f"and actions is a 'block'")
    out = filled(ev, EVENTS[kind], f"{where}, a {kind}")
    for key in ("conditions", "actions"):
        if key in out:
            out[key] = [new_ace(a, f"{where} {key[:-1]} {i}") for i, a in enumerate(as_list(out[key], f"{where} {key}"), 1)]
    if "functionParameters" in out:
        out["functionParameters"] = [filled(fp, PARAMETER, f"{where} parameter {i}") for i, fp in
                                     enumerate(as_list(out["functionParameters"], f"{where} functionParameters"), 1)]
    if "children" in out:
        out["children"] = [new_event(c, f"{where} sub-event {i}") for i, c in
                           enumerate(as_list(out["children"], f"{where} children"), 1)]
    return out


def as_list(value, where: str) -> list:
    """A list, or the one object that was written without the brackets."""
    if isinstance(value, dict):
        return [value]
    if not isinstance(value, list):
        raise PlanError(f"{where} is {json.dumps(value)[:60]}, not a list [...]")
    return value


def count(things: list, word: str) -> str:
    return f"{len(things)} {word}{'' if len(things) == 1 else 's'}"


def sids_of(obj) -> list[int]:
    if isinstance(obj, dict):
        return [v for k, v in obj.items() if k == "sid" and isinstance(v, int)] + [s for v in obj.values() for s in sids_of(v)]
    return [s for v in obj for s in sids_of(v)] if isinstance(obj, list) else []


def give_sids(obj, used: set[int]) -> int:
    """A sid for every new entry that has none the project is free of; returns how many were given."""
    given = 0
    if isinstance(obj, dict):
        if "sid" in obj:
            sid = obj["sid"]
            if not isinstance(sid, int) or isinstance(sid, bool) or sid <= 0 or sid in used:
                while (sid := random.randrange(10 ** 14, 10 ** 15)) in used:
                    pass
                obj["sid"], given = sid, 1
            used.add(sid)
        return given + sum(give_sids(v, used) for k, v in obj.items() if k != "sid")
    return sum(give_sids(v, used) for v in obj) if isinstance(obj, list) else 0


# --- the sheet as a tree the editor's numbers point into ------------------------------------------
def numbers(events: list, counter: list[int], out: dict | None = None) -> dict[int, tuple[int, int]]:
    """id(event) -> (its number, the last number below it). A variable, comment
    or include carries the number of the next numbered row, as in print_sheet.py."""
    out = {} if out is None else out
    for ev in events:
        numbered = ev.get("eventType") in NUMBERED
        counter[0] += numbered
        first = counter[0] + (not numbered)
        numbers(ev.get("children", []), counter, out)
        out[id(ev)] = (first, max(first, counter[0]))
    return out


def place_of(events: list, node: dict) -> tuple[list, int] | None:
    """The list that holds node, and where."""
    for i, ev in enumerate(events):
        if ev is node:
            return events, i
        found = place_of(ev.get("children", []), node)
        if found:
            return found
    return None


def with_comments(siblings: list, i: int) -> int:
    """The index of the first of the comments directly above siblings[i]: they are about it."""
    while i and siblings[i - 1].get("eventType") == "comment":
        i -= 1
    return i


class Plan:
    def __init__(self, sheet: dict, used: set[int]) -> None:
        self.sheet = copy.deepcopy(sheet)
        self.used = set(used)
        self.by_number = {}
        self.index(self.sheet["events"], [0])
        self.total = len(self.by_number)
        self.done: list[tuple[str, list[dict]]] = []      # what each operation says it did, and the events to show
        self.own_row: set[int] = set()                    # events shown without their sub-events: only their actions changed
        self.operation_of: dict[int, int] = {}            # sid of a new entry, or of the event it went into -> operation
        self.sids_given = 0
        self.gone: dict[int, str] = {}                    # id of an event taken out -> which operation did it, and how

    def index(self, events: list, counter: list[int]) -> None:
        for ev in events:
            if ev.get("eventType") in NUMBERED:
                counter[0] += 1
                self.by_number[counter[0]] = ev
            self.index(ev.get("children", []), counter)

    def event(self, n, op: str, zero: bool = False) -> dict | None:
        if isinstance(n, bool) or not isinstance(n, int) or not (0 if zero else 1) <= n <= self.total:
            raise PlanError(f"{op}: {json.dumps(n)} is not an event of the sheet, which has {self.total}"
                            + ("; 0 is the sheet itself" if zero else ""))
        return self.by_number.get(n)

    def place(self, node: dict, n: int, op: str) -> tuple[list, int]:
        found = place_of(self.sheet["events"], node)
        if not found:
            raise PlanError(f"{op}: event {n} is gone, {self.gone.get(id(node), 'an operation before this one took it out')}; "
                            f"what is kept of an event goes into the \"events\" that replace it, or a \"move\" takes it out first")
        return found

    def forget(self, taken: list[dict], said: str) -> None:
        numbers = {id(ev): n for n, ev in self.by_number.items()}
        for top in taken:
            held = f"{said} event {numbers[id(top)]}, which held it" if id(top) in numbers else said + " the event that held it"
            self.gone[id(top)] = said + " it"
            stack = list(top.get("children", []))
            while stack:
                ev = stack.pop()
                self.gone[id(ev)] = held
                stack.extend(ev.get("children", []))

    def put(self, events: list[dict], where: str, n: int, op: str) -> None:
        if where == "into":
            target = self.event(n, op, zero=True)
            if target is None:
                self.sheet["events"].extend(events)
                return
            self.place(target, n, op)
            if target.get("eventType") not in HOLDS_EVENTS:
                raise PlanError(f"{op}: event {n} is a {target.get('eventType')}, which holds no sub-events")
            target.setdefault("children", []).extend(events)
            in_order(target)
            return
        siblings, i = self.place(self.event(n, op), n, op)
        i = with_comments(siblings, i) if where == "before" else i + 1
        siblings[i:i] = events

    def take(self, n: int, op: str, comments: bool) -> list[dict]:
        siblings, i = self.place(self.event(n, op), n, op)
        first = with_comments(siblings, i) if comments else i
        taken = siblings[first:i + 1]
        del siblings[first:i + 1]
        return taken

    def new_events(self, op: dict, name: str) -> list[dict]:
        if not op.get("events"):
            raise PlanError(f"{name} needs \"events\": [...], the events to put there")
        events = [new_event(ev, f"{name} event {i}") for i, ev in enumerate(as_list(op["events"], f"{name} events"), 1)]
        return events

    def amend(self, op: dict, n, name: str) -> None:
        """Values of an event, or of one of its conditions or actions, set; or a condition or action taken out.
        The place is the one a finding names: sheet Game event 5 condition 1."""
        target = self.event(n, name)
        self.place(target, n, name)
        kinds = [k for k in ("condition", "action") if k in op]
        if len(kinds) > 1 or {"add-actions", "add-conditions", "position"} & set(op) or ("set" in op) == ("remove" in op):
            raise PlanError(f'{name} is one of {{"event": N, "set": {{...}}}}, {{"event": N, "condition"|"action": J, '
                            f'"set": {{...}}}} and {{"event": N, "condition"|"action": J, "remove": true}}')
        if "set" in op and not isinstance(op["set"], dict):
            raise PlanError(f"{name}: \"set\" is an object of the values to change, {{\"id\": \"set-text\"}}")
        if not kinds:
            if "remove" in op:
                raise PlanError(f"{name}: an event is removed with {{\"remove\": {n}}}")
            assign(target, op["set"], name, ("sid", "eventType", "conditions", "actions", "children", "functionParameters"))
            said = f"event {n} changed"
        else:
            kind, j = kinds[0], op[kinds[0]]
            entries = target.get(kind + "s")
            if entries is None:
                raise PlanError(f"{name}: event {n} is a {target.get('eventType')}, which has no {kind}s")
            if isinstance(j, bool) or not isinstance(j, int) or not 1 <= j <= len(entries):
                raise PlanError(f"{name}: event {n} has {count(entries, kind)}, and {json.dumps(j)} is not one of them")
            if "remove" in op:
                if op["remove"] is not True:
                    raise PlanError(f"{name}: \"remove\" is true")
                self.used -= set(sids_of(entries.pop(j - 1)))
                said = f"{kind} {j} of event {n} removed"
            else:
                assign(entries[j - 1], op["set"], name, ("sid",))
                said = f"{kind} {j} of event {n} changed"
        self.done.append((said, [target]))
        self.own_row.add(id(target))

    def apply(self, op, i: int) -> None:
        self.change(op, i)
        for sid in sids_of(self.done[-1][1]):
            self.operation_of.setdefault(sid, i)

    def change(self, op, i: int) -> None:
        name = f"operation {i}"
        if not isinstance(op, dict):
            raise PlanError(f"{name} is {json.dumps(op)[:60]}, not an object such as {{\"after\": 8, \"events\": [...]}}")
        places = [k for k in ("replace", "remove", *PLACES) if k in op]
        verb = "move" if "move" in op else "event" if "event" in op else places[0] if len(places) == 1 else None
        allowed = {"move": {"move", *PLACES}, "remove": {"remove"},
                   "event": {"event", "add-actions", "add-conditions", "position", "condition", "action", "set", "remove"},
                   }.get(verb, {verb, "events"})
        if verb == "event" and "add-events" in op:
            raise PlanError(f"{name}: sub-events go into an event with {{\"into\": {json.dumps(op['event'])}, \"events\": [...]}}")
        if verb is None or set(op) - allowed:
            raise PlanError(f"{name} has the keys {', '.join(op) or 'none'}; an operation is one of: "
                            '{"after"|"before"|"into"|"replace": N, "events": [...]}, {"remove": N}, '
                            '{"move": N, "after"|"before"|"into": M}, {"event": N, "add-actions"|"add-conditions": [...]}, '
                            '{"event": N, "condition"|"action": J, "set": {...}}, {"event": N, "set": {...}}, '
                            '{"event": N, "condition"|"action": J, "remove": true}')
        n = op[verb]
        name = f"{name} ({verb} {json.dumps(n)})"
        if verb in PLACES:
            events = self.new_events(op, name)
            self.put(events, verb, n, name)
            self.sids_given += give_sids(events, self.used)
            self.done.append((f"{count(events, 'event')} {verb} event {n}" if n else f"{count(events, 'event')} at the end", events))
        elif verb == "replace":
            events = self.new_events(op, name)
            siblings, at = self.place(self.event(n, name), n, name)
            self.used -= set(sids_of(siblings[at]))
            if len(events) == 1 and events[0].get("sid", 0) is None:       # the same event with other contents
                events[0]["sid"] = siblings[at].get("sid")
            self.forget([siblings[at]], f"operation {i} replaced")
            if len(events) == 1 and events[0].get("eventType") in NUMBERED:
                self.by_number[n] = events[0]                              # the number stays with what stands there now
            siblings[at:at + 1] = events
            self.sids_given += give_sids(events, self.used)
            self.done.append((f"event {n} replaced by {count(events, 'event')}", events))
        elif verb == "remove":
            taken = self.take(n, name, comments=True)
            self.forget(taken, f"operation {i} removed")
            self.used -= set(sids_of(taken))
            self.done.append((f"event {n} removed" + (f", with {count(taken[1:], 'comment')} above it" if taken[1:] else ""), []))
        elif verb == "move":
            where = [k for k in PLACES if k in op]
            if len(where) != 1:
                raise PlanError(f"{name} needs one of \"after\", \"before\", \"into\": the event it goes to")
            moved = self.event(n, name)
            target = self.event(op[where[0]], name, zero=where[0] == "into")
            if target is not None and (target is moved or place_of(moved.get("children", []), target)):
                raise PlanError(f"{name}: event {op[where[0]]} is event {n} or inside it")
            taken = self.take(n, name, comments=True)
            self.put(taken, where[0], op[where[0]], name)
            self.done.append((f"event {n} moved {where[0]} event {op[where[0]]}", taken))
        elif {"condition", "action", "set", "remove"} & set(op):
            self.amend(op, n, name)
        else:
            target = self.event(n, name)
            self.place(target, n, name)
            lists = [k for k in ("add-conditions", "add-actions") if k in op]
            if not lists or ("position" in op and len(lists) > 1):
                raise PlanError(f"{name} needs \"add-actions\" or \"add-conditions\"; \"position\" goes with one of them")
            for key in lists:
                kind = key[4:]
                if kind not in target:
                    raise PlanError(f"{name}: event {n} is a {target.get('eventType')}, which has no {kind}")
                aces = [new_ace(a, f"{name} {kind[:-1]} {j}") for j, a in enumerate(as_list(op[key], f"{name} {key}"), 1)]
                at = op.get("position", len(target[kind]) + 1)
                if isinstance(at, bool) or not isinstance(at, int) or not 1 <= at <= len(target[kind]) + 1:
                    raise PlanError(f"{name}: position is 1 to {len(target[kind]) + 1}, event {n} has {len(target[kind])} {kind}")
                target[kind][at - 1:at - 1] = aces
                self.sids_given += give_sids(aces, self.used)
            self.done.append((f"{' and '.join(count(as_list(op[k], k), k[4:-1]) for k in lists)} added to event {n}", [target]))
            self.own_row.add(id(target))


# --- checking, writing, reporting -----------------------------------------------------------------
REFUSED_STYLE = ("comment", "run", "cases", "tick")     # the style kinds of check_project.check_style a plan may not add


def findings_of(project: c3.Project, args, sheets: dict | None) -> tuple[check_project.Checker, c3.Findings]:
    """The project checked, with a sheet that is not on disk yet in the place of the one that is."""
    fresh = c3.Findings()
    # Style warnings on: what a plan adds is the agent's own writing, and only the
    # warnings new after the plan are printed, so the sheet's older events stay quiet.
    checker = check_project.Checker(c3.Project(project.root, project.rag, args.locale, fresh), sheets=sheets, style=True)
    checker.check()
    return checker, fresh


def unnumbered(finding: str) -> str:
    """A finding without its event number, which an insert above it changes; the sid stays."""
    return re.sub(r" event \d+ ", " event ", finding)


def main() -> int:
    ap = c3.argument_parser(
        "Change an event sheet from a plan, a JSON file of operations addressed by the editor's event numbers: "
        "events put in, moved, replaced or removed, conditions and actions added, changed or removed. New entries "
        "get their sids and the keys the editor always writes. The result is checked before it is written; a plan "
        "that adds a problem changes nothing.",
        "a plan:\n"
        '  [{"before": 1, "events": [{"eventType": "variable", "name": "timeLeft", "initialValue": "30"}]},\n'
        '   {"event": 2, "add-actions": [{"id": "set-text", "objectClass": "ScoreText", "parameters": {"text": "timeLeft"}}]},\n'
        '   {"event": 7, "action": 2, "set": {"parameters": {"text": "\\"Score: \\" & score"}}},\n'
        '   {"event": 5, "condition": 1, "set": {"isInverted": null}}, {"event": 6, "action": 3, "remove": true},\n'
        '   {"into": 3, "events": [{"eventType": "block", "conditions": [...], "actions": [...]}]},\n'
        '   {"after": 8, "events": [{"eventType": "group", "title": "Timer", "children": [...]}]},\n'
        '   {"move": 7, "after": 6}, {"replace": 5, "events": [...]}, {"remove": 4}]\n'
        "Every number is one of the sheet as print_sheet.py prints it now, and as a finding of check_project.py\n"
        "names it: event 5 condition 1. \"into\": 0 is the end of the sheet.\n\n"
        "examples:\n"
        "  python scripts/edit_sheet.py Game plan.json\n"
        "  python scripts/edit_sheet.py Game plan.json --dry-run   check the plan and show the result, write nothing\n"
        "  python scripts/print_sheet.py Game --show 5             event 5 as JSON, to change and put back with replace\n\n"
        "exit codes: 0 written, or a dry run that would be; 1 nothing written: the plan cannot be read, names an\n"
        "event the sheet does not have or adds a problem, or project/clone not found; 2 a project file lacks a key\n"
        "the editor always writes")
    ap.add_argument("sheet", metavar="SHEET", help="the event sheet's name")
    ap.add_argument("plan", metavar="PLAN.json", help="the operations, a JSON list")
    ap.add_argument("--dry-run", action="store_true", help="check the plan and print the result, write nothing")
    args = ap.parse_args()
    c3.utf8_output()
    findings = c3.Findings()
    c3.stop_with_a_sentence("edit_sheet.py", findings)
    project = c3.Project.open(args, findings)
    drift = c3.skill_drift(project.rag)
    if drift:
        print(f"note: {drift}")

    path = project.listed_files("eventSheets").get(args.sheet)
    if path is None:
        sys.exit(f"no event sheet named {args.sheet!r}; sheets: {', '.join(project.listed_files('eventSheets'))}")
    on_disk = path.read_text(encoding="utf-8")
    sheet = json.loads(on_disk)
    try:
        text = Path(args.plan).read_text(encoding="utf-8-sig")
    except OSError as e:
        sys.exit(f"{args.plan}: {e.strerror}; PLAN.json is a file with the operations as a JSON list")
    try:
        operations = json.loads(text)
    except json.JSONDecodeError as e:
        sys.exit(f"{args.plan} is not valid JSON, line {e.lineno} column {e.colno}: {e.msg}"
                 + ("; it holds <new sid>: leave \"sid\" out, every new entry gets one" if "<new sid>" in text else ""))

    before, found_before = findings_of(project, args, None)
    existing = set(before.sids) | set(before.ace_sids)      # the sheet's events before the plan; the rest it creates
    plan = Plan(sheet, set(existing))
    try:
        if not operations:
            raise PlanError(f"{args.plan} holds no operation; a plan is a list such as "
                            '[{"after": 8, "events": [...]}]')
        for i, op in enumerate(operations if isinstance(operations, list) else [operations], 1):
            plan.apply(op, i)
    except PlanError as e:
        sys.exit(f"{e}\nnothing was written")

    after, found_after = findings_of(project, args, {args.sheet: plan.sheet})
    known = {unnumbered(e) for e in found_before.errors}
    added = [e for e in found_after.errors if unnumbered(e) not in known]
    # An event the plan created, without a comment above it, with eight actions in a row
    # and no comment action, or with case sub-events and no comment above any of them, is
    # refused like a problem: the fix is one comment, and a
    # warning was not acted on in half the small-model runs of 2026-09-22
    # (event-sheet-design-guidance.md). An event the plan moved or extended is the user's;
    # a finding on it prints as a warning below.
    known_style = {unnumbered(m) for _, m in found_before.style}
    added += [m for kind, m in found_after.style if kind in REFUSED_STYLE and unnumbered(m) not in known_style
              and (sid := re.search(r"\(sid (\d+)\)", m)) and int(sid.group(1)) not in existing]
    if added:
        # The event number of a finding is one the sheet would have; the plan's author knows the operation.
        sid_in = [re.search(r"\(sid (\d+)\)", e) for e in added]
        added = [(f"operation {plan.operation_of[int(m.group(1))]}: " if m and int(m.group(1)) in plan.operation_of else "") + e
                 for e, m in zip(added, sid_in)]
        fit = max(c3.fitting(added, args.limit and max(args.limit - 300, 3)), 1)
        print("\n".join(added[:fit]))
        print((f"... and {len(added) - fit} more\n" if fit < len(added) else "")
              + f"the plan adds {len(added)} problem(s) to the project; nothing was written")
        return 1

    layout = json.dumps(plan.sheet, indent="\t", ensure_ascii=False)
    if not args.dry_run:
        draft = path.with_name(path.name + ".tmp")
        draft.write_text(layout, encoding="utf-8", newline="\n")
        os.replace(draft, path)

    # What changed, as the editor words it, under the numbers the sheet has now.
    span = numbers(plan.sheet["events"], [0])
    rows = list(print_sheet.sheet_rows(after.p, plan.sheet["events"], [0]))
    total = max((last for _, last in span.values()), default=0)
    room = args.limit - 600 if args.limit else None
    print(f"{args.sheet}: {count(plan.done, 'operation')}, {plan.total} events before and {total} now, "
          f"{plan.sids_given} new sids" + (" (dry run)" if args.dry_run else ""))
    for said, events in plan.done:
        shown = [(span[id(ev)][0],) * 2 if id(ev) in plan.own_row else span[id(ev)] for ev in events if id(ev) in span]
        if not shown:
            print(f"-- {said}")
            continue
        first, last = min(a for a, _ in shown), min(max(b for _, b in shown), total)
        lines, stopped = print_sheet.part(rows, first, last, room)
        print(f"-- {said}: now event{'s' if last > first else ''} {first}{f'-{last}' if last > first else ''}"
              + (f"; shown up to {stopped - 1}, the rest with print_sheet.py" if stopped else ""))
        if room is None or room > 0:
            print("\n".join(lines))
            room = None if room is None else room - sum(len(line) + 1 for line in lines)
    known_warnings = {unnumbered(w) for w in found_before.warnings}
    for w in found_after.warnings:
        if unnumbered(w) not in known_warnings:
            print(f"warning: {w}")
    if on_disk.replace("\r\n", "\n") != json.dumps(sheet, indent="\t", ensure_ascii=False) and not args.dry_run:
        print(f"note: {path.name} was not laid out as the editor writes it (tabs, LF); it is now, so its diff is the whole file")
    if found_after.errors:
        print(f"{len(found_after.errors)} problem(s) were in the project before this plan and still are: "
              f"check_project.py lists them")
    else:
        print(after.ok_line(then_open=not args.dry_run))
    if args.dry_run:
        print("dry run: nothing was written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
