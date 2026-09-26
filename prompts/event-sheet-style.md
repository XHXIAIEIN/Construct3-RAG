# Construct 3 Event Sheet — Authoring Style

Read this after the design, before events go into a project or a generator.
It is how the official examples organise, name and comment a sheet
(`Construct-Example-Projects`, the 221 games by Viridino and Forsteri
Studios; the counts behind every rule are in
`docs/decisions/event-sheet-design-guidance.md`). A sheet the user already
keeps has conventions of its own: follow those where they exist.

## Six habits to avoid

`check_project.py --style` reports the last five over a project the agent
wrote; `edit_sheet.py` refuses a plan whose new events add the long block,
the uncommented cases or the extra Every tick, whose fix is one comment or
one deleted condition, and warns on the tree and the ladder. The pile of
globals has no mechanical form and stays here. Fix the shape, not the
warning.

| Habit | The examples instead |
|-------|----------------------|
| State globals piled at the top of the sheet: `touchSX`, `foodX`, `tailUID`, `nextX` | Only what several groups read is global. State one group owns is that group's first children: a static local for what outlives the tick (`touchStartX` in `Player Controls`), a plain local for what is recomputed each tick. A value one event computes and reads is a local of that event, set in an unconditioned sub-event. What describes an instance is its instance variable (`dir` on the head), not a global. A link to an instance is *Pick children* or a condition, not a stored UID |
| A block of 20 actions with nothing between them | A comment action every three to five actions, `Clear the board`, `Create the head`, `Show the start panel`, and the block stays one block |
| A decision as a tree three sub-events deep, one call per leaf | One gate event with the shared conditions, then the cases as flat sibling sub-events, each with its comment, `Else` with conditions as the else-if; or one expression when the outcomes differ only by a number, `(round(angle(x0, y0, Touch.X, Touch.Y) / 90) % 4 + 4) % 4` |
| The same event five times over with other values: one per option, per building, per state, `wood < 4`, `wood < 8`, `wood < 12` | One event over what differs: the option's instance variables (`costWood`, `kind`), a family, a Dictionary loaded from a project file, the state's name inside the animation name |
| `Every tick` beside an event's other conditions: `Every tick`, `Player: Platform is on floor` | The other conditions alone: an event without a trigger is tested every tick already. `Every tick` is an event's one condition, where it reads as "always" |
| Cases as sub-events with no comment on any of them | A comment above each case, saying which case it is: `Player is on the floor`, `Otherwise, end the slide` |

## The shape

A sheet as `print_sheet.py` prints one. Constants under `Settings`, shared
state under `Gameplay variables`, then one group per subsystem in play
order (`Setup`, `Tutorial`, `Player`, `Enemies`, `Camera`, `HUD`, `Game Over`,
`Restart`), every event in a group, a comment above every event.

```
     // Coins. Tap a coin to collect it; when the last one is gone the layout restarts.
     // Settings
     global constant number COIN_COUNT = 6          // Coins dealt at the start
     // Gameplay variables
     global number score = 0                        // Points collected this round
   1 group Setup
       // Deal the coins and show the empty score
   2   System: On start of layout
           -> ScoreText: Set text to "Score: 0"
           -> // Deal the coins
           -> ...
   3 group Player
       static number touchStartX = 0                // Where the swipe began
       // Only while the player can act
   4   Player: NOT Is dead
       System: Is tutorial (inverted)
         // Jump
   5     Keyboard: On Space pressed
             -> Player: Jump()
         // Dash
   6     Keyboard: On Right pressed
             -> Player: Dash()
       // Shrink the coin away and score it
   7   Coin: Collect()             (custom action, description "Shrink the coin away and score it")
```

Inside a group: its variables, then its functions and custom actions, then
its events. A trigger carries its filters in the same block and its
branches as sub-events, one comment each; two levels of sub-events cover
almost every event in the examples.

## Comments

The examples' 10,500 comments are one sentence of eight words at the
median, eighteen at the ninetieth percentile; one in forty has a second
sentence. A comment names the things of the game (the player, the wall, the
trail), never the ACE: `Turn the player left`, not `Set angle to Self.Angle
- 90`. Written in the user's language. No period at the end, where the
examples put one: a second sentence keeps the period between the two, and a
variable's comment and a function's description end the same way.

