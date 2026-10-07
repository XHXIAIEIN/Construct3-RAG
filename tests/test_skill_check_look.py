"""check_look.py: the look's rules, read off the images, layouts and sheets of a project."""
import re
import struct
import zlib

from tests.skill_helpers import tool, edit, template_module


def png_chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def test_check_look_passes_the_stand_in_and_names_each_fault(project):
    code, out = tool(project, "check_look")
    assert code == 0 and out.splitlines()[-1].startswith("ok: 4 images, 3 world instances on a 32 px grid, "
                                                          "1 runtime creations"), out
    t = template_module()
    t.ROOT = project
    t.write_png("smudge.png", 2, 1, lambda x, y: [(9, 9, 9, 0), (*t.PALETTE["danger"], 128)][x])
    t.write_png("glow.png", 1, 1, lambda x, y: (*t.PALETTE["danger"], 37), painted=True)
    (project / "images" / "dirty.png").write_bytes(      # a clear pixel with a colour under it
        b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(bytes([0, 9, 9, 9, 0]))) + png_chunk(b"IEND", b""))
    edit(project, "layouts/Objects.json", lambda d: d["layers"][0]["instances"][0]["world"].update(x=150))
    sheet = project / "eventSheets" / "Game.json"
    sheet.write_text(re.sub(r'"x": "(?:[^"\\]|\\.)*loopindex(?:[^"\\]|\\.)*"', '"x": "random(96, 1728)"',
                            sheet.read_text(encoding="utf-8"), count=1), encoding="utf-8")
    code, out = tool(project, "check_look")
    assert code == 1, out
    assert "alpha.pure: images/dirty.png has 1 clear pixels that hold a colour, the first at (0,0)" in out
    assert re.search(r"alpha.pure: images/glow.png has alpha 37 at \(0,0\); the project's shadow is 128.*--painted glow.png", out)
    assert re.search(r"grid.world-placement: layout Objects layer Objects: Coin at \(\d+,\d+\) \d+x\d+ is off the 32 px grid", out)
    assert "grid.runtime-spawn: sheet Game: create Coin at x = random(96, 1728), a raw random()" in out
    assert out.splitlines()[-1].startswith("4 findings:")
    code, out = tool(project, "check_look", "--painted", "glow.png")
    assert "glow.png" not in out and out.splitlines()[-1].startswith("3 findings:")
    edit(project, "objectTypes/Coin.json", lambda d: d["behaviorTypes"].append(
        {"behaviorId": "Flash", "name": "Flash", "sid": 633333333333333}))
    code, out = tool(project, "check_look", "--painted", "glow.png")
    assert "motion.hit: Coin has the Flash behavior Flash; a hit shows as a colour for an instant" in out
    edit(project, "objectTypes/Coin.json", lambda d: d["behaviorTypes"].append(
        {"behaviorId": "solid", "name": "Solid", "sid": 644444444444444}))
    code, out = tool(project, "check_look", "--painted", "glow.png")
    assert ("motion.squash-art: sheet Game: Coin is squashed but has solid, so its collision box grows into the "
            "floor; squash its art") in out
