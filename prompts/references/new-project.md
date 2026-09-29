# A new project: sheets, layers, objects and look

How the official examples lay out a project: its sheets and groups, then
its viewport, colours, grid, HUD, folders, layers and objects. Read it when
generating a project, or when adding a layout, layer, event sheet, group or
object type to one. Design the events first with
[event-sheet-thinking.md](../event-sheet-thinking.md).

## Sheets and groups

The official examples split the same way every time (groups in 237 of 432,
several sheets in 48, includes in 14). What goes inside a group, and how it
is named and commented, is [event-sheet-style.md](../event-sheet-style.md),
read before writing into a project.

- One layout: one sheet. Groups by subsystem, named as the examples name them:
  *Setup* (`On start of layout`), *Player*, *Controls*, *Camera*, *Tutorial*,
  *Game over*, *Restart* (the restart key and *Restart layout*).
- A second layout: each screen gets its own sheet (*Menu*, *Game*,
  *Credits*); levels share one (samuroof: Level1 to Level5 use *Game*). A
  subsystem several screens need, or one that outgrows the sheet, moves to
  its own sheet (*Player*, *Enemies*, *HUD*, *Camera*, *Effects*, *Sound*) and
  the screen's sheet includes it (kiwi-story: eMain includes nine).
- Globals are project-wide wherever they are declared. Declare them on one
  sheet (*Globals*) so they can be found; kiwi-story, samuroof and
  kitty-katcher do.
- A group that starts inactive is for a phase that begins later: tutorial,
  a boss enabled on entry, debug tools (19 examples). Deactivating a group
  stops its events and nothing else, so it is not a pause.

[manual: project-primitives/events/groups.md, includes.md, event-sheets.md
"share events between layouts", variables.md "Global variables"; examples:
kiwi-story, samuroof, airborne-explorer, family-tree, labyrinth; survey of
Construct-Example-Projects, 2026-09-18]

## Project

- Pixel art at a 320×180 viewport, *Nearest* sampling, *Letterbox integer
  scale*; otherwise 1920×1080 and *Trilinear*. A one-screen game's layout
  is the viewport's size.
- Colours by role, and few of them. The median pixel-art project draws its
  art in 35 colours, 9 of them covering 95% of its opaque pixels, with hard
  edges; each colour is there for something: the player, what hurts, what is
  collected, the panels, the text. Labels come in one to three colours,
  white in two of three, and in two sizes, rarely more than four. Every
  label reads 4.5:1 against what is behind it, 3:1 from the title size up
  (WCAG 2.2, 1.4.3). All 159 studio projects at 360 px or less sample
  *Nearest*, 116 of them at *Letterbox integer scale*. The generator
  template holds these as `PALETTE` and `rgb()`, the colour check of
  `write_png()`, `FONT` and `TEXT_SIZE`, the contrast check of `hud_text()`,
  and `PIXEL_ART`.
- Until the art arrives, a generated game is a blockout: value carries the
  hierarchy, from a light checker backdrop through a solid grey to ink, and
  two accents mark what is collected and what hurts, each shown by its ink
  outline. A rectangle is the player or structure, a circle what is
  collected, a triangle what hurts; an area or an edge is a striped Tiled
  Background, and objects stay flat. A level is a run of beats, each asking
  one thing, with a rest after every hard one. The generator template holds
  these as `PALETTE`, `shape()`, `PATTERNS`, `area()`, `backdrop()` and
  `BEATS`; the record is `docs/decisions/greybox-blockout.md`.
- Positions and sizes on a grid: 8 px at 320×180 (three quarters of the
  examples' x and five sixths of their widths sit on it), 32 px at
  1920×1080 (half of their x, three fifths of their widths). Whole numbers,
  angle 0 unless the object is meant to lean. The HUD is on the parallax-0
  layer, held against a corner or an edge, one unit inside it (the
  examples' edge offsets are 0, one unit or two); the middle of the screen
  is the game's. A game shown on a TV keeps graphics 5% inside every edge
  (EBU R95). A tapped object is at least a finger wide: 48 dp (Android
  accessibility help), 44 pt (Apple HIG, *Accessibility*, the iOS default
  control size), 44 px (WCAG 2.5.5), which is 48 × the viewport's shorter
  side / 360 in viewport pixels, a phone showing that side across about
  360 dp: 24 px at 320×180, 160 px at 1920×1080, with 8 dp between two
  targets. A label's box is as wide as its longest text and reads towards
  the edge it hangs on; a row of hearts is spaced by a unit; nothing on the
  HUD overlaps or leaves the viewport. The generator template holds these
  as `UNIT`, `MARGIN`, `TOUCH`, `anchor()`, `hud_text()`, `row()` and
  `no_overlap()`.
- One `ObjectRepository` layout, no event sheet, one instance of every type
  the events create; nothing else there. No global objects.
- One sheet, `MainCode`, until about sixty types. Beyond that `GameEvents`,
  `MenuEvents`, `CreditsEvents` per screen; subsystems (`PlayerEvents`,
  `EnemyEvents`, `SoundEvents`) included; `Globals` for shared variables.
- Object folders from about forty types, every type inside one and the
  root empty: `System` (managers, camera, fader, input), `Player`, `World`,
  `UI`, `Interactable`, `Global`, and one per extra screen (`MainMenu`,
  `Credits`). One level. Below forty the list stays flat.
- Layers bottom to top: `Background`, `World`, `UI` or `HUD` at parallax 0,
  `Fader`; `Tutorial` on a layer of its own. Two or three per layout.
- Collision apart from graphics. `PlayerCollision` is an invisible
  one-colour Sprite carrying Platform or 8 Direction; `PlayerGraphics`
  holds the animations and no behavior. The two are a container, and
  *PlayerCollision: On created* sets the graphics' position and *Add child*
  (X, Y, destroy with parent). Enemies the same, `EnemyCollision` with
  `EnemyAnimations`. Ground is a Tilemap with Solid (`GroundCollision`)
  under the art (`Background`, a Tiled Background); a shadow is a child
  Sprite (`PlayerShadow`). Hierarchy, not Pin.
- Movement behaviors run with *Default controls* off; the input events
  call *Simulate control*.
- What has no picture is a 16×16 one-colour Sprite, invisible, stretched
  over its area when it has one: `GameManager` holding the Timers and value
  Tweens the sheet reads; `Camera` with Scroll To (or Scroll To on
  `PlayerCollision`); `Trigger`, `TeleportTrigger`, `FinishLine`,
  `SpawnPoint`, `InvisibleWall` with Solid, tested with *On collision* or
  *Is overlapping* and told apart by an instance variable.
- `Fader`: a one-colour Tiled Background the size of the viewport on the
  top layer, Tween opacity; *On tweens finished*: *Go to layout* or
  *Restart layout*.
- A light is a one-colour Sprite with *Additive* blend, soft-edged by a Glow
  or Blur effect; darkness is a `Darkness` sprite or layer with
  *Destination out* holes, on a layer with *Force own texture*.
- Text is a SpriteFont in two games of three, the Text plugin in the third,
  never both in one project.
- Feel comes from behaviors: Tween on almost everything, a fade included
  (Tween on Opacity), Timer, Sine, Flash, Rotate, Bullet, Particles; the
  effects used are HSL adjust, Glow, Blur, Warp object.
- Families for Z order (`ZOrderables`) and enemies; containers for the
  collision and graphics pair and for an enemy with its parts. The player's
  instance variables are `hp`, `maxHp`, `dead`.
