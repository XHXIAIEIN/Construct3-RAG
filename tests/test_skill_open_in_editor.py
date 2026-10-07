"""open_in_editor.py: handing the project to the editor."""
import itertools
import json
import re
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from tests.skill_helpers import REPO, SKILL, INSTALLED, SHEET, run, script_module

# The result of a project the editor opened, before a preview or the TypeScript definitions.
OPENED = {"project": "Game", "status": "opened", "title": "Game - Construct 3",
          "editor": "https://editor.construct.net/", "dialogs": [], "warnings": [], "exception": ""}


oe = script_module("open_in_editor")


def test_open_in_editor_hands_the_editor_the_project_the_current_directory_is_in(project, tmp_path):
    """Offline: finding the project, packing it, and the steps for an agent's own browser tool."""
    script = f"{INSTALLED}/scripts/open_in_editor.py"
    (project / ".git").mkdir()
    (project / ".git" / "HEAD").write_text("ref: refs/heads/main", encoding="utf-8")
    worktree = project / ".claude" / "worktrees" / "a"     # an agent's copies, 2.2 GB in a game
    worktree.mkdir(parents=True)
    (worktree / "project.c3proj").write_text("{}", encoding="utf-8")
    code, out = run(project, script, "--help")
    assert code == 0 and "exit codes:" in out and "--steps" in out, out
    empty = tmp_path / "empty"
    empty.mkdir()
    # the clone's copy: an installed one falls back to the project it is installed in
    code, out = run(empty, SKILL / "scripts" / "open_in_editor.py")
    assert code == 2 and "no project.c3proj or .c3p found" in out and "--project" in out, out

    code, out = run(project, script, "--browser", str(tmp_path / "no-browser.exe"))
    assert code == 2 and "could not be driven" in out and "--steps" in out, out

    code, out = run(project, script, "--steps")
    c3p = project / ".tmp" / "open-in-editor.c3p"
    assert code == 3 and str(c3p) in out and 'the input "Project to open"' in out, out
    assert (project / ".tmp" / ".gitignore").read_text(encoding="utf-8") == "*\n"
    assert "\nSETUP:\nasync () => {\n" in out and "\nRESULT:\nasync () => {\n" in out
    assert "https://editor.construct.net/" in out

    code, out = run(project, script, "--steps", "--preview")
    assert code == 3 and out.rstrip().endswith("read the console of the preview window it opens."), out
    code, out = run(project, script, "--steps", "--state", "Player")
    assert code == 3 and out.rstrip().endswith("as references/reading-the-runtime.md says."), out
    code, out = run(project, script, "--steps", "--typescript")
    assert code == 2 and "TypeScript > Update TypeScript definitions" in out, out

    with zipfile.ZipFile(c3p) as packed:
        names = packed.namelist()
    assert "project.c3proj" in names and SHEET in names
    # only the files the editor reads: the skill's copy and the worktrees under .claude stay out
    assert not any(n.startswith((".git/", ".tmp/", ".claude/", ".agents/")) for n in names), names


@pytest.mark.skipif(sys.platform != "win32", reason="MAX_PATH is Windows'")
def test_open_in_editor_keeps_the_preview_indexeddb_inside_max_path(tmp_path):
    """The browser opens no IndexedDB whose folder path, \\\\?\\ counted, reaches MAX_PATH: a
    preview on a profile past 189 characters stopped answering (observed in Edge, 2026-10-01).
    A long profile goes by its 8.3 short name where the volume keeps one; one still too deep
    is refused before the preview."""
    assert not oe.too_deep("\\\\?\\" + "C:\\" + "x" * 186) and oe.too_deep("\\\\?\\" + "C:\\" + "x" * 187)
    assert oe.user_data_dir(tmp_path) == str(tmp_path.resolve())
    deep = tmp_path / ("y" * 100) / ("z" * 100) / ".tmp" / "editor-msedge"
    deep.mkdir(parents=True)
    data = oe.user_data_dir(deep)
    assert len(data) <= 150 or data == "\\\\?\\" + str(deep.resolve()), data

    project = tmp_path / "p"
    project.mkdir()
    code, out = run(project, SKILL / "scripts" / "open_in_editor.py", "--help")
    assert code == 0 and "--profile FOLDER" in out, out


