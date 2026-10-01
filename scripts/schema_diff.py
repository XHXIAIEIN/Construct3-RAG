#!/usr/bin/env python3
"""Report what changed in data/c3-schemas between two snapshots, and which
tracked files name an ACE or addon that was removed, deprecated or changed.

Each side is a folder holding `_index.json` or a git revision; the base
defaults to HEAD and the target to the working tree's data/c3-schemas, which
is the state right after `scripts/init.py`. Structure is read from the
primary locale, since the structural fields are the same in every locale.

Usage:
    python scripts/schema_diff.py
    python scripts/schema_diff.py --base <revision or folder> --target <revision or folder>
    python scripts/schema_diff.py --format json
    python scripts/schema_diff.py --output report.md --github-output

Exit codes: 0 report written, 2 a snapshot could not be read.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.lookup.schema_layout import PRIMARY_SCHEMA_LOCALE, SCHEMA_INDEX_FILE

SCHEMAS = "data/c3-schemas"
ACE_KINDS = ("conditions", "actions", "expressions")
ADDON_KINDS = ("plugins", "behaviors", "effects")
# Fields whose change alters how an event using the ACE is written or behaves.
ACE_FLAGS = (
    "scriptName",
    "isTrigger",
    "isLooping",
    "isInvertible",
    "isCompatibleWithTriggers",
    "isAsync",
    "returnType",
)
# Tracked text that may name an ACE or addon id. Tests are left out, since the
# suite fails on its own, and so is the generated source of _common.
MENTION_ROOTS = ("prompts", "skills", "src", "scripts", "docs", "AGENTS.md")
MENTION_SUFFIXES = {".md", ".py", ".json", ".jsonl", ".txt", ".yml", ".yaml"}
MENTION_EXCLUDED = {"src/ingest/common_aces.json"}
COMMON_NAME = "Every world object"  # _common.json carries a placeholder name
DEFAULT_LIMIT = 60000  # a pull request body holds 65536 characters


class SnapshotError(RuntimeError):
    """A side of the comparison is not a readable schema snapshot."""


class Source:
    """Reads JSON files of one snapshot by path relative to its schema root."""

    label: str

    def read(self, rel: str) -> Any | None:
        raise NotImplementedError


class FolderSource(Source):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.label = str(root)

    def read(self, rel: str) -> Any | None:
        path = self.root / rel
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


class GitSource(Source):
    def __init__(self, revision: str, repo: Path) -> None:
        self.label = revision
        listing = _git(repo, "ls-tree", "-r", "--name-only", revision, "--", SCHEMAS)
        paths = [line for line in listing.splitlines() if line.endswith(".json")]
        self.files = _git_read_many(repo, revision, paths)

    def read(self, rel: str) -> Any | None:
        text = self.files.get(f"{SCHEMAS}/{rel}")
        return None if text is None else json.loads(text)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0:
        raise SnapshotError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def _git_read_many(repo: Path, revision: str, paths: list[str]) -> dict[str, str]:
    """Read many blobs in one `git cat-file --batch` call."""
    request = "".join(f"{revision}:{p}\n" for p in paths).encode("utf-8")
    result = subprocess.run(
        ["git", "cat-file", "--batch"], cwd=repo, input=request, capture_output=True
    )
    if result.returncode != 0:
        raise SnapshotError(f"git cat-file: {result.stderr.decode('utf-8', 'replace').strip()}")
    out, pos, files = result.stdout, 0, {}
    for path in paths:
        header_end = out.index(b"\n", pos)
        header = out[pos:header_end].split()
        pos = header_end + 1
        if len(header) == 3:
            size = int(header[2])
            files[path] = out[pos : pos + size].decode("utf-8")
            pos += size + 1
    return files


def open_source(spec: str, repo: Path) -> Source:
    """A folder holding `_index.json`, else a git revision of `repo`."""
    folder = Path(spec)
    if (folder / SCHEMA_INDEX_FILE).is_file():
        return FolderSource(folder)
    if folder.is_dir():
        raise SnapshotError(f"{spec}: a folder without {SCHEMA_INDEX_FILE}")
    return GitSource(spec, repo)


@dataclass
class Addon:
    kind: str
    id: str
    name: str
    aces: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    params: dict[str, dict[str, Any]] = field(default_factory=dict)  # effects


@dataclass
class Snapshot:
    version: str
    addons: dict[tuple[str, str], Addon]
    deprecated_addons: set[tuple[str, str]]
    deprecated_aces: set[tuple[str, str, str, str]]


def load_snapshot(source: Source) -> Snapshot:
    index = source.read(SCHEMA_INDEX_FILE)
    if not isinstance(index, dict):
        raise SnapshotError(f"{source.label}: no {SCHEMA_INDEX_FILE}")
    files: list[tuple[str, str, str]] = []
    for kind in ADDON_KINDS:
        for addon_id, entry in (index.get(kind) or {}).items():
            files.append((kind, addon_id, entry["file"]))
    files.append(("plugins", "_common", "plugins/_common.json"))

    addons: dict[tuple[str, str], Addon] = {}
    for kind, addon_id, rel in files:
        data = source.read(f"{PRIMARY_SCHEMA_LOCALE}/{rel}")
        if data is None:
            if addon_id == "_common":
                continue
            raise SnapshotError(f"{source.label}: the index lists {rel}, which is missing")
        name = COMMON_NAME if addon_id == "_common" else data.get("name") or addon_id
        addon = Addon(kind, addon_id, name)
        if kind == "effects":
            addon.params = {p["id"]: p for p in data.get("parameters") or []}
        else:
            for ace_kind in ACE_KINDS:
                for ace in data.get(ace_kind) or []:
                    addon.aces[(ace_kind, ace["id"])] = ace
        addons[(kind, addon_id)] = addon

    deprecated = source.read(f"{PRIMARY_SCHEMA_LOCALE}/_deprecated.json") or {}
    deprecated_addons = {
        (kind, addon_id)
        for kind, ids in (deprecated.get("addons") or {}).items()
        for addon_id in ids
    }
    deprecated_aces = {
        (kind, addon_id, ace_kind, ace_id)
        for kind, by_addon in (deprecated.get("aces") or {}).items()
        for addon_id, by_kind in by_addon.items()
        for ace_kind, ids in by_kind.items()
        for ace_id in ids
    }
    for (kind, addon_id), addon in addons.items():
        for (ace_kind, ace_id), ace in addon.aces.items():
            if ace.get("isDeprecated"):
                deprecated_aces.add((kind, addon_id, ace_kind, ace_id))
    return Snapshot(str(index.get("version", "")), addons, deprecated_addons, deprecated_aces)


@dataclass
class Change:
    """One line of the report: what changed, on which addon and ACE."""

    section: str  # added, removed, deprecated, changed
    kind: str
    addon_id: str
    addon_name: str
    ace_kind: str = ""
    ace_id: str = ""
    ace_name: str = ""
    details: list[str] = field(default_factory=list)
    # Whether an event or a script written against the base may now be wrong.
    breaking: bool = False

    @property
    def watched(self) -> bool:
        return self.section in ("removed", "deprecated") or self.breaking

    @property
    def mention_id(self) -> str:
        return self.ace_id or self.addon_id

    def title(self) -> str:
        if not self.ace_id:
            return f"{self.addon_name} (`{self.addon_id}`, {self.kind[:-1]})"
        return f"{self.addon_name}: {self.ace_name} (`{self.ace_id}`, {self.ace_kind[:-1]})"


def _ace_name(ace: dict[str, Any]) -> str:
    return ace.get("list-name") or ace.get("translated-name") or ace["id"]


def _param_changes(old: dict[str, Any], new: dict[str, Any]) -> tuple[list[str], bool]:
    """What changed in a parameter list, and whether a value written for the old one may break."""
    details: list[str] = []
    for pid in old.keys() - new.keys():
        details.append(f"parameter `{pid}` removed")
    for pid in new.keys() - old.keys():
        details.append(f"parameter `{pid}` added")
    for pid in old.keys() & new.keys():
        before, after = old[pid], new[pid]
        if before.get("type") != after.get("type"):
            details.append(f"parameter `{pid}` type {before.get('type')} → {after.get('type')}")
        old_items, new_items = set(before.get("items") or {}), set(after.get("items") or {})
        if old_items - new_items:
            details.append(f"parameter `{pid}` loses items {', '.join(sorted(old_items - new_items))}")
        if new_items - old_items:
            details.append(f"parameter `{pid}` gains items {', '.join(sorted(new_items - old_items))}")
    if not details and list(old) != list(new):
        details.append("parameters reordered")
    breaking = any("gains items" not in d for d in details)
    return sorted(details), breaking


def _ace_changes(old: dict[str, Any], new: dict[str, Any]) -> tuple[list[str], bool]:
    details, breaking = _param_changes(old.get("params") or {}, new.get("params") or {})
    for flag in ACE_FLAGS:
        if old.get(flag) != new.get(flag):
            details.append(f"{flag} {old.get(flag)} → {new.get(flag)}")
            # A field the base did not record yet is new information, not a change;
            # the files watched for mentions quote ids, never script names.
            breaking = breaking or (flag != "scriptName" and old.get(flag) is not None)
    if _ace_name(old) != _ace_name(new):
        details.append(f"renamed from “{_ace_name(old)}”")
    return details, breaking


def diff_snapshots(base: Snapshot, target: Snapshot) -> list[Change]:
    changes: list[Change] = []
    for key in sorted(target.addons.keys() - base.addons.keys()):
        addon = target.addons[key]
        changes.append(Change("added", addon.kind, addon.id, addon.name))
    for key in sorted(base.addons.keys() - target.addons.keys()):
        addon = base.addons[key]
        section = "deprecated" if key in target.deprecated_addons else "removed"
        changes.append(Change(section, addon.kind, addon.id, addon.name))

    for key in sorted(base.addons.keys() & target.addons.keys()):
        old, new = base.addons[key], target.addons[key]
        kind, addon_id = key
        if kind == "effects":
            details, breaking = _param_changes(old.params, new.params)
            if details:
                changes.append(Change("changed", kind, addon_id, new.name, details=details, breaking=breaking))
            continue
        for ace_key in sorted(new.aces.keys() - old.aces.keys()):
            ace = new.aces[ace_key]
            changes.append(Change("added", kind, addon_id, new.name, *ace_key, _ace_name(ace)))
        for ace_key in sorted(old.aces.keys() - new.aces.keys()):
            ace = old.aces[ace_key]
            if (kind, addon_id, *ace_key) in target.deprecated_aces:
                section, details = "deprecated", ["left out of the schema"]
            else:
                section, details = "removed", []
            changes.append(Change(section, kind, addon_id, new.name, *ace_key, _ace_name(ace), details))
        for ace_key in sorted(old.aces.keys() & new.aces.keys()):
            ace = new.aces[ace_key]
            full = (kind, addon_id, *ace_key)
            if full in target.deprecated_aces and full not in base.deprecated_aces:
                changes.append(Change("deprecated", kind, addon_id, new.name, *ace_key, _ace_name(ace)))
            details, breaking = _ace_changes(old.aces[ace_key], ace)
            if details:
                changes.append(
                    Change("changed", kind, addon_id, new.name, *ace_key, _ace_name(ace), details, breaking)
                )
    return changes


def tracked_text_files(repo: Path) -> list[Path]:
    listing = _git(repo, "ls-files", "--", *MENTION_ROOTS)
    return [
        repo / line
        for line in listing.splitlines()
        if Path(line).suffix in MENTION_SUFFIXES and line not in MENTION_EXCLUDED
    ]


def find_mentions(changes: list[Change], files: list[Path], repo: Path) -> dict[str, list[str]]:
    """`file:line` of each quoted or backticked mention of an id a change may have broken."""
    watched = {c.mention_id for c in changes if c.watched}
    if not watched:
        return {}
    pattern = re.compile(r"""(["'`])(%s)\1""" % "|".join(map(re.escape, sorted(watched))))
    found: dict[str, list[str]] = {}
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(repo).as_posix()
        for number, line in enumerate(lines, 1):
            for mention_id in {m.group(2) for m in pattern.finditer(line)}:
                found.setdefault(mention_id, []).append(f"{rel}:{number}")
    return found


SECTION_TITLES = {
    "removed": "Removed",
    "deprecated": "Deprecated",
    "changed": "Changed",
    "added": "Added",
}


def render_markdown(
    base: Snapshot,
    target: Snapshot,
    changes: list[Change],
    mentions: dict[str, list[str]],
    limit: int,
) -> str:
    head = [f"## Construct 3 {base.version} → {target.version}", ""]
    if not changes:
        return "\n".join(head + ["No structural change in `data/c3-schemas`."]) + "\n"
    counts = {s: sum(c.section == s for c in changes) for s in SECTION_TITLES}
    head += [", ".join(f"{n} {s}" for s, n in counts.items() if n) + ".", ""]

    body: list[str] = []
    if mentions:
        body += [
            "### Mentions to check",
            "",
            "Tracked files that quote an id this release removed, deprecated, or changed in a way "
            "that can break an event or a script written for the old one. "
            "An id shared by several addons may belong to another one.",
            "",
        ]
        by_id: dict[str, list[Change]] = {}
        for change in changes:
            if change.watched:
                by_id.setdefault(change.mention_id, []).append(change)
        for mention_id in sorted(mentions):
            what = "; ".join(f"{c.title()}, {c.section}" for c in by_id[mention_id])
            places = ", ".join(f"`{p}`" for p in mentions[mention_id])
            body.append(f"- {what}: {places}")
        body.append("")
    for section, title in SECTION_TITLES.items():
        rows = [c for c in changes if c.section == section]
        if not rows:
            continue
        body += [f"### {title}", ""]
        for change in rows:
            line = f"- {change.title()}"
            if change.details:
                line += ": " + "; ".join(change.details)
            body.append(line)
        body.append("")

    text = "\n".join(head + body)
    if limit and len(text) > limit:
        cut = text.rfind("\n", 0, limit - 200)
        text = (
            text[:cut]
            + "\n\n… cut here to fit; run `python scripts/schema_diff.py` locally for the whole report.\n"
        )
    return text


def render_json(
    base: Snapshot, target: Snapshot, changes: list[Change], mentions: dict[str, list[str]]
) -> str:
    rows = [
        {
            "section": c.section,
            "kind": c.kind,
            "addon": c.addon_id,
            "aceKind": c.ace_kind or None,
            "ace": c.ace_id or None,
            "name": c.ace_name or c.addon_name,
            "details": c.details,
            "breaking": c.watched,
            "mentions": mentions.get(c.mention_id, []) if c.watched else [],
        }
        for c in changes
    ]
    report = {"base": base.version, "target": target.version, "changes": rows}
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        epilog="Example, after scripts/init.py: python scripts/schema_diff.py --output schema-diff.md",
    )
    parser.add_argument("--base", default="HEAD", help="git revision or schema folder (default: HEAD)")
    parser.add_argument(
        "--target",
        default=str(ROOT / SCHEMAS),
        help=f"git revision or schema folder (default: the working tree's {SCHEMAS})",
    )
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path, help="write the report here instead of stdout")
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"cut the markdown at about this many characters, 0 for all (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--github-output",
        action="store_true",
        help="append needs_review=true|false to $GITHUB_OUTPUT; true when a tracked file "
        "quotes an id a change may have broken",
    )
    args = parser.parse_args(argv)

    try:
        base = load_snapshot(open_source(args.base, ROOT))
        target = load_snapshot(open_source(args.target, ROOT))
        changes = diff_snapshots(base, target)
        mentions = find_mentions(changes, tracked_text_files(ROOT), ROOT)
    except (SnapshotError, json.JSONDecodeError, KeyError) as error:
        print(f"schema_diff: {error}", file=sys.stderr)
        return 2

    if args.format == "json":
        text = render_json(base, target, changes, mentions)
    else:
        text = render_markdown(base, target, changes, mentions, args.limit)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    if args.github_output:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
            print(f"needs_review={'true' if mentions else 'false'}", file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
