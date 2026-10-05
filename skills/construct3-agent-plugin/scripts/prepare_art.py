"""Turn the pictures of the session's image tool into a generated game's art.

    python scripts/prepare_art.py --list     the next step: the prompts of the pictures to make
    python scripts/prepare_art.py            cut out and fit every picture in art/raw/

The generator's art() asks for each sprite by what it shows, in a box of whole
units, and writes the list to art/wanted.json; until its picture is there, the
sprite shows its stand-in shape. --list prints one step at a time: while
ART_STYLE is empty, that it is to be written; with more than one sprite to
make, the key picture, a line-up of the game's subjects that sets the style;
then a prompt per picture, starting with ART_STYLE so that the pictures share
one style. Make each with the image tool and save it as art/raw/<name>.png,
.jpg or .webp, where <name> is the image's file name without .png, and the key
picture as art/raw/_key.png: each sprite's prompt then gives it as the
reference image. Without --list, each picture there is:

  cut out    a picture with transparency keeps it. Any other picture was
             asked for on a flat magenta or green, the key. The key is
             removed where it touches the edge and where it shows through a
             gap, and taken out of the colour of the edge pixels it blends
             with. A picture on another background, or one whose edge still
             leans to the key after the cut, is refused with what to make
             instead
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

A refused picture is recorded in art/refused.json, and --list gives its
prompt again with what to make instead. After three refusals a picture keeps
its stand-in, and both runs count it and move on.

Exit 0: no picture waits to be made again. Exit 1: a picture could not be
used; its line says why. Exit 2: no art/wanted.json, or no Pillow.
"""
import hashlib
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
# RGB distances from the background colour, the key as the model painted it. NEAR: background
# that joins the edge. POCKET: a gap in the subject, anywhere, when it also lies within KEYLINE of
# the key made darker or lighter. docs/decisions/art-from-the-image-tool.md has the measurements.
NEAR, POCKET, KEYLINE = 60, 70, 60
# The edge is REACH px deep, or a pixel per REACH_PER px of the picture's long side when that is
# more, because a real picture's blend widens with its size. An edge pixel is unmixed when it
# leans to the key MARGIN more than the subject behind it, or lies within LINE of the line between
# the background and that subject. The subject's colour is carried along a strand that has no
# inside for up to SWEEPS px.
REACH, REACH_PER, MARGIN, LINE, SWEEPS = 3, 240, 16, 30, 16
# Key light inside the subject: a pixel that leans SPILL more to the key than the 5x5 around it.
SPILL = 60
# A cut whose edge pixels lean to the key in more than this share, and more than FRINGE_MIN of
# them, is refused.
FRINGE, FRINGE_MIN = 0.005, 8
LINEUP = 4                                 # subjects in the key picture: more in one picture repeat or merge
WORK = 4                                   # a picture is cut out at up to this many times its box
REFUSED = "art/refused.json"               # the pictures this script refused, which --list reads
TRIES = 3                                  # refusals before a picture keeps its stand-in
MARK = "c3-art"                            # the PNG text key check_look.py reads as a painting


class Unusable(Exception):
    """A picture the run cannot use: what is wrong with it, then `again`, what to make instead,
    which --list adds to the picture's next prompt, and `key`, the key colour that prompt asks
    for when it changes. A file Pillow cannot read has no `again`: it is saved again, not made
    again."""

    def __init__(self, problem: str, again: str = "", key: str | None = None):
        super().__init__(f"{problem}; {again}" if again else problem)
        self.again, self.key = again, key


def key_for(item: dict, style: str) -> tuple[str, tuple]:
    """The key colour a sprite is asked for on: the one its last refusal named, else green for a
    subject in pink or purple, else magenta."""
    words = f"{item['subject']} {style}".lower()
    name = item.get("key") or ("green" if any(w in words for w in NEAR_MAGENTA) else "magenta")
    return name, KEYS[name]


def hex_of(c: tuple) -> str:
    return "#%02X%02X%02X" % tuple(c[:3])


def ratio(w: int, h: int) -> str:
    a, b = min(RATIOS, key=lambda r: abs(math.log(r[0] / r[1]) - math.log(w / h)))
    return f"{a}:{b}"


def lead(style: str) -> str:
    """ART_STYLE as the start of a prompt."""
    return f"{style.strip().rstrip('。. ')}; " if style.strip() else ""


