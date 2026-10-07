# Event Sheet Pitfalls: Input

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- The Mouse object reacts only to a pointer whose type is mouse. *Mouse button
  is down*, *On any click*, *On button released*, a single *On click* and
  `Mouse.X`, `Mouse.Y` ignore a finger and a pen. *On movement* is the
  exception and fires for touch too. Touch with *Use mouse input* on fires for
  the mouse and the finger alike and has no expression for the pointer type.
  Drag & Drop takes a left click and a finger without the Touch object. So if
  a drag behaves differently under a finger, such as a piece lifted higher so
  the finger does not hide it, test `Mouse: Mouse button is down (left)`: true
  while a mouse drags, false while a finger does. Test it in an event that
  runs every tick under Drag & Drop *Is dragging*, not under *On drag start*.
  That trigger runs from the same pointer-down dispatch as the Mouse object's
  own handler, and the two run in the order they subscribed in, which nothing
  documents. This test decides per drag, so a touchscreen laptop gets each
  drag right. The input-method triggers of the next entry choose a control
  scheme instead. [runtime: exported c3runtime.js r503,
  `Plugins.Mouse.Instance` `_OnPointerDown`, `_OnPointerMove` and
  `_OnPointerUp` each test `"mouse"===e["pointerType"]` before touching the
  position or the button map, and the movement trigger in `_OnPointerMove`
  runs before that test, while a double click comes from the browser's
  `dblclick` untested; `Plugins.Touch.Instance` `_OnPointerDown` drops only a
  mouse pointer with *Use mouse input* off; `Behaviors.DragnDrop` listens to
  the pointer events itself; manual: plugin-reference/mouse.md "On movement",
  plugin-reference/touch.md "Use mouse input"; schema: plugins/touch.json has
  no pointer-type expression; observed in a game project, r503 preview,
  2026-09-30]
- With *Use mouse input* on, a left click is a touch. *On any touch start*,
  *On touched object* and *On tap* fire for it, so a Touch trigger cannot
  detect a finger. Detect the input method with *Use mouse input* off. Then
  *On any touch start* means a finger or a pen, and Mouse *On any click* or
  Keyboard *On any key pressed* means a desktop. Each sets a global variable
  that decides the controls (see "Native first" in
  [event-sheet-thinking.md](../event-sheet-thinking.md)). The example
  detecting-input-method decides once, on its title screen. The same triggers
  in a sheet that runs during play follow a change of device. Gamepad *On any
  button pressed* adds a gamepad. With *Use mouse input* off, a mouse fires
  no Touch trigger, so every button the mouse must press needs its own Mouse
  event. A project that clicks its Touch buttons with the mouse keeps the
  setting on and tells a finger drag from a mouse drag with the Mouse test
  above. The global variable follows the last input. Whether it has changed
  when a drag starts on the same press depends on the same undocumented order
  as above. [manual: plugin-reference/touch.md "Use mouse input"; example:
  detecting-input-method, `Title events` events 2 and 3 and the comment of 3,
  Touch object with *Use mouse input* off; schema: plugins/gamepad.json
  `on-any-button-pressed`, a trigger; runtime: exported c3runtime.js r503,
  `Plugins.Touch.Instance._OnPointerDown`]
- Touch *On touched object*, *Is touching object*, *On tap object* and Mouse
  *On object clicked*, *Cursor is over object* find an instance only by its shape
  under the pointer. So the player can press an invisible instance, one with
  collisions disabled and one on an invisible layer. These conditions skip
  only an instance outside the viewport or on a layer that is not interactive.
  A button hidden to switch it off still works. Add *Is visible* to its event,
  or turn its layer off with *Set layer interactive*. Disabled collisions fail
  overlap and collision tests, not these. [runtime: exported c3runtime.js
  r504, those conditions call `TestAndSelectCanvasPointOverlap`, which tests
  the layer's `IsSelfAndParentsInteractive`, `IsInViewport2` and
  `ContainsPoint`; manual: project-primitives/layers.md "Initially
  interactive"; observed in a game project, r504 preview, 2026-10-03: a tap on
  a button ran its *On touched object* event with the button invisible, with
  its collisions disabled and with its layer invisible, and did not with the
  layer not interactive]
- Touch *On touched object*, *On tap object* and Mouse *On object clicked*
  pick every instance under the pointer, not the one in front. So when
  popups, menus or buttons overlap, a click or tap on the front one also
  runs the event for each instance behind it: the press goes through. Add
  the button's own *Pick top/bottom* (top) as a second condition of the
  trigger's event: it keeps the front instance, counting layers first and
  then Z order, so it works across popup layers too. It compares instances of
  one object type, so buttons made of several types go into a family and the
  event uses the family. [manual: plugin-reference/common-features/common-conditions.md
  "Pick top/bottom"; runtime: the `TestAndSelectCanvasPointOverlap` of the
  entry above selects each instance that contains the point]
