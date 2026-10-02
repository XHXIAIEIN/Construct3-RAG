"""Save a project as a .c3p, a .zip or a project folder, in the layout the editor opens.

    python scripts/pack_project.py [SOURCE] [--project FOLDER] [--out FILE.c3p | FILE.zip | FOLDER]
                                   [--keep NAME ...] [--open]

A .c3p is a zip of the project folder's contents with project.c3proj at the
root of the archive. A zip that holds the folder itself, the files one level
down, does not open: the editor says "Check it is a valid Construct 3
single-file (.c3p) project". This script writes the root layout every time, so
a project handed over as a file, an attachment to a bug report among them, is
packed with it and not by hand.

The source is the folder project, or a .c3p or .zip; the output, chosen by
--out, a .c3p, a .zip or a new project folder. A .zip and a .c3p differ only
in their name: a site that takes .zip uploads gets the .zip. A zip that holds
the project one folder down comes out with project.c3proj at the root.

What is written is what the editor saves: project.c3proj, llm-context.md, the
root's *.uistate.json and the editor's folders (objectTypes, layouts,
eventSheets, images, videos, 3dmodels, palettes, tilemapBrushes, addons for
bundled addons, ...). Anything else at the top, the agent's skill copy,
AGENTS.md, a tools/ generator, an export, is left out and named in the
output; --keep NAME puts one back.
"""
from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

import c3project as c3

SCRATCH = ".tmp"
# Where a pack goes by default: the products of the skill's scripts, kept apart from the scratch of .tmp/.
BUILD = ".build"
# The top-level folders the editor saves a project in, as Scirra's guide "Construct's project format"
# lists them, and the one file beside project.c3proj it writes into every project. addons/ is where a
# project saved with Bundle addons keeps addons/<type>/<id>.c3addon (r504 save, 2026-10-03).
EDITOR_FOLDERS = ("objectTypes", "families", "layouts", "eventSheets", "timelines", "flowcharts", "3dmodels",
                  "images", "icons", "files", "sounds", "music", "videos", "fonts", "scripts", "palettes",
                  "tilemapBrushes", "addons")
EDITOR_ROOT_FILES = ("project.c3proj", "llm-context.md")
ARCHIVES = (".c3p", ".zip")
# Windows reads no file past MAX_PATH unless asked to; a browser handed such a file over the
# DevTools protocol gets it empty, with no error.
MAX_PATH = 260

EPILOG = """examples:
  python scripts/pack_project.py                                 the project here as .build/<folder>.c3p
  python scripts/pack_project.py --out repro.zip --open          a bug report's attachment, opened once in the editor
  python scripts/pack_project.py downloaded.c3p --out game       a .c3p as a project folder
  python scripts/pack_project.py nested.zip --out fixed.zip      a zip with the folder inside, repacked at the root

output:
  packed <n> files into <file>, project.c3proj at the root
  left out: AGENTS.md, .agents/, tools/
  next: python scripts/open_in_editor.py <file>

exit codes: 0 written (and opened, with --open); 1 written, but the editor did not open it;
2 no project, no project.c3proj in the archive, or --out names a folder that is not empty
"""


class Refused(Exception):
    pass


def from_folder(project: Path) -> dict[str, Path]:
    """Every file of a folder project by its path in the archive, .git/, .tmp/ and .build/ aside."""
    return {f.relative_to(project).as_posix(): f for f in sorted(project.rglob("*"))
            if f.is_file() and f.relative_to(project).parts[0] not in (".git", SCRATCH, BUILD)}


def editor_files(files: dict, keep: tuple[str, ...]) -> tuple[dict, list[str]]:
    """The files the editor reads, and the top-level names left out: project.c3proj, llm-context.md,
    the root's *.uistate.json, the folders the editor saves, and what --keep names."""
    folders = set(EDITOR_FOLDERS) | set(keep)
    kept: dict = {}
    left: list[str] = []
    for name, data in files.items():
        top, _, rest = name.partition("/")
        if (rest and top in folders) or (not rest and (top in EDITOR_ROOT_FILES or top.endswith(".uistate.json")
                                                       or top in keep)):
            kept[name] = data
        elif (shown := top + ("/" if rest else "")) not in left:
            left.append(shown)
    return kept, sorted(left, key=str.lower)


