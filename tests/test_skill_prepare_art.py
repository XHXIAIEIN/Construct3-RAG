"""prepare_art.py: the image tool's pictures cut out, fitted to the boxes art() asks for, and taken
by the generator in place of the stand-ins."""
import json
import math
import os
import sys
from pathlib import Path

import pytest

from tests.skill_helpers import SKILL, edit, run, tool

pytest.importorskip("PIL", reason="Pillow is not installed; pip install pillow")
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

sys.path.insert(0, str(SKILL / "scripts"))
import prepare_art  # noqa: E402

MAGENTA = (255, 0, 255)
KEYS = prepare_art.KEYS
SS = 4                                          # the figure is drawn at this many times its size
OUTLINE, SKIN, SHIRT, WHITE = (28, 18, 16), (238, 206, 178), (245, 245, 240), (252, 252, 252)
RED, GREEN_HAIR, GOLD, HOT_PINK = (200, 40, 30), (90, 190, 60), (230, 180, 40), (249, 40, 142)
GREEN_HEART = (17, 207, 99)                                       # 92 from the key, as on a real picture
PAINTED = {"magenta": (250, 4, 240), "green": (6, 246, 10)}      # the key as a model paints it
POCKET = {"magenta": (215, 40, 200), "green": (40, 200, 35)}     # the key seen through a gap, about 60 off
RING = (20, 128, 32, 140)                                         # the gap, in pixels
SPILL = [(70, 60), (90, 56), (80, 66)]                          # 2x2 spots of key light in the hair


def picture(path: Path, bg: tuple[int, int, int] = MAGENTA, r: int = 200, shadow: bool = True,
            stripes: bool = False) -> None:
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


def figure(key: str, spill: bool = True, hair: tuple | None = None, gap: bool = True) -> tuple:
    """A figure whose matte is known, (truth, picture): drawn at SS times its size and box-reduced,
    so its edge has every alpha, then laid over the key as a model paints it. A face with white
    eye highlights over a white shirt, a hair cap with strands 0.5 to 2 px wide, a ring of hair
    with the key showing through it, a heart in a colour near the key (hot pink under magenta,
    green under green), a red ball under magenta or a gold ball under green, and spots where the
    key's light falls on the hair. Without `gap`, the key shows through the ring unshaded."""
    w, h = 160, 200
    hair = hair or (GREEN_HAIR if key == "magenta" else RED)
    big = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)

    def at(*v):
        return [round(x * SS) for x in v]

    d.ellipse(at(33.8, 73.8, 126.2, 166.2), fill=OUTLINE)
    d.pieslice(at(36, 76, 124, 164), 180, 360, fill=SKIN)
    d.pieslice(at(36, 76, 124, 164), 0, 180, fill=SHIRT)
    for x in (60, 88):
        d.ellipse(at(x, 92, x + 12, 104), fill=OUTLINE)
        d.ellipse(at(x + 3, 94, x + 7, 98), fill=WHITE)
    heart = HOT_PINK if key == "magenta" else GREEN_HEART
    d.polygon([tuple(at(68, 132)), tuple(at(92, 132)), tuple(at(80, 148))], fill=heart)
    d.ellipse(at(67, 125, 81, 139), fill=heart)
    d.ellipse(at(79, 125, 93, 139), fill=heart)
    d.ellipse(at(118, 140, 146, 168), fill=RED if key == "magenta" else GOLD)
    d.chord(at(46, 44, 114, 112), 180, 360, fill=hair)
    for deg, thick, length in ((-160, 0.5, 22), (-135, 0.7, 24), (-110, 1.0, 22), (-70, 1.4, 20), (-45, 0.8, 22),
                               (-20, 2.0, 20)):
        c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        x0, y0 = 80 + 32 * c, 78 + 32 * s
        d.line(at(x0, y0, x0 + length * c, y0 + length * s), fill=hair, width=max(1, round(thick * SS)))
    d.ellipse(at(12, 120, 40, 148), fill=hair)
    d.ellipse(at(*RING), fill=(0, 0, 0, 0))
    d.rectangle(at(38, 131, 42, 137), fill=hair)
    truth = big.resize((w, h), Image.BOX)
    back = Image.new("RGB", (w, h), PAINTED[key])
    if gap:
        ImageDraw.Draw(back).ellipse([RING[0] - 1, RING[1] - 1, RING[2] + 1, RING[3] + 1], fill=POCKET[key])
    fg, bg = truth.tobytes(), back.tobytes()
    out = bytearray(w * h * 3)
    for i in range(w * h):
        a = fg[4 * i + 3] / 255
        for c in range(3):
            out[3 * i + c] = round(a * fg[4 * i + c] + (1 - a) * bg[3 * i + c])
    pic = Image.frombytes("RGB", (w, h), bytes(out))
    if spill:
        px, tr = pic.load(), truth.load()
        for x, y in ((sx + dx, sy + dy) for sx, sy in SPILL for dx in (0, 1) for dy in (0, 1)):
            px[x, y] = tuple(round(0.6 * a + 0.4 * b) for a, b in zip(tr[x, y][:3], PAINTED[key]))
    return truth, pic


