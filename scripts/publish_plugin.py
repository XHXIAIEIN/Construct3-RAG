#!/usr/bin/env python3
"""Publish plugin/ to Construct3-Agent-Skills, the plugin's own repository, as its plugin/ folder.

    python scripts/publish_plugin.py --clone <folder>              sync the clone, commit, push
    python scripts/publish_plugin.py --clone <folder> --no-push    sync and commit only
    python scripts/publish_plugin.py --clone <folder> --dry-run    print what would change, write nothing

The clone's plugin/ is made equal to plugin/ here, and its
.claude-plugin/marketplace.json names that folder as the plugin, so that
`claude plugin marketplace add XHXIAIEIN/Construct3-Agent-Skills` installs
it. Files the clone's plugin/ holds that plugin/ here does not are removed.
The clone's other files are that repository's own and stay as they are.
The commit names the commit of this repository that the build came from.
Why: docs/decisions/plugin-repository.md.

The script refuses when plugin/ differs from a fresh build, because the
published folder must be what the tests checked, and when the folder is
not a clone of the plugin repository.

exit codes: 0 published or nothing to publish, 1 refused
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import build_plugin  # noqa: E402

REPOSITORY = "XHXIAIEIN/Construct3-Agent-Skills"
PLUGIN_DIR = "plugin"
MARKETPLACE = ".claude-plugin/marketplace.json"


def marketplace_text(manifest: dict) -> str:
    """The marketplace manifest of the plugin repository: one plugin, in plugin/."""
    market = {
        "name": "construct3-agent-skills",
        "owner": {"name": manifest["author"]["name"]},
        "metadata": {"description": "The Construct 3 plugin for Claude Code, built from Construct3-RAG."},
        "plugins": [{"name": manifest["name"], "source": f"./{PLUGIN_DIR}", "description": manifest["description"],
                     "category": "game-development"}],
    }
    return json.dumps(market, ensure_ascii=False, indent="\t") + "\n"


def wanted() -> dict[str, bytes]:
    """The files the script owns in the plugin repository, by relative path, from plugin/ here."""
    files = {f"{PLUGIN_DIR}/{rel}": p.read_bytes() for rel, p in build_plugin.files(build_plugin.OUT).items()}
    manifest = json.loads(files[f"{PLUGIN_DIR}/{build_plugin.MANIFEST}"].decode("utf-8"))
    files[MARKETPLACE] = marketplace_text(manifest).encode("utf-8")
    return files


def held(clone: Path) -> dict[str, Path]:
    """The files of the clone that the script owns: plugin/ and the marketplace manifest."""
    return {rel: p for rel, p in build_plugin.files(clone).items()
            if rel.startswith(f"{PLUGIN_DIR}/") or rel == MARKETPLACE}


def git(clone: Path, *args: str) -> str:
    p = subprocess.run(["git", "-C", str(clone), *args], capture_output=True, text=True, encoding="utf-8")
    if p.returncode:
        sys.exit(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def source_commit() -> str:
    """The commit of this repository that plugin/ comes from, as the publish commit names it. A "#" is
    dropped, because GitHub turns "#N" in a commit message into a reference on that issue's timeline."""
    p = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%h %s"],
                       capture_output=True, text=True, encoding="utf-8")
    return p.stdout.strip().replace("#", "") if p.returncode == 0 else "an uncommitted build"


def changes(clone: Path, files: dict[str, bytes]) -> list[str]:
    """What sync would write or remove in the clone, as lines."""
    have = held(clone)
    out = [f"write {rel}" for rel, data in files.items() if rel not in have or have[rel].read_bytes() != data]
    out += [f"remove {rel}" for rel in have if rel not in files]
    return out


def sync(clone: Path, files: dict[str, bytes]) -> None:
    """The clone's plugin/ and marketplace manifest equal to files; everything else in the clone stays."""
    for rel, p in held(clone).items():
        if rel not in files:
            p.unlink()
    plugin = clone / PLUGIN_DIR
    if plugin.is_dir():
        for folder in sorted((p for p in plugin.rglob("*") if p.is_dir()), reverse=True):
            if not any(folder.iterdir()):
                folder.rmdir()
    for rel, data in files.items():
        path = clone / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file() or path.read_bytes() != data:
            path.write_bytes(data)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--clone", required=True, type=Path, help=f"a clone of {REPOSITORY}")
    ap.add_argument("--no-push", action="store_true", help="commit, but do not push")
    ap.add_argument("--dry-run", action="store_true", help="print the changes, write nothing")
    args = ap.parse_args()
    clone = args.clone.resolve()

    if problems := build_plugin.check():
        print("\n".join(problems))
        print("plugin/ differs from a fresh build; run python scripts/build_plugin.py and commit it first")
        return 1
    if not (clone / ".git").exists():
        print(f"{clone} is not a Git clone")
        return 1
    remote = git(clone, "remote", "get-url", "origin").strip()
    if REPOSITORY.lower() not in remote.lower():
        print(f"{clone}: origin is {remote}, not {REPOSITORY}")
        return 1

    files = wanted()
    lines = changes(clone, files)
    if not lines:
        print(f"{clone}/{PLUGIN_DIR}: equal to plugin/, nothing to publish")
        return 0
    print("\n".join(lines))
    if args.dry_run:
        print(f"{len(lines)} changes; nothing written")
        return 0
    sync(clone, files)
    git(clone, "add", "-A", "--", PLUGIN_DIR, MARKETPLACE)
    git(clone, "commit", "-q", "-m", f"Construct3-RAG {source_commit()}")
    version = json.loads(files[f"{PLUGIN_DIR}/{build_plugin.MANIFEST}"].decode("utf-8"))["version"]
    if args.no_push:
        print(f"committed version {version} in {clone}, not pushed")
        return 0
    git(clone, "push", "-q", "-u", "origin", "HEAD")     # -u: a fresh clone of an empty repository has no upstream
    print(f"published version {version} to {REPOSITORY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
