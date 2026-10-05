#!/usr/bin/env python3
"""Build plugin/, the Claude Code plugin, from the skill and the data it reads.

    python scripts/build_plugin.py            write plugin/
    python scripts/build_plugin.py --check    fail when plugin/ differs from a fresh build

The plugin folder carries what the construct3-agent-plugin skill reads, under
the limits of Claude's plugin directory: 512 files or fewer, and every file
other than an image under 256 KiB. The skill, the schemas, the guides, the
prompts and the empty project are copied to the same paths. The TypeScript
definitions and the examples are written as bundles, which
skills/construct3-agent-plugin/scripts/c3project.py reads with data_texts;
the language packs keep the parts check_project.py reads. Why:
docs/decisions/plugin-folder.md.

The build also sets the version in .claude-plugin/plugin.json. The published
plugin is the one at the commit that HEAD shares with origin/main, or at HEAD
without that ref. During a merge, it is the one at the commit that the merge
commit will share with origin/main. If the built files other than plugin.json
equal the published ones, the build keeps the published version; otherwise it
writes the published version with its patch raised by one. The version in
scripts/plugin/plugin.json is the floor, raised by hand for a minor or major
release. The build reads Git locally and never fetches. Why:
docs/decisions/plugin-tracks-commits.md.

exit codes: 0 built or equal, 1 plugin/ differs or breaks a limit
"""
import argparse
import filecmp
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "plugin"
SOURCES = ROOT / "scripts" / "plugin"          # the manifest, README and icon of the plugin
SKILL = "skills/construct3-agent-plugin"
MANIFEST = ".claude-plugin/plugin.json"

# Copied to the same path inside the plugin
COPIED = (SKILL, "data/c3-schemas", "data/c3-guides", "data/c3-new-project", "prompts",
          "data/c3-ts-defs/autocomplete-data.json")
LEFT_OUT = (f"{SKILL}/evals/",)
# Written as bundles: folder, the files of it to take
BUNDLED = (("data/c3-ts-defs", "*.d.ts"), ("data/c3-examples/en-US", "*.json"), ("data/c3-examples/zh-CN", "*.json"))
# The language pack keys check_project.py reads
LANG_KEYS = (("text", "ui", "bars", "properties", "project"), ("text", "ui", "bars", "timeline", "eases"))

MAX_FILES = 512
MAX_SIZE = 256 * 1024
BUNDLE_SIZE = 240 * 1024     # below MAX_SIZE, so that a bundle stays under it as its files grow a little
IMAGES = (".png",)


def tracked(path: str) -> list[str]:
    """The files under path that Git tracks or would track, in the order git lists them."""
    p = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "--", path],
                       capture_output=True, text=True, encoding="utf-8", check=True)
    return sorted({line for line in p.stdout.splitlines()
                   if (ROOT / line).is_file() and not line.startswith(LEFT_OUT) and "__pycache__" not in line})


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def bundles(folder: str, pattern: str) -> list[tuple[str, str]]:
    """The bundles of a folder, <folder>.bundle-<n>.json, each under BUNDLE_SIZE."""
    files = {}
    for rel in tracked(folder):
        inner = rel[len(folder) + 1:]
        if PurePosixPath(inner).match(pattern) and "sdk" not in inner.split("/"):
            files[inner] = (ROOT / rel).read_text(encoding="utf-8-sig")
    out, part = [], {}

    def dump(d: dict) -> str:
        return json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True) + "\n"

    for inner, text in files.items():
        if part and len(dump({**part, inner: text}).encode("utf-8")) > BUNDLE_SIZE:
            out.append(dump(part))
            part = {}
        part[inner] = text
    if part:
        out.append(dump(part))
    return [(f"{folder}.bundle-{n}.json", text) for n, text in enumerate(out, 1)]


def lang_subset(locale: str) -> str:
    pack = json.loads((ROOT / "data" / "c3-lang" / f"{locale}.json").read_text(encoding="utf-8-sig"))
    out: dict = {}
    for keys in LANG_KEYS:
        src, dst = pack, out
        for k in keys[:-1]:
            src, dst = src[k], dst.setdefault(k, {})
        dst[keys[-1]] = src[keys[-1]]
    return json.dumps(out, ensure_ascii=False, indent="\t", sort_keys=True) + "\n"


def build(out: Path) -> None:
    for part in COPIED:
        for rel in tracked(part):
            (out / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, out / rel)
    for folder, pattern in BUNDLED:
        for rel, text in bundles(folder, pattern):
            write(out / rel, text)
    for locale in ("en-US", "zh-CN"):
        write(out / "data" / "c3-lang" / f"{locale}.json", lang_subset(locale))
    (out / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCES / "plugin.json", out / ".claude-plugin" / "plugin.json")
    shutil.copyfile(SOURCES / "icon.png", out / ".claude-plugin" / "icon.png")
    shutil.copyfile(SOURCES / "README.md", out / "README.md")
    shutil.copyfile(ROOT / "LICENSE", out / "LICENSE")