def test_open_in_editor_closes_the_start_up_window_once_when_projects_open_at_once(tmp_path, monkeypatch):
    """--jobs 2: both jobs found the browser's start-up window among the targets before either
    closed it, and the second close failed its project with "Target.closeTarget: No target with
    given id found" (timer-1 to timer-3, 2026-10-03). The first page to open closes it, once."""
    created = threading.Barrier(2)

    class Browser:
        """The browser end of DevTools: the window it started with and a page per createTarget.
        A list of the targets is out of date by the time it arrives, as over a socket."""

        def __init__(self) -> None:
            self.pages, self.closed = {"start-up": "about:blank"}, []
            self.ids, self.lock = itertools.count(), threading.Lock()

        def call(self, method: str, wait: float = oe.CALL, session: str | None = None, **params) -> dict:
            if method == "Target.createTarget":
                with self.lock:
                    target = f"page-{next(self.ids)}"
                    self.pages[target] = params["url"]
                created.wait(5)     # both projects have a page before either goes on
                return {"targetId": target}
            if method == "Target.getTargets":
                infos = [{"targetId": t, "type": "page", "url": url} for t, url in self.pages.items()]
                time.sleep(0.2)
                return {"targetInfos": infos}
            if method == "Target.closeTarget":
                with self.lock:
                    if self.pages.pop(params["targetId"], None) is None:
                        raise oe.DevToolsError("Target.closeTarget: No target with given id found")
                    self.closed.append(params["targetId"])
                return {"success": True}
            raise AssertionError(method)

    browser = Browser()
    profile = tmp_path / "editor-msedge"
    profile.mkdir()
    (profile / "DevToolsActivePort").write_text("9222\n/devtools/browser/1", encoding="utf-8")
    monkeypatch.setattr(oe.Browser, "devtools_url", staticmethod(lambda port_file: "ws://127.0.0.1:9222/devtools/browser/1"))
    sent: list[str] = []

    class Page:
        def call(self, method: str, wait: float = oe.CALL, session: str | None = None, **params) -> dict:
            sent.append(method)
            return {}

    monkeypatch.setattr(oe, "DevTools", lambda url, timeout=oe.CALL: browser if "/browser/" in url else Page())

    driven = oe.Browser("msedge.exe", profile, headed=False)
    with ThreadPoolExecutor(2) as pool:
        opened = list(pool.map(lambda _: driven.page(oe.EDITOR)[0], range(2)))
    assert browser.closed == ["start-up"], browser.closed
    assert sorted(browser.pages) == sorted(opened), browser.pages
    # Each page is kept active, so a --headed window the user minimizes still opens the project
    assert sorted(sent) == ["Emulation.setFocusEmulationEnabled"] * 2 + ["Page.setWebLifecycleState"] * 2, sent


def test_open_in_editor_keeps_the_results_and_screenshots_in_the_project_by_default(tmp_path):
    """A run piped through tail or head loses the lines it cut, and a run without --shots shows
    nothing: sessions ran the same preview again only to see them (game projects' transcripts,
    2026-09-27 to 10-02). Both are kept whatever the flags."""
    assert oe.kept(None, None, tmp_path) == (tmp_path / ".tmp" / "open-in-editor.json", tmp_path / ".tmp" / "shots")
    assert (tmp_path / ".tmp" / ".gitignore").read_text(encoding="utf-8") == "*\n"
    assert oe.kept(tmp_path / "a.json", tmp_path / "s", tmp_path) == (tmp_path / "a.json", tmp_path / "s")


def test_open_in_editor_names_where_it_kept_them_in_its_last_line(tmp_path):
    opened = {"status": "opened", "preview": {"errors": []}}
    line = oe.summary([opened, {"status": "failed"}], True, tmp_path / "r.json", tmp_path / "shots")
    assert line == f"1 of 2 opened and ran without errors; full results in {tmp_path / 'r.json'}, " \
                   f"screenshots in {tmp_path / 'shots'}", line


def opened_with(preview: dict, locale: str | None = None) -> list[str]:
    return oe.report({**OPENED, "preview": {"started": True, "layout": "Game", "runtime": "worker",
                                            "errors": [], **preview}},
                     oe.labeler(None, locale)[0] if locale else oe.key_name)


