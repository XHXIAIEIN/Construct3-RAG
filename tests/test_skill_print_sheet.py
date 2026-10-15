"""print_sheet.py: the event sheet in the words of the editor."""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.skill_helpers import (
    REPO, INSTALLED, SHEET, SKILL, EXAMPLES, NEEDS_EXAMPLES, git, run, tool, streams, check, edit, block, events,
    script_module,
)


def committed(root: Path) -> None:
    """The project's files in a commit of a repository of its own, as a game project keeps them."""
    git(root, "init", "-q")
    git(root, "add", "project.c3proj", "eventSheets", "objectTypes")
    git(root, "commit", "-qm", "before")


def test_a_miss_of_print_sheet_prints_on_stdout(project):
    """An unknown sheet, on disk or in the commit of --since, a --show or --events past the end and an event
    too long to show are answers: on stdout, with the exit code 1 they had on stderr, where a harness that
    shows stdout alone showed nothing."""
    committed(project)
    for args, said in ((("Gmae",), "no event sheet named 'Gmae'; sheets: Game"),
                       (("Gmae", "--since", "HEAD"), "no event sheet named 'Gmae' on disk or in HEAD ("),
                       (("Game", "--show", "40"), "sheet Game has 12 events; --show 40 is not one of them"),
                       (("Game", "--events", "40"), "sheet Game has 12 events; --events 40 starts past its end"),
                       (("Game", "--show", "1", "--limit", "20"), "characters of JSON, over the limit of 20 (--limit)")):
        p = streams(project, f"{INSTALLED}/scripts/print_sheet.py", "--rag", str(REPO), *args)
        assert p.returncode == 1 and p.stderr == "" and said in p.stdout, (args, p.stdout, p.stderr)


def test_outline_numbers_events_as_the_editor_does(built):
    """A comment keeps its first 30 characters: an outline is read for its numbers, and the full comments of a
    long sheet, a token a character in Chinese, made outlines of 15 000 to 60 000 characters."""
    code, out = tool(built, "print_sheet", "--outline", "Game")
    rows = [line.split("[sid")[0].rstrip() for line in out.splitlines()]
    assert code == 0
    assert rows[:4] == ["== Game", "   (1) // Coins. Tap a coin to collect i…",
                        "   (1) // Settings", "   (1) string ROUND_COINS = 1,3,6,2,10,1"]
    assert "   1 group Setup" in rows and "   2   System:on-start-of-layout" in rows


def test_print_words_the_sheet_as_the_editor_does(built):
    code, out = tool(built, "print_sheet", "Game")
    assert code == 0
    assert "   5   Touch: On touched Coin (start)\n       Coin: NOT Is any Tween playing\n           -> Coin: Collect()" in out
    assert "     global constant string ROUND_COINS = 1,3,6,2,10,1" in out
    assert "   7 function AddScore(points: number)\n         -> System: Add points to score" in out
    assert "   9   System: Coin.Count = 0\n       System: Trigger once" in out


def test_print_shows_a_group_description_and_a_variable_comment(project):
    """Each under its row, in the column of the actions, where no comment event of the sheet prints."""
    def describe(sheet):
        top = sheet["events"]
        next(ev for ev in top if ev.get("eventType") == "group")["description"] = "Round set-up\nand the first coins"
        next(ev for ev in top if ev.get("name") == "ROUND_COINS")["comment"] = "Coins per round"
    edit(project, SHEET, describe)
    code, out = tool(project, "print_sheet", "Game")
    assert code == 0, out
    assert "   1 group Setup\n         // Round set-up\n         // and the first coins\n" in out
    assert "     global constant string ROUND_COINS = 1,3,6,2,10,1\n         // Coins per round\n" in out