def blob_id(data: bytes) -> str:
    """The id Git gives a file holding data."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def git(*args: str) -> str | None:
    """What git prints, or None when it fails."""
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8")
    return p.stdout if p.returncode == 0 else None


def published() -> tuple[str | None, dict[str, str]]:
    """The version and the blob ids, by path, of the plugin at the commit that HEAD shares with
    origin/main. Without origin/main or a merge base, as in a shallow CI checkout, the commit is HEAD."""
    # During a merge, the commit the merge commit will share: git takes the merge base of the first
    # commit and a merge of the others
    merging = ["MERGE_HEAD"] if git("rev-parse", "-q", "--verify", "MERGE_HEAD") else []
    base = (git("merge-base", "origin/main", "HEAD", *merging) or "HEAD").strip()
    version = None
    for path in (f"plugin/{MANIFEST}", MANIFEST):      # the second path: the manifest in commits that predate plugin/
        text = git("show", f"{base}:{path}")
        if text and (version := json.loads(text).get("version")):
            break
    blobs = {}
    for entry in (git("ls-tree", "-r", "-z", f"{base}:plugin") or "").split("\0"):
        if entry:
            meta, path = entry.split("\t", 1)
            kind, blob = meta.split()[1:]
            if kind == "blob" and path != MANIFEST:
                blobs[path] = blob
    return version, blobs


def release_version(published_version: str | None, published_blobs: dict[str, str],
                    fresh_blobs: dict[str, str], floor: str) -> str:
    """The version of a build. It is the published version while the build's files equal the published
    files, and that version with its patch raised by one once they differ. It is never below the floor."""
    def numbers(version: str) -> tuple[int, ...]:
        return tuple(int(n) for n in version.split("."))

    if published_version is None:
        return floor
    version = numbers(published_version)
    if fresh_blobs != published_blobs:
        version = (*version[:-1], version[-1] + 1)
    return ".".join(map(str, max(version, numbers(floor))))


def set_version(out: Path) -> str:
    """Write the release version into the manifest of the plugin built in out, and return it."""
    manifest = json.loads((out / MANIFEST).read_text(encoding="utf-8"))
    fresh = {rel: blob_id(p.read_bytes()) for rel, p in files(out).items() if rel != MANIFEST}
    manifest["version"] = release_version(*published(), fresh, manifest["version"])
    write(out / MANIFEST, json.dumps(manifest, ensure_ascii=False, indent="\t") + "\n")
    return manifest["version"]


def files(folder: Path) -> dict[str, Path]:
    """The files of a plugin folder, without the bytecode Python writes beside a script it ran."""
    return {p.relative_to(folder).as_posix(): p for p in sorted(folder.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


def limits(folder: Path) -> list[str]:
    """What breaks the directory's limits on the plugin folder."""
    found = files(folder)
    problems = [f"{len(found)} files, more than {MAX_FILES}"] if len(found) > MAX_FILES else []
    for rel, p in found.items():
        if rel.endswith(IMAGES):
            continue
        if p.stat().st_size > MAX_SIZE:
            problems.append(f"{rel}: {p.stat().st_size // 1024} KiB, more than {MAX_SIZE // 1024}")
        try:
            p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            problems.append(f"{rel}: not UTF-8 text")
    return problems


def differences(built: Path, committed: Path) -> list[str]:
    a, b = files(built), files(committed) if committed.is_dir() else {}
    out = [f"missing from plugin/: {rel}" for rel in a if rel not in b]
    out += [f"not in a fresh build: {rel}" for rel in b if rel not in a]
    out += [f"differs: {rel}" for rel in a if rel in b and not filecmp.cmp(a[rel], b[rel], shallow=False)]
    return out


def rebuild() -> list[str]:
    """plugin/ replaced by a fresh build, and what in it breaks the limits. A folder
    there that holds no plugin is left alone."""
    if OUT.exists() and not (OUT / ".claude-plugin" / "plugin.json").exists():
        sys.exit(f"{OUT} holds no .claude-plugin/plugin.json; not overwritten")
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / "plugin"
        build(fresh)
        set_version(fresh)
        if OUT.exists():
            shutil.rmtree(OUT)
        shutil.copytree(fresh, OUT)
    return limits(OUT)


def version_in(folder: Path) -> str | None:
    manifest = folder / MANIFEST
    return json.loads(manifest.read_text(encoding="utf-8")).get("version") if manifest.is_file() else None


def check() -> list[str]:
    """How plugin/ differs from a fresh build, and what in the build breaks the limits."""
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / "plugin"
        build(fresh)
        version = set_version(fresh)
        problems = limits(fresh) + differences(fresh, OUT)
    if version_in(OUT) != version:
        problems.append(f"version: {version_in(OUT)} in plugin/, {version} in a fresh build")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                 description="Build plugin/, the Claude Code plugin, from the skill and the data it reads.",
                                 epilog="exit codes: 0 built or equal, 1 plugin/ differs or breaks a limit")
    ap.add_argument("--check", action="store_true", help="compare plugin/ with a fresh build, write nothing")
    args = ap.parse_args()
    problems = check() if args.check else rebuild()
    for line in problems:
        print(line)
    if args.check:
        print(f"plugin/: {'differs or breaks a limit; run python scripts/build_plugin.py' if problems else 'equal to a fresh build'}")
    else:
        print(f"plugin/: built, version {version_in(OUT)}, {len(files(OUT))} files"
              f"{'; breaks the limits above' if problems else ''}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
