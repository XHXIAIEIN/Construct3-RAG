"""print_sheet.py: the event sheet in the words of the editor."""
import os
import re
import shutil
import subprocess
import sys

import pytest

from tests.skill_helpers import REPO, INSTALLED, SHEET, tool, check, edit, block, events


def test_outline_numbers_events_as_the_editor_does(built):
    code, out = tool(built, "print_sheet", "--outline", "Game")
    rows = [line.split("[sid")[0].rstrip() for line in out.splitlines()]
    assert code == 0
    assert rows[:4] == ["== Game", "   (1) // Coins. Tap a coin to collect it; when the last one is gone the next round starts.",
                        "   (1) // Settings", "   (1) string ROUND_COINS = 1,3,6,2,10,1"]
    assert "   1 group Setup" in rows and "   2   System:on-start-of-layout" in rows


def test_print_words_the_sheet_as_the_editor_does(built):
    code, out = tool(built, "print_sheet", "Game")
    assert code == 0
    assert "   5   Touch: On touched Coin (start)\n       Coin: NOT Is any Tween playing\n           -> Coin: Collect()" in out
    assert "     global constant string ROUND_COINS = 1,3,6,2,10,1" in out
    assert "   7 function AddScore(points: number)\n         -> System: Add points to score" in out
    assert "   9   System: Coin.Count = 0\n       System: Trigger once" in out


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
    assert "  12 (every tick)\n         -> Coin: Set scale to 1.5" in out
    assert "  13 group Idle\n  14   (every tick)\n           -> Coin: Set scale to 1.5" in out
    assert out.count("(every tick)") == 2 and out.count("(runs with its parent)") == 2, out


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
    code, whole = tool(built, "print_sheet", "Game")
    parts, events = [], "1-"
    while events:
        code, out = tool(built, "print_sheet", "Game", "--events", events, "--limit", "900")
        assert code == 0 and len(out) < 1500, out
        parts.append(out)
        last = out.splitlines()[-1]
        events = re.search(r"--events (\d+-)", last).group(1) if last.startswith("-- stopped at the limit") else None
    assert len(parts) > 1 and parts[0].startswith("== Game: events 1-")
    printed = {line for part in parts for line in part.splitlines() if "[context]" not in line}
    assert [line for line in whole.splitlines()[1:] if line not in printed] == []


def test_print_of_a_part_starts_with_the_events_it_sits_in(built):
    code, out = tool(built, "print_sheet", "Game", "--events", "9")
    assert code == 0
    assert out.splitlines()[:4] == ["== Game: events 9-9 of 9; a [context] row is an event these sit in, without its actions",
                                    "   8 group Restart  [context]", "       // Start the next round when the last coin is gone",
                                    "   9   System: Coin.Count = 0"]
    assert "Touch: On touched" not in out


@pytest.mark.parametrize("events, said", [("40-", "has 9 events"), ("x", "40-80, 40- or 40"), ("5-2", "ends before it starts")])
def test_print_refuses_a_range_it_cannot_read(built, events, said):
    code, out = tool(built, "print_sheet", "Game", "--events", events)
    assert code == 1 and said in out


def test_print_without_a_name_lists_the_sheets_that_do_not_fit(project):
    shutil.copy(project / SHEET, project / "eventSheets" / "Menu.json")
    edit(project, "project.c3proj", lambda data: data["eventSheets"]["items"].append("Menu"))
    code, out = tool(project, "print_sheet", "--limit", "900")
    assert code == 0
    assert "2 event sheets" in out and re.search(r"Game +9 events +\d+ characters", out) and "-> " not in out
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
    for locale in ("en-US", "zh-CN"):
        code, out = tool(project, "print_sheet", "Game", "--locale", locale)
        assert code == 0, out
        assert out.count(" [disabled]") == 4 and out.count(" [event disabled]") == 2, out
    code, out = tool(project, "print_sheet", "Game")
    assert "   5   Touch: On touched Coin (start)\n       Coin: NOT Is any Tween playing [disabled]\n" \
           "           -> Coin: Collect() [disabled]" in out
    assert "   7 function AddScore(points: number)\n         -> System: Add points to score [disabled]" in out
    assert "   8 group Restart [event disabled]\n" in out
    assert "   9   System: Coin.Count = 0 [disabled] [event disabled]\n       System: Trigger once\n" in out


def test_scripts_write_utf8_and_survive_a_code_page_that_cannot(built):
    """A piped Python on Windows writes the ANSI code page: mojibake under cp936, a crash under cp1252."""
    script = built / INSTALLED / "scripts" / "print_sheet.py"
    for codec, want in ((None, "场景开始"), ("cp1252", "System: ")):
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
        env.update({"PYTHONIOENCODING": codec} if codec else {})
        p = subprocess.run([sys.executable, str(script), "Game", "--locale", "zh-CN", "--rag", str(REPO)],
                           cwd=built, env=env, capture_output=True)
        assert p.returncode == 0, p.stdout + p.stderr
        assert want in p.stdout.decode(codec or "utf-8")
