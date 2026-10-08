"""export_project.py: the version an export carries, where its runtime starts, and what a run
that stops leaves in the editor."""
import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

from tests.skill_helpers import INSTALLED, SHEET, SKILL, edit, events, run

SCRIPT = f"{INSTALLED}/scripts/export_project.py"


def load(scripts: Path):
    """export_project as a module, with the scripts beside it importable."""
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location("export_project", scripts / "export_project.py")
        export = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(export)
    finally:
        sys.path.remove(str(scripts))
    return export


def test_export_bumps_the_last_export_and_carries_a_hand_edit(project):
    """--bump adds one to the version in the export folder's data.json, a number past 99 carrying
    into the one before, and keeps the project's Version when a hand edit made it greater."""
    web = project / "export" / "web"
    web.mkdir(parents=True)
    (web / "data.json").write_text(json.dumps({"project": ["Coins", None, "0.1.0.99", 1]}), encoding="utf-8")
    code, out = run(project, SCRIPT, "--to", "export/web", "--bump", "--dry-run")
    assert code == 0 and "would export 1.0.0.0 " in out, out     # the project's 1.0.0.0 is greater than 0.1.1.0
    (web / "data.json").write_text(json.dumps({"project": ["Coins", "1.0.0.99"]}), encoding="utf-8")
    code, out = run(project, SCRIPT, "--to", "export/web", "--bump", "--dry-run")
    assert code == 0 and "would export 1.0.1.0 " in out and "project.c3proj version 1.0.0.0 -> 1.0.1.0" in out, out
    code, out = run(project, SCRIPT, "--version", "1.2", "--dry-run")
    assert code == 2 and "not 3 or 4 numbers" in out, out
    code, out = run(project, SCRIPT, "--dry-run")
    assert code == 0 and f"into {project.resolve() / '.build' / 'web'}" in out, out    # the products' folder
    assert not (project / ".build").exists()                                             # a dry run writes nothing


def test_export_refuses_a_folder_it_would_empty_of_other_files(project, tmp_path):
    """The export replaces everything in --to, so the project, a folder above it, a drive's root, a
    file and a folder of other files are refused before the browser starts, and stay as they were;
    a new or empty folder and an earlier export are taken (the audit of 2026-10-07 emptied a
    temporary project through --to .)."""
    other = tmp_path / "notes"
    other.mkdir()
    (other / "todo.txt").write_text("keep", encoding="utf-8")
    a_file = tmp_path / "a.txt"
    a_file.write_text("keep", encoding="utf-8")
    for to in (".", "..", str(other), str(a_file), str(Path(project.resolve().anchor))):
        code, out = run(project, SCRIPT, "--to", to, "--dry-run")
        assert code == 2 and "the export replaces everything in the folder" in out, (to, out)
    assert (other / "todo.txt").read_text(encoding="utf-8") == "keep" and (project / "project.c3proj").is_file()
    earlier, empty = project / "export" / "web", tmp_path / "empty"
    earlier.mkdir(parents=True)
    (earlier / "data.json").write_text(json.dumps({"project": ["Coins", "1.0.0.0"]}), encoding="utf-8")
    empty.mkdir()
    for to in ("export/web", str(empty), str(tmp_path / "new")):
        code, out = run(project, SCRIPT, "--to", to, "--dry-run")
        assert code == 0 and "would export" in out, (to, out)
    export = load(SKILL / "scripts")
    assert export.refused_folder(tmp_path / "game", Path(tmp_path.anchor)) == "it is the root of a drive"


def test_export_hands_the_editor_the_version_to_export(project):
    """The .c3p the editor opens carries the version to export with Auto-increment version off, so
    that the export carries it unchanged, and Use worker Auto; it holds only the
    files the editor reads: no export folder, .tmp or the worktrees under .claude (a game's .c3p was
    1.8 GB, 2026-10-03)."""
    export = load(project / INSTALLED / "scripts")
    path = project / "project.c3proj"
    path.write_text(path.read_text(encoding="utf-8").replace('"autoIncrementVersion": false',
                                                             '"autoIncrementVersion": true')
                    .replace('"useWorker": "auto"', '"useWorker": "dom"'), encoding="utf-8")
    web, worktree = project / "export" / "web", project / ".claude" / "worktrees" / "a"
    web.mkdir(parents=True)
    (web / "data.json").write_text("{}", encoding="utf-8")
    worktree.mkdir(parents=True)     # an agent's copies, 2.2 GB in a game
    (worktree / "project.c3proj").write_text("{}", encoding="utf-8")
    with zipfile.ZipFile(io.BytesIO(export.pack(project, "2.3.4.5", project / "export"))) as z:
        names = z.namelist()
        text = z.read("project.c3proj").decode("utf-8")
    assert '\t\t"version": "2.3.4.5",' in text and '"autoIncrementVersion": false' in text, text[:400]
    assert '"useWorker": "auto"' in text, text[:400]
    assert not any(n.startswith(("export/", ".tmp/", ".claude/")) for n in names), names
    assert any(n.startswith("layouts/") for n in names), names
    assert export.project_version(project) == "1.0.0.0"     # the project file itself is not touched
    assert '"useWorker": "dom"' in path.read_text(encoding="utf-8")