- Drag & Drop starts one drag per press, on the front instance under the
  pointer: the one on the highest layer, then the one highest in Z order on
  that layer. It considers only instances whose behavior is enabled and
  whose layer is interactive, of every object type that has the behavior. It
  ignores visibility, of the instance and of its layer. A popup without
  Drag & Drop takes no part, so the pieces under it can still be dragged, and
  a hidden piece or a piece on a hidden layer is dragged too. To stop drags
  while a popup shows, turn the pieces' layer off with
  *Set layer interactive*, or the behavior with *Set enabled*. [runtime:
  exported c3runtime.js r504, `Behaviors.DragnDrop` `_OnInputDown` skips an
  instance whose behavior is disabled or whose layer fails
  `IsSelfAndParentsInteractive`, then keeps the instance with the highest
  layer index, then the highest Z index; observed in a minimal project, r504
  preview, 2026-10-05: of two overlapping instances on two layers, the upper
  layer's dragged, also with that layer hidden and with that instance
  hidden, and the lower one dragged once the upper layer was not interactive;
  of two on one layer, the higher in Z dragged]
- A touch's speed, from `Touch.SpeedAt`, `Touch.SpeedForID` or *Compare
  touch speed*, is the distance between the last two pointer moves divided by
  the time between them. Once the finger has been still for about 50 ms, the
  speed reads 0. The release adds no move. So in *On any touch end* the speed
  is that of the last move if the finger lifts while it moves, and 0 if it
  stopped first: a flick test there passes only for a release made in
  motion. [runtime: exported c3runtime.js r504, `Plugins.Touch.TouchInfo`
  `GetSpeed`; `Plugins.Touch.Instance` `_OnTick2` sets a touch's last time
  to the present once it has not moved for 50 ms, which makes the speed 0,
  and `_OnPointerUp` records no position; observed in a minimal project, r504
  preview, 2026-10-05: pointer events dispatched in the page, ten moves
  16 ms apart, read 1829 px/s in *On any touch end* with the release 16 or
  36 ms after the last move, and 0 with the release 56 ms or more after it]
- *Simulate control* acts in the tick it runs, as if the control were held
  for that tick. So put it in an event whose condition stays true while the
  control is held, such as Keyboard *Key is down*. In an *On key pressed*
  event the player moves for one tick and stops. [manual:
  behavior-reference.md "Custom controls", the tip that the input events
  must be continually true]
- *Default controls* is a property of each instance, and every instance
  with it on moves with the arrow keys. A crate given Platform to be pushed,
  or an enemy given 8 Direction, has it on by default and walks with the
  player. Turn it off on every instance the player does not steer, in each
  layout: `"default-controls": false` in the instance's behavior
  properties. Move those objects with *Simulate control*. The
  `construct3-agent-plugin` skill's `check_project.py` warns when instances
  of two object types in one layout have it on. [manual:
  behavior-reference/platform.md, 8-direction.md, car.md and
  tile-movement.md "Default controls"]
- A game that moves with W, A, S and D alone is hard to control on an AZERTY
  keyboard. There those letters sit elsewhere and ZQSD takes their place.
  Give every direction its arrow key too, in an OR block with the letter or
  in its own event. The arrow keys work on most layouts. The same holds for
  any control chosen for where its key sits. The 8 Direction, Platform and
  Car behaviors move with the arrow keys while *Default controls* is on. A
  project that turns it off to simulate controls from letters adds the arrows
  itself. [manual: plugin-reference/keyboard.md, the note on keyboard
  layouts; behavior-reference/8-direction.md, platform.md and car.md "Default
  controls"; example: detecting-input-method, `Game events` 5 to 8: each
  direction an OR block of its arrow key and its letter, simulating 8
  Direction]
- These actions ask the browser for something it grants only just after the
  player touches, clicks or presses a key: *Request fullscreen*, *Request
  install*, *Request permission* (Touch), *Request wake lock*, *Request
  pointer lock*, *Share*, the clipboard's paste requests, the File chooser's
  *Click*, the File System pickers, a Bluetooth device request, screen
  recording, speech recognition and Google Play *Sign in*. In *On start of
  layout* or on a timer the browser refuses *Request fullscreen*, and *On
  fullscreen error* fires. Put each in an event with an *On tap*, *On click*,
  *On key pressed* or form control trigger, such as a fullscreen button, or in
  a function such an event calls. The `construct3-agent-plugin` skill's
  `check_project.py` warns if one has no touch, mouse, keyboard or form
  control condition in its event or above it. *Request MIDI access* is the
  exception. Some browsers allow it on startup, so the MIDI examples ask there
  and offer a button for a second try. [manual: plugin-reference/browser.md
  "Request fullscreen", "On fullscreen error", "Request install"; touch.md
  "Request permission"; platform-info.md "Request wake lock"; mouse.md
  "Request pointer lock"; share.md; clipboard.md; file-chooser.md "Click";
  filesystem.md; bluetooth.md; bbc-micro-bit.md; video-recorder.md;
  speech-recognition.md; google-play.md "Sign in"; midi.md; example:
  midi-input, event 2]
