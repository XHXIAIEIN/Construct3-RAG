"""review_look.py: the mechanical findings over the instances a layout holds, and
what the run prints. The browser is not started: the checks are pure functions
of what LOOK_JS reads from the runtime."""
import sys

from tests.skill_helpers import SKILL, INSTALLED, run

LAYERS = {"Game": {"parallax": [1, 1], "shown": True, "view": [0, 0, 1280, 720]},
          "UI": {"parallax": [0, 0], "shown": True, "view": [0, 0, 1280, 720]}}


def module():
    sys.path.insert(0, str(SKILL / "scripts"))
    try:
        import review_look as rl
    finally:
        sys.path.pop(0)
    return rl


def inst(uid, kind, box, layer="UI", **extra):
    return {"type": kind, "uid": uid, "layer": layer, "box": box, "shown": True, "angle": 0, "root": uid, **extra}


def text(uid, kind, box, words, size, layer="UI", align=("center", "center"), **extra):
    return inst(uid, kind, box, layer, text=words, textSize=size, align=list(align), **extra)


def snap(*instances, size=(1280, 720)):
    return {"layout": "Map", "size": list(size), "viewport": [1280, 720], "layers": LAYERS,
            "instances": list(instances)}


def pairs(found):
    return [(f["rule"], f["uids"]) for f in found]


def rules(rl, *instances, **kw):
    return pairs(rl.findings(snap(*instances, **kw)))


def test_review_look_finds_a_text_its_box_cuts_or_wraps():
    """A text wider than its box is cut; one taller by a second line wraps beyond it.
    A single line a little taller than its box draws whole."""
    rl = module()
    found = rl.findings(snap(
        text(1, "HelpText", [592, 170, 688, 202], "选择前进之路", [144, 28]),
        text(2, "ResultText", [560, 300, 720, 364], "得分 1500 最高 0", [92, 165]),
        text(3, "CardName", [580, 240, 700, 260], "金刃风暴", [85, 25]),
        text(4, "Hidden", [0, 0, 10, 10], "too long for its box", [200, 20], shown=False),
        text(5, "Turned", [0, 0, 10, 10], "too long for its box", [200, 20], angle=0.5)))
    assert pairs(found) == [("text", [1]), ("text", [2])], found
    assert 'HelpText uid 1 "选择前进之路": the text needs 144x28 px and its box is 96x32' in found[0]["line"]
    assert "make the box at least 144x32 or the font smaller" in found[0]["line"]


def test_review_look_finds_instances_created_and_never_moved_apart():
    """The names of five cards on one card: one finding for the group, with the texts."""
    rl = module()
    names = ["木灵护体", "金刃风暴", "剑意通玄", "苍木缠身", "水火既济"]
    found = rl.findings(snap(*[text(10 + n, "CardName", [300, 420, 420, 450], w, [80, 24], layer="Game")
                               for n, w in enumerate(names)],
                             inst(20, "Card", [100, 400, 220, 560], layer="Game")))
    assert pairs(found) == [("stacked", [10, 11, 12, 13, 14])], found
    assert found[0]["line"].startswith("CardName: 5 instances on one box at (300, 420) 120x30, uids 10, 11")
    assert "set each one's position from the instance it belongs to" in found[0]["line"]
    assert rules(rl, inst(1, "Tiles", [0, 0, 1216, 256], layer="Game"), inst(2, "Tiles", [0, 0, 1216, 256]),
                 inst(3, "Drop", [60, 180, 61, 182], layer="Game"), inst(4, "Drop", [60, 180, 61, 182], layer="Game")) == []


def test_review_look_leaves_out_one_box_that_shows_different_frames():
    """A slot's fill frame under its rim frame, one type on one box, is drawn so on purpose;
    two of the same frame there were never moved apart."""
    rl = module()
    slot = [100, 400, 172, 472]

    def frame(uid, animation, n):
        return inst(uid, "Slot", slot, layer="Game", animation=animation, frame=n, frames=2, playing=False)
    assert rules(rl, frame(1, "Default", 0), frame(2, "Default", 1)) == []
    assert rules(rl, frame(1, "Fill", 0), frame(2, "Rim", 0)) == []
    assert rules(rl, frame(1, "Default", 0), frame(2, "Default", 1), frame(3, "Default", 1)) == [("stacked", [2, 3])]


