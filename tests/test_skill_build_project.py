"""assets/build_project.py, the generator template, and the stand-in game it generates."""
import builtins
import datetime
import json
import re
import shutil
import symtable
import sys
from pathlib import Path

import pytest

from tests.skill_helpers import (
    EXAMPLES, NO_EXAMPLES, REPO, SKILL, INSTALLED, run, tool, check, edit, every_event, warnings, findings,
    template_module, png_pixels,
)

sys.path.insert(0, str(SKILL / "scripts"))
import c3project as c3  # noqa: E402

# What a game's generator holds outside the markers and the helpers read: the settings above
# them, and below them BEATS and the functions build_all() calls.
EVERY_GAME = {"ROOT", "VIEW_W", "VIEW_H", "PROJECT_NAME", "FIRST_LAYOUT", "ORIENTATION", "UNIT", "MARGIN", "TOUCH",
              "PALETTE", "SHAPE_STYLE", "HIT_FLASH", "SQUASH", "FONT", "TEXT_SIZE", "PIXEL_ART", "ART_STYLE",
              "BEATS", "build_files", "build_images", "build_object_types", "build_layouts", "build_event_sheet"}


def test_template_stamps_its_helpers():
    """The end marker carries the version and the stamp of the helpers between the markers, so that
    a game's copy tells an older version of them, which install.py replaces, from one edited there,
    which it keeps. Changed helpers fail here until the end marker carries their stamp."""
    lines = (SKILL / "assets" / "build_project.py").read_text(encoding="utf-8").split("\n")
    helpers = c3.helpers_in(lines)
    assert isinstance(helpers, c3.Helpers), helpers
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    assert helpers.stamp == helpers.actual, (
        f"the helpers of assets/build_project.py changed, so their version and stamp did: replace line "
        f"{helpers.end + 1}, the end marker, with\n{c3.helpers_end_line(today, helpers.actual)}")
    assert lines[helpers.end] == c3.helpers_end_line(helpers.version, helpers.stamp)


def test_template_helpers_read_only_what_every_game_has():
    """A refresh replaces the helpers and keeps the rest of a game's generator, so the helpers import
    the modules they use and read nothing from outside the markers but what every generator has:
    a helper that reads a new setting stops a game refreshed onto it with a NameError."""
    lines = (SKILL / "assets" / "build_project.py").read_text(encoding="utf-8").split("\n")
    helpers = c3.helpers_in(lines)
    table = symtable.symtable("\n".join(lines[helpers.begin + 1:helpers.end]), "helpers", "exec")
    defined = {s.get_name() for s in table.get_symbols() if s.is_assigned() or s.is_imported()}
    read: set[str] = set()

    def walk(scope) -> None:
        read.update(s.get_name() for s in scope.get_symbols()
                    if s.is_referenced() and (scope.get_type() == "module" or s.is_global()))
        for child in scope.get_children():
            walk(child)
    walk(table)
    outside = {name for name in read - defined - set(dir(builtins)) if not name.startswith("__")}
    assert outside <= EVERY_GAME, (
        f"the helpers read {sorted(outside - EVERY_GAME)}, which a game copied before them does not have: import "
        f"a module between the markers, and give a new setting a default there, NAME = globals().get(\"NAME\", ...)")


def test_stand_in_project_passes_without_warnings(built):
    code, out = check(built)
    assert code == 0, out
    assert out.startswith("ok:") or "\nok:" in out
    assert warnings(out) == [], out


def test_template_behavior_blocks_hold_the_schemas_keys():
    """A behavior the template has no block for is guessed from the schema, whose
    properties carry no values, or copied from an example: the blocks here are the
    editor's key sets, checked against the schemas, with a combo value from its items."""
    template = template_module()
    blocks = {"TWEEN": "tween", "TIMER": "timer", "SOLID": "solid", "SINE": "sin", "FLASH": "flash",
              "BULLET": "bullet", "EIGHT_DIR": "eightdir", "PLATFORM": "platform", "MOVE_TO": "moveto",
              "ROTATE": "rotate", "DRAG_DROP": "dragndrop", "SCROLL_TO": "scrollto",
              "DESTROY_OUTSIDE": "destroy", "BOUND_TO_LAYOUT": "bound", "LINE_OF_SIGHT": "los"}
    for const, behavior in blocks.items():
        schema = json.loads((REPO / "data" / "c3-schemas" / "en-US" / "behaviors" / f"{behavior}.json")
                            .read_text(encoding="utf-8"))
        props = schema.get("properties") or {}
        (name, block), = getattr(template, const).items()
        assert list(block) == ["properties"], const
        assert list(block["properties"]) == list(props), f"{const}: {list(block['properties'])} != {list(props)}"
        for key, value in block["properties"].items():
            if "items" in props[key]:
                assert value in props[key]["items"], f"{const}.{key} = {value!r}"
            else:
                assert isinstance(value, (bool, int, float, str)), f"{const}.{key}"
        assert " " not in name and name[0].isalnum(), name


def test_shape_style_switches_the_baked_outline_and_shadow(tmp_path):
    """Construct's effects have no outline or drop shadow, so shape() draws them into the image
    from SHAPE_STYLE: the outline inside the shape, which keeps its size, the shadow outside it,
    which widens the image on its side and stays out of the collision polygon and the origin."""
    template = template_module()
    template.ROOT = tmp_path
    style = template.SHAPE_STYLE
    style.update(outline=True, shadow=True, outline_width=4, shadow_distance=10, shadow_angle=90, shadow_opacity=0.5)
    ink, fill = template.rgb(style["outline_role"]), template.rgb("reward")

    f = template.shape("on.png", "rect", 64, 32, "reward")
    px = png_pixels(tmp_path / "images" / "on.png")
    w, h = len(px[0]), len(px)
    assert (w, h) == (f["width"], f["height"]) == (64, 42)
    assert px[0][0] == (*ink, 255) and px[3][3] == (*ink, 255) and px[4][4] == (*fill, 255)
    assert px[40][32] == (*template.rgb(style["shadow_role"]), 128)
    assert (f["originX"], f["originY"]) == (0.5, 16 / 42)
    assert max(f["collisionPoly"]["points"][1::2]) == round(32 / 42, 4)
    assert template.drawn("on.png") is f

    style.update(shadow_angle=180)
    f = template.shape("left.png", "circle", 32, 32, "reward")
    assert (f["width"], f["height"], f["originX"]) == (42, 32, 26 / 42)

    style.update(outline=False, shadow=False)
    f = template.shape("off.png", "triangle", 32, 32, "solid")
    px = png_pixels(tmp_path / "images" / "off.png")
    w, h = len(px[0]), len(px)
    assert (w, h) == (32, 32) and {p[:3] for row in px for p in row if p[3]} == {template.rgb("solid")}
    f = template.shape("one.png", "rect", 32, 32, "reward", outline=True)
    assert png_pixels(tmp_path / "images" / "one.png")[0][0] == (*ink, 255)


