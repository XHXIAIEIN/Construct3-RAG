# Construct 3 Event Sheet — Authoring Style

Read this after the design, before events go into a project or a
generator. It shows how the official examples
(`Construct-Example-Projects`, the games by Viridino and Forsteri Studios)
organise, name and comment a sheet. If the user's sheet has conventions of
its own, follow those. If a rule here differs from what an example does, or
a style check's threshold is in question, read
`docs/decisions/event-sheet-design-guidance.md`.

## Six habits to avoid

In a project the agent wrote, `check_project.py --style` reports the last
five. `edit_sheet.py` refuses a plan that adds the long block, the
uncommented cases or the extra Every tick, since one comment or one
deleted condition fixes each. It warns on the decision tree and the
repeated event. No check detects the state globals; only this file covers
them. To fix a warning, change the events to the right column's shape, not
just enough to silence it.

| Habit | The examples instead |
|-------|----------------------|
| State globals piled at the top of the sheet: `touchSX`, `foodX`, `tailUID`, `nextX` | Only what several groups read is global. State one group alone uses is declared first in it: a static local if it lasts between ticks (`touchStartX` in `Player Controls`), a plain local if it is recomputed each tick. A value one event computes and reads is that event's local, set in an unconditioned sub-event. An instance's property is its instance variable (`dir` on the head), not a global. A link to an instance is *Pick children* or a condition, not a stored UID |
| A long block of 20 actions without a comment action | A comment action every three to five actions: `Clear the board`, `Create the head`, `Show the start panel`. The block stays one block |
| A decision as a tree three sub-events deep, one function call per leaf | One gate event with the shared conditions, then the cases as flat sibling sub-events with a comment each. `Else` with conditions is the else-if. If the outcomes differ only by a number, one expression: `(round(angle(x0, y0, Touch.X, Touch.Y) / 90) % 4 + 4) % 4` |
| The same event five times over with other values, one per option, building or state: `wood < 4`, `wood < 8`, `wood < 12` | One event, with the differences in the option's instance variables (`costWood`, `kind`), a family, a Dictionary loaded from a project file, or the state's name inside the animation name |
| `Every tick` beside an event's other conditions: `Every tick`, `Player: Platform is on floor` | The other conditions alone, because an event without a trigger is already tested every tick. `Every tick` is an event's only condition, where it reads as "always" |
| Case sub-events with no comment above any of them | A comment above each case that says which case it is: `Player is on the floor`, `Otherwise, end the slide` |

## The shape

Here is a sheet as `print_sheet.py` prints it.

```
     // Coins. Tap a coin to collect it; when the last one is gone the layout restarts.
     // Settings
     global constant number COIN_COUNT = 6          // Coins dealt at the start
     // Gameplay variables
     global number score = 0                        // Points collected this round
   1 group Setup
       // Empty the score and deal the coins
   2   System: On start of layout
           -> System: Set score to 0
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

Constants go under `Settings`, shared state under `Gameplay variables`,
then one group per subsystem in play order (`Setup`, `Tutorial`, `Player`,
`Enemies`, `Camera`, `HUD`, `Game Over`, `Restart`). Every event is in a
group, with a comment above it. A group holds its variables, then its
functions and custom actions, then its events. A trigger has its filter
conditions in the same block and its branches in sub-events, one comment
each. Two levels of sub-events cover almost every event in the examples.

## Comments

The examples' comments are one sentence of eight words at the median and
eighteen at the ninetieth percentile. One in forty has a second sentence.
A comment names the things of the game (the player, the wall, the trail),
never the ACE: `Turn the player left`, not `Set angle to Self.Angle - 90`
or `Set score to 0`. It never holds a `TODO`, a change history, how the
author got there, `#`, colours or BBCode. Write comments in the user's
language. End
every comment and description without a period, even where the examples
put one. Keep the period between two sentences.

