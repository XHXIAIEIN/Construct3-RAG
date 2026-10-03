"""export_project.py: the version an export carries and where its runtime starts."""
import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

from tests.skill_helpers import INSTALLED, SKILL, run


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
    code, out = run(project, f"{INSTALLED}/scripts/export_project.py", "--to", "export/web", "--bump", "--dry-run")
    assert code == 0 and "would export 1.0.0.0 " in out, out     # the project's 1.0.0.0 is greater than 0.1.1.0
    (web / "data.json").write_text(json.dumps({"project": ["Coins", "1.0.0.99"]}), encoding="utf-8")
    code, out = run(project, f"{INSTALLED}/scripts/export_project.py", "--to", "export/web", "--bump", "--dry-run")
    assert code == 0 and "would export 1.0.1.0 " in out and "project.c3proj version 1.0.0.0 -> 1.0.1.0" in out, out
    code, out = run(project, f"{INSTALLED}/scripts/export_project.py", "--version", "1.2", "--dry-run")
    assert code == 2 and "not 3 or 4 numbers" in out, out


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
    (project / "export" / "web").mkdir(parents=True)
    (project / "export" / "web" / "data.json").write_text("{}", encoding="utf-8")
    (project / ".claude" / "worktrees" / "a").mkdir(parents=True)     # an agent's copies, 2.2 GB in a game
    (project / ".claude" / "worktrees" / "a" / "project.c3proj").write_text("{}", encoding="utf-8")
    with zipfile.ZipFile(io.BytesIO(export.pack(project, "2.3.4.5", project / "export"))) as z:
        names = z.namelist()
        text = z.read("project.c3proj").decode("utf-8")
    assert '\t\t"version": "2.3.4.5",' in text and '"autoIncrementVersion": false' in text, text[:400]
    assert '"useWorker": "auto"' in text, text[:400]
    assert not any(n.startswith(("export/", ".tmp/", ".claude/")) for n in names), names
    assert any(n.startswith("layouts/") for n in names), names
    assert export.project_version(project) == "1.0.0.0"     # the project file itself is not touched
    assert '"useWorker": "dom"' in path.read_text(encoding="utf-8")


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
