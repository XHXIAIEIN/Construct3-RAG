"""The construct3-agent-plugin skill, used the way an agent uses it: what its tests share.

The skill is installed in a project folder by its own install.py and its
scripts run as subprocesses from there. The stand-in game of
assets/build_project.py is generated once (conftest.py); a test breaks a
private copy in one way and reads what a script says about it.
"""
import importlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "construct3-agent-plugin"
INSTALLED = ".agents/skills/construct3-agent-plugin"
SHEET = "eventSheets/Game.json"

sys.path.insert(0, str(SKILL / "scripts"))
from c3project import siblings_folder  # noqa: E402

# The sibling clones are beside the main clone, also when the tests run in one of its
# worktrees: build every sibling path from siblings_folder, never from REPO.parent.
EXAMPLES = siblings_folder(REPO) / "Construct-Example-Projects" / "example-projects"
NO_EXAMPLES = (f"no Construct-Example-Projects clone at {EXAMPLES.parent}; "
               f"python {(REPO / 'scripts' / 'bootstrap.py').as_posix()} clones it")


def script_module(name: str, folder: Path = SKILL / "scripts"):
    """A script of the skill as a module, the scripts beside it importable while it loads and
    nothing left on sys.path. From the skill's own folders it is the module the other scripts import,
    cached like any import; from an installed copy it is loaded by its file, so that what it finds
    from its own location is that copy's."""
    sys.path.insert(0, str(folder))
    try:
        if folder.is_relative_to(SKILL):
            return importlib.import_module(name)
        spec = importlib.util.spec_from_file_location(name, folder / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(folder))


NEEDS_EXAMPLES = pytest.mark.skipif(not EXAMPLES.is_dir(), reason=NO_EXAMPLES)
NEEDS_GIT = pytest.mark.skipif(not shutil.which("git"), reason="git is not installed")


def git(cwd: Path, *args: str, check: bool = True) -> None:
    """git in a repository made under tmp_path, as a committer the machine need not have configured."""
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=check,
                   capture_output=True, timeout=60)