| Above | Frame | From the examples |
|-------|-------|-------------------|
| An event that does something | Imperative verb, object, then the qualifier that makes it exact: `but only if`, `while`, `based on`, `by` if the mechanism is not obvious | `Move the player forward, but only if there's no wall in front of it` `Update the sky texture offset while the "Offset" tag is being played` `Turn the player left by changing its angle` |
| A branch | The case as a statement, or `If ..., ...` | `Player is on the floor` `Car arrived at waypoint` `If the random number is lower or equal to the flower spawn rate, turn the decoration object into a flower` |
| An `Else` | `Otherwise, ...` or `However, if ...`, then the remaining case | `Otherwise, end the slide` `However, if the trail is not the most recent one, it's also a crash` |
| An event whose reason is not obvious | The reason as a clause of the same sentence: `so the`, `to prevent`, `to make sure`, `since`, `to avoid` | `Once the player is done turning, round its angle to avoid undesired floating values like "89.99999999999999"` `Move the foam on top of the water to prevent Z fighting` |
| A one-shot or a per-tick event | `Once ...` or `Constantly ...` first | `Once the player is done moving, round its position` `Constantly update the pixellate effect, so it matches the canvas resolution` |
| A variable | What it holds, in game terms, with its unit or range; a boolean as `Whether ...` or a question | `How long it takes for the player to turn` `How fast the player falls` `Ranges from 0 to 1 and increases with time` `Whether or not the screen was touched at least one time` |
| A batch inside a long block (a comment action) | The step's verb. `Also ...` starts a step that belongs with the one before | `Store the player's previous Z elevation` `Display a victory text` `Also disable the blur mask` |
| A section of globals or of inputs | A noun | `Settings` `Gameplay variables` `Keyboard inputs` |
| The sheet | One line on what it covers | `This is the main gameplay event sheet. Each game component has a dedicated event sheet` |

A function or custom action takes the same sentence as its description.

## Names

| Kind | Form | Examples |
|------|------|----------|
| Object type | PascalCase, role then part, plugin prefix for data and text | `Player`, `PlayerSprite`, `EnemyWaypoint`, `TextScore`, `ArrColors`, `DictProfile`, `Fader` |
| Family | PascalCase plural | `Enemies`, `Solids`, `ZOrderables` |
| Constant | `UPPER_SNAKE` with the module's prefix | `CAM_SPEED`, `P_DASH_SPEED`, `MINO_MELEE_DIST` |
| Other variable | camelCase. A boolean is the state as an adjective or participle, without `is` | `gameOver`, `killCount`, `dead`, `climbing`, `tutorial` |
| Function | camelCase, verb first | `spawnEnemy`, `computeLighting`, `gameOver` |
| Custom action | A verb phrase with spaces, on the object it acts on, in that object's group | `Create trail`, `Teleport to Node`, `Die` |
| Function parameter | A word that is clear alone in an expression (`Self.X + OffsetX`), so `posX`, not `x`. The examples use camelCase and PascalCase equally | `PositionX`, `Duration`, `volumeTweak`, `enemyUid` |
| Timer or Tween tag | PascalCase, verb and noun. A timer that stands for a state is named after it and tested with *Is timer running* | `ShowFader`, `TeleportCooldown`; `dashing`, `dashCooldown` |
| Animation | PascalCase, one animation per kind if one type stands for several | `Idle`, `Walk`, `Walking0`; `Treasures`, `Pathfinder` |
| Group | Title Case with spaces, description empty | `Player Controls`, `Sort Z-Order` |
| Layout, layer, sheet | PascalCase | `MainMenu`, `ObjectRepository`, `HUD`, `GameEvents` |

## Project

To generate a project, add a layout, layer, event sheet, group or object
type to one, or decide how the game looks, read
[references/new-project.md](references/new-project.md). It covers the
viewport, colours, blockout, grid and HUD, the sheets, folders and layers,
and how the examples build their objects.

## UI text

UI text is sentence case and imperative, and names the key:
`Press Space to start`, `[Arrows]: select | [Space]: confirm`. Outcomes are
short and end with `!`: `Game over!`, `You were caught!`. Result banners
are in capitals: `YOU WIN`. HUD labels are `"Score: " & score`. The text
is in the Text object with a `###` placeholder, filled by
`replace(Self.Text, "###", value)` and coloured with BBCode.

If events build a text from two or more values, write one `StringSub`
template, not a chain of `&`:
`StringSub("X = {0}    Y = {1}", round(Box.X), round(Box.Y))`. If the text
breaks a line, pass `newline` as a value:
`StringSub("Level {0}{1}Score: {2}", level, newline, score)`. The examples
never call `StringSub`, but this repository does, because the template
reads as the text it shows. [manual: system-reference/system-expressions.md
"StringSub"]

To see it all before writing, print an example: `python
<Construct3-RAG>/skills/construct3-agent-plugin/scripts/print_sheet.py --project
<Construct-Example-Projects>/example-projects/samuroof Game`; labyrinth,
eventide and digiautos show the same conventions.