def test_print_says_every_tick_only_where_an_event_without_conditions_runs_every_tick(project):
    """At the top of the sheet or in a group there, an event without conditions runs every tick. As a
    sub-event it runs when the event it sits in runs, once a touch under a trigger, once a call in a
    function: read as every tick, it is per-tick logic that is not there."""
    set_scale = {"id": "set-scale", "objectClass": "Coin", "parameters": {"scale": "1.5"}}
    def add(sheet):
        rows = events(sheet)
        rows["input"].setdefault("children", []).insert(0, block([], [set_scale]))
        rows["add_score"].setdefault("children", []).insert(0, block([], [set_scale]))
        sheet["events"] += [block([], [set_scale]),
                            {"eventType": "group", "title": "Idle", "children": [block([], [set_scale])]}]
    edit(project, SHEET, add)
    code, out = tool(project, "print_sheet", "Game")
    assert code == 0, out
    assert "   5   Touch: On touched Coin (start)\n" in out
    assert "   6     (runs with its parent)\n             -> Coin: Set scale to 1.5" in out
    assert "   8 function AddScore(points: number)\n" in out
    assert "   9   (runs with its parent)\n           -> Coin: Set scale to 1.5" in out
    assert "  15 (every tick)\n         -> Coin: Set scale to 1.5" in out
    assert "  16 group Idle\n  17   (every tick)\n           -> Coin: Set scale to 1.5" in out
    assert out.count("(every tick)") == 2 and out.count("(runs with its parent)") == 2, out


def test_print_names_the_sub_events_of_an_event(project):
    """A trigger with no actions of its own looked empty to a model, which removed it and the
    sub-events that did the work."""
    code, out = tool(project, "print_sheet", "Game")
    assert code == 0, out
    parent = next(line for line in out.splitlines() if "[sub-event" in line)
    number = int(parent.split()[0])
    assert parent.endswith(f"[sub-event {number + 1}]") or f"[sub-events {number + 1}-" in parent, out
    assert not any("function" in line and "[sub-event" in line for line in out.splitlines()), out


def test_print_follows_the_locale(built):
    code, out = tool(built, "print_sheet", "Game", "--locale", "zh-CN")
    assert code == 0 and "System: 场景开始" in out


def test_expression_names_are_english_in_every_locale(built):
    """A project file holds `Coin.Count` whatever language the editor runs in; the locale's name is wording."""
    code, out = check(built, "--locale", "zh-CN")
    assert code == 0 and out.splitlines()[-1].startswith("ok:"), out
    code, out = tool(built, "lookup_ace", "Coin", "tween", "progress", "--locale", "zh-CN")
    assert code == 0 and "  write: Coin.Tween.Progress(tags)  -> number" in out, out


def test_print_stops_at_the_limit_and_names_the_part_that_continues(built):
    """A harness cuts long output without saying where; the script stops at an event and says how to go on."""
    _, whole = tool(built, "print_sheet", "Game")
    parts, span = [], "1-"
    while span:
        code, out = tool(built, "print_sheet", "Game", "--events", span, "--limit", "900")
        assert code == 0 and len(out) < 1500, out
        parts.append(out)
        last = out.splitlines()[-1]
        span = re.search(r"--events (\d+-)", last).group(1) if last.startswith("-- stopped at the limit") else None
    assert len(parts) > 1 and parts[0].startswith("== Game: events 1-")
    printed = {line for part in parts for line in part.splitlines() if "[context]" not in line}
    assert [line for line in whole.splitlines()[1:] if line not in printed] == []


def test_print_of_a_part_starts_with_the_events_it_sits_in(built):
    code, out = tool(built, "print_sheet", "Game", "--events", "9")
    assert code == 0
    assert out.splitlines()[:4] == ["== Game: events 9-9 of 12; a [context] row is an event these sit in, without its actions",
                                    "   8 group Restart  [context]", "       // Start the next round when the last coin is gone",
                                    "   9   System: Coin.Count = 0"]
    assert "Touch: On touched" not in out


@pytest.mark.parametrize("span, said", [("40-", "has 12 events"), ("x", "40-80, 40- or 40"), ("5-2", "ends before it starts")])
def test_print_refuses_a_range_it_cannot_read(built, span, said):
    code, out = tool(built, "print_sheet", "Game", "--events", span)
    assert code == 1 and said in out


def with_menu_sheet(project: Path, folder: str | None = None) -> Path:
    """The stand-in game with a second sheet, a copy of Game that no layout runs, in a sheet folder when named."""
    shutil.copy(project / SHEET, project / "eventSheets" / "Menu.json")

    def list_it(data: dict) -> None:
        if folder:
            data["eventSheets"]["subfolders"].append({"name": folder, "items": ["Menu"], "subfolders": []})
        else:
            data["eventSheets"]["items"].append("Menu")
    edit(project, "project.c3proj", list_it)
    return project


