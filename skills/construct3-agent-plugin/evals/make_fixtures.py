"""Lay out the project folders of one eval iteration, one per test case and arm.

    python evals/make_fixtures.py RUNS_DIR [--arms with_skill without_skill] [--cases NAME ...] [--held-out]
                                  [--old-clone FOLDER] [--examples FOLDER]

RUNS_DIR must lie outside the Construct3-RAG clone: an agent started below
the clone reads its AGENTS.md, which routes to this skill, and a baseline
that has the skill is not a baseline. A project is one of three kinds. The
default is the stand-in game of assets/build_project.py, without tools/, so
that the task is a hand edit of a project made in the editor. A fixture
`example:<id>` is a copy of that official example from --examples. A fixture
`empty` is the project that new_project.py creates, for a case that designs a
game before any file exists. A fixture of SEEDS is a stand-in game or an
example with a fault written into it, most of them a mistake small models
make, for a case that asks to fix it. A case marked held_out in evals.json is
left out unless --held-out is given (skills/AGENTS.md, Evals).

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
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
REPO = SKILL.parent.parent
sys.path.insert(0, str(SKILL / "scripts"))
import c3project as c3              # noqa: E402
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
    Coin.Count = 0 / Else -> Set side to 3 - side runs in every tick while coins are left, so the turn
    flips every tick (docs/decisions/event-sheet-design-guidance.md)."""
    path = root / "eventSheets" / "Game.json"
    sheet = json.loads(path.read_text(encoding="utf-8"))
    rows = sheet["events"]
    at = next(i for i, e in enumerate(rows) if e.get("eventType") == "variable" and e.get("name") == "beat") + 1
    rows.insert(at, {"eventType": "variable", "name": "side", "type": "number", "initialValue": "1",
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
                                   "parameters": {"variable": "side", "value": "3 - side"}},
                                  {**text, "sid": 655555555555511,
                                   "parameters": {"text": "\"Player \" & side & \" to tap. Score: \" & score"}}]}]})
    path.write_text(json.dumps(sheet, indent="\t", ensure_ascii=False), encoding="utf-8", newline="\n")


def seed_no_solid(root: Path) -> None:
    """SolidBarrier without its Solid behavior, on the type and on every instance, and in the used addons when
    no other type uses it: the player's 8 Direction walks through the walls that stop it in the example."""
    def edit(path: Path, change) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data, indent="\t", ensure_ascii=False), encoding="utf-8", newline="\n")

    types = {p: json.loads(p.read_text(encoding="utf-8")) for p in (root / "objectTypes").glob("*.json")}
    wall = next(p for p, t in types.items() if t.get("name") == "SolidBarrier")
    edit(wall, lambda t: t.update(behaviorTypes=[b for b in t["behaviorTypes"] if b["behaviorId"] != "solid"]))
    for path in (root / "layouts").glob("*.json"):
        if not path.name.endswith(".uistate.json"):
            edit(path, lambda d: [i.get("behaviors", {}).pop("Solid", None) for layer in d["layers"]
                                  for i in layer["instances"] if i["type"] == "SolidBarrier"])
    if not any(b["behaviorId"] == "solid" for p, t in types.items() if p != wall for b in t.get("behaviorTypes", [])):
        edit(root / "project.c3proj", lambda p: p.update(usedAddons=[a for a in p["usedAddons"] if a["id"] != "solid"]))


