# A new project: sheets, layers, objects and look

Read this to generate a project or add a layout, layer, event sheet, group or
object type to one. It shows how the official examples lay out a project: its
sheets and groups, then its viewport, colours, grid, HUD, folders, layers and
objects. Design the events first with
[event-sheet-thinking.md](../event-sheet-thinking.md).

## Sheets and groups

The official examples always split events the same way (groups in 237 of 432,
several sheets in 48, includes in 14). Before writing into a project, read
[event-sheet-style.md](../event-sheet-style.md) for what goes inside a group
and how to name and comment it.

- One layout has one sheet, with groups by subsystem named as in the
  examples: *Setup* (`On start of layout`), *Player*, *Controls*, *Camera*,
  *Tutorial*, *Game over*, *Restart* (the restart key and *Restart layout*).
- With a second layout, each screen gets its own sheet (*Menu*, *Game*,
  *Credits*); levels share one (samuroof: Level1 to Level5 use *Game*). A
  subsystem several screens need, or one that outgrows the sheet, moves to
  its own sheet (*Player*, *Enemies*, *HUD*, *Camera*, *Effects*, *Sound*),
  which the screen's sheet includes (kiwi-story: eMain includes nine).
- Globals are project-wide wherever declared. Declare them on one sheet
  (*Globals*) so they can be found, as kiwi-story, samuroof and kitty-katcher
  do.
- If a phase begins later, its group starts inactive: a tutorial, a boss
  enabled on entry, debug tools (19 examples). Deactivating a group stops its
  events and nothing else, so it is not a pause.

[manual: project-primitives/events/groups.md, includes.md, event-sheets.md
"share events between layouts", variables.md "Global variables"; examples:
kiwi-story, samuroof, airborne-explorer, family-tree, labyrinth; survey of
Construct-Example-Projects, 2026-09-18]

## Viewport, look and HUD

- Pixel art uses a 320×180 viewport, *Nearest* sampling and *Integer scale
  outer*; other art 1920×1080, *Trilinear* and *Scale outer*. Both fill the
  screen at any aspect ratio. The screen then shows more than the viewport
  on its longer side. So a HUD element held to an edge carries the Anchor
  behavior for that edge, and a backdrop or a dim reaches far past the
  viewport
  ([coordinates-and-angles.md](../pitfalls/coordinates-and-angles.md),
  [input.md](../pitfalls/input.md)). A one-screen game's layout is the
  viewport's size, with *Unbounded scrolling* on so that the game stays
  centred with the HUD.
- Use few colours, each for a role: the player, what hurts, what is
  collected, the panels, the text. The median pixel-art project draws its art
  with hard edges in 35 colours, and 9 of them cover 95% of its opaque
  pixels. Labels use one to three colours, white in two of three, and two
  sizes, rarely more than four. Every label has 4.5:1 contrast with what is
  behind it, 3:1 from 18 pt up, large-scale text (WCAG 2.2, 1.4.3). Every
  studio project at 360 px or less samples *Nearest*, and most scale by
  whole numbers. The generator template holds these as `PALETTE` and
  `rgb()`, the colour check of `write_png()`, `FONT` and `TEXT_SIZE`, the
  contrast check of `hud_text()`, `PIXEL_ART` and `FULLSCREEN`.
- Until the art arrives, a generated game is a plain sheet: flat shapes on
  an off-white canvas that fills the screen, without outlines, shadows,
  cards or panels. Lightness shows the hierarchy, from the canvas through a
  solid grey to ink. Two accents mark what is collected and what hurts, each
  at least 3:1 on the canvas by colour alone.
  Labels are in the platform's own face, `system-ui`, with no font file;
  a number the player plays for is large and regular under a small dim
  name. A rectangle is the player or structure, a
  circle what is collected, a triangle what hurts. Where something is
  transparent, a mask, or a background still to come, the backdrop is the
  transparency checker instead. An area or an edge is a striped Tiled
  Background, and objects stay flat. A level is a run of beats, each asking
  one thing, with a rest after every hard one. The generator template holds
  these as `PALETTE`, `shape()`, `PATTERNS`, `area()`, `backdrop()` and
  `BEATS`; the record is `docs/decisions/greybox-blockout.md`.
- The art arrives through the template's `art()`, in the boxes of the
  stand-ins: from the session's image tool by way of the skill's
  `prepare_art.py`, or from the user. It is not drawn in code, which looks
  worse than the stand-ins and mixes styles
  (`docs/decisions/art-from-the-image-tool.md`).
