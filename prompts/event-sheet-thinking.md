# Construct 3 Event Sheet — Design Guide

This guide decides what the events are before you write them.
[event-sheet-assistant.md](event-sheet-assistant.md) says how to write an
event down. [event-sheet-pitfalls.md](event-sheet-pitfalls.md) lists the
runtime facts that intuition gets wrong, one line each. It names the topic
file under `pitfalls/` to open for each group that the events touch.
Before the events go into a project or a generator, read
[event-sheet-style.md](event-sheet-style.md). It says how the official
examples organise, name and comment a sheet, and the three habits that the
checker warns on.

A sheet is a program transcribed into events if it:

- links objects through UID variables
- resets picking with `Pick all`, then picks again from a stored link
- copies picked results into variables and branches on the numbers
- rebuilds a timer, a tween or a lookup table out of variables and
  `Every tick`

Such a sheet works, but an experienced Construct user rejects it.

## The model

Events filter instances. Each condition narrows the picked instances, and
the actions run on those that are left. If no condition names an object,
all its instances stay picked. A trigger fires with the instances involved
already picked. A sub-event and its siblings all start from the set that
their parent picked. Top-level events start from all instances. Spatial
relations (`Is overlapping another object`, `Pick overlapping point`,
`Pick nearest/furthest`) are conditions, so they pick too.
[manual: project-primitives/events/how-events-work.md,
project-primitives/events/sub-events.md,
plugin-reference/common-features/common-conditions.md]

Manual paths are relative to the `Construct3-Manual/` directory inside the
`Construct3-Manual` clone, next to this repository. Read the clone, because
construct.net rejects fetches from an agent. The live page is the same path
without `.md`, after
`https://www.construct.net/en/make-games/manuals/construct-3/`.

## Rules

1. **Test a relation with a condition.** "Is this slot taken?" is
   `Slot: Is overlapping Piece`. "Which slot did it land on?" is
   `Pick Slot overlapping point (Piece.X, Piece.Y)`. "Belongs to" is a
   container, a hierarchy or a family. Add an instance variable only if no
   condition can answer the question.
2. **Read the state that the engine already keeps.** Position, overlap,
   dragging, tween progress, animation name and frame, parent and child all
   have conditions and expressions. So does the number of instances:
   `Brick.Count`, and `PickedCount` for the instances a pick kept. A
   destroyed instance still counts until the top-level event ends
   ([pitfalls: Picking](pitfalls/picking.md)). A variable that copies one of
   these (`occupied`, `isDragging`, `bricksLeft`) stops matching the engine
   as soon as instances move or are destroyed. Every event that must update
   it can forget to. Store only what nothing can answer (level, score,
   where a drag started), on the instance it describes. If family events read it, declare it on the
   family.

   A decision that plays out as an animation is such a value. While the
   units of a pour drain and fill, the engine's state still describes each
   tube as it was. So a check that reads this state can seal the tube that
   the pour is about to empty. Record the decision when you make it, and let
   the animation follow.
3. **Use the trigger's pick.** Inside `On drop`, `Piece` is the dropped
   piece. Narrow the pick with sub-events instead of copying its UID into
   a variable and picking it again.
4. **Use a family for a second instance of the same type.** The dropped
   `Piece` and the `Pieces` already on the slot are two independent picks
   in one event, so it can compare `Pieces.level = Piece.level`, then
   `Piece: Destroy`.
5. **Disable collisions instead of setting a flag.** Run
   `Set collisions disabled` at `On drag start`, and enable them again when
   the instance settles (Tween `On any finished`). Every overlap test then
   ignores it: its old slot tests as empty, and a drop back on that slot
   takes the empty-slot branch. In the same way, a Solid that should stop
   blocking, such as a door that opens, gets Solid *Set enabled* off. Its
   animation alone leaves it blocking.
6. **Shape an interaction as a trigger, narrowing sub-events and Else.**
   Each branch reads as a sentence: on drop; over a slot; slot holds a
   piece; same level: merge. Else: swap. Else: move in. Else: go back.
   Collecting values into variables first and branching on the numbers is
   the wrong shape. A branch holds one trigger, and a function counts as
   one. So the *On finished* of a tween that a function starts is a
   top-level event of its own
   ([pitfalls: Triggers and Else](pitfalls/triggers-and-else.md)).
7. **Derive appearance every tick.** One event without conditions sets the
   default look. The next picks the exceptions and overrides it, so nothing
   needs a reset.
