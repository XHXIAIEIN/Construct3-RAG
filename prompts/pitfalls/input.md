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
- Touch *On touched object*, *Is touching object*, *On tap object* and
  Mouse *On object clicked*, *Is over object* find an instance by its shape
  under the pointer and nothing else: an invisible instance, one with
  collisions disabled and one on an invisible layer are all pressed. Only a
  layer that is not interactive, or an instance outside the viewport, is
  passed over. A button hidden to switch it off keeps working: add *Is
  visible* to its event, or turn its layer off with *Set layer interactive*.
  Collisions disabled fails overlap and collision tests, not these. [runtime:
  exported c3runtime.js r504, those conditions call
  `TestAndSelectCanvasPointOverlap`, which tests the layer's
  `IsSelfAndParentsInteractive`, `IsInViewport2` and `ContainsPoint`;
  manual: project-primitives/layers.md "Initially interactive"; observed in
  a game project, r504 preview, 2026-10-03: a tap on a button ran its *On
  touched object* event with the button invisible, with its collisions
  disabled and with its layer invisible, and did not with the layer not
  interactive]
- A game that moves with W, A, S and D alone is hard to control on an
  AZERTY keyboard, where those letters sit elsewhere and ZQSD takes their
  place. Give every direction its arrow key as well, in an OR block with
  the letter or in an event of its own; arrows cover most layouts. The same
  holds for any control chosen for where its key sits.
  The 8 Direction, Platform and Car behaviors move with the arrow keys while
  *Default controls* is on; a project that turns it off to simulate controls
  from letters adds the arrows itself. [manual:
  plugin-reference/keyboard.md, the note on keyboard layouts;
  behavior-reference/8-direction.md, platform.md and car.md "Default
  controls"; example: detecting-input-method, `Game events` 5 to 8: each
  direction an OR block of its arrow key and its letter, simulating 8
  Direction]
- *Request fullscreen*, *Request install*, *Request permission* (Touch),
  *Request wake lock*, *Request pointer lock*, *Share*, the clipboard's paste
  requests, the File chooser's *Click*, the File System pickers, a Bluetooth
  device request, screen recording, speech recognition and Google Play
  *Sign in* ask the browser for something it grants only just after the
  player touched, clicked or pressed a key. In *On start of layout* or on a
  timer the browser refuses *Request fullscreen*, and *On fullscreen error*
  fires. Put each in an event with an *On tap*, *On click*, *On key pressed*
  or form control trigger, such as a fullscreen button, or in a function
  such an event calls. The `construct3-agent-plugin` skill's
  `check_project.py` warns when one has no touch, mouse, keyboard or form
  control condition in its event or above it. *Request MIDI access* is
  the exception: some browsers allow it on startup, so the MIDI examples ask
  there and offer a button for a second try. [manual:
  plugin-reference/browser.md "Request fullscreen", "On fullscreen error",
  "Request install"; touch.md "Request permission"; platform-info.md
  "Request wake lock"; mouse.md "Request pointer lock"; share.md;
  clipboard.md; file-chooser.md "Click"; filesystem.md; bluetooth.md;
  bbc-micro-bit.md; video-recorder.md; speech-recognition.md;
  google-play.md "Sign in"; midi.md; example: midi-input, event 2]