def from_archive(archive: Path) -> dict[str, bytes]:
    """The archive's files with project.c3proj at the root: a single folder around them is taken off."""
    try:
        with zipfile.ZipFile(archive) as z:
            entries = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}
    except zipfile.BadZipFile:
        raise Refused(f"{archive} is not a zip; a .c3p is one") from None
    if "project.c3proj" not in entries:
        tops = {n.split("/", 1)[0] for n in entries if n.endswith("/project.c3proj") and n.count("/") == 1}
        if len(tops) != 1:
            raise Refused(f"{archive} holds no project.c3proj at its root or one folder down")
        prefix = tops.pop() + "/"
        entries = {n[len(prefix):]: b for n, b in entries.items() if n.startswith(prefix)}
    for name in entries:
        parts = PurePosixPath(name).parts
        if PurePosixPath(name).is_absolute() or ".." in parts:
            raise Refused(f"{archive} names a path outside itself: {name}")
    return entries


def write_archive(out: Path, files: dict[str, bytes | Path]) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            if isinstance(data, Path):
                z.write(data, name)
            else:
                z.writestr(name, data)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(buf.getvalue())


def write_folder(out: Path, files: dict[str, bytes | Path]) -> None:
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise Refused(f"{out} is not an empty folder; name a new one with --out")
    for name, data in files.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data.read_bytes() if isinstance(data, Path) else data)


def default_out(source: Path, is_archive: bool) -> Path:
    if is_archive:
        return source.with_suffix("")
    build = source / BUILD
    build.mkdir(exist_ok=True)
    if not (build / ".gitignore").exists():
        (build / ".gitignore").write_text("*\n", encoding="utf-8")
    return build / f"{source.name}.c3p"


def committed_note(out: Path, project: Path) -> str | None:
    """A note when --out lands in the project folder outside .build/ and .tmp/, where Git commits it."""
    if not out.is_relative_to(project):
        return None
    top = out.relative_to(project).parts[:1]
    if top and top[0] in (BUILD, SCRATCH, ".git"):
        return None
    return (f"note: {out} is inside the project, where Git commits it; "
            f"a product goes in {project / BUILD}, which ignores its contents")


def main() -> int:
    c3.utf8_output()
    ap = argparse.ArgumentParser(description=__doc__, epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", metavar="SOURCE",
                    help="a .c3p or .zip to unpack or repack (default: the folder project, --project)")
    ap.add_argument("--project", metavar="FOLDER",
                    help="the folder that holds project.c3proj (default: found from the current directory upward)")
    ap.add_argument("--out", metavar="FILE|FOLDER", type=Path,
                    help="a .c3p or .zip to write, or a new folder for a project folder (default: "
                         ".build/<folder>.c3p of the project, or a folder beside the archive)")
    ap.add_argument("--keep", metavar="NAME", action="append", default=[],
                    help="a top-level file or folder of the project to pack although the editor does not save it")
    ap.add_argument("--open", action="store_true",
                    help="open the written .c3p or .zip in the editor with open_in_editor.py")
    ap.add_argument("--rag", help=argparse.SUPPRESS)
    args = ap.parse_args()

    source = Path(args.source).resolve() if args.source else c3.find_project(args.project)
    if source is None or not source.exists():
        print(f"no project.c3proj found from {args.project or args.source or Path.cwd()}; run this in the project "
              f"folder or pass --project <folder>", file=sys.stderr)
        return 2
    is_archive = source.is_file()
    if not is_archive and not (source / "project.c3proj").is_file():
        print(f"{source} holds no project.c3proj", file=sys.stderr)
        return 2
    out = (args.out if args.out and args.out.is_absolute() else Path.cwd() / args.out).resolve() if args.out \
        else default_out(source, is_archive)
    try:
        files, left = editor_files(from_archive(source) if is_archive else from_folder(source), tuple(args.keep))
        if out.suffix.lower() in ARCHIVES:
            write_archive(out, files)
            print(f"packed {len(files)} files into {out}, project.c3proj at the root")
        else:
            write_folder(out, files)
            print(f"wrote {len(files)} files into the project folder {out}")
    except Refused as e:
        print(e, file=sys.stderr)
        return 2
    if not is_archive and (note := committed_note(out, source)):
        print(note)
    if left:
        print(f"left out: {', '.join(left)} (--keep NAME packs one)")
    if os.name == "nt" and len(str(out)) >= MAX_PATH and out.suffix.lower() in ARCHIVES:
        print(f"warning: the path is {len(str(out))} characters, past Windows' {MAX_PATH}: a browser handed this "
              f"file arrives with 0 bytes and no error; pass an --out in a shorter folder before uploading it")
    if out.suffix.lower() not in ARCHIVES:
        return 0
    opener = Path(__file__).with_name("open_in_editor.py")
    if not args.open:
        print(f"next: python {opener.relative_to(Path.cwd()) if opener.is_relative_to(Path.cwd()) else opener} {out}")
        return 0
    sys.stdout.flush()
    done = subprocess.run([sys.executable, str(opener), str(out)])
    return 0 if done.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