8. **Choose a UID, `Pick all` or a global last.** A UID or a global fits a
   singleton and a reference that crosses events (an inventory array of
   UIDs, a persisted selection). `Pick all` fits when the events after it
   need the rest of a type and not the trigger's instance: relic-hunter
   stops every ghost when one touches the player. If they read both, as a
   merge compares two levels, use a family for the second (rule 4). Inside
   one interaction, `Pick all` followed by a pick from a stored link means
   the events discarded a pick and rebuilt it by hand. That pick is
   *Pick by unique ID*, or *Pick by comparison* on a variable that holds a
   UID or a slot number.

## Native first

Before you add a variable, an `Every tick` or a formula, ask which built-in
already does it. A draft that rebuilds one of the built-ins below by hand
is a program transcribed into events, even without a picking smell.

| Need | Use | Not |
|------|-----|-----|
| A delay, a countdown, a cooldown | Timer behavior: *Start timer*, *On timer*, `Duration(tag) - CurrentTime(tag)` | An instance variable decremented by `dt` and compared every tick |
| A fixed-duration move, scale, fade, colour change: known start, known end, known time | Tween behavior: *Tween (one/two/three properties)*, *On any finished* | A progress variable stepped by `dt`, passed to `lerp` and checked for 1 |
| A fixed-duration change of something Tween has no property for: an effect parameter, a behavior property, Z height, a full 360° turn | *Tween (value)*, then *Is playing* with *Set …* to `Self.Tween.Value(tag)` ([pitfalls: Tween](pitfalls/tween.md)) | The same progress variable, or a one-property angle tween set to a full turn |
| Smooth follow of a target that keeps moving: camera, cursor, aim angle | `lerp(a, b, 1 - f^dt)` (`anglelerp` for angles) in `Every tick`; it reads the target again each tick and never finishes | A Tween restarted every tick; `lerp(a, b, 0.1)` with a constant factor, which is framerate-dependent |
| A value derived from another live value: colour from health, zoom from speed, a slider position | `lerp(lo, hi, t)` with `t` from `unlerp`, a ratio, `Tween.Value(tag)` or a timeline; no duration of its own | A variable holding the mapped value, updated from several events |
| Continuous motion toward a target or along a heading | MoveTo, Bullet, Pathfinding, Platform, 8 Direction | `Set X`/`Set Y` from your own velocity variables |
| A part that moves with a body: the graphics on a collision box, a shadow, a held item | Hierarchy: *Add child* once, when the body is created; the child then follows it | An every-tick *Set position* to the body's X and Y |
| Repeating or periodic movement, flashing, fading out | Sine, Flash, Rotate; a fade is a Tween on Opacity | Hand-written oscillation; the Fade behavior, superseded |
| Level data, loot tables, stat curves, any lookup table | Array or Dictionary project file (Project Bar: *New - Array / Dictionary*), loaded in *On start of layout*: AJAX *Request project file*, *Wait for previous actions*, then *Load* from `AJAX.LastData`, all in that one block, because a *Wait* delays only its own block (cell-linking loads its level this way). An AJAX *On completed* is a trigger and cannot sit under *On start of layout*. Nested or hand-written data through the JSON plugin | Per-level instance variables, `level1Hp`, chained conditions or nested ternaries that encode the table in expressions |
| A list that changes at runtime: a deck and its discard pile, a queue, an inventory, a playlist | One Array per list, width 0 at start: *Push* to add, *Shuffle*, `Front`, `Back` or `At(i)` to read, then *Pop* or *Delete* to remove (they return nothing, so read first), *Contains value* to test membership, `Width` to count (place-stickers `InventoryArray`, airborne-explorer `ArrBGM`). Load definitions with several fields from a project file (row above) | A separated string read with `tokenat` (smell table) |
| Things each instance holds, each with its own numbers and its own time: stacked shields, buffs, status effects | One instance per item, made a child of its holder with *Add child* (destroy with parent on): its own variables (`amount`) and a Timer that destroys it when it runs out. The holder reads its items with *Pick children*, counts them with `PickedCount`, and takes them in order with *For each (ordered)* by `Self.Timer.Duration(tag) - Self.Timer.CurrentTime(tag)`. *Pick children* works through a family. A new kind of item is one more *Create object* and *Add child* | An Array in the holder's container: a container belongs to one object type, and an event that picks through the family does not pick it ([pitfalls: Picking](pitfalls/picking.md)). Expiry times kept in cells and swept by a loop |
| What a move, an effect or an attack does: its kind and its numbers | One field per fact, a `kind` text and `amount` and `times` numbers, as instance variables or fields of a project file (row above); the branch is an exact comparison, `kind = "block"`, one sibling event or `Else` per kind (alien-battle: under the boss's *On Timer*, `AnimationState = 0`, `= 1`, `= 2`, one attack each) | A code such as `"A6x2"` parsed with `mid`, `tokenat` or `right` and dispatched with `find` (smell table) |
| A sequence scripted in data: an attack pattern, a cutscene, a line of dialogue with its pauses and colours | A cue list in a project file, rows of `delay, cue, params`, parsed once with CSV *Parse CSV* into an Array and drained by a clock; dialogue through Text or Sprite Font *Typewriter text* when nothing moves per glyph ([references/scripted-sequences.md](references/scripted-sequences.md)) | A *While* that reads the string with `mid` every tick; a chain of *Wait* actions, one per cue |
| A menu steered by keys or a gamepad, with sub-menus and a way back | One Array holds the selected item's id per depth: *Push* on entering a sub-menu, *Pop* on back, `Back` is the current selection; a second column holds the name of the function that back calls, through a function map. The next item in a direction is the nearest item whose angle from the current one is within a few degrees of that direction, or, when there is none, the farthest item the opposite way, so the cursor wraps. The highlight is derived every tick from the selected id (rule 7) (a studied project, 2026-10-06) | A global per menu depth; a highlight moved in every input event; one event per item and direction |
| A value that depends on a condition | `condition ? ifTrue : ifFalse` (airborne-explorer `endlessMode ? ENDLESS_TIME_LIMIT : ...`, balloon-blower `currAudioSource > 0 ? ... : ...`); `chooseindex(i, a, b, c)` to pick by a number, `choose` at random | `chooseindex(condition, ifFalse, ifTrue)`, the branches in reverse reading order |
| A cycle of states, elements or turns; whether a set holds an item | The state as a number 0 to N - 1: the next is `(n + 1) % N`, the one after `(n + 2) % N` (alien-battle `(AnimationState + 1) % 3`, balloon-blower `(currAudioSource + 1) % UserMedia.AudioSourceCount`), its name from an Array at that index. Membership: Dictionary *Has key* (airborne-explorer `DictCombo: Has key "Boss"`), Array *Contains value* | Letters looked up through two strings, `mid("FEMAW", find("WFAEM", e), 1)`; `find("," & RELICS & ",", ",rel5,") >= 0` |
| Weighted random, seeded random, noise | Advanced Random: probability tables, `Weighted`, `Seed`, `Classic2d` | A chain of `random()` comparisons with hand-tuned thresholds |
| Data that survives a reload | Local Storage: *Set item*, *Get item*, *On item get* | Globals, which reset on reload; the Persist behavior, which keeps instances across layout changes, not across sessions |
| Logic shared by several events | Functions with parameters and return values; a *custom action* on the object or family if it acts on picked instances | The same action block pasted into several events |
| A part of the sheet that runs only in one phase: tutorial, a boss's AI, debug tools | A Group, off at start if the phase comes later, *Set group active* at the transition. Only its events stop: behaviors, timers and tweens keep running | A global mode variable that every event in that part compares |
| Which controls to offer: on-screen buttons for touch, keys and mouse on a desktop | Touch with *Use mouse input* off: *On any touch start* sets a global to touch, Mouse *On any click* or Keyboard *On any key pressed* sets it to desktop. The global shows the touch-controls layer and activates its group (detecting-input-method). A drag that behaves differently under a finger tests *Mouse button is down* every tick instead ([pitfalls: Input](pitfalls/input.md)) | Touch triggers with *Use mouse input* on, which also fire for a click |
| Pause, slow motion, hit stop | *Set time scale* 0 (pause) or 0.1 (hit stop, slow motion); *Set object time scale* 1 on the UI that must keep moving; *Use time scale* off on the wait that ends it | A `paused` global checked in every event; behaviors disabled one by one |
| One thing after another inside one interaction: knock back, then re-enable; fade out, then go to layout | *Wait* and *Wait for previous actions* in the same block, which keep the picked instances | A flag set in the block and a Timer or `On any finished` elsewhere to finish the sequence |
| Reacting to a state any instance may reach, whoever started it | Timer *On timer*; Tween *On any finished* | A *Wait* that assumes one caller |
| HUD and UI that stay on screen while the layout scrolls | A layer with parallax 0, 0; *Global* on that layer if every layout shows the same HUD | Every-tick *Set position* from `ViewportLeft`/`ViewportTop` |
| A number shown as a bar, a gauge or a row of icons: health, fuel, progress, lives | One object, `Set width to value / max × LENGTH` clamped, its origin on the edge it grows from, a frame behind it, Tween *Width* for a change; the art decides which object ([references/progress-bars.md](references/progress-bars.md)) | A Sprite scaled from its centre origin; a per-tick lerp of the width; one object type or one event per heart |
| A panel, menu or popup opened and closed as a whole | Its own layer, *Initially visible* off: *Set layer visible*; to fade it, *Set layer opacity* from a *Tween (value)* on a manager object (airborne-explorer, `MenuUI` and `ShopUI`; eventide, `PauseUI`) | *Set visible* on each of its objects, in every event that opens or closes it |
| A set of objects treated alike | Family; instance variables and behaviors declared on the family | Duplicate event blocks per object type |
| Objects that belong together | Container (created, destroyed and picked together); hierarchy for parent-relative position | UID variables, or every-tick position copying |

[manual: behavior-reference/timer.md, behavior-reference/tween.md,
system-reference/system-expressions.md "lerp", "dt", "find", "choose",
"chooseindex", project-primitives/events/expressions.md "Operators" (`%`,
`?:`), plugin-reference/dictionary.md "Has key",
behavior-reference/move.md, behavior-reference/bullet.md,
plugin-reference/array.md "Load", "Manipulating arrays", "Push", "Pop",
"Shuffle", "Contains value", plugin-reference/ajax.md "Request project
file", plugin-reference/json.md, plugin-reference/advanced-random.md
"Probability tables", plugin-reference/local-storage.md,
project-primitives/events/functions.md,
project-primitives/events/custom-actions.md,
project-primitives/events/groups.md, plugin-reference/touch.md "Use mouse
input", system-reference/system-actions.md
"Set group active", "Set time scale", "Set object time scale", "Set layer
visible", "Set layer opacity", "Wait", "Wait for previous actions to
complete", project-primitives/layers.md "Parallax", "Global layers",
"Initially visible", project-primitives/objects/families.md,
project-primitives/objects/containers.md; the pause, hit-stop and wait rows
are sourced in [pitfalls: Wait and time scale](pitfalls/wait-and-time-scale.md)]

Check two things before you choose. A Timer is state with transitions, so
list its transitions ([pitfalls: Timer](pitfalls/timer.md)). An Array
*Load* reads Construct's own JSON format, so make the file in the Array
editor; the JSON plugin reads hand-written JSON.

A behavior that exists can still be the wrong choice. An existing project
may keep a superseded feature, but a new project uses its replacement. Fade
runs a fixed series of opacity tweens, so use a *Tween (one property)* on
Opacity. In place of Pin, use a hierarchy: *Add child* on the parent. It
stays reliable where chains of pinned objects do not. In place of the Solid
behavior's own *Tags* property, use instance tags, which *Use instance
tags* selects by default. Z axis scale *Normalized* is deprecated rather
than superseded. A new project uses *Regular*, where Z is a co-ordinate on
the same scale as X and Y, so 3D sizes match how they look.
[manual: tips-and-guides/superseded-features.md,
tips-and-guides/deprecated-features.md]

## Feel

[references/feel.md](references/feel.md) has the recipe for each of these:
screen shake, hit stop, squash, hit flash, a choreographed sequence, a
following camera, a fade between layouts, a keyframed motion such as a
weapon swing, effects layered on one body, and a dragged thing that lags.
[references/sound.md](references/sound.md) says which sounds play, when and
how loud, and how to make and check a placeholder file. If you generate a
game or write events for any of these, read both files first.
[references/scripted-sequences.md](references/scripted-sequences.md) says
how an attack pattern, a cutscene or dialogue runs from a data file, and
how dialogue markup is parsed and localised.

## Layout of the sheet

If you generate a project, or add a layout, layer, event sheet, group or
object type to one, read [references/new-project.md](references/new-project.md)
first. It says how the examples split the sheets and groups and build the
rest.

## Smell table

If a draft matches one row, redesign it instead of patching it.

| The draft has | Why it is wrong | Replace with |
|---------------|-----------------|--------------|
| Instance variables holding another object's UID | A relation stored as pointers | Container, hierarchy, family, or a spatial condition |
| `Pick all` inside a trigger's sub-events, then a pick from a stored link | A pick discarded and rebuilt | Narrowing sub-events; a family for a second instance of the type |
| Globals such as `DragUID`, `Selected` | The trigger's pick copied into globals | The picked instance; store only what the engine cannot recover, such as a start position |
| Local variables filled by one block, then an `Else` chain on them | A program transcribed into events | Trigger, narrowing sub-events, `Else` |
| A boolean such as `occupied`, `busy` written from several events | State that copies a condition | `Is overlapping another object`, `Is dragging`, `Is playing` |
| A variable that counts instances: raised on create, lowered on destroy, or set from `PickedCount` every tick | A copy of the engine's count | `Brick.Count`, read where the decision is made. A destroyed instance is released at the end of the top-level event, and a pick of no instance stops its event. So test "none left" with `Brick.Count = 0` in a top-level event of its own ([pitfalls: Picking](pitfalls/picking.md)) |
| Custom actions named `attach`, `detach`, `sync` that write two variables | Two copies of one fact | One source, usually the engine's |
| `Pick by unique ID` for the object the trigger already picked | Re-picking what is picked | Delete the condition |
| `For each` before actions that already run per picked instance | A redundant loop | Delete it, unless a function call or a pick by one instance's position follows (see [pitfalls: Triggers and Else](pitfalls/triggers-and-else.md)) |
| `Every tick` stepping a progress variable by `dt` and feeding it to `lerp` between fixed ends | A tween written by hand, with its own "finished" bookkeeping. `lerp` toward a moving target, or from a value that the engine updates, is not this | Tween behavior, *On any finished* |
| Per-level numbers in variable names, expression constants or a chain of `Compare` blocks | A lookup table transcribed into events | Array or Dictionary project file, loaded once; Advanced Random for weights |
| A separated string used as a list or a record: `tokenat`/`tokencount` to read, a `Repeat` that rebuilds it to remove one item, `find` to test membership | An array transcribed into string handling, a loop per removal (a generated card game kept its draw pile, discard pile, hand and exhaust pile this way, and each card as 17 `\|`-separated fields) | Array: *Push*, *Pop*, *Delete*, *Shuffle*, *Contains value*; records in a JSON or Array project file |
| Behaviour coded in strings: sibling events testing `find(code, "B")`, `find(code, "BU")`, numbers cut out with `mid`, `tokenat`, `right` | A mini-language parsed by hand. `find` matches any part of the text and ignores case, so the branch of `"B"` runs for `"BU"` and `"s"` for `"SHIFT"` (a generated card game coded its enemy moves and card effects this way) | One field per fact, compared with `=` (Native first, "What a move, an effect or an attack does") |
| A cue list or dialogue markup read with `mid` one character at a time, in a *While* that runs every tick | Here the script is the product and a string is the right file for it, but the sheet parses it again on every tick | Parse the file once when it loads, into an Array of rows, and step that Array ([references/scripted-sequences.md](references/scripted-sequences.md)) |
| A global `state` or `paused` compared at the top of many events | A phase switch or a pause written as a flag | A Group and *Set group active*; *Set time scale* for pause; a layout of its own for another screen |
| A boolean set by one event and a Timer or `Every tick` elsewhere waiting to finish what that event started | A sequence split across events | *Wait* or *Wait for previous actions* in the block that started it |

## Before proposing a structure

1. Write one line per relation: what touches what, what belongs to what,
   which instance the trigger picks.
2. Find an official example with the same behaviors. Filter
   `data/c3-examples/{locale}/*.json` on `used-addons` (`"DragnDrop"` under
   `behaviors` for a drag case). If `Construct-Example-Projects` is cloned
   alongside, copy the event shape from `example-projects/{id}/eventSheets/`.
   Read a sheet as events, not as JSON: `python
   <Construct3-RAG>/skills/construct3-agent-plugin/scripts/print_sheet.py --project
   <Construct-Example-Projects>/example-projects/{id}` prints it in the
   editor's wording, at about a quarter of the length.
   In `family-tree` and `alchemist`, the drop pattern is `On drop`, a
   sub-event `Is overlapping another object`, narrowing conditions, then
   `Else`.
3. Go through the Native first table, and the [Feel](references/feel.md)
   table for each effect the draft names. For each delay, motion, table,
   phase, sequence or effect in the draft, name the built-in that does it.
   Place a new sheet, group or object type as
   [references/new-project.md](references/new-project.md) says. If the
   events go into a project, group, name and comment them as
   [event-sheet-style.md](event-sheet-style.md) says.
4. Read the manual page for each mechanism that you plan to use.
5. Write the draft. Before you show it, check it against the smell table
   and the [pitfalls](event-sheet-pitfalls.md), with the topic file of each
   group that it touches.
6. Only then verify the names with `lookup_ace.py`, as
   [event-sheet-assistant.md](event-sheet-assistant.md) says. ACEs that all
   world objects share are in `plugins/_common.json`.

## Worked case: pieces on a slot grid

If the events drag pieces onto slots or a grid to merge, swap, move or
return them, or if a draft hit the smell table, read
[references/worked-case-slot-grid.md](references/worked-case-slot-grid.md).
It writes the interaction natively, then as a program transcribed into
events.
