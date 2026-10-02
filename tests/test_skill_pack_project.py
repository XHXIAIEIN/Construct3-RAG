"""pack_project.py: a project saved as a .c3p, a .zip or a project folder, in the layout the editor opens."""
import io
import zipfile

from tests.skill_helpers import SHEET, tool


def names(path) -> list[str]:
    return zipfile.ZipFile(io.BytesIO(path.read_bytes())).namelist()


def test_a_folder_project_is_packed_with_project_c3proj_at_the_root(project, tmp_path):
    """The editor refuses a zip that holds the folder ("Check it is a valid Construct 3 single-file
    (.c3p) project", r504, 2026-10-02); what it does not save stays out and is named."""
    code, out = tool(project, "pack_project")
    c3p = project / ".build" / f"{project.name}.c3p"
    assert code == 0 and f"into {c3p}, project.c3proj at the root" in out, out
    packed = names(c3p)
    assert "project.c3proj" in packed and SHEET in packed
    assert (project / ".build" / ".gitignore").read_text(encoding="utf-8") == "*\n"
    assert not any(n.startswith((".agents/", ".tmp/", ".build/", "tools/", "art/")) or n in ("AGENTS.md", "CLAUDE.md")
                   for n in packed)
    assert "left out: .agents/, AGENTS.md, art/, CLAUDE.md, tools/ (--keep NAME packs one)" in out, out
    assert "next: python " in out and "open_in_editor.py" in out

    code, out = tool(project, "pack_project", "--out", str(tmp_path / "repro.zip"), "--keep", "tools")
    assert code == 0 and "tools/build_project.py" in names(tmp_path / "repro.zip"), out
    assert "note:" not in out, out


def test_build_and_tmp_stay_out_of_the_pack(project):
    """A pack made before, an export and the scratch are neither packed nor named as left out, and
    an --out in the project outside .build/ is written with a note that Git commits it."""
    for rel in (".build/old.c3p", ".build/web/index.html", ".tmp/shots/a.png"):
        (project / rel).parent.mkdir(parents=True, exist_ok=True)
        (project / rel).write_text("x", encoding="utf-8")
    code, out = tool(project, "pack_project")
    packed = names(project / ".build" / f"{project.name}.c3p")
    assert code == 0 and not any(n.startswith((".build/", ".tmp/")) for n in packed), packed
    left = next(line for line in out.splitlines() if line.startswith("left out:"))
    assert ".build" not in left and ".tmp" not in left, out

    code, out = tool(project, "pack_project", "--out", str(project / "game.c3p"))
    assert code == 0 and (project / "game.c3p").is_file(), out
    assert "note:" in out and "Git commits it" in out and ".build" in out, out


def test_every_folder_the_project_format_guide_names_is_packed(project):
    """Scirra's guide "Construct's project format" names videos, 3dmodels, palettes and
    tilemapBrushes beside the folders the official examples hold, and the editor writes
    llm-context.md into every project."""
    kept = ["videos/clip.webm", "3dmodels/Model.json", "palettes/Palette 1.json", "tilemapBrushes/Brush.json",
            "llm-context.md"]
    for rel in kept:
        (project / rel).parent.mkdir(parents=True, exist_ok=True)
        (project / rel).write_text("{}", encoding="utf-8")
    code, out = tool(project, "pack_project")
    packed = names(project / ".build" / f"{project.name}.c3p")
    assert code == 0 and all(rel in packed for rel in kept), out


def test_an_archive_with_the_folder_inside_is_repacked_and_unpacked(project, tmp_path):
    nested = tmp_path / "nested.zip"
    with zipfile.ZipFile(nested, "w") as z:
        for f in sorted(project.rglob("*")):
            if f.is_file() and ".agents" not in f.parts:
                z.write(f, f"game/{f.relative_to(project).as_posix()}")
    code, out = tool(project, "pack_project", str(nested), "--out", str(tmp_path / "fixed.c3p"))
    assert code == 0 and "project.c3proj" in names(tmp_path / "fixed.c3p"), out
    assert not any(n.startswith("game/") for n in names(tmp_path / "fixed.c3p"))

    folder = tmp_path / "unpacked"
    code, out = tool(project, "pack_project", str(tmp_path / "fixed.c3p"), "--out", str(folder))
    assert code == 0 and (folder / "project.c3proj").is_file() and (folder / SHEET).is_file(), out
    code, out = tool(project, "pack_project", str(tmp_path / "fixed.c3p"), "--out", str(folder))
    assert code == 2 and "is not an empty folder" in out, out

    (tmp_path / "other.zip").write_bytes(b"not a zip")
    code, out = tool(project, "pack_project", str(tmp_path / "other.zip"))
    assert code == 2 and "is not a zip" in out, out
    with zipfile.ZipFile(tmp_path / "empty.zip", "w") as z:
        z.writestr("readme.txt", "")
    code, out = tool(project, "pack_project", str(tmp_path / "empty.zip"))
    assert code == 2 and "holds no project.c3proj" in out and "Traceback" not in out, out


def test_bundled_addons_are_packed(project, tmp_path):
    """A project saved with Bundle addons keeps addons/<type>/<id>.c3addon, which the editor needs to
    open it without the addon installed (r504 save, 2026-10-03)."""
    addon = project / "addons" / "effect" / "Custom_Glow.c3addon"
    addon.parent.mkdir(parents=True)
    addon.write_bytes(b"PK\x05\x06" + bytes(18))
    code, out = tool(project, "pack_project", "--out", str(tmp_path / "bundled.c3p"))
    assert code == 0 and "addons/effect/Custom_Glow.c3addon" in names(tmp_path / "bundled.c3p"), out
    assert "addons/" not in out.split("left out:")[-1], out
