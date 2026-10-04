"""The construct3-agent-plugin skill, used the way an agent uses it: what its tests share.

The skill is installed in a project folder by its own install.py and its
scripts run as subprocesses from there. The stand-in game of
assets/build_project.py is generated once (conftest.py); a test breaks a
private copy in one way and reads what a script says about it.
"""
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "construct3-agent-plugin"
INSTALLED = ".agents/skills/construct3-agent-plugin"
SHEET = "eventSheets/Game.json"


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
        assert "VIEW_W, VIEW_H = 720, 1280" in source
        source = source.replace("VIEW_W, VIEW_H = 720, 1280", view)
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
