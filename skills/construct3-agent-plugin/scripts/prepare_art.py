"""Turn the pictures of the session's image tool into a generated game's art.

    python scripts/prepare_art.py --list     the prompt for each picture still to make
    python scripts/prepare_art.py            cut out and fit every picture in art/raw/

The generator's art() asks for each sprite by what it shows, in a box of whole
units, and writes the list to art/wanted.json; until its picture is there, the
sprite shows its stand-in shape. --list prints a prompt per picture, starting
with ART_STYLE so that the pictures share one style. Make each with the image
tool and save it as art/raw/<name>.png, .jpg or .webp, where <name> is the
image's file name without .png. Without --list, each picture there is:

  cut out    a picture with transparency keeps it; any other was asked for on
             a flat key colour, removed where it touches the edge and wherever
             it is that colour exactly, with the edge blended
  fitted     trimmed to the subject and fitted into its box, centred, standing
             on the box's bottom when the origin is at the feet; a scene
             covers its box and is cropped
  written    as art/<name>.png at the box's size, a clear pixel holding no
             colour, with art/<name>.hit.png, its silhouette in the flash
             colour, for hit_frame()

Then run the generator: art() takes each picture in place of its stand-in.
Needs Pillow (pip install pillow).

The last line starts with ok: once every picture art() asks for is in art/;
before that it counts what is left and names the next step.

Exit 0: no picture was refused. Exit 1: a picture could not be used; its line
says what to make instead. Exit 2: no art/wanted.json, or no Pillow.
"""
import json
import math
import sys
from pathlib import Path

import c3project as c3

RAW_TYPES = (".png", ".jpg", ".jpeg", ".webp")
KEYS = {"magenta": (255, 0, 255), "green": (0, 255, 0)}
# a subject in these colours is asked for on green, so the key does not eat it
NEAR_MAGENTA = ("pink", "magenta", "purple", "violet", "fuchsia", "lilac", "lavender", "rose", "粉", "紫", "品红")
RATIOS = ((1, 1), (4, 3), (3, 4), (3, 2), (2, 3), (16, 9), (9, 16), (2, 1), (1, 2))
# Distances in RGB from the background colour, the key as the model painted it: background where
# it joins the edge and is within NEAR; a gap in the subject, anywhere, within POCKET when it is
# also within KEYLINE of the key in shade. On real pictures 70 clears the shaded gaps between
# strands, 66 to 70 away; 50 left them, and 90 cut into the subject and into the edge of a green
# heart under green, 92 away.
NEAR, POCKET, KEYLINE = 60, 70, 60
# The subject's edge: pixels up to a pixel per REACH_PER of the picture's long side in from the
# background, and at least REACH, are unmixed from it when they lean to the key MARGIN more than
# the subject behind them, or lie within LINE of the line between the two. A real picture's blend
# widens with its size: 3 cleared it at 718 px, 4 at 1005 px, 5 at 1436 px. SWEEPS carries the
# subject's colour along a strand that has no inside.
REACH, REACH_PER, MARGIN, LINE, SWEEPS = 3, 240, 16, 30, 16
# Key light inside the subject: a pixel leaning SPILL more to the key than the 5x5 around it.
SPILL = 60
WORK = 4                                   # a picture is cut out at up to this many times its box
MARK = "c3-art"                            # the PNG text key check_look.py reads as a painting


class Unusable(Exception):
    """A picture the run cannot use; the message says what to make instead."""


def key_for(item: dict, style: str) -> tuple[str, tuple]:
    words = f"{item['subject']} {style}".lower()
    name = "green" if any(w in words for w in NEAR_MAGENTA) else "magenta"
    return name, KEYS[name]


def hex_of(c: tuple) -> str:
    return "#%02X%02X%02X" % tuple(c[:3])


def ratio(w: int, h: int) -> str:
    a, b = min(RATIOS, key=lambda r: abs(math.log(r[0] / r[1]) - math.log(w / h)))
    return f"{a}:{b}"


