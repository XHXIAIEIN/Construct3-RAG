"""scripts/example_usage.py: which official examples use each condition, action and expression."""
import json
from pathlib import Path

from scripts import example_usage


def example(clone: Path, name: str, events: list) -> None:
    """An example project with a Sprite object Player that has the Platform behavior, and one sheet, Game."""
    root = clone / "example-projects" / name
    (root / "objectTypes").mkdir(parents=True)
    (root / "eventSheets").mkdir()
    (root / "project.c3proj").write_text(json.dumps({
        "objectTypes": {"items": ["Player"], "subfolders": []},
        "families": {"items": [], "subfolders": []},
        "eventSheets": {"items": ["Game"], "subfolders": []}}), encoding="utf-8")
    (root / "objectTypes" / "Player.json").write_text(json.dumps({
        "name": "Player", "plugin-id": "Sprite",
        "behaviorTypes": [{"behaviorId": "Platform", "name": "Platform"}],
        "instanceVariables": [{"name": "hp", "type": "number"}]}), encoding="utf-8")
    (root / "eventSheets" / "Game.json").write_text(json.dumps({"name": "Game", "events": events}), encoding="utf-8")


EVERY_TICK = {"id": "every-tick", "objectClass": "System"}


def clone(tmp_path: Path) -> Path:
    folder = tmp_path / "Construct-Example-Projects"
    example(folder, "platformer", [
        {"eventType": "variable", "name": "time", "type": "number", "initialValue": "0"},
        {"eventType": "block", "conditions": [EVERY_TICK], "actions": [
            {"id": "set-x", "objectClass": "Player",
             "parameters": {"x": "Player.X + random(2) + Player.Platform.VectorX + Player.hp + time"}}],
         "children": [
             {"eventType": "block",
              "conditions": [{"id": "is-on-floor", "objectClass": "Player", "behaviorType": "Platform"}],
              "actions": [{"id": "set-animation", "objectClass": "Player",
                           "parameters": {"animation": "\"dt\" & Self.AnimationName", "from": "beginning"}}]}]}])
    # one example in both languages: two folders with the same events
    for name in ("ticker-js", "ticker-ts"):
        example(folder, name, [{"eventType": "block", "conditions": [EVERY_TICK], "actions": []}])
    return folder


def test_each_ace_is_keyed_by_its_addon_with_the_events_of_its_first_use(tmp_path):
    files = example_usage.build(clone(tmp_path))
    read = {name: {kind: {ace: entry["read"] for ace, entry in aces.items()} for kind, aces in content.items()}
            for name, content in files.items() if name != "_source.json"}
    # an event with a sub-event is read with it
    assert read["plugins/_common.json"] == {"actions": {"set-x": [["platformer", "Game", 1, 2]]},
                                            "expressions": {"x": [["platformer", "Game", 1, 2]]}}
    assert read["behaviors/platform.json"] == {"conditions": {"is-on-floor": [["platformer", "Game", 2, 2]]},
                                               "expressions": {"vectorx": [["platformer", "Game", 1, 2]]}}
    # Self is the object of the action
    assert read["plugins/sprite.json"] == {"actions": {"set-animation": [["platformer", "Game", 2, 2]]},
                                           "expressions": {"animationname": [["platformer", "Game", 2, 2]]}}
    # a variable named time is not the System expression, and "dt" in quotes is text
    assert read["plugins/system.json"]["expressions"] == {"random": [["platformer", "Game", 1, 2]]}


def test_an_example_in_two_languages_counts_once_and_the_smallest_sheet_comes_first(tmp_path):
    files = example_usage.build(clone(tmp_path))
    every_tick = files["plugins/system.json"]["conditions"]["every-tick"]
    assert every_tick == {"examples": 2, "read": [["ticker-js", "Game", 1, 1], ["platformer", "Game", 1, 2]]}
    assert files["_source.json"]["examples"] == 2


def test_the_index_replaces_the_folder_and_writes_the_same_bytes_twice(tmp_path):
    folder, out = clone(tmp_path), tmp_path / "data" / "c3-example-usage"
    (out / "plugins").mkdir(parents=True)
    (out / "plugins" / "gone.json").write_text("{}", encoding="utf-8")
    example_usage.refresh(folder, out)
    first = {p.relative_to(out).as_posix(): p.read_bytes() for p in sorted(out.rglob("*.json"))}
    assert "plugins/gone.json" not in first and "behaviors/platform.json" in first
    example_usage.refresh(folder, out)
    assert {p.relative_to(out).as_posix(): p.read_bytes() for p in sorted(out.rglob("*.json"))} == first
    assert json.loads(first["plugins/system.json"])["conditions"]["every-tick"]["examples"] == 2


def test_without_a_clone_the_committed_index_stays(tmp_path):
    out = tmp_path / "c3-example-usage"
    (out / "plugins").mkdir(parents=True)
    (out / "plugins" / "sprite.json").write_text("{}", encoding="utf-8")
    said = example_usage.refresh(tmp_path / "missing", out)
    assert said.startswith("no Construct-Example-Projects clone at ") and "kept the committed index" in said
    assert (out / "plugins" / "sprite.json").read_text(encoding="utf-8") == "{}"
