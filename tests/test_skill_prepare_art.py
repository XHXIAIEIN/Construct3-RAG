"""prepare_art.py: the image tool's pictures cut out, fitted to the boxes art() asks for, and taken
by the generator in place of the stand-ins."""
import json

import pytest

from tests.skill_helpers import run, tool

PIL = pytest.importorskip("PIL")
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

MAGENTA = (255, 0, 255)


def picture(path, bg=MAGENTA, r=200, shadow=True, stripes=False):
    """A picture as an image model makes one: a gold coin with soft edges on a key colour that
    is not quite flat, a darker patch of that colour under it, saved as a JPEG."""
    img = Image.new("RGB", (512, 512), bg)
    d = ImageDraw.Draw(img)
    for y in range(0, 512, 8):
        d.rectangle([0, y, 512, y + 7], fill=tuple(max(0, v - y // 64) for v in bg))
    if stripes:
        for x in range(0, 512, 32):
            d.rectangle([x, 0, x + 15, 512], fill=(x % 256, 120, 40))
    if shadow:
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).ellipse([96, 236 + r - 20, 416, 236 + r + 40], fill=160)
        img = Image.composite(Image.new("RGB", img.size, tuple(v // 2 for v in bg)), img,
                              mask.filter(ImageFilter.GaussianBlur(12)))
        d = ImageDraw.Draw(img)
    d.ellipse([256 - r, 236 - r, 256 + r, 236 + r], fill=(150, 100, 20))
    d.ellipse([256 - r + 24, 236 - r + 24, 256 + r - 24, 236 + r - 24], fill=(240, 190, 40))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.filter(ImageFilter.SMOOTH).save(path, quality=85)


def test_prepare_art_lists_a_prompt_for_each_picture_to_make(project):
    code, out = tool(project, "prepare_art", "--list")
    lines = out.splitlines()
    assert code == 0, out
    assert lines[0].startswith("style: none. Write ART_STYLE in tools/build_project.py first")
    assert "make coin-default-000: ratio 1:1, for a 96x96 box -> art/raw/coin-default-000.png" in lines
    assert ('  "a gold coin seen from the front. One subject, whole and centred with room around it, on a flat '
            'magenta #FF00FF background: no scenery, no shadow on the ground, no text."') in lines
    assert lines[-1] == ("to make: 1, to prepare: 0, done: 0; next: make each with the image tool, then python "
                         ".agents/skills/construct3-agent-plugin/scripts/prepare_art.py")
    assert (project / "art" / "raw").is_dir()

    wanted = json.loads((project / "art" / "wanted.json").read_text(encoding="utf-8"))
    wanted["style"] = "Bright flat vector, thick dark outlines."
    wanted["images"] += [{"file": "rose-default-000.png", "kind": "circle", "width": 64, "height": 64,
                          "origin": [0.5, 0.5], "subject": "a pink rose"},
                         {"file": "sky-default-000.png", "kind": "scene", "width": 720, "height": 1280,
                          "origin": [0, 0], "subject": "a night sky over hills"}]
    (project / "art" / "wanted.json").write_text(json.dumps(wanted), encoding="utf-8")
    code, out = tool(project, "prepare_art", "--list")
    assert "style: Bright flat vector, thick dark outlines." in out
    assert 'key picture: make it first, "Bright flat vector, thick dark outlines; a line-up of' in out
    assert "a pink rose. One subject, whole and centred with room around it, on a flat green #00FF00" in out
    assert "make sky-default-000: ratio 9:16, for a 720x1280 box" in out
    assert "a night sky over hills. A full-frame background scene, no characters in front, no text." in out

    (project / "art" / "wanted.json").unlink()
    code, out = tool(project, "prepare_art")
    assert code == 2 and "no art/wanted.json" in out and "give every sprite an art()" in out


def test_prepare_art_cuts_out_a_picture_and_the_generator_takes_it(project):
    picture(project / "art" / "raw" / "coin-default-000.jpg")
    code, out = tool(project, "prepare_art")
    assert code == 0, out
    assert ("coin-default-000: coin-default-000.jpg 512x512, background #" in out
            and "-> art/coin-default-000.png 96x96" in out), out
    assert out.splitlines()[-1] == "ok: 1 pictures in art/; next: python tools/build_project.py"
    code, out = tool(project, "prepare_art", "--list")
    assert out.splitlines()[-1] == "ok: all 1 pictures done; next: python tools/build_project.py", out
    img = Image.open(project / "art" / "coin-default-000.png")
    assert img.mode == "RGBA" and img.size == (96, 96) and img.info.get("c3-art") == "painted"
    px = img.load()
    assert px[0, 0] == (0, 0, 0, 0) and px[48, 48][3] == 255 and px[48, 48][0] > 200
    shown = [px[x, y] for x in range(96) for y in range(96) if px[x, y][3]]
    fringe = [p for p in shown if p[0] > 120 and p[1] < 60 and p[2] > 120 and p[3] > 32]
    assert not fringe, f"the key or its shadow is left: {fringe[:5]}"
    assert all(px[x, y] == (0, 0, 0, 0) for x in range(96) for y in range(96) if not px[x, y][3])
    assert any(0 < p[3] < 255 for p in shown), "the edge is blended"
    hit = Image.open(project / "art" / "coin-default-000.hit.png").load()
    assert all(hit[x, y][3] == px[x, y][3] for x in range(96) for y in range(96))
    assert hit[48, 48] == (255, 255, 255, 255)

    code, out = run(project, "tools/build_project.py")
    assert code == 0 and "art: all 1 images from art/" in out, out
    assert (project / "images" / "coin-default-000.png").read_bytes() == \
        (project / "art" / "coin-default-000.png").read_bytes()
    coin = json.loads((project / "objectTypes" / "Coin.json").read_text(encoding="utf-8"))
    frames = coin["animations"]["items"][0]["frames"]
    assert [(f["width"], f["height"], f["tag"]) for f in frames] == [(96, 96, ""), (96, 96, "hit")]
    assert len(frames[0]["collisionPoly"]["points"]) == 32          # the stand-in's circle
    code, out = tool(project, "check_look")
    assert code == 0 and out.splitlines()[-1].startswith("ok: 3 images"), out


def test_prepare_art_refuses_a_picture_it_cannot_cut_out(project):
    picture(project / "art" / "raw" / "coin-default-000.jpg", stripes=True)
    code, out = tool(project, "prepare_art")
    assert code == 1, out
    assert "coin-default-000: coin-default-000.jpg: its edge is not one flat colour" in out
    assert "make it again on a flat magenta #FF00FF background, or with a transparent one" in out
    assert out.splitlines()[-1] == ("prepared: 0, could not use: 1, still to make: 0; next: make the pictures above "
                                    "again as their lines say, then run this again")
    picture(project / "art" / "raw" / "coin-default-000.jpg", r=270, shadow=False)
    code, out = tool(project, "prepare_art")
    assert code == 1 and "the subject runs off the picture over" in out and "make it again whole" in out, out


def test_prepare_art_fits_a_scene_and_keeps_a_picture_with_transparency(project):
    wanted = json.loads((project / "art" / "wanted.json").read_text(encoding="utf-8"))
    wanted["images"].append({"file": "sky-default-000.png", "kind": "scene", "width": 720, "height": 1280,
                             "origin": [0, 0], "subject": "a night sky"})
    (project / "art" / "wanted.json").write_text(json.dumps(wanted), encoding="utf-8")
    (project / "art" / "raw").mkdir(parents=True)
    Image.new("RGB", (1365, 768), (20, 30, 80)).save(project / "art" / "raw" / "sky-default-000.jpg")
    cut = Image.new("RGBA", (300, 600), (0, 0, 0, 0))
    ImageDraw.Draw(cut).rectangle([100, 100, 200, 500], fill=(30, 140, 220, 255))
    cut.save(project / "art" / "raw" / "coin-default-000.png")
    code, out = tool(project, "prepare_art")
    assert code == 0, out
    assert "sky-default-000: sky-default-000.jpg 1365x768 -> art/sky-default-000.png 720x1280, cropped to cover it" in out
    assert "coin-default-000.png 300x600, its own transparency" in out
    assert "note: the subject, 24x96, fills 25% of its 96x96 box; give art() a box of the subject's shape" in out, out
    sky = Image.open(project / "art" / "sky-default-000.png")
    assert sky.size == (720, 1280) and sky.getpixel((0, 0))[3] == 255
