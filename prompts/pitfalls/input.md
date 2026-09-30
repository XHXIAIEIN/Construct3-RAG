# Event Sheet Pitfalls: Input

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- The Mouse object reacts only to a pointer whose type is mouse: *Mouse
  button is down*, *On any click*, *On button released*, a single *On
  click* and `Mouse.X`, `Mouse.Y` ignore a finger and a pen. *On movement*
  is the exception and fires for touch too. Touch with *Use mouse input* on fires
  for the mouse and the finger alike and has no expression for the pointer
  type, and Drag & Drop takes a left click and a finger without the Touch
  object. So a drag that behaves differently under a finger, such as a piece
  lifted higher so the finger does not hide it, asks `Mouse: Mouse button is
  down (left)`: true while a mouse drags, false while a finger does. Test it
  in an event that runs every tick under Drag & Drop *Is dragging*, not
  under *On drag start*: that trigger runs from the same pointer-down
  dispatch as the Mouse object's own handler, and which of the two runs
  first is the order they subscribed in, which nothing documents. This picks
  per drag, so a touchscreen laptop gets each drag right; the input-method
  triggers of the next entry pick a control scheme instead. [runtime:
  exported c3runtime.js r503, `Plugins.Mouse.Instance` `_OnPointerDown`,
  `_OnPointerMove` and `_OnPointerUp` each test `"mouse"===e["pointerType"]`
  before touching the position or the button map, and the movement trigger
  in `_OnPointerMove` runs before that test, while a double click comes
  from the browser's `dblclick` untested; `Plugins.Touch.Instance`
  `_OnPointerDown` drops only a mouse pointer with *Use mouse input* off;
  `Behaviors.DragnDrop` listens to the pointer events itself; manual:
  plugin-reference/mouse.md "On movement", plugin-reference/touch.md "Use
  mouse input"; schema: plugins/touch.json has no pointer-type expression;
  observed in a game project, r503 preview, 2026-09-30]
- With *Use mouse input* on, a left click is a touch: *On any touch start*,
  *On touched object* and *On tap* fire for it, so a Touch trigger cannot
  say the player used a finger. Detecting the input method needs it off:
  *On any touch start* then means a finger or a pen, and Mouse *On any
  click* or Keyboard *On any key pressed* means a desktop; each sets a
  global the controls are chosen from (see "Native first" in
  [event-sheet-thinking.md](../event-sheet-thinking.md)). With it off a
  mouse fires no Touch trigger at all, so every button the mouse must press
  needs a Mouse event of its own; a project that clicks its Touch buttons
  with the mouse keeps it on and tells a finger drag from a mouse drag with
  the Mouse test above. The global follows the last input, and whether it
  has changed yet when a drag starts on the same press is the same
  undocumented order as above. [manual: plugin-reference/touch.md "Use mouse
  input"; example: detecting-input-method, `Title events` event 3 and its
  comment, Touch object with *Use mouse input* off; runtime: exported
  c3runtime.js r503, `Plugins.Touch.Instance._OnPointerDown`]