def new_colours(src, out) -> list:
    """The pixels of `out`, a scaled `src`, shown (alpha >= 38) in a colour more than one level
    outside the range of the shown source pixels under them."""
    sp, op = src.load(), out.load()
    fx, fy = src.width / out.width, src.height / out.height
    bad = []
    for v in range(out.height):
        for u in range(out.width):
            if op[u, v][3] < 38:
                continue
            xs = range(max(0, math.floor((u - 0.5) * fx)), min(src.width, math.ceil((u + 1.5) * fx)))
            ys = range(max(0, math.floor((v - 0.5) * fy)), min(src.height, math.ceil((v + 1.5) * fy)))
            seen = [sp[x, y] for y in ys for x in xs if sp[x, y][3]]
            if any(not min(p[k] for p in seen) - 1 <= op[u, v][k] <= max(p[k] for p in seen) + 1 for k in range(3)):
                bad.append((u, v))
    return bad


def leaning(img, key: tuple) -> tuple[int, int]:
    """The shown pixels within 3 px of a clear one that lean to the key by more than 40, and all
    shown pixels there."""
    px = img.load()
    near = Image.frombytes("L", img.size, bytes(255 if a == 0 else 0 for a in img.getchannel("A").tobytes()))
    near = near.filter(ImageFilter.MaxFilter(7)).load()
    on = [k for k in range(3) if key[k]]
    off = [k for k in range(3) if not key[k]]
    shown = [px[x, y] for y in range(img.height) for x in range(img.width) if near[x, y] and px[x, y][3] >= 32]
    return sum(min(p[k] for k in on) - max(p[k] for k in off) > 40 for p in shown), len(shown)


def matte(truth, cut) -> tuple[float, int]:
    """The mean alpha error in levels, and the pixels at least half covered in the truth that are
    shown in a colour more than 40 off it."""
    t, c = truth.load(), cut.load()
    px = [(t[x, y], c[x, y]) for y in range(truth.height) for x in range(truth.width)]
    err = sum(abs(a[3] - b[3]) for a, b in px) / len(px)
    return err, sum(a[3] >= 128 and b[3] >= 32 and max(abs(a[k] - b[k]) for k in range(3)) > 40 for a, b in px)


def sprite(file: str, subject: str, w: int = 64, h: int = 64) -> dict:
    return {"file": file, "kind": "circle", "width": w, "height": h, "origin": [0.5, 0.5], "subject": subject}