class Tab:
    """A tab of the user's browser as export_project drives it: what it was asked, in order."""

    def __init__(self, target: str = "tab-1") -> None:
        self.target, self.asked = target, []

    def call(self, method: str, wait: float = 10, **params) -> dict:
        self.asked.append(method)
        return {}

    def evaluate(self, expression: str, by_value: bool = True, wait: float = 10):
        self.asked.append(expression)
        return None


def stopped_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, opened: bool, stop_in: str) -> tuple:
    """export_project.run over --attach, stopped in open_project or in export; the module, the
    browser connection, the tab and the pages close_project was given, once run has raised."""
    export = load(SKILL / "scripts")
    browser, tab, closed = Tab("browser"), Tab(), []

    def stop(*args):
        raise export.Stop(f"stopped in {stop_in}")
    monkeypatch.setattr(export, "scratch", lambda project: tmp_path)
    monkeypatch.setattr(export, "pack", lambda project, version, skip: b"zip")
    monkeypatch.setattr(export, "attach", lambda spec: browser)
    monkeypatch.setattr(export, "attached_page", lambda devtools, project: (tab, opened))
    monkeypatch.setattr(export, "wait_for_login", lambda page: "Someone")
    monkeypatch.setattr(export, "open_project", stop if stop_in == "open_project" else lambda *a: None)
    monkeypatch.setattr(export, "export", stop if stop_in == "export" else lambda page: b"")
    monkeypatch.setattr(export, "close_project", lambda page: closed.append(page))
    with pytest.raises(export.Stop):
        export.run(tmp_path, tmp_path / "web", "1.0.0.0", "9222", None)
    assert not (tmp_path / "export-project.c3p").exists()
    return export, browser, tab, closed


def test_a_stopped_export_closes_the_tab_it_opened(monkeypatch, tmp_path):
    """A run that stopped left its copy open in the user's browser, and the next run, which takes
    only a tab on the start page, opened another (2026-10-04, r495-2). A tab the run opened is
    closed when it stops, as after an export."""
    export, browser, tab, closed = stopped_run(monkeypatch, tmp_path, opened=True, stop_in="export")
    assert browser.asked == ["Target.closeTarget"] and closed == [], (browser.asked, closed)


@pytest.mark.parametrize("stop_in", ["open_project", "export"])
def test_a_stopped_export_leaves_the_users_own_tab_on_the_start_page(monkeypatch, tmp_path, stop_in):
    """In a tab of the user's the copy is closed without saving, and the dialogs, the file input
    and the interval open_in_editor's SETUP put there are taken away; the tab and its login stay."""
    export, browser, tab, closed = stopped_run(monkeypatch, tmp_path, opened=False, stop_in=stop_in)
    assert closed == [tab] and browser.asked == [], (closed, browser.asked)
    assert tab.asked[-2:] == [export.DISMISS_JS, export.UNSET_JS], tab.asked
    assert "window.__c3Keep = setInterval" in export.oe.SETUP_JS


def test_a_crashed_editor_is_restarted_to_close_the_copy(capsys):
    """An export left the user's tab on the editor's crash report, which has no close button and
    came back each time the menu opened, so the copy could not be closed (2026-10-04, r495-2).
    Restart reloads the editor once the page's question about leaving is answered, which the
    DevTools protocol sees only after Page.enable; the editor was back on its start page in 3 s."""
    export = load(SKILL / "scripts")

    class Crashed(Tab):
        reloaded = pressed = False

        def call(self, method: str, wait: float = 10, **params) -> dict:
            super().call(method)
            if method == "Page.handleJavaScriptDialog":
                if not self.pressed:
                    raise export.oe.DevToolsError("Page.handleJavaScriptDialog: No dialog is showing")
                self.reloaded = True
            return {}

        def evaluate(self, expression: str, by_value: bool = True, wait: float = 10):
            super().evaluate(expression)
            if expression == "document.title":
                return "Game Making Software - Construct 3" if self.reloaded else "Coins - Construct 3"
            if expression == export.CRASH_JS:
                return not self.reloaded
            if "reloadButton" in expression:
                self.pressed = True
                return 1
            if expression.startswith("[performance.timeOrigin"):
                return [2 if self.reloaded else 1, self.reloaded]
            return 1 if expression == "performance.timeOrigin" else None

    tab = Crashed()
    export.close_project(tab)
    assert tab.reloaded and tab.asked.index("Page.enable") < tab.asked.index("Page.handleJavaScriptDialog")
    assert not any("mainMenuButton').getBoundingClientRect" in a for a in tab.asked), tab.asked   # no menu
    assert "pressing its Restart, which reloads the editor: log in there again if it asks" in capsys.readouterr().out