def test_open_in_editor_reports_a_notice_over_the_opened_project_as_a_warning():
    """template-quiz opened, its title turned to the project's name, and the editor showed
    #deprecatedFeaturesDialog over it (2026-10-02, r495-2 and r504): opened, with the notice
    as a warning. The crash report also comes after the title has turned, so a dialog is a
    notice by its id, not by the title."""
    notice = ("Deprecated features This project uses some deprecated features. ... This project used the "
              "legacy Flat export file structure mode. It has been updated to the modern Folders mode.")
    lines = oe.report({**OPENED, "project": "Quiz", "title": "Quiz template - Construct 3", "warnings": [notice]})
    assert lines == ["opened   Quiz  (Quiz template - Construct 3, https://editor.construct.net/)",
                     f"  warning: {notice}"], lines
    assert "d.id == 'deprecatedFeaturesDialog'" in oe.RESULT_JS


def test_open_in_editor_writes_the_typescript_definitions_the_editor_wrote(tmp_path):
    """Save as project folder, then Set up TypeScript for external editor, wrote 57 files under
    scripts/ts-defs of a game project, a class per object type among them (2026-10-04, r495-2). They go over
    the ones there; a tsconfig.json the project has is the user's and stays."""

    class Page:
        def evaluate(self, expression, wait=None):
            assert "'ui.bars.project.menu.fileFolderItem.set-up-external-typescript'" in expression
            return {"files": {"ts-defs/instanceTypes.d.ts": "declare namespace InstanceType {\n\tclass Coin {}\n}",
                              "ts-defs/runtime/IRuntime.d.ts": "new", "tsconfig.json": "editor's"}}

    scripts = tmp_path / "scripts"
    (scripts / "ts-defs" / "runtime").mkdir(parents=True)
    (scripts / "ts-defs" / "runtime" / "IRuntime.d.ts").write_text("old", encoding="utf-8")
    (scripts / "tsconfig.json").write_text("user's", encoding="utf-8")
    wrote = oe.typescript(Page(), tmp_path)
    assert wrote == {"written": ["ts-defs/instanceTypes.d.ts", "ts-defs/runtime/IRuntime.d.ts"]}, wrote
    assert (scripts / "ts-defs" / "runtime" / "IRuntime.d.ts").read_text(encoding="utf-8") == "new"
    assert (scripts / "tsconfig.json").read_text(encoding="utf-8") == "user's"
    lines = oe.report({**OPENED, "typescript": wrote})
    assert lines[1] == "  typescript: wrote 2 files into scripts/ts-defs", lines
    assert oe.typescript(Page(), tmp_path / "game.c3p") == {
        "error": "a .c3p has no scripts folder to write into: pass the folder project"}
    failed = {"status": "opened", "typescript": {"error": "the Project Bar shows no Scripts folder"}}
    assert oe.failed(failed) and oe.report({**failed, "project": "Game", "title": "", "editor": "", "warnings": []})[1] \
        == "  typescript: not written, the Project Bar shows no Scripts folder"


def test_open_in_editor_finds_the_typescript_menus_by_the_keys_of_their_labels():
    """Menu items carry no id, so their labels are read from the editor's language file by key:
    an editor in Chinese wrote the same 57 files (2026-10-04, r495-2). Each key names the label
    the steps click, in the language files this repository keeps."""
    keys = re.findall(r"'((?:main-menu|ui\.bars)\.[\w.-]+)'", oe.TYPESCRIPT_JS)
    assert len(keys) == 6, keys
    for locale in ("en-US", "zh-CN"):
        text = json.loads((REPO / "data" / "c3-lang" / f"{locale}.json").read_text(encoding="utf-8"))["text"]
        for key in keys:
            node = text
            for part in key.split("."):
                node = node[part]
            assert isinstance(node, str) and node, (locale, key)


def test_open_in_editor_reports_how_long_the_game_ran_in_the_preview():
    """A 5 s preview ran the game 3.7 to 4.7 s, once 0.7 s: the window loads first. The line
    says what the runtime ran, ticks and its own wall time (measured 2026-10-02, r504)."""
    lines = opened_with({"ticks": 597, "wallTime": 4.3545})
    assert lines[1] == "  preview: layout 'Game', runtime in the worker, 597 ticks in 4.4 s, no errors", lines


def test_open_in_editor_leaves_the_ticks_out_when_the_runtime_gave_none():
    lines = opened_with({"ticks": None, "wallTime": None})
    assert lines[1] == "  preview: layout 'Game', runtime in the worker, no errors", lines


def test_open_in_editor_leaves_the_ticks_out_when_the_wall_time_is_missing():
    """A release whose runtime gave no wall time must not end the run of every project."""
    lines = opened_with({"ticks": 597, "wallTime": None})
    assert lines[1] == "  preview: layout 'Game', runtime in the worker, no errors", lines