def test_prepare_art_lists_the_next_step_only(project):
    """No ART_STYLE: that step alone. Then the key picture alone, while more than one sprite is to
    make. Then a prompt per picture."""
    code, out = tool(project, "prepare_art", "--list")
    assert code == 0, out
    assert out.splitlines() == [
        "style: none. Write ART_STYLE in tools/build_project.py, one sentence of art direction the user agreed, so "
        "that every picture shares it",
        "to make: 1, to prepare: 0, done: 0; next: write ART_STYLE, run python tools/build_project.py, then python "
        ".agents/skills/construct3-agent-plugin/scripts/prepare_art.py --list again"]
    assert (project / "art" / "raw").is_dir()

    edit(project, "art/wanted.json", lambda wanted: wanted.update(style="Bright flat vector, thick dark outlines."))
    code, out = tool(project, "prepare_art", "--list")
    lines = out.splitlines()
    assert lines[0] == "style: Bright flat vector, thick dark outlines."
    assert "make coin-default-000: ratio 1:1, for a 160x160 box -> art/raw/coin-default-000.png" in lines
    assert ('  "Bright flat vector, thick dark outlines; a gold coin seen from the front. One subject, whole and '
            'centred with room around it, on a flat magenta #FF00FF background: no scenery, no shadow on the '
            'ground, no text."') in lines
    assert lines[-1] == ("to make: 1, to prepare: 0, done: 0; next: make each with the image tool, then python "
                         ".agents/skills/construct3-agent-plugin/scripts/prepare_art.py")

    edit(project, "art/wanted.json", lambda wanted: wanted["images"].extend(
        [sprite("coin-default-001.png", "a silver coin"), sprite("rose-default-000.png", "a pink rose"),
         {"file": "sky-default-000.png", "kind": "scene", "width": 720, "height": 1280, "origin": [0, 0],
          "subject": "a night sky over hills"}]))
    code, out = tool(project, "prepare_art", "--list")
    assert out.splitlines() == [
        "style: Bright flat vector, thick dark outlines.",
        'key picture: "Bright flat vector, thick dark outlines; a line-up of a gold coin seen from the front; a pink '
        'rose; a silver coin, side by side on a flat green #00FF00 background, no text". If the user is in the '
        'session, show it and keep the one they choose. Save it as art/raw/_key.png',
        "to make: 4, to prepare: 0, done: 0; next: make the key picture, then python "
        ".agents/skills/construct3-agent-plugin/scripts/prepare_art.py --list for the prompts of the others"], out

    # the key picture is the style reference of every sprite, not of a scene
    Image.new("RGB", (64, 32), (0, 255, 0)).save(project / "art" / "raw" / "_key.png")
    code, out = tool(project, "prepare_art", "--list")
    lines = out.splitlines()
    assert ("make rose-default-000: ratio 1:1, for a 64x64 box, art/raw/_key.png as the reference image -> "
            "art/raw/rose-default-000.png") in lines
    assert ('  "Bright flat vector, thick dark outlines; a pink rose. One subject, whole and centred with room around '
            'it, on a flat green #00FF00 background: no scenery, no shadow on the ground, no text. The reference '
            'image sets the style and the palette; it is not a picture to copy, so draw only this subject."') in lines
    assert "make sky-default-000: ratio 9:16, for a 720x1280 box -> art/raw/sky-default-000.png" in lines
    assert ('  "Bright flat vector, thick dark outlines; a night sky over hills. A full-frame background scene, no '
            'characters in front, no text."') in lines

    (project / "art" / "wanted.json").unlink()
    code, out = tool(project, "prepare_art")
    assert code == 2 and "no art/wanted.json" in out and "give every sprite an art()" in out


def test_prepare_art_warns_of_subjects_that_come_out_wrong(project):
    """A subject that names what its prompt or ART_STYLE decides, and subjects that differ only in
    colour or element words, are warned about; the prompts are printed all the same. A word after
    a negation asks for what the prompt asks for."""
    items = [sprite("knight-default-000.png", "a knight casting a long shadow, pixel art, watercolour"),
             sprite("sign-default-000.png", "a sign with the word EXIT"),
             sprite("tree-default-000.png", "a tree on a hill background"),
             sprite("crate-default-000.png", "a wooden crate with a stone texture, no shadow, without any text"),
             sprite("card-default-000.png", "卡牌背面：暗色底、鎏金纹章，无文字，暗金描边"),
             {"file": "sky-default-000.png", "kind": "scene", "width": 720, "height": 1280, "subject": "a night sky"}]
    items += [sprite(f"slime-default-00{i}.png", f"a {colour} slime")
              for i, colour in enumerate(("red", "blue", "green"))]
    items += [sprite(f"wolf-default-00{i}.png", f"{e}属性狼妖的圆形徽章肖像：{c}狼头")
              for i, (e, c) in enumerate((("木", "青绿色"), ("火", "赤红"), ("水", "蓝色")))]
    items += [sprite(f"gem-default-00{i}.png", f"a red {thing}") for i, thing in enumerate(("gem", "heart", "star"))]
    assert prepare_art.warnings(items, "Dark gilded flat shapes, 暗金描边.") == [
        "warning: tree-default-000: the subject names a background. A sprite is made on the key colour alone and cut "
        "out, so take the background out of the subject, or make the picture a scene",
        "warning: knight-default-000: the subject names a shadow. The cut removes a shadow together with the "
        "background, so take it out of the subject",
        "warning: sign-default-000: the subject names text. The image tool misspells words, so take them out of the "
        "subject and write them with a Text object",
        "warning: knight-default-000: the subject names the drawing style \"pixel\", and ART_STYLE does not. Pictures "
        "in two styles do not match, so add the style to ART_STYLE or take it out of the subject",
        "warning: knight-default-000: the subject names the drawing style \"watercolour\", and ART_STYLE does not. "
        "Pictures in two styles do not match, so add the style to ART_STYLE or take it out of the subject",
        "warning: slime-default-000, slime-default-001, slime-default-002; wolf-default-000, wolf-default-001, "
        "wolf-default-002: the subjects differ only in colour or element words, so each group comes out as one "
        "figure in several colours. If they are different things, say in each subject what else sets it apart: its "
        "shape, its size, what it holds"]

    edit(project, "art/wanted.json", lambda wanted: wanted.update(style="Dark gilded flat shapes, 暗金描边.",
                                                                  images=items))
    (project / "art" / "raw").mkdir(parents=True)
    Image.new("RGB", (64, 32), (255, 0, 255)).save(project / "art" / "raw" / "_key.png")
    code, out = tool(project, "prepare_art", "--list", "--limit", "0")
    lines = out.splitlines()
    assert code == 0 and lines[1].startswith("warning: tree-default-000") and lines[6].startswith("warning: slime"), out
    assert ("make knight-default-000: ratio 1:1, for a 64x64 box, art/raw/_key.png as the reference image -> "
            "art/raw/knight-default-000.png") in lines


