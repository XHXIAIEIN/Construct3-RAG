# A Generated Game Fills the Screen, and Its Layers Read in Order

Date: 2026-10-08
Schema: Construct 3 r495.2

## Problem

A generated game fills the screen at any aspect ratio. A *Letterbox* mode
shows bars on a screen whose shape differs from the viewport's, and a
browser window rarely has the viewport's shape.

Filling the screen has two traps, both in `prompts/pitfalls/`:

- Under *Scale outer* the screen shows more than the viewport on its longer
  side, and a layer at parallax 0 stays centred on the viewport. A HUD
  placed at the viewport's edge then floats inside a wider or taller screen
  (`coordinates-and-angles.md`).
- A backdrop or a popup's dim sized to the viewport leaves strips
  uncovered. The layer's colour shows there, and a tap there misses the
  dim (`input.md`).

The Layout View draws a layer in the order its file lists the instances.
An order left to placement shows an order no user would choose, and a
label listed before its panel draws under it.

## Evidence

- Most official examples use a *Letterbox* mode, so the examples' habit
  does not decide the default. The examples that use the Anchor behavior
  run under *Scale outer* or *Letterbox scale*. They write *Left edge*
  `window-left` with *Top edge* `window-top` or `window-bottom`, and the
  other two edges `none`.
- The manual: *Left edge* and *Top edge* move an object to keep its
  distance from the viewport edge they name, without resizing it. *Right
  edge* and *Bottom edge* resize it. An anchored object belongs on a layer
  at parallax 0 (`behavior-reference/anchor.md`).
- A game generated from the template needed all three: *Scale outer*, an
  anchored hint, and layers sorted by the Y of each object's feet.
- Previews of the stand-in game at 430×932, 1280×720 and 1600×700, and at
  320×180 under *Integer scale outer* (r495.2): every label sat `MARGIN`
  from the screen's edges it hangs on, right and bottom included. The
  backdrop and a dim covered every corner of the screen.

## Options

1. **Keep Letterbox.** Nothing to anchor or cover, but bars on most
   screens.
2. **Scale outer, with each game placing its own HUD for it.** Every
   generated game repeats the two traps until its author meets them.
3. **Scale outer in the template, with the HUD helpers anchoring and the
   backdrop covering by default.** The helpers already know the edge each
   element hangs on. Chosen.

For pixel art, *Integer scale outer* is chosen because every pixel stays
square. The cost is a margin that varies with the screen. *Scale outer*
would fill exactly but scale the pixels unevenly.

## Decision

- `FULLSCREEN` is `scale-outer`, or `integer-scale-outer` when `PIXEL_ART`.
  `build_project()` writes it over the mode an editor-saved project holds.
  A game that wants another mode sets `FULLSCREEN` below the helpers' end
  marker.
- `anchored(where)` gives the Anchor behavior's block for an edge or
  corner. The left edge goes to `window-left` or `window-right`, the top
  edge to `window-top` or `window-bottom`, and a centred axis gets `none`,
  since the viewport stays centred. `hud_text()`, `hud_bar()`,
  `labelled_bar()` and `band_text()` give the block to what they place. An
  instance placed by `anchor()` or `row()` takes it as `behaviors=`.
  `build_all()` gives each type with an anchored instance the behavior, and
  that type's other instances a block that holds nothing (`anchor_types()`).
- `backdrop()` and `screen_box()` reach `SCREEN_PAD`, twice the viewport's
  longer side, past the viewport on every side. This covers a screen up to
  4:1 in either orientation. A dim is laid out over `screen_box()`. The tap
  that closes a popup is still tested against the panel, as `input.md`
  says.
- `layout()` turns on *Unbounded scrolling* in a layout of the viewport's
  size. Bounded, the camera keeps the layout's left and top edges on the
  screen's: a preview at 1600×700 showed the stage left of the screen's
  middle, where the HUD is centred. Unbounded, both layers share the
  centre. A larger layout keeps bounded scrolling, and its backdrop covers
  what shows past its edges.
- `build_all()` lists every layer in `z_order()`. The backdrop comes first,
  then the areas of `pattern()`, then the rest by the Y of their feet. A
  child of `link()` follows its parent. A box wholly inside another box
  follows it, unless the outer box is a label: a fill follows its frame.
  Equal keys keep the placement order. A game that draws by another rule,
  such as a 3D layer by depth, defines `z_order()` below the end marker.
- `check_look.py` warns, `screen.fill`, when `project.c3proj` is in a
  *Letterbox* mode. It is a warning, not a finding, because the editor
  accepts the mode and the bars can be a choice.
- `check_look.py` does not flag an edge HUD element without Anchor.
  Position alone does not tell an edge element from a centred one, so the
  check would give false findings.

## Re-evaluate when

- A preview shows an anchored HUD element off its edge, or a backdrop edge
  on screen.
- A small model's generated game places a HUD element without
  `anchored()`. No eval has run on this change, because it is in the
  helpers' defaults, which a run copies with the template.
- A game needs a HUD element centred on an edge that grows with the screen,
  which needs *Right edge* or *Bottom edge*.
- Users of the skill ask for bars, such as for a game designed to one
  fixed screen shape.