def test_open_in_editor_reports_the_crash_report_the_preview_left_in_the_editor(monkeypatch):
    """A frame whose collision polygon held two points opened; F5 then showed the editor's crash
    report, "assertion failure: must have at least three points in a collision poly", while the
    preview window opened and ran behind it, and the run said "no errors" (2026-10-04, r495-2).
    The editor's page is read once the preview has run, and its crash report fails the project."""
    crash = ("Construct Oops! Something went wrong. ... Type: assertion failure Message: must have at least "
             "three points in a collision poly")

    class Win:
        events: list = []
        ws = SimpleNamespace(close=lambda: None)

        def call(self, method, wait=None, session=None, **params):
            return {}

        def evaluate(self, expression, wait=None, session=None):
            return {"layout": "Game", "tickCount": 389, "wallTime": 2.7} if "snapshot" in expression else 0

    class Page:
        def evaluate(self, expression, wait=None):
            assert expression == oe.CRASH_JS
            return crash

    browser = SimpleNamespace(devtools=Win())
    monkeypatch.setattr(oe, "start_preview", lambda b, target, page: ({"targetId": "preview"}, Win()))
    monkeypatch.setattr(oe, "attach", lambda win, patience=0: ([None], [None], False))
    monkeypatch.setattr(oe.time, "sleep", lambda seconds: None)
    ran = oe.preview(browser, ("editor", Page()), 4)
    assert ran["started"] and ran["editor"] == crash and ran["errors"] == [], ran
    lines = opened_with({"ticks": 389, "wallTime": 2.7, "editor": crash})
    assert lines[1:] == ["  preview: layout 'Game', runtime in the worker, 389 ticks in 2.7 s, 1 error",
                         f"  editor: {crash}"], lines
    assert oe.failed({"status": "opened", "preview": {"errors": [], "editor": crash}})


# A player read by --state: a Sprite with the Platform behavior, as the probe returns it
PLATFORM = {"behaviors.platform.debugger.vector-x": 127.99999785, "behaviors.platform.properties.enabled.name": True,
            "behaviors.platform.debugger.animation-mode": ["behaviors.platform.debugger.anim-moving"]}
SPRITE = {"title": "plugins.sprite.debugger.animation-properties.title",
          "values": {"plugins.sprite.debugger.animation-properties.current-animation": "Run"}}
PLAYER = {"uid": 4, "x": 56.0, "y": 239.9375, "width": 8, "height": 12, "angle": 0, "layer": "World",
          "zIndex": 1, "isVisible": False, "opacity": 1, "animationName": "Run", "animationFrame": 2,
          "instVars": {"Health": 3}, "inspector": {"plugin": [SPRITE], "behaviors": {"Platform": PLATFORM}}}


def test_open_in_editor_prints_the_state_the_game_left():
    """--state prints the globals and every type's count. Then each named type's instances
    show their instance variables and the inspector values under the names the editor gives
    them. A behavior's section keeps the behavior's name on the object, and a miss names the
    nearest type."""
    state = {"globalVars": {"Score": 0, "Playable": True}, "counts": {"Player": 1, "Coin": 12},
             "objects": {"Player": {"count": 1, "instances": [PLAYER]},
                         "Coin": {"count": 12, "instances": [{"uid": 9, "x": 1, "y": 2, "width": 4, "height": 4,
                                                              "layer": "World", "text": None}]},
                         "Enemey": None},
             "types": ["Player", "Coin", "Enemy"]}
    lines = opened_with({"state": state}, "en-US")
    assert lines[2:] == [
        "  globals: Score 0, Playable true",
        "  objects: Player 1, Coin 12",
        "  Player: 1 instance",
        "    uid 4, at (56, 239.94) 8x12, on World, hidden; Health 3",
        '      Sprite animation: Current animation "Run"',
        "      Platform: Vector X 128, Enabled true, Animation mode Moving",
        "  Coin: 12 instances",
        "    uid 9, at (1, 2) 4x4, on World",
        "    and 11 more, not read",
        "  Enemey: no object type of that name; closest: Enemy",
    ], lines


