"""Lay out the project folders of one eval iteration, one per test case and arm.

    python evals/make_fixtures.py RUNS_DIR [--arms with_skill without_skill] [--cases NAME ...]
                                  [--old-clone FOLDER] [--examples FOLDER]

RUNS_DIR must lie outside the Construct3-RAG clone: an agent started below
the clone reads its AGENTS.md, which routes to this skill, and a baseline
that has the skill is not a baseline. A project is the stand-in game of
assets/build_project.py, without tools/, so that the task is a hand edit of
a project made in the editor; or, for a fixture `example:<id>`, a copy of
that official example from --examples. A fixture of SEEDS is one of those with
a mistake small models make written into it, for a case that asks to fix it.

An arm named with_... holds the skill and the block as install.py leaves
them, without_... holds neither, and old_... holds the previous version of
the skill, installed by the install.py of --old-clone: a checkout of the
commit before the change, such as `git worktree add --detach FOLDER HEAD`
made before editing. The old copy then names the old checkout as its clone;
pointed at this one it would report that it differs and be refreshed.

exit codes: 0 laid out, 1 RUNS_DIR is inside the clone, a target exists, or
an example or the old clone is missing
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
REPO = SKILL.parent.parent
CASES = json.loads((Path(__file__).parent / "evals.json").read_text(encoding="utf-8"))["evals"]


def run(*cmd: str, cwd: Path) -> str:
    p = subprocess.run([sys.executable, *cmd], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if p.returncode:
        sys.exit(f"{' '.join(cmd)} failed in {cwd}:\n{p.stdout}{p.stderr}")
    return p.stdout


def stand_in(root: Path) -> Path:
    """The generated game, as tests/conftest.py builds it, with the
    generator and the skill taken out again: each arm installs its own. The
    seed holds what the editor would not write itself; the generator fills the
    rest of project.c3proj, so the fixture opens in the editor."""
    (root / "tools").mkdir(parents=True)
    (root / "project.c3proj").write_text(json.dumps({"uniqueId": "eval", "properties": {}}), encoding="utf-8")
    run(str(SKILL / "scripts" / "install.py"), "--project", str(root), cwd=root)
    shutil.copy(SKILL / "assets" / "build_project.py", root / "tools" / "build_project.py")
    run("tools/build_project.py", cwd=root)
    for left in ("tools", ".agents"):
        shutil.rmtree(root / left)
    (root / "AGENTS.md").unlink()
    return root


def seed_load_errors(root: Path) -> None:
    """Five mistakes the editor refuses, each one a small model has made
    (Construct3-RAG/docs/decisions/checker-editor-load-rules.md)."""
    path = root / "eventSheets" / "Game.json"
    sheet = json.loads(path.read_text(encoding="utf-8"))
    rows = sheet["events"]
    groups = {e.get("title"): e for e in rows if e["eventType"] == "group"}
    collect = next(e for e in rows if e["eventType"] == "custom-ace-block")
    add_score = next(e for e in rows if e["eventType"] == "function-block")

    def first_block(group: dict) -> dict:    # the comment above it is the group's first child
        return next(e for e in group["children"] if e["eventType"] == "block")

    call = next(a for a in collect["actions"] if a.get("callFunction") == "AddScore")
    tween = next(a for a in collect["actions"] if isinstance(a.get("parameters"), dict)
                 and a["parameters"].get("tags") == '"collect"')
    collect["actions"] = [a for a in collect["actions"] if a is not call]   # a trigger inside a custom action
    collect["children"] = [{
        "eventType": "block",
        "conditions": [{"id": "on-tweens-finished", "objectClass": "Coin", "sid": 611111111111111,
                        "behaviorType": "Tween", "parameters": {"tags": "\"collect\""}}],
        "actions": [call],
        "sid": 622222222222222,
    }]
    first_block(groups["Input"])["conditions"][0]["parameters"]["type"] = "\"start\""   # a quoted combo value
    del tween["behaviorType"]                                                             # a behavior action without it
    next(a for a in add_score["actions"] if a.get("id") == "set-text")["id"] = "set-txt"  # a misspelt id
    first_block(groups["Setup"])["conditions"][0]["isInverted"] = True                  # an inverted trigger
    path.write_text(json.dumps(sheet, indent="\t", ensure_ascii=False), encoding="utf-8", newline="\n")


def seed_key_pressed(root: Path) -> None:
    """W, A, S and D under Keyboard On key pressed, each simulating its 8 Direction control on Player:
    the player moves for the one tick of each press (docs/decisions/event-sheet-design-guidance.md)."""
    path = root / "eventSheets" / "event sheet 1.json"
    sheet = json.loads(path.read_text(encoding="utf-8"))
    sid = iter(range(633333333333301, 633333333333399))
    for key, control in ((87, "up"), (65, "left"), (83, "down"), (68, "right")):
        sheet["events"] += [
            {"eventType": "comment", "text": f"Walk {control} with {chr(key)}", "sid": next(sid)},
            {"eventType": "block", "sid": next(sid),
             "conditions": [{"id": "on-key-pressed", "objectClass": "Keyboard", "sid": next(sid), "parameters": {"key": key}}],
             "actions": [{"id": "simulate-control", "objectClass": "Player", "sid": next(sid), "behaviorType": "8Direction",
                          "parameters": {"control": control}}]}]
    path.write_text(json.dumps(sheet, indent="\t", ensure_ascii=False), encoding="utf-8", newline="\n")


def seed_timer_restart(root: Path) -> None:
    """The round ends on a Timer started with no trigger: Coin.Count = 0 -> ScoreText Start timer, which
    starts the timer over each tick, so On timer never restarts the layout
    (docs/decisions/event-sheet-design-guidance.md)."""
    def edit(rel: str, change) -> None:
        path = root / rel
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data, indent="\t", ensure_ascii=False), encoding="utf-8", newline="\n")

    edit("objectTypes/ScoreText.json", lambda t: t["behaviorTypes"].append({"behaviorId": "Timer", "name": "Timer",
                                                                            "sid": 644444444444401}))
    edit("layouts/Game.json", lambda d: next(i for layer in d["layers"] for i in layer["instances"]
                                             if i["type"] == "ScoreText").setdefault("behaviors", {}).update(
        Timer={"properties": {}}))
    edit("project.c3proj", lambda p: p["usedAddons"].append({"type": "behavior", "id": "Timer", "name": "Timer",
                                                             "author": "Scirra", "bundled": False}))

    def round_end(sheet: dict) -> None:
        restart = next(e for e in sheet["events"] if e.get("eventType") == "group" and e.get("title") == "Restart")
        old = next(e for e in restart["children"] if e["eventType"] == "block")
        timer = {"objectClass": "ScoreText", "behaviorType": "Timer"}
        restart["children"] = [
            {"eventType": "comment", "text": "When the last coin is gone, count down to the next round", "sid": 644444444444402},
            {"eventType": "block", "sid": 644444444444408, "conditions": [c for c in old["conditions"] if c["id"] != "trigger-once-while-true"],
             "actions": [{"id": "set-text", "objectClass": "ScoreText", "sid": 644444444444403,
                          "parameters": {"text": "\"Next round soon\""}},
                         {"id": "start-timer", **timer, "sid": 644444444444404,
                          "parameters": {"duration": "3", "type": "once", "tag": "\"next\""}}]},
            {"eventType": "comment", "text": "Then deal the next round", "sid": 644444444444405},
            {"eventType": "block", "sid": 644444444444406,
             "conditions": [{"id": "on-timer", **timer, "sid": 644444444444407, "parameters": {"tag": "\"next\""}}],
             "actions": [a for a in old["actions"] if a["id"] != "wait"]}]
    edit("eventSheets/Game.json", round_end)


def seed_turn_flip(root: Path) -> None:
    """Two players take turns, and the turn passes in a top-level Else after a test of the round's end:
    Coin.Count = 0 / Else -> Set turn to 3 - turn runs in every tick while coins are left, so the turn
    flips every tick (docs/decisions/event-sheet-design-guidance.md)."""
    path = root / "eventSheets" / "Game.json"
    sheet = json.loads(path.read_text(encoding="utf-8"))
    rows = sheet["events"]
    at = next(i for i, e in enumerate(rows) if e.get("eventType") == "variable" and e.get("name") == "beat") + 1
    rows.insert(at, {"eventType": "variable", "name": "turn", "type": "number", "initialValue": "1",
                     "comment": "Whose turn it is, 1 or 2", "isStatic": False, "isConstant": False,
                     "sid": 655555555555501})
    text = {"id": "set-text", "objectClass": "ScoreText"}
    rows.append({"eventType": "group", "disabled": False, "title": "Turns", "description": "",
                 "isActiveOnStart": True, "sid": 655555555555502, "children": [
                     {"eventType": "comment", "text": "When the round is over, nobody taps", "sid": 655555555555503},
                     {"eventType": "block", "sid": 655555555555504,
                      "conditions": [{"id": "compare-two-values", "objectClass": "System", "sid": 655555555555505,
                                      "parameters": {"first-value": "Coin.Count", "comparison": 0,
                                                     "second-value": "0"}}],
                      "actions": [{**text, "sid": 655555555555506,
                                   "parameters": {"text": "\"Round over. Score: \" & score"}}]},
                     {"eventType": "comment", "text": "Otherwise the turn passes to the other player",
                      "sid": 655555555555507},
                     {"eventType": "block", "sid": 655555555555508,
                      "conditions": [{"id": "else", "objectClass": "System", "sid": 655555555555509}],
                      "actions": [{"id": "set-eventvar-value", "objectClass": "System", "sid": 655555555555510,
                                   "parameters": {"variable": "turn", "value": "3 - turn"}},
                                  {**text, "sid": 655555555555511,
                                   "parameters": {"text": "\"Player \" & turn & \" to tap. Score: \" & score"}}]}]})
    path.write_text(json.dumps(sheet, indent="\t", ensure_ascii=False), encoding="utf-8", newline="\n")


# fixture -> (the fixture it starts from, the mistake written into it). The seeded entries' sids start
# with 6333, 6444 or 6555, so a grader can tell the example's own events from them.
SEEDS = {"families-key-pressed": ("example:families", seed_key_pressed),
         "coins-timer-restart": ("coins", seed_timer_restart),
         "coins-turn-flip": ("coins", seed_turn_flip)}


def digest(project: Path) -> dict:
    """The game's own files by hash, line endings aside, and the sids of the
    sheet's events; grade.py reads it to see what a run changed or lost."""
    def sids(events: list) -> list[int]:
        return [s for ev in events for s in ([ev["sid"]] if "sid" in ev else []) + sids(ev.get("children", []))]

    out: dict = {p.relative_to(project).as_posix(): hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                 for p in sorted(project.rglob("*"))
                 if p.is_file() and p.name != "AGENTS.md" and not {".agents", "__pycache__", "tools"} & set(p.parts)}
    for path in sorted((project / "eventSheets").rglob("*.json")):
        if not path.name.endswith(".uistate.json"):
            sheet = json.loads(path.read_text(encoding="utf-8"))
            out[f"{path.relative_to(project).as_posix()}.sids"] = sids(sheet["events"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs_dir", metavar="RUNS_DIR", help="a new or empty folder outside the clone, one per iteration")
    ap.add_argument("--arms", nargs="+", default=["with_skill", "without_skill"], metavar="ARM",
                    help="folders to lay out per test case; without_... gets no skill, old_... the one of --old-clone")
    ap.add_argument("--cases", nargs="+", metavar="NAME", help="test cases by name (default: all of evals.json)")
    ap.add_argument("--old-clone", metavar="FOLDER", help="a checkout of the clone before the change, for old_... arms")
    ap.add_argument("--examples", metavar="FOLDER",
                    default=str(REPO.parent / "Construct-Example-Projects" / "example-projects"),
                    help="the example-projects folder of the Construct-Example-Projects clone (default: beside this clone)")
    args = ap.parse_args()

    out = Path(args.runs_dir).resolve()
    if out.is_relative_to(REPO):
        sys.exit(f"{out} is inside the clone {REPO}: an agent started there reads the clone's AGENTS.md; "
                 f"name a folder outside it, such as one under the system's temporary directory")

    installers = {"with_": SKILL / "scripts" / "install.py"}
    if any(arm.startswith("old_") for arm in args.arms):
        installers["old_"] = Path(args.old_clone or "") / "skills" / SKILL.name / "scripts" / "install.py"
        if not args.old_clone or not installers["old_"].exists():
            sys.exit(f"an old_... arm needs --old-clone, a checkout that holds skills/{SKILL.name}/scripts/install.py")
    unknown = set(args.cases or []) - {c["name"] for c in CASES}
    if unknown:
        sys.exit(f"no test case named {', '.join(sorted(unknown))}; evals.json has: {', '.join(c['name'] for c in CASES)}")

    with tempfile.TemporaryDirectory() as tmp:
        game = stand_in(Path(tmp) / "coins")
        for case in (c for c in CASES if not args.cases or c["name"] in args.cases):
            source, seed = game, None
            fixture = case["fixture"]
            if fixture in SEEDS:
                fixture, seed = SEEDS[fixture]
            if fixture.startswith("example:"):
                source = Path(args.examples) / fixture.split(":", 1)[1]
                if not (source / "project.c3proj").exists():
                    sys.exit(f"{source} is not a folder project; --examples is the example-projects folder of the "
                             f"Construct-Example-Projects clone")
            for arm in args.arms:
                target = out / case["name"] / arm / "project"
                if target.exists():
                    sys.exit(f"{target} exists; name a new folder for a new iteration")
                shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.uistate.json"))
                (target.parent / "outputs").mkdir()
                if case["fixture"] == "coins-load-errors":
                    seed_load_errors(target)
                if seed:
                    seed(target)
                installer = next((script for prefix, script in installers.items() if arm.startswith(prefix)), None)
                if installer:
                    run(str(installer), "--project", str(target), cwd=target)
                if case["fixture"] == "coins-generator":
                    # The game keeps its generator, the template of the arm's own skill, run once so the
                    # files are that template's: the task is a change to tools/build_project.py and a rerun.
                    if not installer:
                        sys.exit(f"{case['name']} needs a skill: its generator checks with the skill's checker; "
                                 f"lay it out with with_... and old_... arms only")
                    (target / "tools").mkdir()
                    shutil.copy(installer.parent.parent / "assets" / "build_project.py", target / "tools" / "build_project.py")
                    run("tools/build_project.py", cwd=target)
                (target.parent / "fixture.json").write_text(json.dumps(digest(target), indent=2), encoding="utf-8")
                print(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
