"""open_in_editor.py: handing the project to the editor."""
import itertools
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.skill_helpers import SKILL, INSTALLED, SHEET, run


def test_open_in_editor_hands_the_editor_the_project_the_current_directory_is_in(project, tmp_path):
    """Offline: finding the project, packing it, and the steps for an agent's own browser tool."""
    (project / ".git").mkdir()
    (project / ".git" / "HEAD").write_text("ref: refs/heads/main", encoding="utf-8")
    code, out = run(project, f"{INSTALLED}/scripts/open_in_editor.py", "--help")
    assert code == 0 and "exit codes:" in out and "--steps" in out, out
    empty = tmp_path / "empty"
    empty.mkdir()
    # the clone's copy: an installed one falls back to the project it is installed in
    code, out = run(empty, SKILL / "scripts" / "open_in_editor.py")
    assert code == 2 and "no project.c3proj or .c3p found" in out and "--project" in out, out

    code, out = run(project, f"{INSTALLED}/scripts/open_in_editor.py", "--browser", str(tmp_path / "no-browser.exe"))
    assert code == 2 and "could not be driven" in out and "--steps" in out, out

    code, out = run(project, f"{INSTALLED}/scripts/open_in_editor.py", "--steps")
    c3p = project / ".tmp" / "open-in-editor.c3p"
    assert code == 3 and str(c3p) in out and 'the input "Project to open"' in out, out
    assert (project / ".tmp" / ".gitignore").read_text(encoding="utf-8") == "*\n"
    assert "\nSETUP:\nasync () => {\n" in out and "\nRESULT:\nasync () => {\n" in out
    assert "https://editor.construct.net/" in out

    code, out = run(project, f"{INSTALLED}/scripts/open_in_editor.py", "--steps", "--preview")
    assert code == 3 and out.rstrip().endswith("read the console of the preview window it opens."), out
    code, out = run(project, f"{INSTALLED}/scripts/open_in_editor.py", "--steps", "--state", "Player")
    assert code == 3 and out.rstrip().endswith("as references/reading-the-runtime.md says."), out

    import io
    import zipfile
    names = zipfile.ZipFile(io.BytesIO(c3p.read_bytes())).namelist()
    assert "project.c3proj" in names and SHEET in names
    assert not any(n.startswith((".git/", ".tmp/")) for n in names), names


@pytest.mark.skipif(sys.platform != "win32", reason="MAX_PATH is Windows'")
def test_open_in_editor_keeps_the_preview_indexeddb_inside_max_path(tmp_path):
    """The browser opens no IndexedDB whose folder path, \\\\?\\ counted, reaches MAX_PATH: a
    preview on a profile past 189 characters stopped answering (observed in Edge, 2026-10-01).
    A long profile goes by its 8.3 short name where the volume keeps one; one still too deep
    is refused before the preview."""
    oe = opener()
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


def opener():
    sys.path.insert(0, str(SKILL / "scripts"))
    try:
        import open_in_editor as oe
    finally:
        sys.path.pop(0)
    return oe


def test_open_in_editor_closes_the_start_up_window_once_when_projects_open_at_once(tmp_path, monkeypatch):
    """--jobs 2: both jobs found the browser's start-up window among the targets before either
    closed it, and the second close failed its project with "Target.closeTarget: No target with
    given id found" (timer-1 to timer-3, 2026-10-03). The first page to open closes it, once."""
    oe = opener()
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
    oe = opener()
    assert oe.kept(None, None, tmp_path) == (tmp_path / ".tmp" / "open-in-editor.json", tmp_path / ".tmp" / "shots")
    assert (tmp_path / ".tmp" / ".gitignore").read_text(encoding="utf-8") == "*\n"
    assert oe.kept(tmp_path / "a.json", tmp_path / "s", tmp_path) == (tmp_path / "a.json", tmp_path / "s")


def test_open_in_editor_names_where_it_kept_them_in_its_last_line(tmp_path):
    oe = opener()
    opened = {"status": "opened", "preview": {"errors": []}}
    line = oe.summary([opened, {"status": "failed"}], True, tmp_path / "r.json", tmp_path / "shots")
    assert line == f"1 of 2 opened and ran without errors; full results in {tmp_path / 'r.json'}, " \
                   f"screenshots in {tmp_path / 'shots'}", line