def test_open_in_editor_names_the_debuggers_values_in_the_locale_and_keeps_a_key_the_pack_lacks():
    """--locale zh-CN gives the editor's Chinese names. A key the language pack lacks, such as
    a third-party addon's, keeps its last word."""
    zh = json.loads((REPO / "data" / "c3-lang" / "zh-CN.json").read_text(encoding="utf-8"))["text"]
    platform = zh["behaviors"]["platform"]
    state = {"globalVars": {}, "counts": {"Player": 1}, "objects": {"Player": {"count": 1, "instances": [PLAYER]}}}
    lines = opened_with({"state": state}, "zh-CN")
    assert lines[6:8] == [
        f'      {zh["plugins"]["sprite"]["debugger"]["animation-properties"]["title"]}: '
        f'{zh["plugins"]["sprite"]["debugger"]["animation-properties"]["current-animation"]} "Run"',
        f'      Platform: {platform["debugger"]["vector-x"]} 128, {platform["properties"]["enabled"]["name"]} true, '
        f'{platform["debugger"]["animation-mode"]} {platform["debugger"]["anim-moving"]}',
    ], lines
    label, note = oe.labeler(None, "en-US")
    assert note is None and label("plugins.myaddon.debugger.charge") == "charge"
    assert label("plugins.myaddon.properties.power.name") == "power"


def test_open_in_editor_refuses_a_locale_the_clone_has_no_language_pack_for(project, tmp_path):
    code, out = run(project, f"{INSTALLED}/scripts/open_in_editor.py", "--state", "Player", "--locale", "xx-XX",
                    "--browser", str(tmp_path / "no-browser.exe"))
    assert code == 2 and "no language pack for --locale xx-XX; the clone has: en-US, zh-CN" in out, out


def test_state_says_in_one_line_when_no_clone_names_the_inspector_values(project, tmp_path):
    """Without a clone, --state and a plan with a state step print the note first. --preview and a plan
    without a state step print none, because they show no inspector values."""
    agents = project / "AGENTS.md"
    agents.write_text("".join(line for line in agents.read_text(encoding="utf-8").splitlines(keepends=True)
                              if "Construct3-RAG:" not in line), encoding="utf-8")
    browser = str(tmp_path / "no-browser.exe")
    note = ("note: Construct3-RAG not found, so each inspector value shows the last word of its key, not its name "
            "in --locale zh-CN. Set CONSTRUCT3_RAG to the clone's folder, or write the line "
            "'- Construct3-RAG: <folder>' in the project's AGENTS.md, then run again.")
    code, out = run(project, f"{INSTALLED}/scripts/open_in_editor.py", "--state", "Player", "--locale", "zh-CN",
                    "--browser", browser)
    assert code == 2 and out.splitlines()[0] == note and "could not be driven" in out, out
    code, out = run(project, f"{INSTALLED}/scripts/open_in_editor.py", "--preview", "--browser", browser)
    assert code == 2 and "note:" not in out, out
    plan = tmp_path / "plan.json"
    for steps, noted in (([{"wait": 1}, {"state": ["Player"]}], True), ([{"wait": 1}], False)):
        plan.write_text(json.dumps({"steps": steps}), encoding="utf-8")
        code, out = run(project, f"{INSTALLED}/scripts/preview_project.py", str(plan), "--locale", "zh-CN",
                        "--browser", browser)
        assert code == 2 and (out.splitlines()[0] == note) == noted and "could not be driven" in out, out


def test_open_in_editor_says_when_the_state_was_not_read():
    lines = opened_with({"state": {"error": "TypeError: c3probe is undefined\n    at <anonymous>"}})
    assert lines[2:] == ["  state: not read: TypeError: c3probe is undefined"], lines


def test_install_addon_reads_addon_json_before_the_editor(tmp_path):
    """A .c3addon whose addon.json the editor could not read is refused here, with what to fix."""
    good, folder, broken = tmp_path / "good.c3addon", tmp_path / "folder.c3addon", tmp_path / "broken.c3addon"
    with zipfile.ZipFile(good, "w") as z:
        z.writestr("addon.json", '{"id": "MyFx", "type": "effect", "name": "My Fx", "version": "1.0.0.0"}')
    with zipfile.ZipFile(folder, "w") as z:
        z.writestr("MyFx/addon.json", "{}")
    with zipfile.ZipFile(broken, "w") as z:
        z.writestr("addon.json", '{"id": "MyFx",}')
    assert oe.addon_json(good)["type"] == "effect"
    assert "zip the files of the addon, not its folder" in oe.addon_json(folder)
    assert "not valid JSON" in oe.addon_json(broken)
    assert "not a zip file" in oe.addon_json(tmp_path / "missing.c3addon")
