# Event Sheet Pitfalls: Coordinates and angles

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- The origin (0, 0) is the top-left of the layout and Y grows downwards. So
  up is `Y - n`, gravity pulls towards +Y, and the top of the screen is the
  smallest Y. [manual: tips-and-guides/common-conventions.md "Units"]
- Angles are in degrees. 0 faces right and angles increase clockwise, so 90
  points down, 180 left and 270 (or -90) up. 360 is 0 again, so a bullet
  fired at 360 goes right, and `random(360)` is a full turn. `sin`, `cos` and
  `angle` take and return degrees. Some expressions return -180..180 and
  others 0..360. So compare angles with `anglediff`, *Is between angles* or
  *Is clockwise from*, never with `<`. Normalise with `(a + 360) % 360` only
  where a value must land in 0..360. [manual:
  tips-and-guides/common-conventions.md "Units";
  system-reference/system-expressions.md "Math";
  system-reference/system-conditions.md "Is between angles"]
- A sprite is drawn facing right at angle 0. So art painted pointing up
  appears turned a quarter clockwise when *Set angle towards position* runs.
  Paint it facing right, or add the same 90 in every *Set angle*. Do not add a
  different correction in each event. [consequence of the same convention;
  Rotate's speed is positive clockwise: manual behavior-reference/rotate.md
  "Speed"]
- A Bullet's angle of motion and the object's angle are two values. They
  change together only while the behavior's *Set angle* property is on, and 8
  Direction and Car have the same property. At speed 0 the angle of motion is
  0 and cannot be set, so set the speed first, then the angle. [manual:
  behavior-reference/bullet.md "Set angle", "Set angle of motion",
  "AngleOfMotion"; behavior-reference/8-direction.md "Set angle"; Ashley in
  Scirra/Construct-bugs#6105: by design, set the angle of motion again after
  the speed]
- A sprite's origin is image point 0, the point X, Y and rotation refer to.
  The editor puts it at the centre (`originX`, `originY` 0.5 in the layout
  file), so a sprite at the layout's edge shows half. For a muzzle or a
  hinge, position by an image point (*Spawn another object* takes one). Move
  the origin in the image editor, not by an offset in events. [manual:
  interface/animations-editor.md "Image points"; official example layouts]
- `ViewportLeft`, `ViewportWidth` and the rest take a layer, because a
  parallaxed or scaled layer shows a different rectangle. Write
  `ViewportLeft("HUD")`. `LayoutWidth` is the whole layout,
  `ViewportWidth(layer)` the part on screen in layout coordinates, and
  `OriginalViewportWidth` the project's *Viewport size* property. [manual:
  system-reference/system-expressions.md "Viewport", "Layout";
  plugins/system.json: every `Viewport*` expression has a `layer` parameter]
- Under *Scale outer* the screen shows more than the *Viewport size* on its
  longer side, split evenly. A parallax 0, 0 layer is centred on the original
  viewport too. So a HUD placed at the top of the viewport stays at the top
  of the design area, not at the top of a taller screen, and the layout
  beyond the viewport shows on the sides. Pin an edge HUD with the Anchor
  behavior on that layer. If a backdrop must reach the screen's sides, give
  it Anchor with *Left edge* Viewport left and *Right edge* Viewport right.
  The right edge resizes it to the screen's width, so lay it out a little
  wider than the viewport, not thousands of pixels past the layout. A shaking
  camera moves the viewport, and 20 px past each side covers a shake of 8.
  Anchor moves a left edge without resizing. So if a piece grows to one side
  only, its other end fixed, set it under *On start of layout* OR Browser *On
  resized*. Set its width to `Self.BBoxRight - ViewportLeft(layer) + 20`,
  then its X to `ViewportLeft(layer) - 20`. [manual:
  behavior-reference/anchor.md; observed in a game project, a 430×932
  portrait export switched to *Scale outer* and shown at 560×380 and 300×700
  in Chrome, 2026-09-30; the Anchor backdrop and the one-sided piece
  previewed at 900×500 and 330×800 and after a resize, r504, 2026-09-30]
- Drag & Drop moves the dragged instance only when the pointer moves. It sets
  the position to the pointer minus the grab offset, and a tick without
  movement writes nothing. A *Set position* on the dragged instance holds
  while the finger rests, but the next move overwrites it. So put a look that
  trails or lifts above the finger on a child the events position. Drops and
  overlaps are still judged by the dragged instance. [runtime: exported
  c3runtime.js r503, `Behaviors.DragnDrop` `_OnMove`, called from the
  `pointermove` dispatch only; observed in a game project, r503 preview,
  2026-09-29]
