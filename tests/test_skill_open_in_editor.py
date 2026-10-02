"""open_in_editor.py: handing the project to the editor."""
import sys

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
    sys.path.insert(0, str(SKILL / "scripts"))
    try:
        import open_in_editor as oe
    finally:
        sys.path.pop(0)
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


def opened_with(preview: dict) -> list[str]:
    sys.path.insert(0, str(SKILL / "scripts"))
    try:
        import open_in_editor as oe
    finally:
        sys.path.pop(0)
    return oe.report({"project": "Game", "status": "opened", "title": "Game - Construct 3",
                      "editor": "https://editor.construct.net/", "dialogs": [], "exception": "",
                      "preview": {"started": True, "layout": "Game", "runtime": "worker", "errors": [], **preview}})


def test_open_in_editor_reports_how_long_the_game_ran_in_the_preview():
    """A 5 s preview ran the game 3.7 to 4.7 s, once 0.7 s: the window loads first. The line
    says what the runtime ran, ticks and its own wall time (measured 2026-10-02, r504)."""
    lines = opened_with({"ticks": 597, "wallTime": 4.3545})
    assert lines[1] == "  preview: layout 'Game', runtime in the worker, 597 ticks in 4.4 s, no errors", lines


def test_open_in_editor_leaves_the_ticks_out_when_the_runtime_gave_none():
    lines = opened_with({"ticks": None, "wallTime": None})
    assert lines[1] == "  preview: layout 'Game', runtime in the worker, no errors", lines