def test_prepare_art_cuts_out_a_picture_and_the_generator_takes_it(project):
    picture(project / "art" / "raw" / "coin-default-000.jpg")
    code, out = tool(project, "prepare_art")
    assert code == 0, out
    assert ("coin-default-000: coin-default-000.jpg 512x512, background #" in out
            and "-> art/coin-default-000.png 160x160" in out), out
    assert out.splitlines()[-1] == "ok: 1 pictures in art/; next: python tools/build_project.py"
    code, out = tool(project, "prepare_art", "--list")
    assert out.splitlines()[-1] == "ok: all 1 pictures done; next: python tools/build_project.py", out
    img = Image.open(project / "art" / "coin-default-000.png")
    assert img.mode == "RGBA" and img.size == (160, 160) and img.info.get("c3-art") == "painted"
    px = img.load()
    assert px[0, 0] == (0, 0, 0, 0) and px[48, 48][3] == 255 and px[48, 48][0] > 200
    shown = [px[x, y] for x in range(160) for y in range(160) if px[x, y][3]]
    fringe = [p for p in shown if p[0] > 120 and p[1] < 60 and p[2] > 120 and p[3] > 32]
    assert not fringe, f"the key or its shadow is left: {fringe[:5]}"
    assert all(px[x, y] == (0, 0, 0, 0) for x in range(160) for y in range(160) if not px[x, y][3])
    assert any(0 < p[3] < 255 for p in shown), "the edge is blended"
    hit = Image.open(project / "art" / "coin-default-000.hit.png").load()
    assert all(hit[x, y][3] == px[x, y][3] for x in range(160) for y in range(160))
    assert hit[48, 48] == (255, 255, 255, 255)

    code, out = run(project, "tools/build_project.py")
    assert code == 0 and "art: all 1 images from art/" in out, out
    assert (project / "images" / "coin-default-000.png").read_bytes() == \
        (project / "art" / "coin-default-000.png").read_bytes()
    coin = json.loads((project / "objectTypes" / "Coin.json").read_text(encoding="utf-8"))
    frames = coin["animations"]["items"][0]["frames"]
    assert [(f["width"], f["height"], f["tag"]) for f in frames] == [(160, 160, ""), (160, 160, "hit")]
    assert len(frames[0]["collisionPoly"]["points"]) == 32          # the stand-in's circle
    code, out = tool(project, "check_look")
    assert code == 0 and out.splitlines()[-1].startswith("ok: 4 images"), out


def test_prepare_art_scales_a_picture_without_new_colours():
    """LANCZOS gives a light rim and a key tint that no source pixel had."""
    truth = figure("magenta", spill=False)[0]
    for scale in (0.2, 0.35, 0.5, 0.75):
        size = (round(truth.width * scale), round(truth.height * scale))
        assert len(new_colours(truth, truth.resize(size, Image.LANCZOS))) > 100
        assert new_colours(truth, prepare_art.resample(truth, size, Image.HAMMING)) == [], scale
        assert new_colours(truth, prepare_art.resample(truth, size, Image.BOX)) == [], scale