def test_template_draws_an_accent_that_shows_without_its_outline_and_a_fill_the_outline_shows_on(tmp_path):
    """The plain sheet draws no outline, so an accent reads 3:1 on canvas_alt or is drawn with its
    outline; a fill too near the ink hides its own outline."""
    t = template_module()
    t.ROOT = tmp_path
    t.shape("spike.png", "triangle", 32, 32, "danger")                          # 3.5:1, shows alone
    t.PALETTE["danger"] = (245, 120, 110)
    with pytest.raises(SystemExit, match=r"spike.png: danger \(245, 120, 110\) reads 2\.\d\d:1 on canvas_alt, and an "
                                         r"accent without an outline needs 3:1 .* darken danger, or draw it with its outline"):
        t.shape("spike.png", "triangle", 32, 32, "danger")
    t.shape("spike.png", "triangle", 32, 32, "danger", outline=True)
    t.shape("wall.png", "rect", 32, 32, "solid")                                 # a grey may go without
    t.shape("player.png", "rect", 32, 64, "ink", outline=True)                   # the player is ink, its outline too
    t.PALETTE["dim"] = (60, 60, 60)
    with pytest.raises(SystemExit, match=r"shade.png: its dim fill reads 1\.\d:1 against its ink outline, which needs "
                                         r"3:1 to show; fill it in one of canvas, canvas_alt, solid, reward, danger, flash"):
        t.shape("shade.png", "rect", 32, 32, "dim", outline=True)


def test_template_palette_keeps_the_ratios_of_the_blockout():
    """The sheet's greys: the checker's two at most 1.2:1, structure 3:1 on the darker, and the
    accents 3:1 on it as well, so every shape shows without an outline; the run stops on a palette
    that loses the greys' ratios, naming the role to move."""
    t = template_module()
    ratios = {pair: round(t.contrast(t.rgb(pair[0]), t.rgb(pair[1])), 2) for pair in (
        ("canvas", "canvas_alt"), ("solid", "canvas_alt"), ("reward", "canvas_alt"), ("danger", "canvas_alt"),
        ("ink", "solid"), ("ink", "reward"), ("ink", "danger"))}
    assert ratios == {("canvas", "canvas_alt"): 1.11, ("solid", "canvas_alt"): 3.23, ("reward", "canvas_alt"): 3.1,
                      ("danger", "canvas_alt"): 4.12, ("ink", "solid"): 5.03, ("ink", "reward"): 5.24,
                      ("ink", "danger"): 3.94}
    t.check_palette()
    assert [role for role in t.PALETTE if t.accent(role)] == ["reward", "danger"]
    t.PALETTE["canvas_alt"] = (200, 200, 200)
    with pytest.raises(SystemExit, match=r"PALETTE: canvas .* and canvas_alt .* are 1\.\d\d:1; the backdrop's two greys "
                                         r"stay at most 1\.2:1"):
        t.check_palette()
    t.PALETTE.update(canvas_alt=(238, 238, 234), solid=(160, 160, 160))
    with pytest.raises(SystemExit, match=r"PALETTE: solid \(160, 160, 160\) on canvas_alt .* reads 2\.\d\d:1; structure "
                                         r"needs 3:1 .* Darken solid"):
        t.check_palette()


def test_template_patterns_tile_by_the_unit_and_meet_without_a_seam(tmp_path):
    """An area is a Tiled Background of a pattern; its image offset is minus its corner modulo
    the tile, which the runtime subtracts from the texture coordinate, so every piece lines up
    with the layout. The plain sheet and the checker are the backdrop's alone, the high-contrast
    stripes strips and small zones."""
    t = template_module()
    t.ROOT = tmp_path
    for name, kind in (("Sheet", "plain"), ("Backdrop", "checker"), ("Ledge", "low"), ("Door", "caution"),
                       ("Lava", "hazard")):
        t.pattern(name, kind)
        px = png_pixels(tmp_path / "images" / f"{name.lower()}.png")
        assert (len(px), len(px[0])) == (32, 32)
        assert {p[:3] for row in px for p in row} == {t.rgb(role) for role in t.PATTERNS[kind]}
        assert {p[3] for row in px for p in row} == {255}
    checker = png_pixels(tmp_path / "images" / "backdrop.png")
    assert checker[0][0][:3] == checker[16][16][:3] == t.rgb("canvas") and checker[0][16][:3] == t.rgb("canvas_alt")
    stripes = png_pixels(tmp_path / "images" / "lava.png")
    assert all(stripes[y][x] == stripes[(y + 1) % 32][(x - 1) % 32] for y in range(32) for x in range(32))  # 45 degrees
    assert t.pattern_type("Lava")["image"]["width"] == 32 and t.pattern_type("Lava")["plugin-id"] == "TiledBg"
    lava = t.area("Lava", 3, 20, 8, 2)
    assert (lava["world"]["x"], lava["world"]["y"], lava["world"]["width"], lava["world"]["height"]) == (96, 640, 256, 64)
    assert (lava["properties"]["image-offset-x"], lava["properties"]["image-offset-y"]) == (0, 0)
    off = t.tiledbg_inst("Lava", 100, 50, 64, 64, 0.5, 0.5)                   # corner (68, 18)
    assert (off["properties"]["image-offset-x"], off["properties"]["image-offset-y"]) == (28, 14)
    assert all(((x - 68) - 28) % 32 == x % 32 for x in range(68, 132))      # texture x = (local - offset) / tile
    assert t.tiledbg_inst("HpFill", 100, 50, 64, 64)["properties"]["image-offset-x"] == 0   # a bar is no pattern
    back = t.backdrop("Backdrop")
    assert (back["world"]["x"], back["world"]["y"], back["world"]["width"], back["world"]["height"]) == (0, 0, 720, 1280)
    assert t.backdrop("Sheet")["world"]["width"] == 720
    for name, kind in (("Backdrop", "checker"), ("Sheet", "plain")):
        with pytest.raises(SystemExit, match=rf"area\('{name}'\): the {kind} pattern is empty space, the backdrop alone"):
            t.area(name, 0, 0, 4, 4)
    with pytest.raises(SystemExit, match=r"area\('Lava'\): 10x6 cells of hazard stripes; .* keep the shorter side to 5 cells"):
        t.area("Lava", 0, 0, 10, 6)
    t.area("Ledge", 0, 0, 10, 6)                                             # low stripes may cover more
    with pytest.raises(SystemExit, match=r"backdrop\('Door'\): the backdrop is the plain sheet or the checker"):
        t.backdrop("Door")
    with pytest.raises(SystemExit, match=r"area\('Wall'\): not a pattern"):
        t.area("Wall", 0, 0, 1, 1)