def test_export_reads_where_the_runtime_starts(tmp_path):
    """The end of an r504 export's scripts/main.js, worker off and on."""
    export = load(SKILL / "scripts")
    main = tmp_path / "scripts" / "main.js"
    main.parent.mkdir()
    for flag, expected in (("false", False), ("true", True)):
        main.write_text('// start-export.js\n"use strict";if(window["C3_IsSupported"]){const e=' + flag +
                        ';window["c3_runtimeInterface"]=new self.RuntimeInterface({useWorker:e,workerMainUrl:'
                        '"workermain.js",runtimeMainScript:"scripts/c3main.js"})}', encoding="utf-8")
        assert export.exported_worker(tmp_path) is expected
    main.write_text("", encoding="utf-8")
    assert export.exported_worker(tmp_path) is None


def zipped_export(version: str) -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as z:
        z.writestr("data.json", json.dumps({"project": ["Coins", version]}))
        z.writestr("index.html", version)
    return data.getvalue()


def test_a_failed_unpack_keeps_the_earlier_export(monkeypatch, tmp_path):
    """The new export is extracted beside the folder and checked before it takes the folder's place,
    so an extraction that fails, a version that differs and a swap that fails leave the earlier export
    as it was (the audit of 2026-10-07 lost it to a failed extraction)."""
    export = load(SKILL / "scripts")
    web = tmp_path / "web"
    web.mkdir()
    (web / "data.json").write_text(json.dumps({"project": ["Coins", "1.0.0.0"]}), encoding="utf-8")
    (web / "index.html").write_text("1.0.0.0", encoding="utf-8")
    before = {f.name: f.read_bytes() for f in web.iterdir()}

    def kept() -> bool:
        return {f.name: f.read_bytes() for f in web.iterdir()} == before and sorted(tmp_path.iterdir()) == [web]

    with pytest.raises(export.Stop, match="not 1.0.1.0"):
        export.unpack(zipped_export("1.0.2.0"), web, "1.0.1.0")
    assert kept()
    with monkeypatch.context() as m:
        def fail(*_):
            raise OSError("disk full")
        m.setattr(zipfile.ZipFile, "extractall", fail)
        with pytest.raises(export.Stop, match="disk full.*earlier export there is left as it was"):
            export.unpack(zipped_export("1.0.1.0"), web, "1.0.1.0")
    assert kept()
    with monkeypatch.context() as m:
        rename = Path.rename

        def fail_new(self, target):
            if self.name == "web.new":
                raise OSError("in use")
            return rename(self, target)
        m.setattr(Path, "rename", fail_new)
        with pytest.raises(export.Stop, match="in use"):
            export.unpack(zipped_export("1.0.1.0"), web, "1.0.1.0")
    assert kept()
    export.unpack(zipped_export("1.0.1.0"), web, "1.0.1.0")
    assert (web / "index.html").read_text(encoding="utf-8") == "1.0.1.0" and sorted(tmp_path.iterdir()) == [web]
    export.unpack(zipped_export("1.0.2.0"), tmp_path / "first", "1.0.2.0")     # no earlier export
    assert (tmp_path / "first" / "index.html").read_text(encoding="utf-8") == "1.0.2.0"
    mine = tmp_path / "first.old"
    mine.mkdir()
    (mine / "notes.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(export.Stop, match="holds no Web export"):
        export.unpack(zipped_export("1.0.3.0"), tmp_path / "first", "1.0.3.0")
    assert (mine / "notes.txt").is_file() and (tmp_path / "first" / "index.html").read_text(encoding="utf-8") == "1.0.2.0"


def test_export_stops_on_a_key_it_would_ship_and_names_the_hosts(project):
    """Every player of a web export can read its strings; the run stops before the browser starts."""
    key = "sk-" + "proj-" + "Ab1" * 12     # built from parts, so that no file of the repository holds one

    def put(sheet):
        events(sheet)["add_score"]["actions"][1]["parameters"]["text"] = f'"{key}" & "https://api.example.com/v1"'
    edit(project, SHEET, put)
    code, out = run(project, SCRIPT, "--dry-run")
    assert code == 1 and out.startswith("not exported: the export ships every string of the project"), out
    assert "  sheet Game event 7 action 2: an OpenAI API key (sk-pro…); to keep it, write allow-secret in the " \
           "comment above the event" in out and key not in out and "would export" not in out, out

    def mark(sheet):
        rows = sheet["events"]
        rows[rows.index(events(sheet)["add_score"]) - 1]["text"] += " allow-secret"
    edit(project, SHEET, mark)
    code, out = run(project, SCRIPT, "--dry-run")
    assert code == 0, out
    assert out.startswith("the game holds addresses of api.example.com (sheet Game event 7 action 2): tell the user "
                          "which hosts the game contacts\nwould export"), out
