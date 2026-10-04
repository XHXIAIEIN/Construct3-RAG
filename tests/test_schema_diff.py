"""What scripts/schema_diff.py reports between two schema snapshots."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import schema_diff


def write_snapshot(
    root: Path,
    version: str,
    plugins: dict[str, dict],
    effects: dict[str, list] | None = None,
    deprecated: dict | None = None,
) -> Path:
    """A minimal data/c3-schemas: root index, primary-locale files, _deprecated.json."""
    locale = root / "en-US"
    index: dict = {"version": version, "languages": ["en-US"], "plugins": {}, "behaviors": {}, "effects": {}}

    def write_addon(kind: str, addon_id: str, data: dict) -> None:
        rel = f"{kind}/{addon_id}.json"
        index[kind][addon_id] = {"file": rel}
        (locale / kind).mkdir(parents=True, exist_ok=True)
        (locale / rel).write_text(json.dumps({"id": addon_id, **data}), encoding="utf-8")

    for plugin_id, data in plugins.items():
        write_addon("plugins", plugin_id, data)
    for effect_id, parameters in (effects or {}).items():
        write_addon("effects", effect_id, {"name": effect_id.title(), "parameters": parameters})
    (root / "_index.json").write_text(json.dumps(index), encoding="utf-8")
    if deprecated is not None:
        (locale / "_deprecated.json").write_text(json.dumps(deprecated), encoding="utf-8")
    return root


def action(ace_id: str, name: str, **fields) -> dict:
    return {"id": ace_id, "list-name": name, "display-text": name, **fields}


def snapshots(tmp_path: Path, base: dict, target: dict) -> tuple[schema_diff.Snapshot, schema_diff.Snapshot]:
    old = schema_diff.load_snapshot(schema_diff.FolderSource(write_snapshot(tmp_path / "old", "r1", **base)))
    new = schema_diff.load_snapshot(schema_diff.FolderSource(write_snapshot(tmp_path / "new", "r2", **target)))
    return old, new


def diff(tmp_path: Path, base: dict, target: dict) -> list[schema_diff.Change]:
    return schema_diff.diff_snapshots(*snapshots(tmp_path, base, target))


def by_ace(changes: list[schema_diff.Change]) -> dict[tuple[str, str], schema_diff.Change]:
    return {(c.section, c.ace_id or c.addon_id): c for c in changes}


def test_identical_snapshots_report_no_change(tmp_path):
    plugins = {"sprite": {"name": "Sprite", "actions": [action("set-x", "Set X")]}}
    assert diff(tmp_path, {"plugins": plugins}, {"plugins": plugins}) == []


def test_added_removed_and_deprecated_aces_and_addons(tmp_path):
    base = {
        "plugins": {
            "sprite": {"name": "Sprite", "actions": [action("old", "Old"), action("gone", "Gone"), action("kept", "Kept")]},
            "legacy": {"name": "Legacy", "actions": []},
        }
    }
    target = {
        "plugins": {
            "sprite": {
                "name": "Sprite",
                "actions": [action("kept", "Kept", isDeprecated=True), action("new", "New")],
            },
            "fresh": {"name": "Fresh"},
        },
        "deprecated": {
            "addons": {"plugins": {"legacy": {}}},
            "aces": {"plugins": {"sprite": {"actions": {"old": {}}}}},
        },
    }
    changes = by_ace(diff(tmp_path, base, target))
    assert set(changes) == {
        ("added", "fresh"),
        ("deprecated", "legacy"),
        ("added", "new"),
        ("removed", "gone"),
        ("deprecated", "old"),
        ("deprecated", "kept"),
    }
    assert changes[("deprecated", "old")].details == ["left out of the schema"]


def test_parameter_and_flag_changes_and_which_of_them_can_break(tmp_path):
    def params(**kinds):
        return {pid: {"type": t, "name": pid} for pid, t in kinds.items()}

    base = {
        "plugins": {
            "sprite": {
                "name": "Sprite",
                "actions": [
                    action("typed", "Typed", params=params(value="number")),
                    action("combo", "Combo", params={"mode": {"type": "combo", "items": {"a": "A", "b": "B"}}}),
                    action("wider", "Wider", params={"mode": {"type": "combo", "items": {"a": "A"}}}),
                    action("renamed", "Old name", scriptName="Renamed"),
                    action("trigger", "Trigger", isTrigger=False),
                    action("described", "Described"),
                ],
            }
        }
    }
    target = {
        "plugins": {
            "sprite": {
                "name": "Sprite",
                "actions": [
                    action("typed", "Typed", params=params(value="string")),
                    action("combo", "Combo", params={"mode": {"type": "combo", "items": {"a": "A"}}}),
                    action("wider", "Wider", params={"mode": {"type": "combo", "items": {"a": "A", "c": "C"}}}),
                    action("renamed", "New name", scriptName="Renamed2"),
                    action("trigger", "Trigger", isTrigger=True),
                    action("described", "Described", returnType="number"),
                ],
            }
        }
    }
    changes = {c.ace_id: c for c in diff(tmp_path, base, target)}
    assert changes["typed"].details == ["parameter `value` type number → string"]
    assert changes["combo"].details == ["parameter `mode` loses items b"]
    assert changes["wider"].details == ["parameter `mode` gains items c"]
    assert changes["renamed"].details == ["scriptName Renamed → Renamed2", "renamed from “Old name”"]
    breaking = {ace_id for ace_id, c in changes.items() if c.watched}
    assert breaking == {"typed", "combo", "trigger"}


def test_effect_parameters_are_compared(tmp_path):
    base = {"plugins": {}, "effects": {"glow": [{"id": "radius", "type": "float"}]}}
    target = {"plugins": {}, "effects": {"glow": [{"id": "radius", "type": "percent"}, {"id": "tint", "type": "color"}]}}
    [change] = diff(tmp_path, base, target)
    assert change.details == ["parameter `radius` type float → percent", "parameter `tint` added"]
    assert change.watched


def test_mentions_are_quoted_ids_of_watched_changes_only(tmp_path):
    changes = [
        schema_diff.Change("removed", "plugins", "sprite", "Sprite", "actions", "set-x", "Set X"),
        schema_diff.Change("added", "plugins", "sprite", "Sprite", "actions", "set-y", "Set Y"),
        schema_diff.Change("changed", "plugins", "sprite", "Sprite", "actions", "set-z", "Set Z", ["renamed"]),
    ]
    doc = tmp_path / "prompts" / "guide.md"
    doc.parent.mkdir()
    doc.write_text(
        "Use `set-x` here, and \"set-x\" again on this line.\n"
        "Unquoted set-x and offset-x do not count.\n"
        "`set-y` was added and `set-z` only renamed.\n",
        encoding="utf-8",
    )
    assert schema_diff.find_mentions(changes, [doc], tmp_path) == {"set-x": ["prompts/guide.md:1"]}


def test_markdown_puts_mentions_first_and_respects_the_limit(tmp_path):
    base = {"plugins": {"sprite": {"name": "Sprite", "actions": [action(f"a{i}", f"A{i}") for i in range(200)]}}}
    target = {"plugins": {"sprite": {"name": "Sprite", "actions": []}}}
    old, new = snapshots(tmp_path, base, target)
    changes = schema_diff.diff_snapshots(old, new)
    text = schema_diff.render_markdown(old, new, changes, {"a1": ["prompts/x.md:3"]}, limit=0)
    assert text.startswith("## Construct 3 r1 → r2\n\n200 removed.\n")
    assert text.index("### Mentions to check") < text.index("### Removed")
    short = schema_diff.render_markdown(old, new, changes, {}, limit=2000)
    assert len(short) < 2000
    assert "cut here" in short


def test_cli_reads_a_git_revision_and_writes_the_github_output(tmp_path, monkeypatch, capsys):
    github_output = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(github_output))
    assert schema_diff.main(["--base", "HEAD", "--github-output"]) == 0
    assert capsys.readouterr().out.startswith("## Construct 3 ")
    assert github_output.read_text(encoding="utf-8").strip() in {"needs_review=true", "needs_review=false"}


def test_cli_reports_an_unreadable_snapshot(tmp_path, capsys):
    assert schema_diff.main(["--base", str(tmp_path)]) == 2
    assert "_index.json" in capsys.readouterr().err


def test_an_index_entry_without_its_file_is_an_error(tmp_path):
    root = write_snapshot(tmp_path / "s", "r1", {"sprite": {"name": "Sprite"}})
    (root / "en-US" / "plugins" / "sprite.json").unlink()
    with pytest.raises(schema_diff.SnapshotError, match="plugins/sprite.json"):
        schema_diff.load_snapshot(schema_diff.FolderSource(root))