@pytest.mark.parametrize("change, said", [
    (lambda b: b[0].update(intensity=1), "beat 1 intro is at 1; the first beat is at 0"),
    (lambda b: b[3].update(type="practice"), "beat 3 practice at 2 is followed by practice; a beat of 2 or more is "
                                             "followed by a rest"),
    (lambda b: b[3].update(holds=""), "beat 4 rest holds nothing; a rest holds a pickup or a checkpoint"),
    (lambda b: b[2].update(mechanics=["tap", "swipe"]), "beat 3 practice combines tap, swipe, but swipe has had no "
                                                         "teach of its own"),
    (lambda b: b[1].update(type="climax"), "the climax is beat 2 climax, beat 5 climax; a game has one climax, in "
                                           "its last third, beats 5 to 6"),
    (lambda b: b[4].update(intensity=1), "the last third averages 0.5 and the first 0.5; the game rises"),
    (lambda b: b[5].update(type="finale"), "beat 6 finale at 0; a beat is one of intro, teach"),
])
def test_template_pace_stops_a_curve_that_breaks_a_rule(change, said):
    t = template_module()
    beats = [dict(b) for b in t.BEATS]
    assert t.pace(beats)[4] == "beat 5 climax      3 |###| tap"
    change(beats)
    with pytest.raises(SystemExit) as stop:
        t.pace(beats)
    assert said in str(stop.value)


def test_template_deals_the_coins_of_each_beat_round_after_round(built):
    t = template_module()
    sheet = json.loads((built / "eventSheets" / "Game.json").read_text(encoding="utf-8"))
    rounds = next(v for v in sheet["events"] if v.get("name") == "ROUND_COINS")
    assert rounds["initialValue"] == ",".join(str(b["coins"]) for b in t.BEATS) == "1,3,6,2,10,1"
    code, out = tool(built, "print_sheet", "Game")
    assert 'For "i" from 0 to int(tokenat(ROUND_COINS, beat, ",")) - 1' in out
    assert 'Set beat to (beat + 1) % tokencount(ROUND_COINS, ",")' in out


def test_template_measures_a_gap_against_the_players_reach():
    """The reach from PLATFORM's properties: 650 px/s, gravity 1500, no sustain, 330 px/s rise
    141 px and stay 0.87 s in the air, 286 px or 8.9 units across; a gap is easy to half of it,
    hard from eight tenths, and past nine tenths the run stops."""
    t = template_module()
    assert round(t.jump_reach()) == 286 and t.jump_reach(200) == 0
    assert [t.jump(g) for g in (4, 6, 8)] == ["easy", "medium", "hard"]
    assert t.jump(4, rise=4) == "medium" and t.jump(5, rise=4) == "hard"     # landing higher shortens the fall
    with pytest.raises(SystemExit, match=r"a gap of 9 units rising 0 is past the player's reach of 8\.9 units .* keep a "
                                         r"gap to 8 units at most"):
        t.jump(9)


def test_stand_in_project_holds_a_string_variable_as_the_editor_writes_it(built):
    coin = json.loads((built / "objectTypes" / "Coin.json").read_text(encoding="utf-8"))
    assert [(v["name"], v["type"]) for v in coin["instanceVariables"]] == [("value", "number"), ("kind", "string")]
    objects = json.loads((built / "layouts" / "Objects.json").read_text(encoding="utf-8"))
    assert objects["layers"][0]["instances"][0]["instanceVariables"] == {"value": 1, "kind": "gold"}


def test_stand_in_project_writes_containers_where_the_editor_reads_them(project):
    """A container is a row of project.c3proj, not a file: a Doubao run searched objectTypes/
    and the example folders for its format and gave up. The helper writes what saves from
    r342 on hold, members alone, and the checker reads the row."""
    template = template_module()
    assert template.container(["Coin", "ScoreText"]) == {"members": ["Coin", "ScoreText"]}
    proj = json.loads((project / "project.c3proj").read_text(encoding="utf-8"))
    assert proj["containers"] == [] and list(proj).index("containers") < list(proj).index("layouts")
    out = findings(project, lambda p: p["containers"].append({"members": ["Coin", "ScoreText"]}), "project.c3proj")
    assert warnings(out) == [] and out.splitlines()[-1].startswith("ok:"), out
    out = findings(project, lambda p: p["containers"].append({"members": ["Coin", "Wallet"]}), "project.c3proj")
    assert "container ['Coin', 'Wallet']: member Wallet is not an object type" in out


def test_stand_in_project_opens_in_the_editor(built):
    """The editor reads the whole properties block before it reads a file of the
    project, and asserts each value as it goes: a project.c3proj kept down to the
    keys the tools read opens as "TypeError: expected string" and names neither."""
    proj = json.loads((built / "project.c3proj").read_text(encoding="utf-8"))
    assert proj["projectFormatVersion"] == 1 and proj["runtime"] == "c3"
    # below r309 the editor reads an object type from objectTypes/<name in lower case>.json
    assert proj["savedWithRelease"] >= 30900
    assert isinstance(proj["viewportWidth"], int) and isinstance(proj["viewportHeight"], int)
    props = proj["properties"]
    for key in ("description", "version", "author", "authorEmail", "authorWebsite", "appId"):
        assert isinstance(props[key], str), key
    assert props["fullscreenMode"] == "letterbox-scale" and props["fullscreenQuality"] == "high"
    assert props["orientations"] == "portrait" and props["sampling"] == "trilinear"
    assert props["downscaling"] == "medium" and props["loaderStyle"] == "splash"


# Keys the generated project does not write, with the reason the editor opens
# without them: both loaders return from the project's own loader when the key is
# missing (projectResources.js, sPn and G7s), and a generated project has no
# project files and no timeline.
GENERATOR_LEAVES_OUT = {"project": {"rootFileFolders", "timelines"}}


def always_written(root: Path) -> dict[str, set[str]]:
    """The keys every example project carries at each level: what the editor
    writes whatever the project. A level is a file kind, or a block inside one."""
    seen: dict[str, list[set[str]]] = {}

    def note(level, d):
        seen.setdefault(level, []).append(set(d))

    def layers(ls):
        for layer in ls:
            note("layer", layer)
            for inst in layer.get("instances", []):
                note("instance", inst)
                if isinstance(inst.get("world"), dict):
                    note("world", inst["world"])
            layers(layer.get("subLayers", []))

    for f in root.glob("*/project.c3proj"):
        d = json.loads(f.read_text(encoding="utf-8"))
        note("project", d)
        note("properties", d.get("properties", {}))
    for kind, level in (("layouts", "layout"), ("eventSheets", "sheet"), ("objectTypes", "objectType")):
        for f in root.glob(f"*/{kind}/*.json"):
            if f.name.endswith(".uistate.json"):
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            note(level, d)
            if level == "layout":
                layers(d.get("layers", []))
    return {level: set.intersection(*files) for level, files in seen.items()}