def prompt(item: dict, style: str) -> str:
    lead = f"{style.rstrip('. ')}; " if style.strip() else ""
    if item["kind"] == "scene":
        return f"{lead}{item['subject']}. A full-frame background scene, no characters in front, no text."
    name, key = key_for(item, style)
    return (f"{lead}{item['subject']}. One subject, whole and centred with room around it, on a flat {name} "
            f"{hex_of(key)} background: no scenery, no shadow on the ground, no text.")


def raw_of(root: Path, rel: str) -> Path | None:
    stem = rel[:-len(".png")]
    found = [root / "art" / "raw" / (stem + ext) for ext in RAW_TYPES]
    found = [p for p in found if p.exists()]
    return max(found, key=lambda p: p.stat().st_mtime) if found else None


def state(root: Path, item: dict) -> str:
    """make: no picture yet; prepare: a picture newer than its fitted art; done."""
    raw, out = raw_of(root, item["file"]), root / "art" / item["file"]
    if raw is None:
        return "done" if out.exists() else "make"
    return "done" if out.exists() and out.stat().st_mtime >= raw.stat().st_mtime else "prepare"


def list_prompts(root: Path, wanted: dict, skill: str) -> list[str]:
    style, items = wanted.get("style", ""), wanted["images"]
    states = {item["file"]: state(root, item) for item in items}
    out = [f"style: {style}" if style.strip() else
           "style: none. Write ART_STYLE in tools/build_project.py first, one sentence of art direction the user "
           "agreed, so that every picture shares it. Then run the generator"]
    to_make = [item for item in items if states[item["file"]] == "make"]
    sprites = [item for item in to_make if item["kind"] != "scene"]
    if len(sprites) > 1 and raw_of(root, "_key.png") is None:
        lineup = "; ".join(item["subject"] for item in sprites[:4])
        name, key = key_for(sprites[0], style)
        lead = f"{style.rstrip('. ')}; " if style.strip() else ""
        out.append(f"key picture: make it first, \"{lead}a line-up of {lineup}, side by side on a flat {name} "
                   f"{hex_of(key)} background, no text\". If the user is in the session, show it and keep the one "
                   f"they choose. Save it as art/raw/_key.png. Give it as the reference image of every picture "
                   f"below, where the image tool takes one")
    for item in items:
        rel, s = item["file"], states[item["file"]]
        stem = rel[:-len(".png")]
        if s == "make":
            out.append(f"make {stem}: ratio {ratio(item['width'], item['height'])}, for a {item['width']}x"
                       f"{item['height']} box -> art/raw/{stem}.png")
            out.append(f"  \"{prompt(item, style)}\"")
        else:
            out.append(f"{s} {stem}: {raw.name if (raw := raw_of(root, rel)) else 'art/' + rel}")
    counts = {k: list(states.values()).count(k) for k in ("make", "prepare", "done")}
    if counts["make"]:
        out.append(f"to make: {counts['make']}, to prepare: {counts['prepare']}, done: {counts['done']}; next: make "
                   f"each with the image tool, then python {skill}/scripts/prepare_art.py")
    elif counts["prepare"]:
        out.append(f"to prepare: {counts['prepare']}, done: {counts['done']}; next: python "
                   f"{skill}/scripts/prepare_art.py")
    else:
        out.append(f"ok: all {counts['done']} pictures done; next: python tools/build_project.py")
    return out


def leaning_to(key: tuple):
    """How far a colour leans to the key: about 255 on the key, 0 or less on a colour away from
    it. It is linear in a blend with the key, and red under magenta or gold under green lean to it
    no more than grey does."""
    on = [k for k in range(3) if key[k]]
    off = [k for k in range(3) if not key[k]]
    return lambda c: min(c[k] for k in on) - max(c[k] for k in off)