def run(root: Path, script: str | Path, *args: str) -> tuple[int, str]:
    """A script run from the project folder. No CONSTRUCT3_RAG and an empty home:
    the clone and the skill are found through the project alone, and the clone is not fetched."""
    env = {k: v for k, v in os.environ.items() if k != "CONSTRUCT3_RAG"}
    env.update(PYTHONIOENCODING="utf-8", CONSTRUCT3_RAG_OFFLINE="1", HOME=str(root / ".home"), USERPROFILE=str(root / ".home"))
    p = subprocess.run([sys.executable, str(script), *args], cwd=root, env=env,
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


def tool(root: Path, name: str, *args: str) -> tuple[int, str]:
    return run(root, f"{INSTALLED}/scripts/{name}.py", "--rag", str(REPO), *args)


def check(root: Path, *args: str) -> tuple[int, str]:
    return tool(root, "check_project", *args)


def install(root: Path, *args: str) -> tuple[int, str]:
    return run(root, SKILL / "scripts" / "install.py", *args)


def new_project(root: Path) -> Path:
    """A project folder the editor never saved: the generator fills the keys the
    editor reads on open, so what it leaves is what the editor would have."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "project.c3proj").write_text(json.dumps({"uniqueId": "test", "properties": {}}), encoding="utf-8")
    return root


def edit(root: Path, rel: str, change) -> None:
    path = root / rel
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data, indent="\t", ensure_ascii=False), encoding="utf-8")


def folder_project(root: Path, sheets: dict[str, list], types: dict[str, dict], layouts: dict[str, dict],
                   **project) -> Path:
    """The smallest folder project a script reads: eventSheets/<name>.json from `events`, objectTypes/<name>.json
    and layouts/<name>.json from the rest of their files, each named first, and project.c3proj listing them
    with the keys of `project`."""
    files = {"eventSheets": {name: {"events": events} for name, events in sheets.items()},
             "objectTypes": types, "layouts": layouts}
    for folder, named in files.items():
        (root / folder).mkdir(parents=True, exist_ok=True)
        for name, data in named.items():
            (root / folder / f"{name}.json").write_text(json.dumps({"name": name, **data}), encoding="utf-8")
    listing = {folder: {"items": list(named), "subfolders": []} for folder, named in files.items()}
    (root / "project.c3proj").write_text(json.dumps({"name": root.name, **project, **listing}), encoding="utf-8")
    return root


def add_addon(project: Path, kind: str, addon_id: str, name: str) -> None:
    """The stand-in game's project.c3proj lists an addon it did not use before."""
    edit(project, "project.c3proj", lambda p: p["usedAddons"].append(
        {"type": kind, "id": addon_id, "name": name, "author": "Scirra", "bundled": False}))


def add_keyboard(root: Path, key) -> None:
    """A Keyboard object in the stand-in game, and an event on `key` pressed."""
    (root / "objectTypes" / "Keyboard.json").write_text(json.dumps({
        "name": "Keyboard", "plugin-id": "Keyboard", "sid": 3,
        "singleglobal-inst": {"type": "Keyboard", "properties": {}, "uid": 900, "sid": 4, "tags": ""}}), encoding="utf-8")

    def project_file(p):
        p["objectTypes"]["items"].append("Keyboard")
        p["usedAddons"].append({"type": "plugin", "id": "Keyboard", "name": "Keyboard", "author": "Scirra", "bundled": False})
    edit(root, "project.c3proj", project_file)
    edit(root, SHEET, lambda s: s["events"].append(block([cond("on-key-pressed", "Keyboard", {"key": key})])))


def pathfinding_coin(project: Path, obstacles: str = "solids") -> None:
    """Coin gets Pathfinding, taking its obstacles from Solids, and the Backdrop, which no event changes, Solid."""
    edit(project, "objectTypes/Coin.json", lambda t: t["behaviorTypes"].append(
        {"behaviorId": "Pathfinding", "name": "Pathfinding", "sid": 11}))
    edit(project, "layouts/Objects.json", lambda d: d["layers"][0]["instances"][0]["behaviors"].update(
        Pathfinding={"properties": {"obstacles": obstacles}}))
    edit(project, "objectTypes/Backdrop.json", lambda t: t["behaviorTypes"].append(
        {"behaviorId": "solid", "name": "Solid", "sid": 12}))
    edit(project, "layouts/Game.json", lambda d: d["layers"][0]["instances"][0].setdefault("behaviors", {}).update(
        Solid={"properties": {}}))
    add_addon(project, "behavior", "Pathfinding", "Pathfinding")
    add_addon(project, "behavior", "solid", "Solid")


def cond(ace_id: str, obj: str = "System", params: dict | None = None, **extra) -> dict:
    return {"id": ace_id, "objectClass": obj, "sid": 1, **({"parameters": params} if params else {}), **extra}


def block(conditions: list, actions: list | None = None, children: list | None = None) -> dict:
    return {"eventType": "block", "conditions": conditions, "actions": actions or [], "sid": 2,
            **({"children": children} if children else {})}


def every_event(rows: list) -> Iterator[dict]:
    """Every event of `rows` and of their sub-events, each before its sub-events, as the sheet reads."""
    for ev in rows:
        yield ev
        yield from every_event(ev.get("children", []))


def events(sheet: dict) -> dict:
    """The stand-in sheet by role, so a test reads as what it breaks."""
    rows = sheet["events"]
    groups = {e["title"]: e for e in rows if e["eventType"] == "group"}

    def first_block(group):    # the comment above it is the group's first child
        return next(e for e in group["children"] if e["eventType"] == "block")
    return {
        "setup": first_block(groups["Setup"]),
        "loop": first_block(groups["Setup"])["children"][0],
        "input_group": groups["Input"],
        "input": first_block(groups["Input"]),
        "restart": groups["Restart"],
        "restart_block": first_block(groups["Restart"]),
        "collect": next(e for e in rows if e["eventType"] == "custom-ace-block"),
        "add_score": next(e for e in rows if e["eventType"] == "function-block"),
    }


def collect_tween(sheet: dict) -> dict:
    """The tween that shrinks a collected coin away, the last action of Collect."""
    return next(a for a in events(sheet)["collect"]["actions"]
                if isinstance(a.get("parameters"), dict) and a["parameters"].get("tags") == '"collect"')


def warnings(out: str) -> list[str]:
    """The checker's warning lines."""
    return [line for line in out.splitlines() if line.startswith("warning:")]


def findings(root: Path, change, rel: str = SHEET) -> str:
    edit(root, rel, change)
    code, out = check(root)
    assert "Traceback" not in out, out
    return out


def plan(root: Path, *operations: dict, flags: tuple[str, ...] = ()) -> tuple[int, str]:
    (root / "plan.json").write_text(json.dumps(list(operations)), encoding="utf-8")
    return tool(root, "edit_sheet", "Game", "plan.json", *flags)


def template_module(**replace: str):
    """assets/build_project.py as a module, its source changed by `replace` first
    (VIEW="VIEW_W, VIEW_H = 320, 180" for another viewport)."""
    import types
    source = (SKILL / "assets" / "build_project.py").read_text(encoding="utf-8")
    view = replace.get("VIEW")
    if view:
        assert "VIEW_W, VIEW_H = 1920, 1080" in source
        source = source.replace("VIEW_W, VIEW_H = 1920, 1080", view)
    t = types.ModuleType("build_project")
    t.__file__ = str(SKILL / "assets" / "build_project.py")
    exec(compile(source, t.__file__, "exec"), t.__dict__)
    return t


def png_pixels(path: Path) -> list[list[tuple]]:
    """The RGBA rows of a PNG the template wrote: 8-bit RGBA, one IDAT, filter 0 on every row."""
    import struct
    import zlib
    data = path.read_bytes()
    w, h = struct.unpack(">II", data[16:24])
    idat = data.index(b"IDAT")
    raw = zlib.decompress(data[idat + 4:idat + 4 + struct.unpack(">I", data[idat - 4:idat])[0]])
    rows = [raw[y * (4 * w + 1) + 1:(y + 1) * (4 * w + 1)] for y in range(h)]
    return [[tuple(r[4 * x:4 * x + 4]) for x in range(w)] for r in rows]