def seed_door(root: Path) -> None:
    """A Door, a TiledBg with Solid standing on the first floor between the player and the floor's end, and a
    Key, a Sprite with no behaviors behind the player: the platformer template with the art of a locked door
    and no events for it."""
    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def save(path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, indent="\t", ensure_ascii=False), encoding="utf-8", newline="\n")

    types = root / "objectTypes"
    all_types = [load(p) for p in types.glob("*.json")]
    sprite_ids = [t["image"]["imageSpriteId"] for t in all_types if "image" in t] + \
                 [f["imageSpriteId"] for t in all_types for a in t.get("animations", {}).get("items", []) for f in a["frames"]]
    door = load(types / "solidtile.json")
    door.update(name="Door", sid=6666000000001)
    door["behaviorTypes"][0]["sid"] = 6666000000002
    door["image"]["imageSpriteId"] = max(sprite_ids) + 1
    save(types / "door.json", door)
    shutil.copy(root / "images" / "solidtile.png", root / "images" / "door.png")
    key = load(types / "player.json")
    key.update(name="Key", sid=6666000000003, behaviorTypes=[])
    key["animations"]["items"][0]["sid"] = 6666000000004
    key["animations"]["items"][0]["frames"][0]["imageSpriteId"] = max(sprite_ids) + 2
    save(types / "key.json", key)
    shutil.copy(root / "images" / "player-default-000.png", root / "images" / "key-default-000.png")

    project = load(root / "project.c3proj")
    project["objectTypes"]["items"] += ["Door", "Key"]
    save(root / "project.c3proj", project)
    layout_path = root / "layouts" / "layout 1.json"
    layout = load(layout_path)
    game = next(layer for layer in layout["layers"] if layer["name"] == "Game")
    # Single-global objects (Keyboard) keep their uid in their object type file.
    uid = max([i["uid"] for layer in layout["layers"] for i in layer["instances"]]
              + [t["singleglobal-inst"]["uid"] for t in all_types if "singleglobal-inst" in t])
    tile = next(i for i in game["instances"] if i["type"] == "SolidTile")
    player = next(i for i in game["instances"] if i["type"] == "Player")
    game["instances"] += [
        {**json.loads(json.dumps(tile)), "type": "Door", "uid": uid + 1,
         "world": {**tile["world"], "x": 288, "y": 704, "width": 32, "height": 64, "color": [0.6, 0.35, 0.15, 1]}},
        {**json.loads(json.dumps(player)), "type": "Key", "uid": uid + 2, "behaviors": {},
         "world": {**player["world"], "x": 80, "y": 768, "width": 24, "height": 24, "color": [1, 0.85, 0.2, 1]}}]
    save(layout_path, layout)


BIG_SHEET = "Waves"
WAVES = 24
BIG_SHEET_FOCUS = 17


def wave_bonus(wave: int) -> int:
    """The points the end of a wave adds: a different number for each wave, rising with it."""
    return 100 + 20 * wave + (wave % 3) * 7