def cut_out(img, key: tuple) -> tuple[object, str]:
    """The picture as RGBA with its background clear, and how the background was found."""
    from PIL import Image, ImageFilter
    rgba = img.convert("RGBA")
    w, h = rgba.size
    data = rgba.tobytes()
    edge = [i for i in range(w)] + [(h - 1) * w + i for i in range(w)] + \
           [y * w for y in range(1, h - 1)] + [y * w + w - 1 for y in range(1, h - 1)]
    if min(data[4 * i + 3] for i in edge) < 250:
        return rgba, "its own transparency"
    colours = [tuple(data[4 * i:4 * i + 3]) for i in edge]
    bg = tuple(sorted(c[k] for c in colours)[len(colours) // 2] for k in range(3))
    near = sum(sum((a - b) ** 2 for a, b in zip(c, bg)) < NEAR ** 2 for c in colours) / len(colours)
    name = next(n for n, c in KEYS.items() if c == key)
    if near < 0.5:
        raise Unusable(f"its edge is not one flat colour, {near:.0%} of it near {hex_of(bg)}; make it again on a "
                       f"flat {name} {hex_of(key)} background, or with a transparent one")
    lit = min(c for c, k in zip(bg, key) if k)
    if lit < 96 or max(c for c, k in zip(bg, key) if not k) > 0.35 * lit:
        raise Unusable(f"its background is {hex_of(bg)}, not the {name} it was asked on, and a cut on that colour "
                       f"takes the subject's own parts in it; make it again on a flat {name} {hex_of(key)} "
                       f"background, or with a transparent one")
    if near < 0.9:
        raise Unusable(f"the subject runs off the picture over {1 - near:.0%} of its edge, so it is cut off; make "
                       f"it again whole and centred, with room around it")
    n = w * h
    br, bgr, bb = bg
    rgb = [data[4 * i:4 * i + 3] for i in range(n)]
    dist2 = [(r - br) ** 2 + (g - bgr) ** 2 + (b - bb) ** 2 for r, g, b in rgb]
    hue = leaning_to(key)
    ex = [hue(c) for c in rgb]
    e_bg = hue(bg)
    norm = br * br + bgr * bgr + bb * bb

    def shade(c) -> tuple[float, float]:       # how far a colour is from the key darker or lighter, and how much
        s = (c[0] * br + c[1] * bgr + c[2] * bb) / norm
        return math.sqrt((c[0] - s * br) ** 2 + (c[1] - s * bgr) ** 2 + (c[2] - s * bb) ** 2), s

    def background(j: int) -> bool:
        """Near the key, or a shadow on it, which models draw though the prompt says not to: the key
        darker."""
        if dist2[j] < NEAR ** 2:
            return True
        off, s = shade(rgb[j])
        return 0.25 <= s <= 1.05 and off < 40

    def gap(j: int) -> bool:
        """The key seen through a gap in the subject, in shade: kept apart from a subject colour near
        the key, such as a hot pink under magenta, by its distance and its line."""
        return dist2[j] < POCKET ** 2 and ex[j] > e_bg / 2 and shade(rgb[j])[0] < KEYLINE

    clear = bytearray(n)
    shadow = bytearray(n)                      # cleared as the key darker, not as the key
    stack = [i for i in edge if background(i)]
    for i in stack:
        clear[i] = 1
        shadow[i] = dist2[i] >= NEAR ** 2
    while stack:
        i = stack.pop()
        x = i % w
        for j in (i - w, i + w, i - 1 if x else -1, i + 1 if x < w - 1 else -1):
            if 0 <= j < n and not clear[j] and background(j):
                clear[j] = 1
                shadow[j] = dist2[j] >= NEAR ** 2
                stack.append(j)
    gaps = 0
    for i in range(n):
        if not clear[i] and gap(i):
            clear[i] = 1
            gaps += 1

    def mask(on):
        return Image.frombytes("L", (w, h), bytes(255 if v else 0 for v in on))

    # a dark outline's blended edge reads as a shadow too: beside the subject, it is unmixed below
    beside = mask(not c for c in clear).filter(ImageFilter.MaxFilter(3)).tobytes()
    for i in range(n):
        if shadow[i] and beside[i] and not gap(i):
            clear[i] = 0
    # the edge: pixels up to `reach` in from the background, ring by ring
    reach = max(REACH, round(max(w, h) / REACH_PER))
    depth = bytearray(n)
    grown = mask(clear)
    rings = [[]]
    for d in range(1, reach + 1):
        grown = grown.filter(ImageFilter.MaxFilter(3))
        ring = [i for i, g in enumerate(grown.tobytes()) if g and not clear[i] and not depth[i]]
        for i in ring:
            depth[i] = d
        rings.append(ring)

    def around(i: int) -> list[int]:
        x, y = i % w, i // w
        return [yy * w + xx for yy in range(max(0, y - 1), min(h, y + 2)) for xx in range(max(0, x - 1), min(w, x + 2))
                if yy * w + xx != i]

    def mean(cs) -> tuple:
        return tuple(sum(c[k] for c in cs) / len(cs) for k in range(3))

    # behind each edge pixel: the background, carried in from the clear pixels beside it, and the
    # subject, carried out from its inside and then along the edge into strands with no inside
    back = {}
    for d in range(1, reach + 1):
        for i in rings[d]:
            src = [rgb[j] for j in around(i) if clear[j]] if d == 1 else \
                  [back[j] for j in around(i) if depth[j] == d - 1 and j in back]
            if src:
                back[i] = mean(src)
    inner = {}
    for d in range(reach, 0, -1):
        for i in rings[d]:
            src = [rgb[j] for j in around(i) if not clear[j] and not depth[j]] + \
                  [inner[j] for j in around(i) if depth[j] == d + 1 and j in inner]
            if src:
                inner[i] = mean(src)
    loose = [i for i in back if i not in inner]
    for _ in range(SWEEPS):
        reached = {i: mean(src) for i in loose if (src := [inner[j] for j in around(i) if j in inner])}
        if not reached:
            break
        inner.update(reached)
        loose = [i for i in loose if i not in reached]

    def on_line(o, b, s) -> float | None:      # o as a blend of b and s: how much of s, or None
        v = [s[k] - b[k] for k in range(3)]
        t = sum((o[k] - b[k]) * v[k] for k in range(3)) / max(1, sum(x * x for x in v))
        return t if sum((o[k] - b[k] - t * v[k]) ** 2 for k in range(3)) < LINE ** 2 else None

    out = bytearray(data)
    for i in range(n):
        if clear[i]:
            out[4 * i:4 * i + 4] = b"\0\0\0\0"
    # Each edge pixel is a blend o = a*s + (1-a)*b of the subject s and the background b. Its lean
    # to the key is linear in the blend, so a = (hue(b) - hue(o)) / (hue(b) - hue(s)), whatever
    # the subject's colour: red under magenta and gold under green stay opaque. Then o less the
    # background is the subject's colour.
    for i, b in back.items():
        o = rgb[i]
        s = inner.get(i)
        e_s = hue(s) if s else min([0] + [ex[j] for j in around(i) if not clear[j]])
        if ex[i] <= max(e_s, 0) + MARGIN:
            t = on_line(o, b, s) if s and ex[i] > e_s + MARGIN else None
            if t is None or t >= 0.97:
                continue
        e_b = hue(b)
        a = min(1.0, max(0.0, (e_b - ex[i]) / max(64, e_b - e_s)))
        if a < 0.1:
            out[4 * i:4 * i + 4] = b"\0\0\0\0"
        elif a < 1:
            out[4 * i:4 * i + 4] = bytes(min(255, max(0, round((o[k] - (1 - a) * b[k]) / a))) for k in range(3)) + \
                bytes((round(255 * a),))
    # key light caught inside the subject: a pixel between the colour around it and the key gets
    # that colour back, alpha kept
    spill = 0
    around5 = rgba.convert("RGB").filter(ImageFilter.MedianFilter(5)).tobytes()
    for i in range(n):
        if clear[i] or depth[i]:
            continue
        m = around5[3 * i:3 * i + 3]
        if ex[i] - hue(m) <= SPILL:
            continue
        t = on_line(rgb[i], m, bg)
        if t is None or not 0.1 <= t <= 0.9:
            continue
        out[4 * i:4 * i + 3] = bytes(min(255, max(0, round((rgb[i][k] - t * bg[k]) / (1 - t)))) for k in range(3))
        spill += 1
    cut = Image.frombytes("RGBA", (w, h), bytes(out))
    return cut, f"background {hex_of(bg)}, {gaps} px of it in gaps, {spill} px of its light recoloured"


def resample(img, size: tuple[int, int], how: int):
    """An RGBA picture scaled with its coverage and its colour apart. LANCZOS rings: its negative
    lobes and the division by a low alpha at the edge give colours no source pixel had, a light
    rim and a key tint. Here alpha and the colour weighted by alpha go through a filter with no
    negative lobe, HAMMING or BOX, in floats, so each pixel's colour is a mix of the colours under
    it."""
    from array import array
    from PIL import Image
    data = img.tobytes()
    alpha = data[3::4]

    def scaled(layer) -> array:
        return array("f", layer.resize(size, how).tobytes())

    cover = scaled(img.getchannel("A").convert("F"))
    mix = [scaled(Image.frombytes("F", img.size, array("f", (c * a for c, a in zip(data[k::4], alpha))).tobytes()))
           for k in range(3)]
    out = bytearray(4 * size[0] * size[1])
    for i, a in enumerate(cover):
        if a >= 0.5:
            out[4 * i:4 * i + 4] = bytes(min(255, max(0, round(m[i] / a))) for m in mix) + bytes((min(255, round(a)),))
    return Image.frombytes("RGBA", size, bytes(out))


def clean(img):
    """A clear pixel written as (0, 0, 0, 0): a colour under alpha 0 bleeds into the edge when the
    image is scaled with linear sampling."""
    from PIL import Image
    data = bytearray(img.tobytes())
    for i in range(3, len(data), 4):
        if not data[i]:
            data[i - 3:i] = b"\0\0\0"
    return Image.frombytes("RGBA", img.size, bytes(data))


def save(img, path: Path) -> None:
    from PIL import PngImagePlugin
    info = PngImagePlugin.PngInfo()
    info.add_text(MARK, "painted")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, pnginfo=info)


def prepare(root: Path, item: dict, wanted: dict) -> list[str]:
    """Fits one picture; returns its line and any note on it."""
    from PIL import Image
    rel, w, h = item["file"], item["width"], item["height"]
    stem = rel[:-len(".png")]
    raw = raw_of(root, rel)
    try:
        img = Image.open(raw)
        img.load()
    except OSError as e:
        raise Unusable(f"Pillow cannot read it ({e}); save it again as PNG or JPEG")
    rw, rh = img.size
    pixel_art = wanted.get("pixel_art", False)
    notes = []
    if item["kind"] == "scene":
        s = max(w / rw, h / rh)
        big = img.convert("RGB").resize((max(w, round(rw * s)), max(h, round(rh * s))), Image.LANCZOS)
        left, top = (big.width - w) // 2, (big.height - h) // 2
        save(big.crop((left, top, left + w, top + h)).convert("RGBA"), root / "art" / rel)
        return [f"{stem}: {raw.name} {rw}x{rh} -> art/{rel} {w}x{h}, cropped to cover it"]
    s = min(1.0, min(WORK * max(w, h), 1024) / max(rw, rh))
    work = img if s == 1 else resample(img.convert("RGBA"), (max(1, round(rw * s)), max(1, round(rh * s))),
                                       Image.HAMMING)
    cut, how = cut_out(work, key_for(item, wanted.get("style", ""))[1])
    alpha = cut.getchannel("A")
    solid = alpha.point(lambda a: 255 if a >= 128 else 0).getbbox()
    if solid is None:
        raise Unusable(f"nothing is left of the subject once the background is removed ({how}); make the subject "
                       f"in colours far from the background")
    if solid[0] == 0 or solid[1] == 0 or solid[2] == cut.width or solid[3] == cut.height:
        notes.append(f"  note: the subject touches the picture's edge and may be cut off; make it whole, with room "
                     f"around it")
    box = alpha.point(lambda a: 255 if a >= 16 else 0).getbbox()
    subject = cut.crop(box)
    f = min(w / subject.width, h / subject.height)
    sw, sh = max(1, round(subject.width * f)), max(1, round(subject.height * f))
    subject = resample(subject, (sw, sh), Image.BOX if pixel_art else Image.HAMMING)
    if pixel_art:      # Nearest sampling shows a soft edge as a fringe: an edge is in or out
        subject.putalpha(subject.getchannel("A").point(lambda a: 255 if a >= 128 else 0))
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    oy = item.get("origin", [0.5, 0.5])[1]
    canvas.paste(subject, ((w - sw) // 2, h - sh if oy >= 0.75 else (h - sh) // 2))
    canvas = clean(canvas)
    save(canvas, root / "art" / rel)
    flash = tuple(wanted.get("flash", (255, 255, 255)))
    hit = Image.new("RGBA", (w, h), (*flash, 255))
    hit.putalpha(canvas.getchannel("A"))
    save(clean(hit), root / "art" / f"{stem}.hit.png")
    fill = sw * sh / (w * h)
    if fill < 0.5:
        notes.append(f"  note: the subject, {sw}x{sh}, fills {fill:.0%} of its {w}x{h} box; give art() a box of "
                     f"the subject's shape, or make the subject again so that it fills a {ratio(w, h)} picture")
    return [f"{stem}: {raw.name} {rw}x{rh}, {how} -> art/{rel} {w}x{h}, the subject {sw}x{sh} in it"] + notes


def main() -> int:
    c3.utf8_output()
    ap = c3.argument_parser(__doc__.split("\n\n")[0], "examples:\n"
                            "  python scripts/prepare_art.py --list\n"
                            "  python scripts/prepare_art.py --project D:/games/Coins\n\n"
                            "exit codes: 0 when no picture was refused, the last line starting with ok: once all are "
                            "in art/; 1 when a picture could not be used; 2 when art/wanted.json or Pillow is missing")
    ap.add_argument("--list", action="store_true",
                    help="print the prompt of every picture still to make, and what is ready")
    args = ap.parse_args()
    root = c3.find_project(args.project)
    wanted_path = (root or Path.cwd()) / "art" / "wanted.json"
    if root is None or not wanted_path.exists():
        print(f"no art/wanted.json in {root or Path.cwd()}: give every sprite an art() in build_images() of "
              f"tools/build_project.py and run it, which writes the list", file=sys.stderr)
        return 2
    wanted = json.loads(wanted_path.read_text(encoding="utf-8"))
    skill = Path(__file__).resolve().parent.parent
    try:
        skill = skill.relative_to(root)
    except ValueError:
        pass
    failed = 0
    if args.list:
        (root / "art" / "raw").mkdir(parents=True, exist_ok=True)      # where the pictures are saved
        out = list_prompts(root, wanted, skill.as_posix())
    else:
        try:
            import PIL  # noqa: F401
        except ImportError:
            print("prepare_art.py needs Pillow to read and resize the pictures: pip install pillow", file=sys.stderr)
            return 2
        out, waiting, done = [], 0, 0
        for item in wanted["images"]:
            if raw_of(root, item["file"]) is None:
                if (root / "art" / item["file"]).exists():
                    done += 1           # put in art/ as it is, by the user
                else:
                    waiting += 1
                continue
            try:
                out += prepare(root, item, wanted)
                done += 1
            except Unusable as e:
                failed += 1
                out.append(f"{item['file'][:-len('.png')]}: {raw_of(root, item['file']).name}: {e}")
        counts = f"prepared: {done}, could not use: {failed}, still to make: {waiting}"
        if failed:
            out.append(f"{counts}; next: make the pictures above again as their lines say, then run this again")
        elif waiting:
            out.append(f"{counts}; next: python {skill.as_posix()}/scripts/prepare_art.py --list for their prompts")
        else:
            out.append(f"ok: {done} pictures in art/; next: python tools/build_project.py")
    shown = c3.fitting(out, args.limit)
    for line in out[:shown]:
        print(line)
    if shown < len(out):
        print(f"... {len(out) - shown} more lines; --limit 0 prints them all")
        print(out[-1])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