def test_review_look_finds_overlaps_on_the_hud_but_not_a_label_on_its_button():
    rl = module()
    assert rules(rl,
                 inst(1, "Button", [100, 600, 260, 660]),
                 text(2, "ButtonLabel", [100, 600, 260, 660], "Start", [60, 24]),    # its label
                 inst(3, "Panel", [0, 0, 400, 400]),
                 inst(4, "Icon", [20, 20, 60, 60]),                                  # an icon on its panel
                 inst(5, "Bar", [500, 20, 700, 40], root=9),
                 inst(6, "BarFill", [500, 20, 650, 40], root=9),                     # one hierarchy
                 text(7, "Score", [900, 20, 1100, 60], "Score: 10", [120, 30]),
                 text(8, "ScoreShadow", [904, 24, 1104, 64], "Score: 1", [110, 30]),  # its shadow
                 text(9, "Briefing", [40, 40, 1240, 700], "How to play ...", [1100, 600]),  # over the screen
                 ) == []
    assert rules(rl, inst(1, "BeetleIcon", [352, 0, 384, 32]),
                 text(2, "BeetleCount", [368, 0, 432, 32], "x00", [51, 21], align=("left", "center"))) == []
    found = rules(rl,
                  text(1, "Title", [440, 80, 840, 160], "第1幕", [140, 57]),
                  text(2, "Subtitle", [540, 120, 740, 160], "选择前进之路", [144, 28]),   # over the title
                  inst(3, "EndTurn", [1000, 640, 1160, 700]),
                  inst(4, "DeckCount", [1100, 630, 1180, 700]))                      # most of it over the button
    assert found == [("overlap", [1, 2]), ("overlap", [3, 4])], found


def test_review_look_finds_text_over_text_off_the_hud_only():
    """On a layer that scrolls, a name over its body is left to the picture; a text
    over another text is not."""
    rl = module()
    assert rules(rl, inst(1, "Enemy", [560, 100, 720, 240], layer="Game"),
                 text(2, "EnemyName", [560, 150, 720, 190], "青木妖", [90, 30], layer="Game")) == []
    assert rules(rl, text(1, "EnemyName", [560, 150, 720, 190], "青木妖", [90, 30], layer="Game"),
                 text(2, "Intent", [560, 160, 720, 200], "回复", [60, 30], layer="Game")) == [("overlap", [1, 2])]


def test_review_look_finds_a_hud_instance_the_screen_edge_cuts():
    """Not one waiting wholly off screen to move in, one wider than the screen, or
    art on a world layer that runs off the edge."""
    rl = module()
    found = rl.findings(snap(inst(1, "Hint", [1200, 300, 1400, 340])))
    assert pairs(found) == [("edge", [1])], found
    assert "the right edge of the screen cuts it" in found[0]["line"]
    assert rules(rl, text(5, "Counter", [1200, 0, 1300, 32], "x00", [51, 21], align=("left", "center"))) == []
    assert rules(rl, inst(2, "Popup", [400, -300, 880, -20]),
                 inst(3, "Banner", [-20, 0, 1300, 60]),
                 inst(4, "Rock", [1200, 300, 1400, 340], layer="Game")) == []


def test_review_look_finds_kinds_drawn_with_one_frame():
    """Map nodes of three kinds all on frame 0 of 4; not when the frame plays, when
    the animation has one frame, or when a text on each tells them apart."""
    rl = module()

    def node(uid, kind):    # COL differs too, and is no kind
        return inst(uid, "Node", [100 * uid, 300, 100 * uid + 48, 348], layer="Game", animation="Default", frame=0,
                    frames=4, playing=False, instVars={"NTYPE": kind, "COL": uid})
    kinds = ["C", "E", "C", "R", "C"]
    nodes = [node(uid, k) for uid, k in enumerate(kinds, 1)]
    found = rl.findings(snap(*nodes))
    assert pairs(found) == [("frame", [1, 2, 3, 4, 5])], found
    assert "show animation 'Default' frame 0 of 4, though their NTYPE differs" in found[0]["line"]
    assert rules(rl, dict(nodes[0], playing=True), *nodes[1:]) == []
    assert rules(rl, *[dict(one, frames=1) for one in nodes]) == []
    hidden = [dict(one, instVars={"IsMine": k == "C"}) for one, k in zip(nodes, kinds)]
    assert rules(rl, *hidden) == []         # hidden state, drawn the same on purpose
    labels = [text(10 + uid, "NodeLabel", [100 * uid + 4, 310, 100 * uid + 44, 330], k, [20, 20], layer="Game")
              for uid, k in enumerate(kinds, 1)]
    assert rules(rl, *nodes, *labels) == []