def test_print_without_a_name_prints_the_map_when_the_sheets_do_not_fit(project):
    """A project over the limit prints the map, which says which sheet holds a feature."""
    with_menu_sheet(project)
    code, out = tool(project, "print_sheet", "--limit", "900")
    assert code == 0
    assert out.startswith("== Coins: 2 sheets, 24 events, 2 layouts.") and "-> " not in out
    assert re.search(r"\n  Game +12 events +\d+ chars; layouts Game; ", out)
    code, out = tool(project, "print_sheet")
    assert code == 0 and "== Game\n" in out and "== Menu\n" in out


def test_print_counts_the_lines_of_a_script_stored_either_way(project):
    """The editor keeps a script as a list of lines or as one string with newlines; the official examples use both."""
    lines = ["const coin = runtime.objects.Coin.getFirstInstance();", "coin.x += 10;"]
    def add(sheet):
        for script in (lines, "\n".join(lines), lines[:1], lines[0]):
            sheet["events"] += [{"eventType": "script", "script": script},
                                {"eventType": "block", "conditions": [], "actions": [{"type": "script", "script": script}]}]
    edit(project, SHEET, add)
    code, out = tool(project, "print_sheet", "Game")
    assert code == 0 and out.count("script, 2 lines") == 4 and out.count("script, 1 line\n") == 4, out
    assert "script, 67 lines" not in out and "script, 1 lines" not in out, out


def add_script(project: Path, lines: int = 2) -> None:
    (project / "scripts").mkdir(exist_ok=True)
    (project / "scripts" / "main.js").write_text("\n".join(["// game"] * lines), encoding="utf-8")
    def listed(data):
        folder = data.setdefault("rootFileFolders", {}).setdefault("script", {"items": [], "subfolders": []})
        folder["items"].append({"name": "main.js", "type": "application/javascript", "sid": 1, "script-info": {"purpose": "main"}})
    edit(project, "project.c3proj", listed)


def test_print_of_a_project_without_sheets_points_to_its_scripts(project):
    """A project written in JavaScript has no sheet; an empty print read as a project with no logic."""
    add_script(project, 3)
    edit(project, "project.c3proj", lambda data: data["eventSheets"].update(items=[], subfolders=[]))
    code, out = tool(project, "print_sheet")
    assert code == 0 and out.strip().endswith("logic is in its scripts, read them as code: scripts/main.js (3 lines); events go into a new sheet with edit_sheet.py SHEET PLAN.json --new"), out
    (project / "scripts" / "main.js").unlink()
    code, out = tool(project, "print_sheet")
    assert code == 0 and "no event sheets and no scripts" in out, out


def test_print_marks_what_the_editor_has_disabled(project):
    """The editor skips a disabled condition or action and runs the event without it. Printed like the others,
    a disabled NOT condition was read as a check the event still makes. The event's own marker ends the line
    of its first condition, so it names the event."""
    def disable(sheet):
        rows = events(sheet)
        rows["input"]["conditions"][1]["disabled"] = True         # an inverted condition
        rows["input"]["actions"][0]["disabled"] = True            # a custom action
        rows["add_score"]["actions"][0]["disabled"] = True        # an action with an id
        rows["restart"]["disabled"] = True
        rows["restart_block"]["disabled"] = True
        rows["restart_block"]["conditions"][0]["disabled"] = True
    edit(project, SHEET, disable)
    printed = {locale: tool(project, "print_sheet", "Game", "--locale", locale) for locale in ("en-US", "zh-CN")}
    for code, out in printed.values():
        assert code == 0, out
        assert out.count(" [condition disabled]") == 2 and out.count(" [action disabled]") == 2, out
        assert out.count(" [event disabled]") == 2, out
    _, out = printed["en-US"]
    assert "   5   Touch: On touched Coin (start)\n       Coin: NOT Is any Tween playing [condition disabled]\n" \
           "           -> Coin: Collect() [action disabled]" in out
    assert "   7 function AddScore(points: number)\n         -> System: Add points to score [action disabled]" in out
    assert "   8 group Restart [event disabled]\n" in out
    assert "   9   System: Coin.Count = 0 [condition disabled] [event disabled]\n       System: Trigger once\n" in out