def test_prepare_art_refuses_a_picture_it_cannot_cut_out(project):
    """A refusal is counted once per picture, carried into the picture's next prompt, and after the
    third the picture keeps its stand-in."""
    edit(project, "art/wanted.json", lambda wanted: wanted.update(style="Bright flat vector."))
    raw = project / "art" / "raw" / "coin-default-000.jpg"
    picture(raw, stripes=True)
    for _ in range(2):                                   # the same picture again counts once
        code, out = tool(project, "prepare_art")
        assert code == 1, out
        assert ("coin-default-000: coin-default-000.jpg: its edge is not one flat colour" in out
                and "; make it again on a flat magenta #FF00FF background, or with a transparent one (refusal 1 of 3; "
                    "after 3 it keeps its stand-in)" in out), out
    script = ".agents/skills/construct3-agent-plugin/scripts/prepare_art.py"
    assert out.splitlines()[-1] == (f"prepared: 0, could not use: 1, still to make: 0; next: python {script} --list "
                                    f"for the prompts of the pictures above, make them again, then python {script}")
    code, out = tool(project, "prepare_art", "--list")
    lines = out.splitlines()
    assert ("make coin-default-000 again (refusal 1 of 3; after 3 it keeps its stand-in): ratio 1:1, for a 160x160 box "
            "-> art/raw/coin-default-000.png") in lines, out
    assert ('  "Bright flat vector; a gold coin seen from the front. One subject, whole and centred with room around '
            'it, on a flat magenta #FF00FF background: no scenery, no shadow on the ground, no text. Nothing but flat '
            'magenta #FF00FF around the subject, out to every edge, or a transparent background."') in lines
    assert lines[-1].startswith("to make: 1, to prepare: 0, done: 0; next: make each with the image tool")

    picture(raw, r=270, shadow=False)
    code, out = tool(project, "prepare_art")
    assert code == 1 and "the subject runs off the picture over" in out, out
    assert "make it again whole and centred, with room around it (refusal 2 of 3;" in out
    # on white, a cut would take the subject's whites with it
    picture(raw, bg=(250, 250, 250))
    code, out = tool(project, "prepare_art")
    assert code == 0, out
    assert "its background is #F" in out and "neither magenta nor green" in out, out
    keep = "To try again, change its subject in art(), which starts the count again"
    assert ("make it again on a flat magenta #FF00FF background, or with a transparent one. Refused 3 times, so it "
            f"keeps its stand-in. {keep}") in out
    assert out.splitlines()[-1] == ("prepared: 0, could not use: 0, still to make: 0, kept as stand-ins: 1; next: "
                                    "python tools/build_project.py")
    code, out = tool(project, "prepare_art", "--list")
    assert out.splitlines()[-2:] == [
        f"stand-in coin-default-000: refused 3 times, so it keeps its stand-in. {keep}",
        "to make: 0, to prepare: 0, done: 0, stand-ins: 1; next: python tools/build_project.py"], out
    code, out = run(project, "tools/build_project.py")
    assert code == 0 and "1 of 1 images show their stand-in" in out, out

    # a new subject is a new request: its count starts again
    edit(project, "art/wanted.json", lambda wanted: wanted["images"][0].update(subject="a gold coin, flat"))
    code, out = tool(project, "prepare_art", "--list")
    assert "prepare coin-default-000: coin-default-000.jpg" in out.splitlines(), out


def test_prepare_art_fits_a_scene_and_keeps_a_picture_with_transparency(project):
    edit(project, "art/wanted.json", lambda wanted: wanted["images"].append(
        {"file": "sky-default-000.png", "kind": "scene", "width": 720, "height": 1280, "origin": [0, 0],
         "subject": "a night sky"}))
    (project / "art" / "raw").mkdir(parents=True)
    Image.new("RGB", (1365, 768), (20, 30, 80)).save(project / "art" / "raw" / "sky-default-000.jpg")
    cut = Image.new("RGBA", (300, 600), (0, 0, 0, 0))
    ImageDraw.Draw(cut).rectangle([100, 100, 200, 500], fill=(30, 140, 220, 255))
    cut.save(project / "art" / "raw" / "coin-default-000.png")
    code, out = tool(project, "prepare_art")
    assert code == 0, out
    assert "sky-default-000: sky-default-000.jpg 1365x768 -> art/sky-default-000.png 720x1280, cropped to cover it" in out
    assert "coin-default-000.png 300x600, its own transparency" in out
    assert "note: the subject, 40x160, fills 25% of its 160x160 box; give art() a box of the subject's shape" in out, out
    sky = Image.open(project / "art" / "sky-default-000.png")
    assert sky.size == (720, 1280) and sky.getpixel((0, 0))[3] == 255