@pytest.mark.skipif(not EXAMPLES.is_dir(), reason=NO_EXAMPLES)
def test_generated_project_carries_what_the_editor_writes_into_every_project(built):
    """The comparison that finds a missing key before the editor does: the official
    examples are 524 projects the editor saved, so a key in every one of them is one
    the editor writes whatever the project holds. Twice the generated project was
    opened and refused for a key that was missing here and present in all of them."""
    always = always_written(EXAMPLES)
    project = json.loads((built / "project.c3proj").read_text(encoding="utf-8"))
    missing = {"project": always["project"] - set(project) - GENERATOR_LEAVES_OUT["project"],
               "properties": always["properties"] - set(project["properties"])}
    for level, kind in (("layout", "layouts"), ("sheet", "eventSheets"), ("objectType", "objectTypes")):
        for f in sorted((built / kind).glob("*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            missing[f"{kind}/{f.name}"] = always[level] - set(d)
            for layer in d.get("layers", []) if level == "layout" else []:
                missing[f"{f.name} layer {layer['name']}"] = always["layer"] - set(layer)
                for inst in layer["instances"]:
                    missing[f"{f.name} {inst['type']}"] = (always["instance"] - set(inst)) | {
                        f"world.{k}" for k in always["world"] - set(inst.get("world", {}))}
    assert {where: sorted(keys) for where, keys in missing.items() if keys} == {}


def test_generator_exits_with_the_checkers_findings(project):
    """One command builds and checks, so a finding cannot be skipped by forgetting the second."""
    source = project / "tools" / "build_project.py"
    source.write_text(source.read_text(encoding="utf-8").replace(
        'return cond("on-touched-object", "Touch", {"object": obj, "type": "start"})',
        'return cond("on-touched-object", "Touch", {"object": obj, "type": "\\"start\\""})'), encoding="utf-8")
    code, out = run(project, "tools/build_project.py")
    assert code == 1
    assert "generated; checking" in out and 'write it bare, "start"' in out


def test_generator_keeps_only_the_timelines_and_flowcharts_that_have_a_file(project):
    """A project.c3proj copied from the editor's new project lists Timeline 1 and Flowchart 1;
    without their folders the editor stops with "missing file path 'timelines\\Timeline 1.json'"."""
    edit(project, "project.c3proj", lambda p: p.update(
        timelines={"items": ["Timeline 1", "Fade"], "subfolders": [{"items": [], "subfolders": []}]},
        flowcharts={"items": ["Flowchart 1"], "subfolders": []}))
    (project / "timelines").mkdir()
    (project / "timelines" / "Fade.json").write_text("{}", encoding="utf-8")
    code, out = check(project)
    assert code == 1 and ("flowcharts: Flowchart 1 is listed in project.c3proj but flowcharts/Flowchart 1.json "
                          "is missing") in out, out
    run(project, "tools/build_project.py")
    written = json.loads((project / "project.c3proj").read_text(encoding="utf-8"))
    assert written["timelines"]["items"] == ["Fade"] and written["flowcharts"]["items"] == []


def test_generator_without_the_skill_says_so(project):
    shutil.rmtree(project / INSTALLED)
    code, out = run(project, "tools/build_project.py")
    assert code != 0 and "generated, not checked" in out and "install.py" in out


def test_template_run_where_it_sits_says_to_copy_it(project):
    """Run from the skill's assets/, the template would look for project.c3proj in the skill."""
    code, out = run(project, f"{INSTALLED}/assets/build_project.py")
    assert code == 1 and "copy it to tools/build_project.py in the game project" in out
    assert "create the project in the editor" not in out


def test_template_places_the_hud_on_the_grid(built):
    """anchor() returns the origin point of a box held MARGIN inside the viewport edge, on the
    grid; the stand-in's HUD text and its tapped coin come from it, so a generated layout starts
    aligned and a small model fills cells instead of choosing coordinates."""
    t = template_module()
    assert (t.VIEW_W, t.VIEW_H, t.UNIT, t.MARGIN, t.TOUCH) == (720, 1280, 32, 32, 96)
    assert t.units(13) == 416 and t.snap(100) == 96 and t.snap(112) == 128
    assert t.anchor("top-left", 416, 64) == (32, 32)
    assert t.anchor("top-right", 416, 64) == (720 - 32 - 416, 32)          # its right edge MARGIN from the viewport's
    assert t.anchor("bottom", 96, 96, 0.5, 0.5) == (360, 1280 - 32 - 48)   # centred, its bottom edge MARGIN up
    assert t.anchor("center", 96, 96, 0.5, 0.5) == (360, 640)
    assert t.anchor("top-left", 96, 96, 0.5, 0.5, dx=3) == (32 + 96 + 48, 32 + 48)
    # A row of three fingers' width, one unit apart, centred on the top edge: 352 px wide from x 184.
    assert t.row("top", 3, 96, 96) == [(232, 80), (360, 80), (488, 80)]
    # A Text's size is in points, 4/3 px each, so a label's box fits its longest text
    # (8 x 0.6 em x 32 x 4/3 = 205 -> 224) and reads towards the side it hangs on.
    timer = t.hud_text("TimerText", "Time: 30", "top-right")
    assert (timer["world"]["x"], timer["world"]["y"], timer["world"]["width"], timer["world"]["height"]) == (464, 32, 224, 64)
    assert timer["properties"]["horizontal-alignment"] == "right"
    # A wide character is about 1 em, so a Chinese label's box holds its characters at full size.
    assert t.text_ems("Time: 30") == 4.8 and t.text_ems("结束回合，") == 5
    banner = t.hud_text("MapTitle", "地图", "top", size=48, longest="选择前进之路")
    assert banner["world"]["width"] >= len("选择前进之路") * 48 * 4 / 3
    game = json.loads((built / "layouts" / "Game.json").read_text(encoding="utf-8"))
    score = next(i for layer in game["layers"] for i in layer["instances"] if i["type"] == "ScoreText")["world"]
    assert (score["x"], score["y"], score["width"], score["height"]) == (32, 32, 512, 128)   # title size
    for k in ("x", "y", "width", "height"):
        assert score[k] % t.UNIT == 0, k
    # Two HUD boxes that meet, or one past the viewport, stop the generator and name them.
    with pytest.raises(SystemExit, match=r"ScoreText \(32,32\)-\(288,96\) overlaps TimerText .* Move TimerText down 3 units: dy=3"):
        t.no_overlap([t.hud_text("ScoreText", "Score: 0", "top-left", longest="Score: 999"),
                      t.hud_text("TimerText", "Time: 30", "top-left")])
    # The dy the guard names puts the second label's top one unit under the first.
    t.no_overlap([t.hud_text("ScoreText", "Score: 0", "top-left", longest="Score: 999"),
                  t.hud_text("TimerText", "Time: 30", "top-left", dy=3)])
    assert t.hud_text("TimerText", "Time: 30", "top-left", dy=3)["world"]["y"] == 128
    with pytest.raises(SystemExit, match="reaches past the 720x1280 viewport"):
        t.no_overlap([t.sprite_inst("Coin", 32, 32, 96, 96)])
    # A fill inside its frame is a layer on purpose, not a collision: the eighteen bar runs of
    # iteration 19 all met the guard here and worked around it.
    frame = t.sprite_inst("HpFrame", 32 + 192, 128 + 16, 384, 32)
    fill = t.sprite_inst("HpFill", 32 + 96, 128 + 16, 192, 32)
    t.no_overlap([frame, fill])
    t.no_overlap([t.hud_text("ScoreText", "Score: 0", "top-left", longest="Score: 999"), timer])
    # Every box in the way is named at once, one line each, so one run shows all there is to move.
    with pytest.raises(SystemExit) as stop:
        t.no_overlap([t.sprite_inst("Coin", 32, 32, 96, 96), t.hud_text("ScoreText", "Score: 0", "top-left"),
                      t.hud_text("TimerText", "Time: 30", "top-left")])
    said = str(stop.value).splitlines()
    assert len(said) == 4 and "reaches past" in said[0] and all("overlaps" in line for line in said[1:])


def test_template_button_is_a_shape_and_its_label_that_never_come_apart(tmp_path):
    """button() puts a label on its shape as one part: the shape at least button_size() of its
    text, the label centred on the same box in a colour that reads on the fill, and linked as the
    shape's child in the layout's hierarchy, as the editor writes it, so the events that hide or
    move the button take the label along."""
    t = template_module()
    t.ROOT = tmp_path
    assert t.button_size("继续") == (160, 96)                 # 3 units of text and one on each side; TOUCH high
    assert t.button_size("A") == (t.TOUCH, t.TOUCH)        # never smaller than a finger
    t.shape("resume-default-000.png", "rect", *t.button_size("继续"), "solid")
    shape, label = t.button("Resume", "resume-default-000.png", "ResumeLabel", "继续", 3, 10)
    assert (label["world"]["x"], label["world"]["y"], label["world"]["width"], label["world"]["height"]) == \
        (96, 320, 160, 96)
    assert label["properties"]["horizontal-alignment"] == "center" and label["properties"]["size"] == t.TEXT_SIZE["body"]
    assert t.contrast(tuple(round(c * 255) for c in label["properties"]["color"][:3]), t.PALETTE["solid"]) >= 3
    assert shape["sceneGraphData"]["parent-uid"] is None
    assert shape["sceneGraphData"]["children"] == [{"uid": label["uid"], "flags": t.SCENE_FLAGS}]
    assert label["sceneGraphData"]["parent-uid"] == shape["uid"] and label["sceneGraphData"]["flags"]["v"] is True
    assert list(label)[list(label).index("sceneGraphData") + 1] == "showing"
    t.no_overlap([shape, label])                            # a label inside its shape is a layer on purpose
    # A large button gets the large label; a shape too small for its text names the size to draw.
    t.shape("big-default-000.png", "rect", 384, 192, "solid")
    assert t.button("Big", "big-default-000.png", "BigLabel", "继续", 0, 0)[1]["properties"]["size"] == t.TEXT_SIZE["title"]
    t.shape("small-default-000.png", "rect", 96, 96, "solid")
    with pytest.raises(SystemExit, match=r"needs a shape of 256x96 px and images/small-default-000.png is 96x96; "
                                         r"draw it at button_size\('重新开始'\)"):
        t.button("Small", "small-default-000.png", "SmallLabel", "继续", 0, 0, longest="重新开始")
    # A hidden button starts with its label hidden.
    hidden = t.sprite_inst("Panel", 0, 0, 96, 96)
    hidden["properties"]["initially-visible"] = False
    child = t.text_inst("PanelText", "", 0, 0, 96, 96)
    t.link(hidden, child)
    assert child["properties"]["initially-visible"] is False


def test_template_screen_is_named_bands_and_the_stage_sizes_its_main_object():
    """bands() names the parts of a screen, so a label goes into a band by name and the builder
    computes every position; fit() sizes the stage's main object to a share of the stage, and
    labelled_bar() keeps a bar's name in front of it."""
    t = template_module()
    assert t.bands() == {"title": (32, 32, 656, 128), "status": (32, 160, 656, 64), "stage": (32, 256, 656, 896),
                         "hint": (32, 1184, 656, 64)}
    assert t.bands(title=False)["status"] == (32, 32, 656, 64) and t.bands(title=False)["stage"] == (32, 128, 656, 1024)
    assert t.fit(1, 1) == (12, 12) and t.fit(5, 3) == (12, 7)        # 60% of the stage across, proportions kept
    assert t.stage_cell(12, 12) == (5, 16)
    score = t.band_text("Score", "Score: 0", "status", "left", longest="Score: 999")
    timer = t.band_text("Timer", "Time: 30", "status", "right")
    assert (score["world"]["x"], score["world"]["y"]) == (32, 160) and timer["world"]["x"] + timer["world"]["width"] == 688
    t.no_overlap([score, timer])
    title = t.band_text("Title", "开关按钮", "title")
    assert title["properties"]["size"] == t.TEXT_SIZE["title"] and title["world"]["y"] == 32
    assert t.band_text("Title", "一个很长很长很长的标题", "title")["properties"]["size"] == t.TEXT_SIZE["body"]
    with pytest.raises(SystemExit, match=r"the hint band 656; it holds about 15 Chinese characters"):
        t.band_text("Hint", "点" * 20, "hint")
    with pytest.raises(SystemExit, match=r"'side' is no band; the bands are title, status, stage, hint"):
        t.band_text("Hint", "x", "side")
    name, frame, fill = t.labelled_bar("HpName", "HP", "HpFrame", "HpFill", "top-left", 192)
    assert name["world"]["x"] == 32 and frame["world"]["x"] - 96 == name["world"]["x"] + name["world"]["width"] + 32
    t.no_overlap([name, frame, fill])


def test_template_bar_grows_from_its_left_edge_inside_its_frame():
    """hud_bar() is the reference's bar as one call: a Tiled Background fill, origin on the left,
    inset in a frame held by anchor(); its width comes from bar_width(), clamped to the frame;
    the instance properties are the editor's, every key in the plugin's schema."""
    t = template_module()
    frame, fill = t.hud_bar("HpFrame", "HpFill", "top-left", 384, dy=3)
    assert (frame["world"]["x"], frame["world"]["y"], frame["world"]["width"], frame["world"]["height"]) == (224, 144, 384, 32)
    assert (fill["world"]["x"], fill["world"]["y"], fill["world"]["width"], fill["world"]["height"]) == (34, 144, 380, 28)
    assert (fill["world"]["originX"], fill["world"]["originY"], fill["properties"]["origin"]) == (0, 0.5, "left")
    assert frame["properties"]["origin"] == "center" and "Tween" in fill["behaviors"]
    t.no_overlap([t.hud_text("ScoreText", "Score: 0", "top-left", longest="Score: 999"), frame, fill])
    assert t.bar_width("hp", "HP_MAX", 380) == "clamp(hp / HP_MAX, 0, 1) * 380"
    tween = t.tween_width("HpFill", "hp", t.bar_width("hp", "HP_MAX", 380))
    assert tween["id"] == "tween-one-property" and tween["parameters"]["property"] == "offsetWidth"
    assert t.set_width("HpFill", "1")["id"] == "set-width"
    types = t.bar_types("HpFrame", "HpFill")
    assert [types[k]["plugin-id"] for k in ("HpFrame", "HpFill")] == ["TiledBg", "TiledBg"]
    assert types["HpFill"]["image"]["originX"] == 0 and types["HpFill"]["behaviorTypes"][0]["behaviorId"] == "Tween"
    # project.c3proj lists every plugin and behavior the types use, so a bar added later is not refused for its addon.
    assert [(a["type"], a["id"], a["name"]) for a in t.used_addons(types, {})] == [("plugin", "TiledBg", "Tiled Background"), ("behavior", "Tween", "Tween")]
    caps_frame, caps_fill = t.hud_bar("HpFrame", "HpFill", "top-left", 384, caps=True)
    assert t.bar_types("HpFrame", "HpFill", caps=True)["HpFill"]["plugin-id"] == "NinePatch"
    assert caps_fill["properties"]["left-margin"] == 2 and caps_fill["properties"]["origin"] == "left"
    for inst, plugin in ((fill, "tiledbg"), (caps_fill, "ninepatch")):
        schema = json.loads((REPO / "data" / "c3-schemas" / "en-US" / "plugins" / f"{plugin}.json").read_text(encoding="utf-8"))
        unknown = set(inst["properties"]) - set(schema.get("properties") or {})
        assert not unknown, (plugin, unknown)


def test_template_draws_only_the_colours_of_its_palette(built, tmp_path):
    """Every pixel the generator draws that shows is a colour of PALETTE: a new object reuses the
    game's colours or names the role a new one plays, and the message says which role is nearest."""
    t = template_module()
    t.ROOT = tmp_path
    for row in png_pixels(built / "images" / "coin-default-000.png"):
        assert {px[:3] for px in row if px[3]} <= set(t.PALETTE.values())
    t.write_png("half.png", 2, 1, lambda x, y: (*t.PALETTE["danger"], 128 if x else 255))   # the shadow's alpha
    t.write_png("clear.png", 1, 1, lambda x, y: (1, 2, 3, 0))                                # a pixel that does not show
    assert png_pixels(tmp_path / "images" / "half.png") == [[(220, 38, 60, 255), (220, 38, 60, 128)]]
    with pytest.raises(SystemExit, match=r"images/heart.png: \(230, 40, 60\) at \(1,0\) is no colour of PALETTE, "
                                         r"nor are 1 more of its colours; the nearest is danger \(220, 38, 60\)\. "
                                         r"Draw with rgb\('danger'\), or add the colour to PALETTE"):
        t.write_png("heart.png", 3, 1, lambda x, y: [(0, 0, 0, 0), (230, 40, 60, 255), (9, 9, 9, 255)][x])
    assert not (tmp_path / "images" / "heart.png").exists()
    t.write_png("gradient.png", 2, 1, lambda x, y: (x * 200, 100, 0, 255), painted=True)     # a painting keeps its colours
    with pytest.raises(SystemExit, match=r"'crimson' is no role of PALETTE, which has canvas, canvas_alt, solid"):
        t.rgb("crimson")
    t.bar_images("HpFrame", "HpFill", caps=True)
    edge, middle = png_pixels(tmp_path / "images" / "hpfill.png")[0][0], png_pixels(tmp_path / "images" / "hpfill.png")[8][8]
    assert (edge[:3], middle[:3]) == (t.PALETTE["ink"], t.PALETTE["ink"])
    assert png_pixels(tmp_path / "images" / "hpframe.png")[8][8][:3] == t.PALETTE["solid"]


def test_template_labels_read_on_what_is_behind_them():
    """A label is FONT at a size of TEXT_SIZE in a role of PALETTE, and one that reads below
    4.5:1 on its backdrop, 3:1 from 18 pt up, large-scale text (WCAG 2.2, 1.4.3), stops the run
    with the roles that would read there."""
    t = template_module()
    assert round(t.contrast((255, 255, 255), (0, 0, 0)), 2) == 21 and t.contrast((30, 34, 48), (30, 34, 48)) == 1
    score = t.hud_text("ScoreText", "Score: 0", "top-left", longest="Score: 999")
    assert (score["properties"]["font"], score["properties"]["size"], score["properties"]["color"]) == \
        ("Arial", 32, t.rgba(t.PALETTE["ink"]))
    assert (t.text_contrast(8), t.text_contrast(17), t.text_contrast(18), t.text_contrast(32)) == (4.5, 4.5, 3, 3)
    t.PALETTE["dim"] = (120, 120, 120)                                   # 3.8:1 on the checker's darker cell
    t.hud_text("TimerText", "Time: 30", "top-right", color="dim")          # 32 pt is large-scale: 3:1 is enough
    with pytest.raises(SystemExit, match=r"TimerText: dim \(120, 120, 120\) on canvas_alt \(238, 238, 234\) reads 3\.8:1; "
                                         r"text of size 12 needs 4\.5:1\. Roles that read on canvas_alt: ink;"):
        t.hud_text("TimerText", "Time: 30", "top-right", size=12, color="dim")
    t.PALETTE["dim"] = (150, 150, 150)                                   # 2.6:1
    with pytest.raises(SystemExit, match=r"text of size 32 needs 3:1"):
        t.hud_text("TimerText", "Time: 30", "top-right", color="dim")
    t.PALETTE["dim"] = (120, 120, 120)
    banner = t.hud_text("WinText", "YOU WIN", "center", size=t.TEXT_SIZE["title"], color="dim")
    assert banner["properties"]["size"] == 64 and banner["properties"]["color"][:3] == [120 / 255] * 3
    with pytest.raises(SystemExit, match=r"LivesText: flash \(255, 255, 255\) on canvas \(250, 250, 247\) reads 1\.0:1; "
                                         r".* Roles that read on canvas: solid, dim, ink, reward, danger;"):
        t.hud_text("LivesText", "Lives", "top", color="flash", on="canvas")
    game = t.layout("Game", [t.layer("Background", transparent=False), t.layer("UI", parallax=0)], sheet="Game")
    assert [layer["backgroundColor"] for layer in game["layers"]] == [t.rgba(t.PALETTE["canvas"]), [1, 1, 1, 1]]


def test_template_samples_a_pixel_art_viewport_nearest_and_scales_it_by_whole_numbers():
    """The viewport decides the art: at 360 px high or less the grid is 8 px, the text sizes follow
    it and the project samples Nearest at a whole-number scale, as every official example at that
    size samples and 116 of 159 scale; a larger viewport keeps what the project has."""
    t = template_module()
    p = t.build_project({"properties": {}}, {}, {}, [], {}, [])
    assert (t.PIXEL_ART, p["properties"]["sampling"], p["properties"]["fullscreenMode"]) == (False, "trilinear", "letterbox-scale")
    small = template_module(VIEW="VIEW_W, VIEW_H = 320, 180")
    assert (small.UNIT, small.TOUCH, small.PIXEL_ART, small.TEXT_SIZE) == (8, 24, True, {"body": 8, "title": 16})
    p = small.build_project({"properties": {"sampling": "trilinear"}}, {}, {}, [], {}, [])
    assert (p["properties"]["sampling"], p["properties"]["fullscreenMode"]) == ("nearest", "letterbox-integer-scale")


def test_look_manifest_matches_the_template():
    """assets/look-manifest.json is what an agent hands a model and confirms against: every value
    it names in the template is the template's, and every status is one it defines."""
    manifest = json.loads((SKILL / "assets" / "look-manifest.json").read_text(encoding="utf-8"))
    t = template_module()
    ids = [r["id"] for r in manifest["rules"]]
    assert len(ids) == len(set(ids))
    for rule in manifest["rules"]:
        assert rule["status"] in manifest["status"], rule["id"]
        if rule["status"] in ("enforced", "adopted", "open") and "value" in rule:
            assert eval(rule["template"], vars(t)) == eval(rule["value"], vars(t)), rule["id"]
        if rule["status"] == "open":
            assert rule.get("options"), rule["id"]
        named = rule.get("helpers", "") + ("" if "value" in rule else rule.get("template", ""))
        for name in re.findall(r"(\w+)\(\)", named):
            assert callable(getattr(t, name, None)), (rule["id"], name)
    assert {r["id"] for r in manifest["rules"] if r.get("strict")} >= {
        "alpha.pure", "grid.shape-size", "grid.world-placement", "grid.runtime-spawn"}


def test_template_keeps_alpha_pure_and_shapes_on_the_grid(tmp_path):
    """A drawn image is clear, opaque or the shadow's alpha, with nothing under a clear pixel; a
    shape covers whole cells and is placed by its cell; on_grid() stops a world instance off it."""
    t = template_module()
    t.ROOT = tmp_path
    t.write_png("clear.png", 1, 1, lambda x, y: (1, 2, 3, 0))
    assert png_pixels(tmp_path / "images" / "clear.png") == [[(0, 0, 0, 0)]]
    with pytest.raises(SystemExit, match=r"images/soft.png: alpha 37 at \(0,0\); a drawn image is clear, opaque "
                                         r"or the shadow's 128"):
        t.write_png("soft.png", 1, 1, lambda x, y: (*t.PALETTE["danger"], 37))
    t.write_png("glow.png", 1, 1, lambda x, y: (1, 2, 3, 37), painted=True)
    with pytest.raises(SystemExit, match=r"box.png: 40x32 is not whole units of 32 px; .* 64x32 here"):
        t.shape("box.png", "rect", 40, 32, "reward")
    t.SHAPE_STYLE.update(shadow_angle=225)                          # a shadow up and to the left
    t.shape("box.png", "rect", 64, 32, "reward")
    inst = t.shape_inst("Box", "box.png", 3, 5)
    w = inst["world"]
    left, top = w["x"] - w["originX"] * w["width"], w["y"] - w["originY"] * w["height"]
    assert (left + t.PADS["box.png"][0], top + t.PADS["box.png"][1]) == (96, 160)
    t.on_grid([inst], "layer Game")
    inst["world"]["x"] += 5
    with pytest.raises(SystemExit, match=r"layer Game: Box starts at .* off the 32 px grid. Place a shape with shape_inst"):
        t.on_grid([inst], "layer Game")
    assert t.grid_random(0, 624) == "32 * floor(random(0, 20))"


def test_template_art_shows_the_stand_in_until_its_picture_is_there(tmp_path):
    """art() draws the stand-in shape until art/<file> holds the fitted picture, then copies it in
    with the stand-in's box, origin and polygon, so the layouts and events stay as they are."""
    t = template_module()
    t.ROOT = tmp_path
    f = t.art("gem-default-000.png", "circle", 64, 64, "reward", "a red gem")
    assert t.DRAWN_AS["gem-default-000.png"][0] == "circle" and t.ART["gem-default-000.png"]["subject"] == "a red gem"
    stand_in = (tmp_path / "images" / "gem-default-000.png").read_bytes()
    assert f["width"] == 64                                         # the plain sheet casts no shadow
    t.art("sky-default-000.png", "scene", 128, 64, "canvas", "a night sky")
    assert t.drawn("sky-default-000.png")["width"] == 128           # a flat rectangle, no shadow
    with pytest.raises(SystemExit, match=r"art\('x.png'\): 'star' is no kind; art\(\) takes rect, circle, triangle or scene"):
        t.art("x.png", "star", 64, 64, "reward", "a star")
    with pytest.raises(SystemExit, match=r"art\('x.png'\): say what the picture shows"):
        t.art("x.png", "rect", 64, 64, "reward", " ")

    t.write_png("../art/gem-default-000.png", 64, 64, lambda x, y: (200, 30, 30, 255 if x > 8 else 90), painted=True)
    t.write_png("../art/gem-default-000.hit.png", 64, 64, lambda x, y: (255, 255, 255, 255 if x > 8 else 90),
                painted=True)
    f = t.art("gem-default-000.png", "circle", 64, 64, "reward", "a red gem", oy=1)
    assert (tmp_path / "images" / "gem-default-000.png").read_bytes() != stand_in
    assert (f["width"], f["height"], f["originY"], t.PADS["gem-default-000.png"]) == (64, 64, 1, (0, 0))
    assert len(f["collisionPoly"]["points"]) == 32
    hit = t.hit_frame("gem-default-000.png")
    assert hit["tag"] == "hit" and hit["imageSpriteId"] != f["imageSpriteId"] and f["tag"] == ""
    assert png_pixels(tmp_path / "images" / "gem-default-001.png")[0][20] == (255, 255, 255, 255)
    inst = t.shape_inst("Gem", "gem-default-000.png", 2, 3)
    assert (inst["world"]["x"], inst["world"]["y"]) == (96, 160)
    with pytest.raises(SystemExit, match=r"art/gem-default-000.png is 64x64, and art\(\) asks 96x96: put the picture "
                                         r"in art/raw/ and run the skill's scripts/prepare_art.py.* or delete"):
        t.art("gem-default-000.png", "circle", 96, 96, "reward", "a red gem")


def test_template_squashes_the_art_on_a_hit_a_landing_and_a_jump():
    """A squash stops the one the object is in, sets a share of the image's size, holds it for a
    jump, and tweens back under "squash"; one acting on an object that collides stops the run."""
    t = template_module()
    stop, squash, back = t.squash("Coin", "hit")
    assert stop == {**stop, "id": "stop-tweens", "behaviorType": "Tween", "parameters": {"tags": '"squash"'}}
    assert squash["parameters"] == {"width": "Self.ImageWidth * 0.8", "height": "Self.ImageHeight * 1.2"}
    assert (back["parameters"]["tags"], back["parameters"]["end-x"], back["parameters"]["time"],
            back["parameters"]["ease"]) == ('"squash"', "Self.ImageWidth", "0.25", "easeoutback")
    _, land, back = t.squash("PlayerArt", "land")
    assert land["parameters"]["width"] == "Self.ImageWidth * 1.2" and back["parameters"]["ease"] == "easeoutelastic"
    _, jump, hold, back = t.squash("PlayerArt", "jump")
    assert (jump["parameters"]["height"], hold["parameters"]["seconds"], back["parameters"]["time"]) == \
        ("Self.ImageHeight * 1.3", "0.2", "0.75")
    with pytest.raises(SystemExit, match=r"squash\('PlayerArt', 'spin'\): the kinds are hit, land, jump"):
        t.squash("PlayerArt", "spin")
    t.squash_the_art({"PlayerArt": {"behaviorTypes": [t.beh_def("Tween")]}}, {})
    with pytest.raises(SystemExit, match=r"squash\('Player'\): Player has Platform and collides, .* squash its art"):
        t.squash("Player", "land")
        t.squash_the_art({"Player": {"behaviorTypes": [t.beh_def("Platform"), t.beh_def("Tween")]}}, {})


def test_template_shows_a_hit_as_a_frame_of_the_flash_colour(built, tmp_path):
    """A hit is the shape's second frame, the same outline and shadow filled in HIT_FLASH's role
    and tagged "hit", shown for HIT_FLASH["seconds"] of real time and then frame 0 again; the
    Flash behavior stops the run."""
    rest = png_pixels(built / "images" / "coin-default-000.png")
    hit = png_pixels(built / "images" / "coin-default-001.png")
    t = template_module()
    middle = len(rest) // 3
    assert rest[middle][middle][:3] == t.PALETTE["reward"] and hit[middle][middle][:3] == t.PALETTE["flash"]
    assert [[p[3] for p in row] for row in rest] == [[p[3] for p in row] for row in hit]     # same shape and shadow
    coin = json.loads((built / "objectTypes" / "Coin.json").read_text(encoding="utf-8"))
    assert [f["tag"] for f in coin["animations"]["items"][0]["frames"]] == ["", "hit"]
    show, pause, back = t.hit_flash("Coin")
    assert (show["parameters"], back["parameters"]) == ({"frame-number": '"hit"'}, {"frame-number": "0"})
    assert pause["parameters"] == {"seconds": "0.08", "use-timescale": False}
    assert [a["id"] for a in t.hit("Coin")] == ["stop-tweens", "set-size", "tween-two-properties",
                                                "set-animation-frame", "wait", "set-animation-frame"]
    code, out = tool(built, "print_sheet")
    assert 'Coin: Set size to (Self.ImageWidth * 0.8, Self.ImageHeight * 1.2)' in out
    assert 'Coin: Set animation frame to "hit"' in out and "System: Wait 0.08 seconds (use time scale: False)" in out, out
    t.ROOT = tmp_path
    with pytest.raises(SystemExit, match=r"hit_frame\('ball.png'\): draw the frame first"):
        t.hit_frame("ball.png")
    with pytest.raises(SystemExit, match=r"Blink: a hit shows as a colour, not the Flash behavior's blinking"):
        t.beh_def("Flash", "Blink")


def test_template_writes_instances_in_the_editors_key_order_and_number_form(tmp_path):
    """The editor saves a world instance with materialSurfaceType between its effects and
    showing, and every number in its shortest form; anything else comes back changed in the
    diff of the next save."""
    t = template_module()
    t.ROOT = tmp_path
    inst = t.instance("Wall", {}, t.world(108, 284.0, 35, 96, angle=-0.0))
    assert list(inst) == ["type", "properties", "uid", "sid", "tags", "instanceVariables", "behaviors",
                          "materialSurfaceType", "showing", "locked", "world"]
    assert inst["materialSurfaceType"] == "smooth"
    assert "materialSurfaceType" not in t.instance("Data", {}, None)
    t.write_json("i.json", inst)
    text = (tmp_path / "i.json").read_text(encoding="utf-8")
    assert '"y": 284,' in text and '"angle": 0' in text and ".0" not in text


def test_template_writes_a_data_file_lists_it_and_loads_it_at_start(project):
    """A table of records is a project file loaded at start, not hundreds of Add key actions: a
    generated card game put its cards into a Dictionary from events, each value a "|"-joined
    string, and then into 616 flat keys of a Dictionary file nobody could read as a table. The
    records are an Array with a record per row, as grukkle-onslaught keeps its enemies, copied
    into a Dictionary at start. The files are written in the formats eventide and
    airborne-explorer ship, listed as the editor lists them, and loaded with the three actions
    eventide's On start runs."""
    source = project / "tools" / "build_project.py"
    text = source.read_text(encoding="utf-8")
    cards = '{"strike": {"name": "Strike", "cost": 1, "dmg": 6}, "guard": {"name": "Guard", "cost": 1, "block": 5}}'
    for old, new in (
            ('    The stand-in has none."""\n',
             f'    The stand-in has none."""\n    record_table("CardTable", {cards})\n'
             '    dictionary_file("Settings", {"startGold": 60})\n'),
            ('        "Touch": single_global_type(',
             '        "CardTable": nonworld_type("CardTable", "Arr"),\n'
             '        "Cards": nonworld_type("Cards", "Dictionary"),\n'
             '        "Settings": nonworld_type("Settings", "Dictionary"),\n'
             '        "Touch": single_global_type('),
            ('    ], sheet="Game")',
             '    ], sheet="Game", nonworld=[nonworld_inst("CardTable", {"width": 1, "height": 1, "depth": 1}), '
             'nonworld_inst("Cards"), nonworld_inst("Settings")])'),
            ('[on_start()], [set_var("score", "0"), set_text("ScoreText", q("Score: 0"))], children=[',
             '[on_start()], steps(("Load the cards", load_data_file("CardTable", "CardTable.json")), '
             '("Load the settings", load_data_file("Settings", "Settings.json")), '
             '("Empty the score", [set_var("score", "0"), set_text("ScoreText", q("Score: 0"))])), children=['
             '*table_to_dictionary("CardTable", "Cards"), ')):
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    source.write_text(text, encoding="utf-8")
    code, out = run(project, "tools/build_project.py")
    assert code == 0 and warnings(out) == [], out

    table = json.loads((project / "files" / "CardTable.json").read_text(encoding="utf-8"))
    columns = [[cell[0] for cell in column] for column in table["data"]]
    assert table["c2array"] and table["size"] == [5, 3, 1]
    assert [list(row) for row in zip(*columns)] == [
        ["id", "name", "cost", "dmg", "block"], ["strike", "Strike", 1, 6, 0], ["guard", "Guard", 1, 0, 5]]
    assert json.loads((project / "files" / "Settings.json").read_text(encoding="utf-8")) == {
        "c2dictionary": True, "data": {"startGold": 60}}
    proj = json.loads((project / "project.c3proj").read_text(encoding="utf-8"))
    listed = proj["rootFileFolders"]["general"]["items"]
    assert [(e["name"], e["type"], e["file-info"]) for e in listed] == [
        ("CardTable.json", "application/json", {"purpose": "none"}),
        ("Settings.json", "application/json", {"purpose": "none"})]
    assert {"AJAX", "Arr", "Dictionary"} <= {a["id"] for a in proj["usedAddons"]} and "AJAX" in proj["objectTypes"]["items"]

    sheet = json.loads((project / "eventSheets" / "Game.json").read_text(encoding="utf-8"))
    loading = [a for e in every_event(sheet["events"]) for a in e.get("actions", [])
               if a.get("id") in ("request-project-file", "wait-for-previous-actions", "load", "add-key")]
    assert [(a["id"], a["objectClass"]) for a in loading] == [
        ("request-project-file", "AJAX"), ("wait-for-previous-actions", "System"), ("load", "CardTable"),
        ("request-project-file", "AJAX"), ("wait-for-previous-actions", "System"), ("load", "Settings"),
        ("add-key", "Cards")]
    assert loading[0]["parameters"] == {"tag": '"CardTable"', "file": "CardTable.json"}
    assert loading[-1]["parameters"] == {
        "key": 'CardTable.At(0, loopindex("row")) & "." & CardTable.At(loopindex("field"), 0)',
        "value": 'CardTable.At(loopindex("field"), loopindex("row"))'}

    t = template_module()
    with pytest.raises(SystemExit, match=r"'strike': \{.*\} is not a number or a string.*record_table"):
        t.dictionary_file("Cards", {"strike": {"cost": 1}})