def test_scripts_write_utf8_and_survive_a_code_page_that_cannot(built):
    """A piped Python on Windows writes the ANSI code page: mojibake under cp936, a crash under cp1252."""
    script = built / INSTALLED / "scripts" / "print_sheet.py"
    for codec, want in ((None, "场景开始"), ("cp1252", "System: ")):
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
        if codec:
            env["PYTHONIOENCODING"] = codec
        p = subprocess.run([sys.executable, str(script), "Game", "--locale", "zh-CN", "--rag", str(REPO)],
                           cwd=built, env=env, capture_output=True)
        assert p.returncode == 0, p.stdout + p.stderr
        assert want in p.stdout.decode(codec or "utf-8")


def test_print_names_a_renamed_functions_object(project):
    """A model read Renamed.Potion as a function named after the Functions object."""
    edit(project, "project.c3proj", lambda data: data.update(functionsName="Calls"))
    code, out = tool(project, "print_sheet", "Game")
    assert code == 0, out
    assert out.startswith("note: Calls is this project's name for the built-in Functions object"), out
    assert "Calls: Call AddScore(" in out and "Functions: Call" not in out, out


@pytest.mark.parametrize("clone_there", [False, True])
def test_an_example_that_is_not_there_names_the_clone_not_a_new_project(built, tmp_path, clone_there):
    """An official example is read from the examples clone; with no such folder, starting a game
    project is the wrong next step."""
    clone = tmp_path / "Construct-Example-Projects"
    if clone_there:
        (clone / "example-projects").mkdir(parents=True)
    example = clone / "example-projects" / "template-snake"
    code, out = tool(built, "print_sheet", "--project", str(example))
    assert code == 1 and "new_project.py" not in out, out
    if clone_there:
        assert f"no example project at {example}" in out and "search_guides.py" in out, out
    else:
        assert f"the Construct-Example-Projects clone is not at {clone}" in out, out
        assert f"python {(REPO / 'scripts' / 'bootstrap.py').as_posix()} clones it" in out, out


def test_since_lists_what_changed_as_events(project):
    """A review of the agents branch reads the events, not a diff of the sheet's JSON."""
    committed(project)

    def change(sheet):
        rows = events(sheet)
        rows["add_score"]["actions"][1]["parameters"]["text"] = '"Score: " & score'
        rows["restart_block"]["conditions"].pop(1)     # Trigger once
        rows["input_group"]["children"].append(block([{"id": "on-start-of-layout", "objectClass": "System", "sid": 5}]))
        sheet["events"] = [e for e in sheet["events"] if e.get("name") != "deal"]
        rows["restart"]["children"].remove(rows["restart_block"])
        rows["input_group"]["children"].append(rows["restart_block"])
    edit(project, SHEET, change)
    code, out = tool(project, "print_sheet", "--since", "HEAD")
    assert code == 0, out
    lines = out.splitlines()
    assert re.fullmatch(r"== Game since HEAD \(\w+\): 1 added, 2 changed, 1 removed; event numbers as the sheet is on disk",
                        lines[0]), out
    assert "-     global number deal = 0  [removed]" in lines, out
    assert "    4 group Input  [context]" in lines and "+   6   System: On start of layout  [added]" in lines, out
    at = lines.index("    9 function AddScore(points: number)  [changed]")    # 8 before the move into Input
    assert lines[at + 2:at + 4] == ["-         -> ScoreText: Set text to score",
                                    '+         -> ScoreText: Set text to "Score: " & score'], out
    assert "    7   System: Coin.Count = 0  [changed, moved from event 9 in HEAD]" in lines, out
    assert "-       System: Trigger once" in lines, out


def test_since_knows_an_event_whose_sid_a_generator_gave_anew(project):
    """A generator run gives every sid after its first changed line anew: the same content is the same event."""
    committed(project)
    fresh = iter(range(10 ** 14, 10 ** 15, 7919))

    def renumber(node):
        if isinstance(node, dict):
            node.update({"sid": next(fresh)} if "sid" in node else {})
            for value in node.values():
                renumber(value)
        elif isinstance(node, list):
            for value in node:
                renumber(value)
    edit(project, SHEET, renumber)
    code, out = tool(project, "print_sheet", "--since", "HEAD")
    assert code == 0 and re.fullmatch(r"no event changed since HEAD \(\w+\) in Game", out.strip()), out

    edit(project, SHEET, lambda sheet: events(sheet)["add_score"]["actions"][1]["parameters"].update(text='"Score"'))
    code, out = tool(project, "print_sheet", "Game", "--since", "HEAD")
    assert code == 0 and ": 1 changed;" in out.splitlines()[0] and out.count("[") == 1, out


