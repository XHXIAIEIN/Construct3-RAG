# Input Controls: A Slider, a Toggle and a Text Input in the Template

Date: 2026-10-08
Schema: Construct 3 r495.2

## Problem

A settings screen, a name entry or a tuning panel needs a slider, a toggle
and a text box. Drawn by each game, they sit off the grid, in their own
colours, and often work for the mouse only.

Task: each control as one helper call in the template, in the template's
look and on its grid, working with a mouse on a desktop and a finger on a
phone, and events that hand the game its value.

## Evidence

### What Construct and the official examples offer

- Construct's form controls (`button`, `textbox`, `sliderbar`, `list`,
  `progressbar` in `data/c3-schemas/_index.json`) are HTML elements over
  the canvas. They draw over every layer, take no colour of `PALETTE`
  and no Tween (manual: plugin-reference/text-input.md, "Layering HTML
  objects"). The official examples use Text inputs and no Slider bar.
- The examples draw a slider and a toggle on the canvas. audio-player's
  slider knob is a Sprite with Drag & Drop. fireworks-designer moves its
  knob to `clamp(Touch.X, MinX, MaxX)` while a finger is on the bar and
  reads `unlerp(MinX, MaxX, X)`. planet-generator's toggle is a Sprite of
  two frames with Tween.
- A text input's *Auto font size* sets its font to the layer's display
  scale minus 0.2, in em (exported c3runtime.js r503, `_UpdatePosition`
  of the DOM element instance; the r495.2 preview below ran with the
  property off). By that formula a 1920x1080 viewport in
  a 1280 px window, a scale of 0.67, gets 0.47 em, under half the labels'
  size. With the property off, *Set CSS style* sets the font size, and
  `min(a vw, b vh)` scales it as Scale outer scales the canvas: by the
  smaller of the window's width and height over the viewport's.

### What the preview showed

A scratch project with two sliders, a toggle and a text input, each
placed by one call, played in the r495.2 editor's preview from a plan,
once with the mouse at 1280x720 and once with touches at 932x430. The
globals the events set were read after each step:

| Input | Global after it |
|-------|-----------------|
| Drag the volume knob past the track's right end | volume 100 |
| Drag it to a quarter of the track | volume 25 |
| Tap the speed track (0.5 to 2.5, step 0.5) at three quarters | speed 2 |
| Press the speed track away from its knob and slide | speed 1, the step nearest the finger |
| Tap the toggle, then tap it again | sound false, then true |
| Tap the text input and type two keys | player "hi" |

Both runs logged no runtime error. A knob that is a child of its track in
the layout's hierarchy drags with Drag & Drop. At 932x430 the field's text
was the labels' size, so the CSS font size scales with the canvas.

The value after the track and the value over the knob both read cleanly
in a screenshot. The value over the knob stands above the row, so it needs
a free row above it.

## Options

1. The form controls for all three: no layers, no palette, no Tween, and
   a slider bar that no official example uses.
2. All three drawn on the canvas, the text input included: a caret,
   selection, paste and an input method for Chinese rebuilt in events.
3. The slider and the toggle drawn on the canvas, the text input the form
   control placed and styled in the look.

## Decision

Option 3.

- A control is a row TOUCH high from a grid cell: its label, when it has
  one, then the control. Its whole box takes the finger, however small
  its drawing. `CONTROL_SIZE` gives the drawing: a slider bar of half a
  unit, a knob of two units and a switch of four by two, near Material's
  4 to 16 dp track, its 20 dp handle and its 52 x 32 dp switch at the
  360 dp that `TOUCH` assumes.
- One object type per part, `SLIDER`, `TOGGLE` and `TEXT_INPUT`, and many
  controls are instances told apart by the instance variable `name`. Use
  a family only when differently drawn types share one logic. The parts of
  a control are children of its first part (`link()`), so hiding, moving
  or destroying it takes them along, and `no_overlap()` passes two parts
  of one hierarchy.
- The slider: the track a Tiled Background TOUCH high with the bar across
  its middle, the fill a Tiled Background as thick as the bar, the knob a
  Sprite with Drag & Drop along X. Drag & Drop has no bounds, so the
  custom action `Slide` puts each picked knob on its own track: the value from the knob's
  X across the track, rounded to a step and clamped to lo..hi, the knob set
  back on that step, the fill sized to it, the value shown and the global
  of its name set. It runs while a knob is dragged, while a finger holds
  the track away from a knob that is not dragged, and at the start.
- The value shows after the track by default, `value_at="end"`: the row
  stays TOUCH high and the values of a column of sliders line up. Over the
  knob, `value_at="knob"`, it follows the knob and needs a free row above.
  The two look equally good, so the default is the one that keeps the
  row on the grid.
- The toggle: two frames of one Sprite, tagged "off" and "on", the knob
  at the left or the right of the switch. A frame is the state and needs
  no second object or tween; it is how planet-generator draws one. It is
  pressed with `press()`, and the release on it flips the boolean `on`
  and shows its frame.
- The text input: the Text input form control, TOUCH high on the grid,
  *Auto font size* off. At the start `text_input_events()` sets the
  look's font, body size, ink on canvas and a frame in `solid` as CSS
  lengths that scale with the canvas. Its docstring says that it draws
  over every layer.
- Each kind's events set a global per control name. A game declares the
  global, a number for a slider, a boolean for a toggle, a string for a
  text input.
- A slider and a toggle take the mouse and touch. Arrow keys on a slider
  need a focus that the canvas controls do not have, and the text input
  takes the keyboard as the browser's own control.

## Re-evaluate when

- A game needs a slider moved by the keyboard or a gamepad: a focus for
  the canvas controls comes first.
- A Construct release changes how *Auto font size* computes the size, or
  how Drag & Drop moves a child of a hierarchy.
- Games ask more often for the value over the knob than after the track.