def test_prepare_art_unmixes_the_edge_by_how_much_key_it_holds():
    """Each edge pixel is a blend of the subject and the key, and its alpha is the share of the
    subject. A half blend of the key with a colour far from it comes out half clear, not opaque
    and tinted."""
    for key in KEYS:
        truth, pic = figure(key, spill=False, gap=False)
        cut, how = prepare_art.cut_out(pic, KEYS[key])
        err, off = matte(truth, cut)
        assert err < 1 and off <= 10, (key, err, off)
        assert leaning(cut, KEYS[key])[0] == 0, key
        # red under magenta and gold under green lean part way to the key, and stay opaque
        ball = [(x, y) for x in range(120, 145) for y in range(142, 167) if truth.getpixel((x, y))[3] == 255]
        assert ball and all(cut.getpixel(p)[3] == 255 for p in ball), key


def test_prepare_art_clears_gaps_and_key_light_and_keeps_colours_near_the_key():
    for key in KEYS:
        truth, pic = figure(key)
        cut, how = prepare_art.cut_out(pic, KEYS[key])
        assert "102 px cleared in gaps, 12 px of key light recoloured" in how, how
        hole = [(x, y) for x in range(RING[0] + 1, RING[2] - 1) for y in range(RING[1] + 1, RING[3] - 1)
                if truth.getpixel((x, y))[3] == 0]
        assert hole and all(cut.getpixel(p)[3] == 0 for p in hole), key
        for x, y in ((sx + dx, sy + dy) for sx, sy in SPILL for dx in (0, 1) for dy in (0, 1)):
            assert max(abs(a - b) for a, b in zip(cut.getpixel((x, y)), truth.getpixel((x, y)))) <= 24, (key, x, y)
        # a hot-pink heart under magenta, 94 from the key, and a green one under green: untouched
        heart = HOT_PINK if key == "magenta" else GREEN_HEART
        inside = [(x, y) for x in range(66, 94) for y in range(124, 149) if truth.getpixel((x, y)) == (*heart, 255)]
        assert inside and all(cut.getpixel(p) == (*heart, 255) for p in inside), key


def test_prepare_art_refuses_a_cut_that_leaves_the_key_on_the_edge():
    truth, pic = figure("magenta", hair=HOT_PINK)
    with pytest.raises(prepare_art.Unusable, match=r"pixels along the subject's edge lean to magenta: a fringe "
                                                   r"the cut left, or a subject too near the key; make it again on "
                                                   r"a flat green #00FF00 background") as refused:
        prepare_art.cut_out(pic, KEYS["magenta"])
    item = {"file": "x.png", "kind": "circle", "subject": "a knight in red"}
    record = {"x.png": {"pictures": ["0"], "tell": refused.value.tell, "key": refused.value.key}}
    text = prepare_art.prompt(prepare_art.with_refusal(item, record), "")
    assert "on a flat green #00FF00 background" in text and "Keep magenta out of the subject and its edge" in text
    truth, pic = figure("green", hair=HOT_PINK)          # made again as the line says
    cut, how = prepare_art.cut_out(pic, KEYS["magenta"])
    assert how.startswith("background #06F60A") and leaning(cut, KEYS["green"])[0] == 0


REAL = os.environ.get("CONSTRUCT3_RAG_ART_PICTURES", "")


@pytest.mark.skipif(not REAL, reason="CONSTRUCT3_RAG_ART_PICTURES names no folder of real image-model pictures")
def test_prepare_art_cuts_real_pictures():
    """Real pictures, kept out of the repository: one subject each on a flat magenta or green, as
    an image model made them. Each is cut without a refusal, and at most 1 in 1000 of its edge
    pixels leans to the key."""
    pictures = [p for p in sorted(Path(REAL).iterdir()) if p.suffix.lower() in prepare_art.RAW_TYPES]
    assert pictures, f"no .png, .jpg or .webp in {REAL}"
    for path in pictures:
        img = Image.open(path).convert("RGB")
        key = KEYS["magenta" if img.getpixel((0, 0))[0] > 128 else "green"]
        cut, how = prepare_art.cut_out(img, key)
        left, band = leaning(cut, key)
        assert left <= band / 1000, (path.name, left, band)