def test_since_names_what_it_cannot_compare(project):
    code, out = tool(project, "print_sheet", "--since", "HEAD")
    assert code == 1 and "in no git repository" in out and "git init" in out, out
    committed(project)
    code, out = tool(project, "print_sheet", "--since", "nope")
    assert code == 1 and "no such commit, branch or tag" in out and "before" in out, out
    code, out = tool(project, "print_sheet", "--since=--output=x")
    assert code == 1 and "takes a commit" in out, out
    code, out = tool(project, "print_sheet", "--since", "HEAD", "--show", "1")
    assert code == 1 and "--outline and --show read the sheet as it is on disk" in out, out


def test_since_stops_at_the_limit_and_names_the_part_that_continues(project):
    committed(project)
    edit(project, SHEET, lambda sheet: sheet["events"].extend(
        block([{"id": "every-tick", "objectClass": "System", "sid": 5}],
              [{"id": "set-eventvar-value", "objectClass": "System", "sid": 6,
                "parameters": {"variable": "score", "value": str(n)}}]) for n in range(40)))
    code, out = tool(project, "print_sheet", "--since", "HEAD", "--limit", "1500")
    assert code == 0 and len(out) < 1500, out
    last = out.splitlines()[-1]
    assert re.search(r"before event (\d+) of 52\. The rest: python \S+print_sheet.py Game --since HEAD --events \1- "
                     r".*--limit 1500$", last), last
    start = re.search(r"--events (\d+)-", last).group(1)
    code, rest = tool(project, "print_sheet", "Game", "--since", "HEAD", "--events", f"{start}-", "--limit", "0")
    assert code == 0 and f"+{int(start):>4} System: Every tick  [added]" in rest, rest


def big(project: Path) -> Path:
    """The stand-in game with the eval fixture's sheet of 24 waves, 410 events under Chinese comments."""
    script_module("make_fixtures", SKILL / "evals").seed_big_sheet(project)
    return project


def test_a_sheet_over_the_limit_prints_its_groups_and_functions(project):
    """The first 10 000 characters of a long sheet named nothing of the rest, and a model that wanted one event
    printed the whole sheet with --limit 0; the list of its groups says which part to print."""
    code, out = tool(big(project), "print_sheet", "Waves")
    lines = out.splitlines()
    assert code == 0 and len(out) < 10_000, out[-500:]
    assert lines[0].startswith("== Waves: 410 events, ") and "over the limit of 10000 (--limit)" in lines[0]
    assert "     1-17  group Wave 1" in lines and "      2-7    group Wave 1 spawn" in lines
    assert "  273-289  group Wave 17" in lines and "  280-285    group Wave 17 score" in lines
    assert "      410  function GiveBonus" in lines
    assert not any("->" in line for line in lines[:-1])
    assert lines[-1].startswith("-- print one part, a group or a function, by its events: python ")
    assert "Waves --events 1-17" in lines[-1] and "Waves --find NAME" in lines[-1]
    code, part = tool(project, "print_sheet", "Waves", "--events", "280-285")
    assert code == 0 and "-> Functions: Call GiveBonus(454)" in part and "-- stopped" not in part


def test_the_list_of_groups_leaves_the_deeper_ones_out_to_fit(project):
    code, out = tool(big(project), "print_sheet", "Waves", "--limit", "1500")
    lines = out.splitlines()
    assert code == 0 and "    18-34  group Wave 2" in lines and not any("Wave 2 spawn" in line for line in lines)
    assert "(72 groups and functions inside these are left out to stay under the limit)" in out
    code, out = tool(project, "print_sheet", "Waves", "--outline")
    assert code == 0 and out.startswith("== Waves: 410 events, ") and " characters as an outline, " in out
    assert "Waves --events 1-17 --outline" in out.splitlines()[-1]