def prompt(item: dict, style: str, reference: bool = False) -> str:
    """The prompt of one picture. A sprite's says what the key picture beside it is for, with
    `reference`, and what to make instead of the picture last refused, with item["again"]."""
    subject = item["subject"].strip().rstrip("。. ")
    if item["kind"] == "scene":
        return f"{lead(style)}{subject}. A full-frame background scene, no characters in front, no text."
    name, key = key_for(item, style)
    again = f" {item['again'][0].upper()}{item['again'][1:]}." if item.get("again") else ""
    copy = (" The reference image sets the style and the palette; it is not a picture to copy, so draw only this "
            "subject.") if reference else ""
    return (f"{lead(style)}{subject}. One subject, whole and centred with room around it, on a flat {name} "
            f"{hex_of(key)} background: no scenery, no shadow on the ground, no text.{again}{copy}")


def raw_of(root: Path, rel: str) -> Path | None:
    stem = rel[:-len(".png")]
    found = [root / "art" / "raw" / (stem + ext) for ext in RAW_TYPES]
    found = [p for p in found if p.exists()]
    return max(found, key=lambda p: p.stat().st_mtime) if found else None


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def refusals(root: Path, wanted: dict) -> dict:
    """art/refused.json, by file name: the pictures refused, by fingerprint, and the `again` and
    `key` of the last refusal. A record whose subject art() no longer asks for counts no more."""
    try:
        data = json.loads((root / REFUSED).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    subjects = {item["file"]: item["subject"] for item in wanted["images"]}
    return {rel: r for rel, r in data.items() if isinstance(r, dict) and subjects.get(rel) == r.get("subject")}


def with_refusal(item: dict, refused: dict) -> dict:
    """The item with the `again` and `key` of its last refusal, which its next prompt carries."""
    r = refused.get(item["file"])
    return {**item, **{k: r[k] for k in ("again", "key") if r.get(k)}} if r else item


def state(root: Path, item: dict, refused: dict) -> str:
    """make: no picture yet; again: its pictures were refused, fewer than TRIES; stand-in: TRIES
    were; prepare: a picture newer than its fitted art and not refused; done."""
    raw, out = raw_of(root, item["file"]), root / "art" / item["file"]
    if out.exists() and (raw is None or out.stat().st_mtime >= raw.stat().st_mtime):
        return "done"
    r = refused.get(item["file"])
    if raw is not None and (r is None or fingerprint(raw) not in r["pictures"]):
        return "prepare"
    if r is None:
        return "make"
    return "stand-in" if len(r["pictures"]) >= TRIES else "again"


def lineup(sprites: list[dict]) -> list[dict]:
    """The sprites of the key picture, LINEUP of them: the first of each object before a second of
    one, so that it shows the kinds of things the game holds rather than the frames of one."""
    seen, first, more = set(), [], []
    for item in sprites:
        obj = item["file"].split("-")[0]
        (more if obj in seen else first).append(item)
        seen.add(obj)
    return (first + more)[:LINEUP]


def list_prompts(root: Path, wanted: dict, skill: str) -> list[str]:
    """The next step only: ART_STYLE while it is empty, then the key picture while it is missing,
    then a prompt per picture."""
    style, items = wanted.get("style", ""), wanted["images"]
    refused = refusals(root, wanted)
    states = {item["file"]: state(root, item, refused) for item in items}
    counts = {k: list(states.values()).count(k) for k in ("make", "again", "prepare", "done", "stand-in")}
    to_make = counts["make"] + counts["again"]
    count = f"to make: {to_make}, to prepare: {counts['prepare']}, done: {counts['done']}" +         (f", stand-ins: {counts['stand-in']}" if counts["stand-in"] else "")
    sprites = [item for item in items if states[item["file"]] in ("make", "again") and item["kind"] != "scene"]
    if to_make and not style.strip():
        return ["style: none. Write ART_STYLE in tools/build_project.py, one sentence of art direction the user "
                "agreed, so that every picture shares it",
                f"{count}; next: write ART_STYLE, run python tools/build_project.py, then this again"]
    out = [f"style: {style}"] if style.strip() else []
    if len(sprites) > 1 and raw_of(root, "_key.png") is None:
        shown = lineup(sprites)
        subjects = "; ".join(item["subject"].rstrip("。. ") for item in shown)
        name, key = key_for({"subject": subjects}, style)
        return out + [f"key picture: \"{lead(style)}a line-up of {subjects}, side by side on a flat {name} "
                      f"{hex_of(key)} background, no text\". If the user is in the session, show it and keep the "
                      f"one they choose. Save it as art/raw/_key.png",
                      f"{count}; next: make the key picture, the style every other picture follows, then run this "
                      f"again for their prompts"]
    key_picture = raw_of(root, "_key.png")
    for item in items:
        rel, s = item["file"], states[item["file"]]
        stem = rel[:-len(".png")]
        if s in ("make", "again"):
            reference = key_picture is not None and item["kind"] != "scene"
            tried = f" again, refused {len(refused[rel]['pictures'])} of {TRIES} times" if s == "again" else ""
            out.append(f"make {stem}{tried}: ratio {ratio(item['width'], item['height'])}, for a {item['width']}x"
                       f"{item['height']} box" + (f", art/raw/{key_picture.name} as the reference image" if reference
                                                  else "") + f" -> art/raw/{stem}.png")
            out.append(f"  \"{prompt(with_refusal(item, refused), style, reference)}\"")
        elif s == "stand-in":
            out.append(f"stand-in {stem}: refused {TRIES} times, it keeps its stand-in; to try again, change its "
                       f"subject in art()")
        else:
            out.append(f"{s} {stem}: {raw.name if (raw := raw_of(root, rel)) else 'art/' + rel}")
    if to_make:
        out.append(f"{count}; next: make each with the image tool, then python {skill}/scripts/prepare_art.py")
    elif counts["prepare"]:
        out.append(f"{count}; next: python {skill}/scripts/prepare_art.py")
    elif counts["stand-in"]:
        out.append(f"{count}; next: python tools/build_project.py")
    else:
        out.append(f"ok: all {counts['done']} pictures done; next: python tools/build_project.py")
    return out


def leaning_to(key: tuple):
    """A function that gives how far a colour leans to the key: the lowest keyed channel less the
    highest other one, about 255 on the key and 0 or less away from it. The lean is linear in a
    blend with the key. Red under magenta and gold under green lean no more than grey."""
    on = [k for k in range(3) if key[k]]
    off = [k for k in range(3) if not key[k]]
    return lambda c: min(c[k] for k in on) - max(c[k] for k in off)


def cut_out(img, key: tuple) -> tuple[object, str]:
    """The picture as RGBA with its background clear, and a line that gives the background's
    colour and counts the pixels cleared in gaps and recoloured. Raises Unusable when the picture
    cannot be cut cleanly."""
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
        raise Unusable(f"its edge is not one flat colour, {near:.0%} of it near {hex_of(bg)}",
                       f"make it again on a flat {name} {hex_of(key)} background, or with a transparent one")
    # the background is the key asked for, or the other one, as a model paints it: the keyed
    # channels lit, the others dark, as in (216, 46, 147) or (8, 162, 24)
    painted = [n for n, k in KEYS.items()
               if min(c for c, on in zip(bg, k) if on) >= 96
               and max(c for c, on in zip(bg, k) if not on) <= 0.35 * min(c for c, on in zip(bg, k) if on)]
    if not painted:
        raise Unusable(f"its background is {hex_of(bg)}, neither magenta nor green, and a cut on it would also "
                       f"remove the subject's parts in that colour",
                       f"make it again on a flat {name} {hex_of(key)} background, or with a transparent one")
    name = painted[0]
    key = KEYS[name]
    if near < 0.9:
        raise Unusable(f"the subject runs off the picture over {1 - near:.0%} of its edge, so it is cut off",
                       "make it again whole and centred, with room around it")
    n = w * h
    br, bgr, bb = bg
    rgb = [data[4 * i:4 * i + 3] for i in range(n)]
    dist2 = [(r - br) ** 2 + (g - bgr) ** 2 + (b - bb) ** 2 for r, g, b in rgb]
    lean = leaning_to(key)
    ex = [lean(c) for c in rgb]
    e_bg = lean(bg)
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
    # to the key is linear in the blend, so a = (lean(b) - lean(o)) / (lean(b) - lean(s)), whatever
    # the subject's colour: red under magenta and gold under green stay opaque. Then the subject's
    # colour is (o - (1-a)*b) / a.
    for i, b in back.items():
        o = rgb[i]
        s = inner.get(i)
        e_s = lean(s) if s else min([0] + [ex[j] for j in around(i) if not clear[j]])
        if ex[i] <= max(e_s, 0) + MARGIN:
            t = on_line(o, b, s) if s and ex[i] > e_s + MARGIN else None
            if t is None or t >= 0.97:
                continue
        e_b = lean(b)
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
        if ex[i] - lean(m) <= SPILL:
            continue
        t = on_line(rgb[i], m, bg)
        if t is None or not 0.1 <= t <= 0.9:
            continue
        out[4 * i:4 * i + 3] = bytes(min(255, max(0, round((rgb[i][k] - t * bg[k]) / (1 - t)))) for k in range(3))
        spill += 1
    cut = Image.frombytes("RGBA", (w, h), bytes(out))
    left, band = fringe(cut, key)
    if left > max(FRINGE_MIN, FRINGE * band):
        other = next(k for k in KEYS if k != name)
        raise Unusable(f"after the cut, {left} of the {band} pixels along the subject's edge lean to {name}: a "
                       f"fringe the cut left, or a subject too near the key",
                       f"make it again on a flat {other} {hex_of(KEYS[other])} background, or with a transparent one",
                       other)
    return cut, f"background {hex_of(bg)}, {gaps} px cleared in gaps, {spill} px of key light recoloured"


def fringe(img, key: tuple) -> tuple[int, int]:
    """Two counts: the shown pixels within 3 px of a clear one that lean to the key by more than
    40, and all shown pixels there."""
    from PIL import Image, ImageFilter
    data = img.tobytes()
    alpha = data[3::4]
    near = Image.frombytes("L", img.size, bytes(255 if a == 0 else 0 for a in alpha)).filter(ImageFilter.MaxFilter(7))
    lean = leaning_to(key)
    left = band = 0
    for i, z in enumerate(near.tobytes()):
        if z and alpha[i] >= 32:
            band += 1
            left += lean(data[4 * i:4 * i + 3]) > 40
    return left, band


def resample(img, size: tuple[int, int], how: int):
    """An RGBA picture scaled with its alpha and its colour apart. Alpha, and the colour weighted
    by alpha, are scaled in floats through `how`, HAMMING or BOX, then divided. These filters have
    no negative lobe, so each pixel's colour is a mix of the colours under it. LANCZOS has one: on
    an edge, its lobes and the division by a low alpha give a light rim and a key tint."""
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
        raise Unusable(f"nothing is left of the subject once the background is removed ({how})",
                       "make the subject in colours far from the background")
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
                            "exit codes: 0 when no picture waits to be made again, the last line starting with ok: once "
                            "all are in art/; 1 when a picture could not be used; 2 when art/wanted.json or Pillow is "
                            "missing")
    ap.add_argument("--list", action="store_true",
                    help="print the next step: ART_STYLE, the key picture, or the prompt of every picture still to "
                         "make, and what is ready")
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
        refused = refusals(root, wanted)
        out, waiting, done, kept = [], 0, 0, 0
        for item in wanted["images"]:
            rel = item["file"]
            stem, raw = rel[:-len(".png")], raw_of(root, rel)
            if state(root, item, refused) == "stand-in":
                kept += 1
                out.append(f"{stem}: refused {TRIES} times, it keeps its stand-in; to try again, change its subject "
                           f"in art()")
                continue
            if raw is None:
                if (root / "art" / rel).exists():
                    done += 1           # put in art/ as it is, by the user
                else:
                    waiting += 1
                continue
            try:
                out += prepare(root, with_refusal(item, refused), wanted)
                done += 1
                refused.pop(rel, None)
            except Unusable as e:
                line = f"{stem}: {raw.name}: {e}"
                if e.again:
                    r = refused.setdefault(rel, {"subject": item["subject"], "pictures": []})
                    if (seen := fingerprint(raw)) not in r["pictures"]:
                        r["pictures"].append(seen)
                    r["again"] = e.again
                    if e.key:
                        r["key"] = e.key
                    if len(r["pictures"]) >= TRIES:
                        kept += 1
                        out.append(f"{line}. Refused {TRIES} times, it keeps its stand-in; to try again, change its "
                                   f"subject in art()")
                        continue
                    line += f" (refused {len(r['pictures'])} of {TRIES} times)"
                failed += 1
                out.append(line)
        if refused or (root / REFUSED).exists():
            (root / REFUSED).write_text(json.dumps(refused, indent=1, ensure_ascii=False), encoding="utf-8")
        counts = f"prepared: {done}, could not use: {failed}, still to make: {waiting}" +             (f", kept as stand-ins: {kept}" if kept else "")
        if failed:
            out.append(f"{counts}; next: make the pictures above again with the prompts python {skill.as_posix()}"
                       f"/scripts/prepare_art.py --list prints, then run this again")
        elif waiting:
            out.append(f"{counts}; next: python {skill.as_posix()}/scripts/prepare_art.py --list for their prompts")
        elif kept:
            out.append(f"{counts}; next: python tools/build_project.py")
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
