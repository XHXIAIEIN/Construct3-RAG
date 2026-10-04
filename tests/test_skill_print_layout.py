"""print_layout.py: layers, instances and what a text lies on."""
import json
from pathlib import Path

from tests.skill_helpers import tool


def layout_file(project: Path) -> Path:
    return next(p for p in (project / "layouts").rglob("*.json") if not p.name.endswith(".uistate.json"))


def test_layout_prints_layers_and_instances(built):
    code, out = tool(built, "print_layout")
    assert code == 0, out
    lines = out.splitlines()
    assert lines[0].startswith("== ") and " x " in lines[0], out
    assert any(line.startswith("layer ") for line in lines), out
    assert any(line.startswith("  ") and "(Sprite)" in line and ", y " in line for line in lines), out


def test_a_label_off_its_button_says_so(project):
    # A generated menu had its labels 100 px above the button and the panel; nothing said so.
    path = layout_file(project)
    layout = json.loads(path.read_text(encoding="utf-8"))
    layer = layout["layers"][-1]
    sprite = next((i for L in layout["layers"] for i in L["instances"]
                   if "text" not in (i.get("properties") or {})), None)
    assert sprite, "the stand-in game has a sprite"
    w = sprite["world"]
    label = {"type": sprite["type"], "properties": {"text": "Start"},
             "world": {**w, "x": w["x"] + 5000, "y": w["y"] + 5000, "originX": 0.5, "originY": 0.5}}
    on = {"type": sprite["type"], "properties": {"text": "On it"}, "world": {**w}}
    layer["instances"] += [label, on]
    path.write_text(json.dumps(layout, indent="\t", ensure_ascii=False), encoding="utf-8")
    code, out = tool(project, "print_layout", layout["name"])
    assert code == 0, out
    assert 'text "Start"; on no object]' in out, out
    assert f'[text "On it"; on {sprite["type"]}]' in out, out


def test_a_layout_not_there_names_the_layouts(built):
    code, out = tool(built, "print_layout", "Nowhere")
    assert code == 1 and "no layout named 'Nowhere'; layouts: " in out, out