def test_a_sheet_that_fits_prints_as_before(built):
    """Under the limit nothing changes: the whole sheet, no list of groups."""
    code, out = tool(built, "print_sheet", "Game")
    assert code == 0 and out.startswith("== Game\n") and "Its groups and functions" not in out


def test_find_prints_the_events_that_use_a_name_under_the_events_they_sit_in(built):
    """By its name in conditions, actions and expressions, in any case; a comment, a description and quoted
    text do not count."""
    code, out = tool(built, "print_sheet", "Game", "--find", "SCORE")
    lines = out.splitlines()
    assert code == 0 and lines[0].startswith("== Game: 3 events use SCORE, each under the events it sits in")
    assert lines[1:4] == ["     global number score = 0", "         // Points collected this round",
                          "   1 group Setup  [context]"]
    assert "           -> System: Set score to 0" in lines and "   7 function AddScore(points: number)" in lines
    assert not any("Collect" in line for line in lines)       # its description and comment say "Score"
    code, out = tool(built, "print_sheet", "--find", "squash")   # only a quoted tag holds it
    assert code == 1 and out.startswith("no event uses squash in Game")
    code, out = tool(built, "print_sheet", "--find", "AddScor")
    assert code == 1 and "closest: AddScore" in out


def test_find_stops_at_the_limit_and_names_the_part_that_continues(project):
    big(project)
    seen, span = [], None
    while True:
        code, out = tool(project, "print_sheet", "Waves", "--find", "spawnLeft", "--limit", "3000",
                         *(["--events", span] if span else []))
        assert code == 0 and len(out) < 3600, out[-300:]
        seen += [line.split()[0] for line in out.splitlines()[1:] if line[:4].strip().isdigit() and "[context]" not in line]
        last = out.splitlines()[-1]
        if not last.startswith("-- stopped at the limit"):
            break
        assert "Waves --find spawnLeft --events " in last
        span = re.search(r"--events (\d+-)", last).group(1)
    assert len(seen) == len(set(seen)) > 100


def test_find_takes_no_outline_show_or_since(built):
    p = streams(built, f"{INSTALLED}/scripts/print_sheet.py", "--rag", str(REPO), "--find", "score", "--outline")
    assert p.returncode == 2 and "--find prints events as the sheet words them" in p.stderr


def test_find_ends_each_sheet_with_the_layouts_that_run_it(project):
    """A trigger fires only in a sheet the running layout runs, by its own sheet or an include, so the block says
    which layouts run the sheet."""
    with_menu_sheet(project)
    code, out = tool(project, "print_sheet", "--find", "AddScore")
    blocks = out.split("== ")[1:]
    assert code == 0 and len(blocks) == 2
    assert blocks[0].splitlines()[-1] == "-- layouts that run Game, by their own sheet or an include: Game"
    assert blocks[1].splitlines()[-1] == ("-- no layout runs Menu: its triggers do not fire, and a function it defines "
                                          "runs when another sheet calls it")


KIWI = EXAMPLES / "kiwi-story"      # 14 sheets: eMain includes nine, and four layouts' own sheets include eMain


def kiwi_map(*args: str) -> tuple[int, str]:
    return run(SKILL, SKILL / "scripts" / "print_sheet.py", "--project", str(KIWI), "--rag", str(REPO), "--map", *args)


@NEEDS_EXAMPLES
def test_map_names_the_layouts_that_run_each_sheet_through_includes():
    """One line per sheet: the layouts whose own sheet is it or includes it, at any depth, the sheets that include
    it, what it defines, and the objects it names most, System and the functions object left out."""
    code, out = kiwi_map()
    lines = out.splitlines()
    assert code == 0 and len(out) < 10_000 and len(lines) == 16 and not any("->" in line for line in lines)
    assert lines[0].startswith("== KiwiStory: 14 sheets, 219 events, 10 layouts. ")
    assert ("  ePlayer         50 events    7470 chars; layouts TitleScreen, Options, 0_Intro, 1_Forest, 2_Cave, "
            "3_Temple; included by eMain; functions Player_Move, Player_Turn, Player_Jump, Player_Fall, Player_Hurt; "
            "objects Player_Base, Player_Mask, Keyboard, Gamepad, Audio") in lines
    assert "  eCredits         3 events     493 chars; layouts Credits; includes eMusic; objects SpriteFont, EndingSprite" in lines
    assert any(line.startswith("  eGlobal ") and "globals GameStarted, CurrentMenu, MenuLock, CameraZone_UID" in line
               for line in lines)
    assert not any("System" in line.split(";", 1)[1] for line in lines[1:-1])
    assert lines[-1].startswith("-- a sheet no layout runs: its triggers do not fire") and "--find NAME" in lines[-1]