- Positions and sizes use a grid: 8 px at 320×180 (three quarters of the
  examples' x and five sixths of their widths sit on it), 32 px at 1920×1080
  (half of their x, three fifths of their widths). Use whole numbers, angle 0
  unless the object should lean. The HUD is on the parallax-0 layer, against
  a corner or an edge, one unit inside it (the examples' edge offsets are 0,
  one unit or two). The screen's middle is for the game. On a TV, graphics
  stay 5% inside every edge (EBU R95). A tapped object is at least a finger
  wide: 48 dp (Android accessibility help), 44 pt (Apple HIG,
  *Accessibility*, the iOS default control size), 44 px (WCAG 2.5.5). In
  viewport pixels that is 48 × the viewport's shorter side / 360, since a
  phone shows that side across about 360 dp. Rounded up to a whole grid
  unit, it is 24 px at 320×180 and 160 px at
  1920×1080, with 8 dp between two targets. A label's box is as wide as its
  longest text and aligned to the edge it is anchored to. A row of hearts is
  spaced by a unit. Nothing on the HUD overlaps or leaves the viewport. A
  value sits close under its name, and the gap between two groups is at
  least 1.5 times the gap inside one, the ratio slide and poster layout
  guides ask, so the HUD stands apart from the playfield. The playfield is
  centred in what the HUD leaves, not on the whole screen. The
  generator template holds these as `UNIT`, `MARGIN`, `TOUCH`, `anchor()`,
  `hud_text()`, `hud_stat()`, `row()`, `no_overlap()`, `play_area()`,
  `centred()` and `spaced()`, and holds the HUD to the screen's
  edges with `anchored()`.
- A button's text is its label, centred on it, and the two move and hide
  together; a bar's name stands in front of the bar. A one-screen layout is
  bands: the title, the status line, the stage in the middle and the hint at
  the bottom, with the stage's main object at a large share of the stage.
  The generator template holds these as `button()`, `labelled_bar()`,
  `bands()`, `band_text()` and `fit()`; the record is
  `docs/decisions/layout-by-name.md`.
- Each class of object keeps one kind of motion, so the eye knows what
  matters. The HUD and menus fade and slide: of the studio cohort's 480
  one-shot tweens on objects of a parallax-0 layer, in 71 projects, 73%
  tween the opacity, 92% use a sine ease, mostly `easeinoutsine`, the
  middle half lasts 0.5 to 1 s, and 7 overshoot. A button's press is
  quicker, 0.1 to 0.5 s on its size or opacity. The camera moves slowly
  and evenly, 1 s or more with `easeinoutsine`, though only 4 projects
  tween it.
  Overshoot (`easeoutback`, `easeoutbounce`, an elastic ease) belongs to
  world objects: 102 of their 1613 tweens, mostly a vertical offset or the
  size, as in a hit, a landing or a pop ([feel.md](feel.md)). Give a HUD
  element a bounce only when it is the moment's subject, such as a title
  card. [survey of the Tween actions in the examples' studio cohort,
  2026-10-08: each action's object classed as HUD when it has an instance
  on a layer of parallax 0, else as world or camera]

## Layouts, sheets, folders and layers

- One `ObjectRepository` layout, with no event sheet, holds one instance of
  every type the events create, nothing else. No object is global. Keep
  it out of the first place in the project, because the first layout is
  the one the game opens on. If the order puts it first anyway, it gets a
  sheet of one event, *On start of layout* then *Go to layout* the first
  screen [a studied project, 2026-10-06].
- `MainCode` is the only sheet up to about sixty types. Beyond that each
  screen has a sheet (`GameEvents`, `MenuEvents`, `CreditsEvents`),
  subsystems have included ones (`PlayerEvents`, `EnemyEvents`,
  `SoundEvents`), and `Globals` holds shared variables.
- From about forty types, every type is in an object folder, one level deep,
  and the root is empty: `System` (managers, camera, fader, input), `Player`,
  `World`, `UI`, `Interactable`, `Global`, and one per extra screen
  (`MainMenu`, `Credits`). Below forty, the list stays flat.
- Layers, bottom to top: `Background`, `World`, then `UI` (or `HUD`) and
  `Fader`, each at parallax 0; `Tutorial` has its own layer. A layout has
  two or three.
- A layer lists its instances in the order they draw, back to front, as
  an editor user arranges them: the backdrop and the flat areas, then what
  stands, from far to near by the Y of its feet, a child after its parent
  and a label after its board or bar. The generator template puts every
  layer in this order, `z_order()`.

## Objects

- Collision is apart from graphics. `PlayerCollision` is an invisible
  one-colour Sprite with Platform or 8 Direction, and `PlayerGraphics` holds
  the animations and no behavior. The two are a container; *PlayerCollision:
  On created* sets the graphics' position and calls *Add child* (X, Y,
  destroy with parent). From then on the graphics follow the collision
  body, so no event copies the body's position to the graphics. Enemies
  too: `EnemyCollision` with `EnemyAnimations`.
  Ground is a Tilemap with Solid (`GroundCollision`) under the art
  (`Background`, a Tiled Background). A shadow is a child Sprite
  (`PlayerShadow`). Use a hierarchy, not Pin.
- Movement behaviors run with *Default controls* off; the input events call
  *Simulate control* under Keyboard *Key is down*, which is true every tick
  the key is held. Under *On key pressed* the player moves for one tick
  ([pitfalls: Input](../pitfalls/input.md)).
- What has no picture is an invisible 16×16 one-colour Sprite, stretched over
  its area if it has one. `GameManager` holds the Timers and value Tweens the
  sheet reads. `Camera` has Scroll To (or Scroll To on `PlayerCollision`).
  `Trigger`, `TeleportTrigger`, `FinishLine`, `SpawnPoint`, `InvisibleWall`
  with Solid are tested with *On collision* or *Is overlapping* and told
  apart by an instance variable.
- `Fader` is a viewport-sized one-colour Tiled Background on the top layer,
  with Tween on opacity. *On finished* runs *Go to layout* or *Restart
  layout*.
- A light is a one-colour Sprite with *Additive* blend, soft-edged by a Glow
  or Blur effect. Darkness is a `Darkness` sprite or layer with *Destination
  out* holes, on a layer with *Force own texture*.
- Two games of three use Sprite Font for text, the third the Text plugin. No
  project uses both.
- Behaviors make the feel: Tween on almost everything, a fade included (Tween
  on Opacity), Timer, Sine, Flash, Rotate, Bullet, Particles. The effects
  used are HSL adjust, Glow, Blur, Warp object.
- Families serve Z order (`ZOrderables`) and enemies. Containers hold the
  collision and graphics pair, and an enemy with its parts. The player's
  instance variables are `hp`, `maxHp`, `dead`.