| Above | Frame | From the examples |
|-------|-------|-------------------|
| An event that does something | Imperative verb, object, then the qualifier that makes it exact: `but only if`, `while`, `based on`, `by` when the mechanism is not obvious | `Move the player forward, but only if there's no wall in front of it` `Update the sky texture offset while the "Offset" tag is being played` `Turn the player left by changing its angle` |
| A branch | The case as a statement, or `If ..., ...` | `Player is on the floor` `Car arrived at waypoint` `If the random number is lower or equal to the flower spawn rate, turn the decoration object into a flower` |
| An `Else` | `Otherwise, ...` or `However, if ...` naming the remaining case | `Otherwise, end the slide` `However, if the trail is not the most recent one, it's also a crash` |
| An event whose reason is not obvious | The reason as a clause of the same sentence: `so the`, `to prevent`, `to make sure`, `since`, `to avoid` | `Once the player is done turning, round its angle to avoid undesired floating values like "89.99999999999999"` `Move the foam on top of the water to prevent Z fighting` |
| A one-shot or a per-tick event | `Once ...` or `Constantly ...` first | `Once the player is done moving, round its position` `Constantly update the pixellate effect, so it matches the canvas resolution` |
| A variable | What it holds, in game terms, with its unit or range; a boolean as `Whether ...` or a question | `How long it takes for the player to turn` `How fast the player falls` `Ranges from 0 to 1 and increases with time` `Whether or not the screen was touched at least one time` |
| A batch inside a long block (a comment action) | The step's verb; `Also ...` for a step that belongs with the one before | `Store the player's previous Z elevation` `Display a victory text` `Also disable the blur mask` |
| A section of globals or of inputs | A noun | `Settings` `Gameplay variables` `Keyboard inputs` |
| The sheet | One line on what it covers | `This is the main gameplay event sheet. Each game component has a dedicated event sheet` |

The same sentence is the description of a function or custom action. The
examples never write the ACE restated (`Set score to 0`), a `TODO`, a
change history, or how the author got there; no `#`, colours or BBCode.

## Names

| Kind | Form | Examples |
|------|------|----------|
| Object type | PascalCase, role then part; plugin as prefix for data and text | `Player`, `PlayerSprite`, `EnemyWaypoint`, `TextScore`, `ArrColors`, `DictProfile`, `Fader` |
| Family | PascalCase plural | `Enemies`, `Solids`, `ZOrderables` |
| Constant | `UPPER_SNAKE` with the module's prefix | `CAM_SPEED`, `P_DASH_SPEED`, `MINO_MELEE_DIST` |
| Other variable | camelCase; a boolean is the state as an adjective or participle, no `is` | `gameOver`, `killCount`, `dead`, `climbing`, `tutorial` |
| Function | camelCase, verb first | `spawnEnemy`, `computeLighting`, `gameOver` |
| Custom action | a verb phrase with spaces, on the object it acts on, in that object's group | `Create trail`, `Teleport to Node`, `Die` |
| Function parameter | a word that reads bare in an expression (`Self.X + OffsetX`), so `posX` over `x`; the examples split evenly between camelCase and PascalCase | `PositionX`, `Duration`, `volumeTweak`, `enemyUid` |
| Timer or Tween tag | PascalCase, verb and noun; a timer that stands for a state is named for it and tested with *Is timer running* | `ShowFader`, `TeleportCooldown`; `dashing`, `dashCooldown` |
| Animation | PascalCase; one animation per kind when one type stands for several | `Idle`, `Walk`, `Walking0`; `Treasures`, `Pathfinder` |
| Group | Title Case with spaces, description empty | `Player Controls`, `Sort Z-Order` |
| Layout, layer, sheet | PascalCase | `MainMenu`, `ObjectRepository`, `HUD`, `GameEvents` |

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
- Feel comes from behaviors: Tween on almost everything, Timer, Sine, Fade,
  Flash, Rotate, Bullet, Particles; the effects used are HSL adjust, Glow,
  Blur, Warp object.
- Families for Z order (`ZOrderables`) and enemies; containers for the
  collision and graphics pair and for an enemy with its parts. The player's
  instance variables are `hp`, `maxHp`, `dead`.

## UI text

Sentence case, imperative, the key named: `Press Space to start`,
`[Arrows]: select | [Space]: confirm`. Outcomes short, with `!`: `Game
over!`, `You were caught!`; result banners in capitals, `YOU WIN`. HUD labels
are `"Score: " & score`. The copy lives in the Text object with a `###`
placeholder, filled by `replace(Self.Text, "###", value)`, coloured with
BBCode.

To see the whole of it before writing, print an example: `python
<Construct3-RAG>/skills/construct3-project/scripts/print_sheet.py --project
<Construct-Example-Projects>/example-projects/samuroof Game`; labyrinth,
eventide and digiautos show the same conventions.
