"""Print layouts as the Layout View holds them: layers bottom to top, and on each the
instances in Z order with their object, box, size and text, and the object a text sits on.

Read a layout this way to answer where something is, how big it is or what covers what,
and after generating one, to see that a label lies on its button and a backdrop covers
the screen. Whether the look works is still the user's call on a screenshot.
"""
import math
import re
import sys

import c3project as c3

TEXT_PROPERTIES = ("text",)  # Text, SpriteFont, TextInput, Button, HTML elements
EDGE = 0.05  # a value closer than this to a whole pixel prints as that pixel
RUN = 4  # this many instances in a row of one object and size print as one line


def number(v: float) -> str:
    r = round(v)
    return str(r) if abs(v - r) < EDGE else f"{v:.1f}"


def text_of(instance: dict) -> str | None:
    props = instance.get("properties") or {}
    for key in TEXT_PROPERTIES:
        if isinstance(props.get(key), str):
            return props[key]
    return None


def count(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def rows_lines(rows: list[tuple[str, str, tuple, str]], pad: str) -> list[str]:
    """One line per instance; a run of RUN or more of one object with the same size and nothing
    more to say is one line with the box around them all: a wall of 79 tiles."""
    out, i = [], 0
    while i < len(rows):
        j = i
        while j + 1 < len(rows) and rows[j + 1][0] == rows[i][0] and rows[j + 1][3] == rows[i][3] \
                and 'text "' not in rows[i][3]:
            j += 1
        obj, plugin, b, rest = rows[i]
        if j - i + 1 >= RUN:
            run = rows[i:j + 1]
            left, top = min(r[2][0] for r in run), min(r[2][1] for r in run)
            right, bottom = max(r[2][2] for r in run), max(r[2][3] for r in run)
            out.append(f"{pad}  {obj} ({plugin}) x {len(run)}, each {rest}, together x {number(left)}..{number(right)}, "
                       f"y {number(top)}..{number(bottom)}")
            i = j + 1
            continue
        out.append(f"{pad}  {obj} ({plugin})  x {number(b[0])}..{number(b[2])}, y {number(b[1])}..{number(b[3])}, {rest}")
        i += 1
    return out


def layout_lines(p: c3.Project, name: str, layout: dict, only_layer: str | None) -> list[str]:
    props = p.data.get("properties", {})
    vw, vh = props.get("viewportWidth"), props.get("viewportHeight")
    lw, lh = layout.get("width", 0), layout.get("height", 0)
    lines = [f"== {name}  {number(lw)} x {number(lh)}"
             + (f", viewport {vw} x {vh}" if vw and vh else "")
             + (f", event sheet {layout['eventSheet']}" if layout.get("eventSheet") else "")]
    below: list[tuple[str, tuple, bool]] = []  # (object, box, shown) of every instance drawn so far, texts aside
    for layer, depth in c3.layers_of(layout.get("layers", [])):
        pad = "  " * depth
        hud = layer.get("parallaxX", 1) == 0 and layer.get("parallaxY", 1) == 0
        shown_layer = layer.get("isInitiallyVisible", True)
        flags = [f for f, on in (("HUD: parallax 0, fixed to the screen", hud),
                                 ("hidden at start", not shown_layer),
                                 ("not interactive at start", layer.get("isInitiallyInteractive", True) is False),
                                 ("global", layer.get("global"))) if on]
        instances = layer.get("instances", [])
        listed = only_layer is None or layer.get("name") == only_layer
        if listed:
            lines.append(f"{pad}layer {layer.get('name')}" + (f"  [{'; '.join(flags)}]" if flags else "")
                         + (f", {count(len(instances), 'instance')}" if instances else ", empty"))
        rows: list[tuple[str, str, tuple, str]] = []  # (object, plugin, box, the rest of the line)
        for inst in instances:
            world = inst.get("world") or {}
            obj = inst.get("type", "?")
            b = c3.box(world)
            shown = shown_layer and (inst.get("properties") or {}).get("initially-visible", True) is not False
            if listed:
                plugin = p.plugin_of.get(obj, "?")
                notes = []
                opacity = (world.get("color") or [1, 1, 1, 1])[3]
                if opacity < 1:
                    notes.append(f"opacity {round(opacity * 100)}%")
                if (inst.get("properties") or {}).get("initially-visible") is False:
                    notes.append("invisible")
                if world.get("angle"):
                    notes.append(f"angle {number(math.degrees(world['angle']))} degrees, box unrotated")
                if b[2] <= 0 or b[3] <= 0 or b[0] >= lw or b[1] >= lh:
                    notes.append("outside the layout")
                text = text_of(inst)
                if text is not None:
                    shown_text = re.sub(r"\s+", " ", text).strip()
                    notes.append(f'text "{shown_text[:60]}{"..." if len(shown_text) > 60 else ""}"')
                    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                    under = [o for o, ob, on in below if on and ob[0] <= cx <= ob[2] and ob[1] <= cy <= ob[3]]
                    notes.append(f"on {under[-1]}" if under else "on no object")
                rows.append((obj, plugin, b, f"{number(world.get('width', 0))} x {number(world.get('height', 0))}"
                             + (f"  [{'; '.join(notes)}]" if notes else "")))
            if text_of(inst) is None:
                below.append((obj, b, shown))
        if listed:
            lines += rows_lines(rows, pad)
    if only_layer and len(lines) == 1:
        names = [layer.get("name") for layer, _ in c3.layers_of(layout.get("layers", []))]
        lines.append(f"no layer named {only_layer!r}; layers: {', '.join(names)}")
    return lines


def main() -> int:
    ap = c3.argument_parser(
        "Print layouts: layers bottom to top, each instance in Z order with its object, box in layout "
        "pixels, size, opacity and text, and the object under the middle of a text. Read a layout this "
        "way to say where things are and what covers what, and after generating one.",
        "examples:\n"
        "  python scripts/print_layout.py                     every layout\n"
        "  python scripts/print_layout.py Game                one layout\n"
        "  python scripts/print_layout.py Game --layer HUD    one layer of it\n\n"
        "A text marked 'on no object' lies on no instance drawn below it: a label meant for a button is\n"
        "off the button. The box ignores the angle of a rotated instance.\n\n"
        "exit codes: 0 printed, whole or the part that fits; 1 no such layout, or project/clone not found")
    ap.add_argument("layouts", nargs="*", metavar="LAYOUT", help="layout names (default: every layout)")
    ap.add_argument("--layer", metavar="NAME", help="print only this layer of each layout")
    args = ap.parse_args()
    c3.utf8_output()
    findings = c3.Findings()
    c3.stop_with_a_sentence("print_layout.py", findings)
    project = c3.Project.open(args, findings)
    layouts = project.load_listed("layouts")
    if not layouts:
        print("no layouts: project.c3proj lists none")
        return 0
    for name in args.layouts:
        if name not in layouts:
            print(f"no layout named {name!r}; layouts: {', '.join(layouts)}")
            return 1
    lines = [line for name in args.layouts or layouts
             for line in layout_lines(project, name, layouts[name], args.layer)]
    fit = c3.fitting(lines, max(args.limit - 300, 1) if args.limit else 0)
    print("\n".join(lines[:fit]))
    if fit < len(lines):
        print(f"-- {len(lines) - fit} more lines past --limit {args.limit}; name one layout, add --layer, "
              f"or raise --limit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
