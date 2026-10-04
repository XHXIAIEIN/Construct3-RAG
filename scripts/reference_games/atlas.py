"""Tile a game's image atlases into one PNG and measure its palette.

    python -m scripts.reference_games atlas <folder> [more folder names]

Writes ``decoded/<game>/images.png`` (atlases on a mid-grey checker, each scaled to fit a
512 px cell) and ``decoded/<game>/palette.json`` (the most common opaque colours after
quantising to 32 levels per channel, weighted by pixel count).
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw

from .catalog import DECODED

CELL = 512


def checker(w: int, h: int, size: int = 16) -> Image.Image:
    im = Image.new("RGB", (w, h), (150, 150, 150))
    d = ImageDraw.Draw(im)
    for y in range(0, h, size):
        for x in range((y // size) % 2 * size, w, size * 2):
            d.rectangle([x, y, x + size - 1, y + size - 1], fill=(170, 170, 170))
    return im


def main() -> None:
    for arg in sys.argv[1:]:
        game = Path(arg)
        files = sorted(p for p in (game / "images").glob("*") if p.suffix.lower() in {".png", ".webp", ".jpg", ".jpeg"})
        if not files:
            print(f"{game.name}: no images")
            continue
        colours: Counter = Counter()
        thumbs = []
        for f in files:
            try:
                im = Image.open(f).convert("RGBA")
            except OSError:
                continue
            small = im.copy()
            small.thumbnail((256, 256))
            for r, g, b, a in small.get_flattened_data():
                if a > 200:
                    colours[(r >> 3 << 3, g >> 3 << 3, b >> 3 << 3)] += 1
            if im.width * im.height < 64:
                continue
            im.thumbnail((CELL, CELL), Image.NEAREST if im.width < CELL // 2 else Image.LANCZOS)
            thumbs.append(im)
        thumbs.sort(key=lambda t: -t.width * t.height)
        thumbs = thumbs[:24]
        cols = 4
        rows = (len(thumbs) + cols - 1) // cols
        sheet = checker(cols * CELL, max(1, rows) * CELL)
        for i, t in enumerate(thumbs):
            x, y = i % cols * CELL, i // cols * CELL
            sheet.paste(t, (x + (CELL - t.width) // 2, y + (CELL - t.height) // 2), t)
        dest = DECODED / game.name
        dest.mkdir(parents=True, exist_ok=True)
        sheet.save(dest / "images.png")
        total = sum(colours.values()) or 1
        top = [{"hex": "#%02x%02x%02x" % c, "share": round(n / total, 4)} for c, n in colours.most_common(24)]
        (dest / "palette.json").write_text(json.dumps(top, indent=1), encoding="utf-8")
        print(f"{game.name}: {len(files)} images, sheet {sheet.size}, top colours " + " ".join(t["hex"] for t in top[:8]))


if __name__ == "__main__":
    main()
