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
    c3p = project / ".tmp" / f"{project.name}.c3p"
    assert code == 0 and f"into {c3p}, project.c3proj at the root" in out, out
    packed = names(c3p)
    assert "project.c3proj" in packed and SHEET in packed
    assert not any(n.startswith((".agents/", ".tmp/", "tools/")) or n in ("AGENTS.md", "CLAUDE.md") for n in packed)
    assert "left out: .agents/, AGENTS.md, CLAUDE.md, tools/ (--keep NAME packs one)" in out, out
    assert "next: python " in out and "open_in_editor.py" in out

    code, out = tool(project, "pack_project", "--out", str(tmp_path / "repro.zip"), "--keep", "tools")
    assert code == 0 and "tools/build_project.py" in names(tmp_path / "repro.zip"), out


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