def big_sheet() -> dict:
    """A sheet of 24 waves in the shape a long game's sheets take, 400 and more numbered events, every group and
    most events under a comment in Chinese, the language whose comments make an outline long: a group per wave
    with a spawn group and a scoring group inside, then the functions the waves call. Built here, from numbers,
    not copied from anyone's game."""
    sid = iter(range(666666666600001, 666666666699999))

    def ace(id_: str, obj: str = "System", **params: object) -> dict:
        return {"id": id_, "objectClass": obj, "sid": next(sid), **({"parameters": params} if params else {})}

    def block(conditions: list, actions: list, children: list | None = None) -> dict:
        ev = {"eventType": "block", "conditions": conditions, "actions": actions, "sid": next(sid)}
        return ev | ({"children": children} if children else {})

    def comment(text: str) -> dict:
        return {"eventType": "comment", "text": text}

    def group(title: str, description: str, children: list) -> dict:
        return {"eventType": "group", "disabled": False, "title": title, "description": description,
                "isActiveOnStart": True, "children": children, "sid": next(sid)}

    def variable(name: str, value: str, note: str, kind: str = "number") -> dict:
        return {"eventType": "variable", "name": name, "type": kind, "initialValue": value, "comment": note,
                "isStatic": False, "isConstant": False, "sid": next(sid)}

    def wave_is(n: int) -> dict:
        return ace("compare-eventvar", variable="wave", comparison=0, value=str(n))

    events: list = [
        comment("波次表：每一波生成的金币数量、生成间隔和结束奖励都写在这里，按波次分组，改数值时只改对应的那一组"),
        variable("wave", "1", "当前波次，从 1 开始，打完最后一波后回到 1"),
        variable("spawnLeft", "0", "本波还要生成的金币数量，生成一个减一"),
        variable("spawnGap", "1", "本波两次生成之间的秒数"),
        variable("waveScore", "0", "本波已经拿到的分数，换波时清零"),
    ]
    for n in range(1, WAVES + 1):
        count, gap = 4 + n % 5 + n // 6, round(1.6 - 0.04 * n, 2)
        spawn = group(f"Wave {n} spawn", f"第{n}波的生成规则：数量 {count}，间隔 {gap} 秒", [
            comment(f"第{n}波开始：设定本波数量和间隔，清空本波分数"),
            block([wave_is(n), ace("trigger-once-while-true")],
                  [ace("set-eventvar-value", variable="spawnLeft", value=str(count)),
                   ace("set-eventvar-value", variable="spawnGap", value=str(gap)),
                   ace("set-eventvar-value", variable="waveScore", value="0")],
                  [block([ace("compare-eventvar", variable="spawnLeft", comparison=4, value="6")],
                         [ace("set-eventvar-value", variable="spawnGap", value=str(round(gap * 0.9, 2)))])]),
            comment("按间隔生成金币，生成一个就把剩余数量减一"),
            block([wave_is(n), ace("every-x-seconds", **{"interval-seconds": "spawnGap"}),
                   ace("compare-eventvar", variable="spawnLeft", comparison=4, value="0")],
                  [ace("subtract-from-eventvar", variable="spawnLeft", value="1")],
                  [block([], [{"callFunction": "SpawnCoin", "sid": next(sid),
                               "parameters": [f"{n % 3}", f"{(n * 7) % 5}"]}])]),
            comment("剩下最后两个的时候加快生成，让波次的结尾更紧张"),
            block([wave_is(n), ace("compare-eventvar", variable="spawnLeft", comparison=3, value="2")],
                  [ace("set-eventvar-value", variable="spawnGap", value=str(round(gap / 2, 2)))]),
        ])
        score = group(f"Wave {n} score", f"第{n}波的计分：每个金币的分数和本波结束时的奖励", [
            comment("本波每拿到一个金币，本波分数加上这一波的倍数"),
            block([wave_is(n), ace("compare-two-values", **{"first-value": "Coin.Count", "comparison": 2,
                                                             "second-value": "spawnLeft + 1"})],
                  [ace("add-to-eventvar", variable="waveScore", value=str(1 + n // 4))]),
            comment("本波分数超过门槛时额外加一分，门槛随波次升高"),
            block([wave_is(n), ace("compare-eventvar", variable="waveScore", comparison=5, value=str(10 + 2 * n)),
                   ace("trigger-once-while-true")],
                  [ace("add-to-eventvar", variable="waveScore", value="1")]),
            block([wave_is(n), ace("compare-eventvar", variable="waveScore", comparison=5, value=str(20 + 3 * n)),
                   ace("trigger-once-while-true")],
                  [ace("add-to-eventvar", variable="waveScore", value="2")]),
            comment(f"第{n}波结束：金币全部生成并且被收走，发放本波奖励，然后进入下一波"),
            block([wave_is(n), ace("compare-eventvar", variable="spawnLeft", comparison=0, value="0"),
                   ace("compare-two-values", **{"first-value": "Coin.Count", "comparison": 0, "second-value": "0"}),
                   ace("trigger-once-while-true")],
                  [{"callFunction": "GiveBonus", "sid": next(sid), "parameters": [str(wave_bonus(n))]},
                   ace("add-to-eventvar", variable="wave", value="1")]),
            comment("最后一波之后回到第一波"),
            block([ace("compare-eventvar", variable="wave", comparison=4, value=str(WAVES))],
                  [ace("set-eventvar-value", variable="wave", value="1")]),
        ])
        text = group(f"Wave {n} text", f"第{n}波的提示文字", [
            comment("波次开始时在回合文字上显示第几波，清场时换成清场提示"),
            block([wave_is(n), ace("trigger-once-while-true")],
                  [ace("set-text", "RoundTag", text=f'"第{n}波"')]),
            block([wave_is(n), ace("compare-eventvar", variable="spawnLeft", comparison=0, value="0"),
                   ace("compare-two-values", **{"first-value": "Coin.Count", "comparison": 0, "second-value": "0"})],
                  [ace("set-text", "RoundTag", text='"清场"')]),
            block([wave_is(n), ace("compare-eventvar", variable="waveScore", comparison=5, value=str(30 + 3 * n))],
                  [ace("set-text", "ScoreLabel", text='"好"')]),
        ])
        events.append(group(f"Wave {n}", f"第{n}波：先生成，再计分", [spawn, score, text]))
    events += [
        comment("生成一个金币：列和行由调用的波次给出，位置落在棋盘的格子上"),
        {"functionName": "SpawnCoin", "functionDescription": "在棋盘的一个格子上生成一个金币", "functionCategory": "",
         "functionReturnType": "none", "functionCopyPicked": False, "functionIsAsync": False,
         "functionParameters": [{"name": "column", "type": "number", "initialValue": "0", "comment": "列", "sid": next(sid)},
                                {"name": "row", "type": "number", "initialValue": "0", "comment": "行", "sid": next(sid)}],
         "eventType": "function-block", "conditions": [],
         "actions": [ace("create-object", **{"object-to-create": "Coin", "layer": "\"Game\"",
                                             "x": "592 + 192 * column", "y": "400 + 192 * row",
                                             "create-hierarchy": False, "template-name": "\"\""})],
         "sid": next(sid)},
        comment("发放奖励：把奖励加进总分，并在分数文字上显示出来"),
        {"functionName": "GiveBonus", "functionDescription": "加上一波的奖励分数", "functionCategory": "",
         "functionReturnType": "none", "functionCopyPicked": False, "functionIsAsync": False,
         "functionParameters": [{"name": "points", "type": "number", "initialValue": "0", "comment": "奖励的分数",
                                 "sid": next(sid)}],
         "eventType": "function-block", "conditions": [],
         "actions": [{"callFunction": "AddScore", "sid": next(sid), "parameters": ["points"]}],
         "sid": next(sid)},
    ]
    return {"name": BIG_SHEET, "events": events, "sid": next(sid)}


def seed_big_sheet(root: Path) -> None:
    """A second sheet of 400 and more events beside the stand-in's own, listed in project.c3proj and used by no
    layout, so the coins game plays as before; the case reads it."""
    def save(path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, indent="\t", ensure_ascii=False), encoding="utf-8", newline="\n")

    save(root / "eventSheets" / f"{BIG_SHEET}.json", big_sheet())
    path = root / "project.c3proj"
    project = json.loads(path.read_text(encoding="utf-8"))
    project["eventSheets"]["items"].append(BIG_SHEET)
    save(path, project)


# fixture -> (the fixture it starts from, the fault written into it). The seeded entries' sids start
# with 6333, 6444, 6555 or 6666, so a grader can tell the example's own events from them.
SEEDS = {"families-key-pressed": ("example:families", seed_key_pressed),
         "coins-timer-restart": ("coins", seed_timer_restart),
         "coins-turn-flip": ("coins", seed_turn_flip),
         "persistent-walls": ("example:persistent-layouts", seed_no_solid),
         "platformer-door": ("example:template-platformer", seed_door),
         "coins-big-sheet": ("coins", seed_big_sheet)}


def digest(project: Path) -> dict:
    """The game's own files by hash, line endings aside, and the sids of the
    sheet's events; grade.py reads it to see what a run changed or lost."""
    def sids(events: list) -> list[int]:
        return [s for ev in events for s in ([ev["sid"]] if "sid" in ev else []) + sids(ev.get("children", []))]

    out: dict = {p.relative_to(project).as_posix(): hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                 for p in sorted(project.rglob("*"))
                 if p.is_file() and p.name != "AGENTS.md"
                 and not {".agents", "__pycache__", "tools", ".git", ".tmp"} & set(p.parts)}
    for path in sorted((project / "eventSheets").rglob("*.json")):
        if not path.name.endswith(".uistate.json"):
            sheet = json.loads(path.read_text(encoding="utf-8"))
            out[f"{path.relative_to(project).as_posix()}.sids"] = sids(sheet["events"])
    return out


def warnings_of(project: Path) -> list[str]:
    """The checker's warning lines on the fixture: the project's own, which grade.py does not charge to a run."""
    p = subprocess.run([sys.executable, str(SKILL / "scripts" / "check_project.py"), "--project", str(project),
                        "--rag", str(REPO), "--limit", "0"], capture_output=True, text=True, encoding="utf-8",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return [line for line in p.stdout.splitlines() if line.startswith("warning:")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs_dir", metavar="RUNS_DIR", help="a new or empty folder outside the clone, one per iteration")
    ap.add_argument("--arms", nargs="+", default=["with_skill", "without_skill"], metavar="ARM",
                    help="folders to lay out per test case; without_... gets no skill, old_... the one of --old-clone")
    ap.add_argument("--cases", nargs="+", metavar="NAME",
                    help="test cases by name (default: all of evals.json but the held-out ones)")
    ap.add_argument("--held-out", action="store_true",
                    help="lay out the held-out cases too, or the ones --cases names. Use it once a change is otherwise done")
    ap.add_argument("--old-clone", metavar="FOLDER", help="a checkout of the clone before the change, for old_... arms")
    ap.add_argument("--examples", metavar="FOLDER",
                    default=str(c3.siblings_folder(REPO) / "Construct-Example-Projects" / "example-projects"),
                    help="the example-projects folder of the Construct-Example-Projects clone (default: beside this "
                         "clone, or beside its main working tree from a worktree)")
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
    held = sorted(c["name"] for c in CASES if c.get("held_out") and c["name"] in (args.cases or []))
    if held and not args.held_out:
        sys.exit(f"{', '.join(held)} {'is' if len(held) == 1 else 'are'} held out of tuning (skills/AGENTS.md, Evals): "
                 f"add --held-out once the change is otherwise done, or name the other cases")
    chosen = [c for c in CASES if (c["name"] in args.cases if args.cases else args.held_out or not c.get("held_out"))]

    with tempfile.TemporaryDirectory() as tmp:
        game = stand_in(Path(tmp) / "coins")
        for case in chosen:
            fixture, seed = SEEDS.get(case["fixture"], (case["fixture"], None))
            source = game
            if fixture == "empty":
                source = Path(tmp) / "empty"
                if not source.exists():
                    run(str(SKILL / "scripts" / "new_project.py"), str(source), cwd=Path(tmp))
            elif fixture.startswith("example:"):
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
                    # The stand-in of the arm's own template, from the seed stand_in() starts with: what
                    # another template generated would stay beside it, unlisted.
                    for item in target.iterdir():
                        if item.name not in (".agents", ".claude", ".git", "AGENTS.md", "CLAUDE.md"):
                            shutil.rmtree(item) if item.is_dir() else item.unlink()
                    (target / "project.c3proj").write_text(json.dumps({"uniqueId": "eval", "properties": {}}),
                                                           encoding="utf-8")
                    (target / "tools").mkdir()
                    shutil.copy(installer.parent.parent / "assets" / "build_project.py", target / "tools" / "build_project.py")
                    run("tools/build_project.py", cwd=target)
                (target.parent / "fixture.json").write_text(json.dumps(digest(target) | {
                    "check_project.warnings": warnings_of(target)}, indent=2), encoding="utf-8")
                print(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