@NEEDS_EXAMPLES
def test_map_cuts_the_object_lists_first_and_then_stops_naming_the_rest():
    """As the limit falls, the objects go first, then the repeated layouts become counts, then the names of what a
    sheet defines; past that the map stops, and its last line names the --map command for the sheets left."""
    code, whole = kiwi_map("--limit", "0")
    assert code == 0 and "objects Player_Base, Player_Mask, Keyboard, Gamepad, Audio" in whole
    stages, stopped = [], None
    for limit in range(len(whole) - 1, 1200, -150):
        code, out = kiwi_map("--limit", str(limit))
        assert code == 0 and len(out) <= limit, (limit, len(out))
        stages.append((limit, "; objects " in out, "layouts TitleScreen, Options" in out,
                       "functions Player_Move, Player_Turn" in out, out.splitlines()[-1].startswith("-- stopped")))
        if stages[-1][-1] and stopped is None:
            stopped = out
    for before, after in zip(stages, stages[1:]):       # what a stage cut stays cut at a smaller limit
        assert all(not b or a for a, b in zip(before[1:4], after[1:4])), (before, after)
    assert not stages[-1][1] and not stages[-1][2] and not stages[-1][3] and stages[-1][4], stages[-1]
    gone = [next(i for i, stage in enumerate(stages) if not stage[k]) for k in (1, 2, 3)]
    assert gone[0] <= gone[1] <= gone[2] <= next(i for i, stage in enumerate(stages) if stage[4]), stages
    assert any(not stage[1] and stage[2] and stage[3] for stage in stages), stages    # a stage with only the objects cut
    last = stopped.splitlines()[-1]
    rest = re.search(r"The rest: python \S+ (.*?) --map ", last).group(1).split()
    assert rest and rest[-1] == "eCamera" and "eMain" not in rest
    code, out = kiwi_map(*rest)
    assert code == 0 and out.startswith(f"== KiwiStory: {len(rest)} of its 14 sheets (219 events in all), 10 layouts.")
    assert sum(1 for line in out.splitlines() if line.startswith("  ")) == len(rest)


def test_map_groups_the_sheets_by_folder_and_says_when_no_layout_runs_one(project):
    with_menu_sheet(project, folder="Menus")
    code, out = tool(project, "print_sheet", "--map")
    lines = out.splitlines()
    assert code == 0 and lines[2] == "[Menus]" and lines[3].startswith("  Menu ") and "no layout runs it" in lines[3]
    assert lines[1].startswith("  Game ") and "; layouts Game; " in lines[1]
    # Two copies of one sheet: every object both touch is left out, and the header says so
    assert "which every sheet touches, left out)" in lines[0] and "; objects " not in out


def test_map_takes_no_find_events_outline_show_or_since(built):
    p = streams(built, f"{INSTALLED}/scripts/print_sheet.py", "--rag", str(REPO), "--map", "--outline")
    assert p.returncode == 2 and "--map prints one line per sheet" in p.stderr


def test_the_big_sheet_fixture_is_long_and_passes_the_checker(project):
    """The eval fixture of a long sheet: 400 and more events, comments in Chinese, a project the checker passes."""
    make = script_module("make_fixtures", SKILL / "evals")
    sheet = make.big_sheet()

    def comments(events: list) -> list[str]:
        return [t for e in events for t in ([e["text"]] if e.get("eventType") == "comment" else [])
                + comments(e.get("children", []))]

    assert sum(1 for _ in script_module("c3project").numbered_events(sheet["events"])) >= 400
    assert len(comments(sheet["events"])) >= 190 and all(re.search("[一-鿿]", t) for t in comments(sheet["events"]))
    assert make.wave_bonus(make.BIG_SHEET_FOCUS) == 454 and len({make.wave_bonus(n) for n in range(1, 25)}) == 24
    code, out = check(big(project))
    assert code == 0 and out.splitlines()[-1].startswith("ok: "), out[-800:]