def opened_with(preview: dict) -> list[str]:
    return opener().report({"project": "Game", "status": "opened", "title": "Game - Construct 3",
                            "editor": "https://editor.construct.net/", "dialogs": [], "warnings": [], "exception": "",
                            "preview": {"started": True, "layout": "Game", "runtime": "worker", "errors": [],
                                        **preview}})


def test_open_in_editor_reports_a_notice_over_the_opened_project_as_a_warning():
    """template-quiz opened, its title turned to the project's name, and the editor showed
    #deprecatedFeaturesDialog over it (2026-10-02, r495-2 and r504): opened, with the notice
    as a warning. The crash report also comes after the title has turned, so a dialog is a
    notice by its id, not by the title."""
    notice = ("Deprecated features This project uses some deprecated features. ... This project used the "
              "legacy Flat export file structure mode. It has been updated to the modern Folders mode.")
    lines = opener().report({"project": "Quiz", "status": "opened", "title": "Quiz template - Construct 3",
                             "editor": "https://editor.construct.net/", "dialogs": [], "warnings": [notice],
                             "exception": ""})
    assert lines == ["opened   Quiz  (Quiz template - Construct 3, https://editor.construct.net/)",
                     f"  warning: {notice}"], lines
    assert "d.id == 'deprecatedFeaturesDialog'" in opener().RESULT_JS


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


def test_open_in_editor_prints_the_state_the_game_left():
    """--state: the globals, every type's count, then each named type's instances with
    instance variables and the debugger's values under their last word; a miss names
    the nearest type."""
    platform = {"behaviors.platform.debugger.vector-x": 127.99999785, "behaviors.platform.properties.enabled.name": True,
                "behaviors.platform.debugger.animation-mode": ["behaviors.platform.debugger.anim-moving"]}
    sprite = {"title": "plugins.sprite.debugger.animation-properties.title",
              "values": {"plugins.sprite.debugger.animation-properties.current-animation": "Run"}}
    player = {"uid": 4, "x": 56.0, "y": 239.9375, "width": 8, "height": 12, "angle": 0, "layer": "World",
              "zIndex": 1, "isVisible": False, "opacity": 1, "animationName": "Run", "animationFrame": 2,
              "instVars": {"Health": 3}, "inspector": {"plugin": [sprite], "behaviors": {"Platform": platform}}}
    state = {"globalVars": {"Score": 0, "Playable": True}, "counts": {"Player": 1, "Coin": 12},
             "objects": {"Player": {"count": 1, "instances": [player]},
                         "Coin": {"count": 12, "instances": [{"uid": 9, "x": 1, "y": 2, "width": 4, "height": 4,
                                                              "layer": "World", "text": None}]},
                         "Enemey": None},
             "types": ["Player", "Coin", "Enemy"]}
    lines = opened_with({"state": state})
    assert lines[2:] == [
        "  globals: Score 0, Playable true",
        "  objects: Player 1, Coin 12",
        "  Player: 1 instance",
        "    uid 4, at (56, 239.94) 8x12, on World, hidden; Health 3",
        '      sprite: current-animation "Run"',
        "      Platform: vector-x 128, enabled true, animation-mode anim-moving",
        "  Coin: 12 instances",
        "    uid 9, at (1, 2) 4x4, on World",
        "    and 11 more, not read",
        "  Enemey: no object type of that name; closest: Enemy",
    ], lines


def test_open_in_editor_says_when_the_state_was_not_read():
    lines = opened_with({"state": {"error": "TypeError: c3probe is undefined\n    at <anonymous>"}})
    assert lines[2:] == ["  state: not read: TypeError: c3probe is undefined"], lines


def test_install_addon_reads_addon_json_before_the_editor(tmp_path):
    """A .c3addon whose addon.json the editor could not read is refused here, with what to fix."""
    import zipfile
    oe = opener()
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