def test_review_look_names_screenshots_by_layout_and_asks_the_questions_once():
    rl = module()
    assert rl.file_name("第1幕 Map") == "第1幕-Map"
    assert rl.file_name("Game/Level:2") == "Game-Level-2"
    finding = rl.findings(snap(text(1, "HelpText", [592, 170, 688, 202], "选择前进之路", [144, 28])))
    lines = rl.report({"project": "Game", "status": "opened", "title": "Game - Construct 3", "editor": "e",
                       "warnings": [], "preview": {"started": True, "errors": [], "layouts": [
                           {"layout": "Map", "shot": ".tmp/look/Map.png", "findings": finding, "errors": []},
                           {"layout": "Combat", "left": "Reward", "errors": ["Event sheet 2, event 4: TypeError"]}]}})
    assert lines[1] == "layout 'Map' (1 of 2): screenshot .tmp/look/Map.png"
    assert lines[2].startswith('  text: HelpText uid 1 "选择前进之路"')
    assert lines[3].startswith("layout 'Combat' (2 of 2): started, and its events went on to 'Reward'")
    assert lines[4] == "  runtime: Event sheet 2, event 4: TypeError"
    assert lines[5].startswith("questions: open each screenshot above with your image tool")
    assert [line[:5] for line in lines[6:]] == [f"  {n}. " for n in range(1, 8)]
    assert all(line.isascii() for line in rl.QUESTIONS)


def test_review_look_prints_its_help_and_needs_a_project(tmp_path, project):
    code, out = run(project, f"{INSTALLED}/scripts/review_look.py", "--help")
    assert code == 0 and "stacked" in out and "exit codes:" in out, out
    empty = tmp_path / "empty"
    empty.mkdir()
    code, out = run(empty, SKILL / "scripts" / "review_look.py")
    assert code == 2 and "no project.c3proj found" in out, out


def test_review_look_says_what_a_clean_run_left_unseen():
    rl = module()
    clean = {"status": "opened", "preview": {"layouts": [{"layout": "Map", "findings": [], "errors": []}]}}
    found = {"status": "opened", "preview": {"layouts": [{"layout": "Map", "findings": [{}], "errors": []}]}}
    assert rl.look_line([clean], 1.0, ".tmp/review-look.json", ".tmp/look") == (
        "look: 0 findings on 1 layout, 0 runtime errors; each layout ran 1 s after a jump to it, without play, so a "
        "scene the game reaches only in play is unseen; full result in .tmp/review-look.json, screenshots in .tmp/look")
    assert "unseen" not in rl.look_line([found], 1.0, ".tmp/review-look.json", ".tmp/look")


def png(w, h, pixel) -> bytes:
    """An RGBA PNG whose pixel at (x, y) is pixel(x, y)."""
    import struct
    import zlib

    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body))
    raw = b"".join(b"\0" + b"".join(bytes(pixel(x, y)) for x in range(w)) for y in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def test_a_screenshot_of_one_colour_dark_or_clear_is_blank():
    """Over 601 screenshots of games the most one-coloured one that showed something was 99.03%."""
    sys.path.insert(0, str(SKILL / "scripts"))
    try:
        import c3project as c3
    finally:
        sys.path.pop(0)
    assert c3.blank_share(png(100, 100, lambda x, y: (30, 90, 200, 255))) == 1
    assert c3.blank_share(png(100, 100, lambda x, y: ((x * 7 + y) % 16, 0, 5, 255))) == 1      # near black, noisy
    assert c3.blank_share(png(100, 100, lambda x, y: (x % 255, y, 9, x % 15))) == 1           # clear
    coin = lambda x, y: (40, 100, 240, 255) if (x - 10) ** 2 + (y - 10) ** 2 < 36 else (0, 0, 0, 255)
    assert c3.blank_share(png(100, 100, coin)) is None          # a coin on black: 1.1% drawn
    assert c3.blank_share(png(100, 100, lambda x, y: (255, 255, 255, 255) if x else (0, 0, 0, 255))) is None


def test_review_look_retakes_a_blank_screenshot_and_asks_nothing_about_one_that_stays_blank():
    rl = module()
    lines = rl.report({"project": "Game", "status": "opened", "title": "Game - Construct 3", "editor": "e",
                       "warnings": [], "preview": {"started": True, "errors": [], "layouts": [
                           {"layout": "Objects", "shot": ".tmp/look/Objects.png", "findings": [], "errors": [],
                            "blank": {"tries": 3, "share": 0.99995}}]}})
    assert lines[1] == ("layout 'Objects' (1 of 1): screenshot .tmp/look/Objects.png: 99.9% or more of it is one "
                        "colour after 3 shots 1 s apart, so the layout draws nothing in view at its start, or the preview "
                        "did not draw it. No question is asked about it. If it should show something, raise --settle, "
                        "or reach it in play with a shot step of a preview_project.py plan")
    assert not any(line.startswith("questions:") for line in lines)
    lines = rl.report({"project": "Game", "status": "opened", "title": "Game - Construct 3", "editor": "e",
                       "warnings": [], "preview": {"started": True, "errors": [], "layouts": [
                           {"layout": "Map", "shot": ".tmp/look/Map.png", "findings": [], "errors": [],
                            "blank": {"tries": 2, "share": None}}]}})
    assert lines[1] == ("layout 'Map' (1 of 1): screenshot .tmp/look/Map.png, taken when the layout was drawn; the "
                        "shot before showed one colour, not drawn yet")
    assert lines[2].startswith("questions:")
