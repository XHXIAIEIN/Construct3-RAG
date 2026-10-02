# Construct 3 Event Sheet — Design Guide

Decides what the events are before any is written. [event-sheet-assistant.md](event-sheet-assistant.md)
says how to write one down; [event-sheet-pitfalls.md](event-sheet-pitfalls.md)
lists the runtime facts intuition gets wrong, one line each, and says which
topic file under `pitfalls/` to open for the ones the events touch. Before the events go into a
project or a generator, read [event-sheet-style.md](event-sheet-style.md):
how the official examples organise, name and comment a sheet, and the three
habits the checker warns on. Run every draft through the smell table below
before showing it.

A sheet that links objects through UID variables, resets picking with
`Pick all`, copies picked results into variables and branches on the numbers,
or rebuilds a timer, a tween or a lookup table out of variables and `Every
tick` is a program transcribed into events. It works, and an experienced
Construct user rejects it.

## The model

Events filter instances. A condition narrows the picked instances and actions
run on what is left; an object no condition names has all its instances
picked. A trigger fires with the instances involved already picked. Sub-events
carry on from the parent's set, siblings all start from that same set, and
top-level events start from everything. Spatial relations (`Is overlapping
another object`, `Pick overlapping point`, `Pick nearest/furthest`) are
conditions: they pick. [manual: project-primitives/events/how-events-work.md,
project-primitives/events/sub-events.md,
plugin-reference/common-features/common-conditions.md]

Manual paths are relative to the `Construct3-Manual/` directory inside the
`Construct3-Manual` clone alongside this repository. The same path without
`.md` after `https://www.construct.net/en/make-games/manuals/construct-3/`
is the live page, but construct.net rejects fetches from an agent, so read
the clone.

## Rules

1. **A relation is the condition that tests it.** "Is this slot taken?" is
   `Slot: Is overlapping Piece`; "which slot did it land on?" is `Pick Slot
   overlapping point (Piece.X, Piece.Y)`; "belongs to" is a container,
   hierarchy or family. Add an instance variable only when no condition can
   answer the question.
2. **The engine owns the state it already has.** Position, overlap, dragging,
   tween progress, animation name and frame, parent and child all have conditions and
   expressions. A boolean mirroring one (`occupied`, `isDragging`) drifts as
   soon as instances move, and every event that writes it is a place to
   forget. Store only what nothing can ask (level, score, where a drag
   started), on the instance that owns it, declared on the family when family
   events read it. A decision that then plays out as an animation is one of
   these: while the units of a pour drain and fill, the engine's state answers
   for the tube it was, and a check that reads it seals the tube it is about
   to empty. Record the decision the moment it is made, and let the animation
   catch up.
3. **Use the trigger's pick.** Inside `On drop`, `Piece` is the dropped piece.
   Narrow with sub-events; do not copy its UID out and re-pick it.
4. **Second instance of the same type: a family.** The dropped `Piece` and the
   `Pieces` already on the slot are two independent picks in one event:
   `Pieces.level = Piece.level`, then `Piece: Destroy`.
5. **Take an instance out of the world instead of flagging it.** `Set
   collisions disabled` at `On drag start`, enabled again when it settles
   (Tween `On any finished`). Every overlap test now ignores it: its old slot
   reads empty, and dropping back on the origin is the empty-slot branch.
6. **Shape: trigger, narrowing sub-events, Else.** Each branch reads as a
   sentence: on drop; over a slot; slot holds a piece; same level: merge.
   Else: swap. Else: move in. Else: go back. Collecting values into variables
   first and branching on the numbers is the wrong shape.
7. **Derive appearance every tick.** One unconditioned event sets the default
   look; the next picks the exceptions and overrides. Nothing to reset.
8. **UID, `Pick all` and globals come last.** Right for references that cross
   events (an inventory array of UIDs, a persisted selection) and for
   singletons. Inside one interaction they mean the trigger's pick was thrown
   away and rebuilt by hand.

## Native first

Before a variable, an `Every tick` or a formula, ask which built-in already
does it. The mechanisms below exist; a draft that rebuilds one by hand is a
program transcribed into events even when no picking smell shows.

| Need | Use | Not |
|------|-----|-----|
| A delay, a countdown, a cooldown | Timer behavior: *Start timer*, *On timer*, `Duration(tag) - CurrentTime(tag)` | An instance variable decremented by `dt` and compared every tick |
| A fixed-duration move, scale, fade, colour change: known start, known end, known time | Tween behavior: *Tween (one/two/three properties)*, *On any finished* | A progress variable stepped by `dt`, fed to `lerp` and checked for 1 |
| A fixed-duration change of something Tween has no property for: an effect parameter, a behavior property, Z height, a full 360° turn | *Tween (value)*, then *Is playing* with *Set …* to `Self.Tween.Value(tag)` ([pitfalls: Tween](pitfalls/tween.md)) | The same progress variable, or a one-property angle tween asked for a full turn |
| Smooth follow of a target that keeps moving: camera, cursor, aim angle | `lerp(a, b, 1 - f^dt)` (`anglelerp` for angles) in `Every tick`; the target is read fresh each tick and nothing finishes | A Tween restarted every tick; `lerp(a, b, 0.1)` with a constant factor, which is framerate-dependent |
| A value derived from another live value: colour from health, zoom from speed, a slider position | `lerp(lo, hi, t)` with `t` from `unlerp`, a ratio, `Tween.Value(tag)` or a timeline; no time of its own | A variable holding the mapped value, updated from several events |
| Continuous motion toward a target or along a heading | MoveTo, Bullet, Pathfinding, Platform, 8 Direction | `Set X`/`Set Y` from your own velocity variables |
| Repeating or periodic movement, flashing, fading out | Sine, Flash, Rotate; a fade is a Tween on Opacity | Hand-written oscillation; the Fade behavior, superseded |
| Level data, loot tables, stat curves, any lookup table | Array or Dictionary project file (Project Bar: *New - Array / Dictionary*), loaded at start with AJAX *Request project file* then *Load* from `AJAX.LastData`; nested or hand-written data through the JSON plugin | Per-level instance variables, `level1Hp`, chained conditions or nested ternaries that encode the table in expressions |
| Weighted random, seeded random, noise | Advanced Random: probability tables, `Weighted`, `Seed`, `Classic2d` | A cascade of `random()` comparisons with hand-tuned thresholds |
| Data that survives a reload | Local Storage: *Set item*, *Get item*, *On item get* | Globals, which reset on reload; the Persist behavior, which keeps instances across layout changes, not across sessions |
| Logic shared by several events | Functions with parameters and return values; a *custom action* on the object or family when it acts on picked instances | The same action block pasted into several events |
| A slice of the sheet that only runs in one phase: tutorial, a boss's AI, debug tools | A Group, off at start when the phase is later, *Set group active* at the transition. Only events stop: behaviors, timers and tweens in it run on | A global mode variable that every event in the slice compares |
| Which controls to offer: on-screen buttons for touch, keys and mouse on a desktop | Touch with *Use mouse input* off; *On any touch start* sets a global to touch, Mouse *On any click* or Keyboard *On any key pressed* to desktop, and the global shows the touch-controls layer and activates its group (detecting-input-method, decided once on a title screen; left active in play, the same triggers follow a change of device; Gamepad *On any button pressed* adds a pad). It picks a scheme, not a gesture: a drag that differs under a finger tests *Mouse button is down* per tick, which also works with *Use mouse input* on ([pitfalls: Input](pitfalls/input.md)) | Touch triggers with *Use mouse input* on, which fire for a click as well |
| Pause, slow motion, hit stop | *Set time scale* 0 (pause) or 0.1 (hit stop, slow motion); *Set object time scale* 1 on the UI that must keep moving; *Use time scale* off on the wait that ends it | A `paused` global checked in every event; behaviors disabled one by one |
| One thing after another inside one interaction: knock back, then re-enable; fade out, then go to layout | *Wait* and *Wait for previous actions* in the same block; the picked instances are kept | A flag set now and a Timer or `On any finished` elsewhere to finish the sequence |
| Reacting to a state any instance may reach, whoever started it | Timer *On timer*; Tween *On any finished* | A *Wait* that assumes one caller |
| HUD and UI that stay on screen while the layout scrolls | A layer with parallax 0, 0; *Global* on that layer when every layout shows the same HUD | Every-tick *Set position* from `ViewportLeft`/`ViewportTop` |
| A number shown as a bar, a gauge or a row of icons: health, fuel, progress, lives | One object, one property from one expression, `Set width to value / max × LENGTH` clamped, its origin on the edge it grows from, a frame behind it, Tween *Width* for a change; the art decides the object, Tiled Background for a colour or a painting to reveal, 9-patch for caps, one Tiled Background of `count × icon width` for hearts ([references/progress-bars.md](references/progress-bars.md)) | A Sprite scaled from its centre origin; a per-tick lerp of the width; one object type or one event per heart |
| A panel, menu or popup opened and closed as a whole | Its own layer, *Initially visible* off: *Set layer visible*; to fade it, *Set layer opacity* from a *Tween (value)* on a manager object (airborne-explorer, `MenuUI` and `ShopUI`; eventide, `PauseUI`) | *Set visible* on each of its objects, in every event that opens or closes it |
| A set of objects treated alike | Family; instance variables and behaviors declared on the family | Duplicate event blocks per object type |
| Objects that belong together | Container (created, destroyed and picked together); hierarchy for parent-relative position | UID variables, or every-tick position copying |

[manual: behavior-reference/timer.md, behavior-reference/tween.md,
system-reference/system-expressions.md "lerp", "dt",
behavior-reference/move.md, behavior-reference/bullet.md,
plugin-reference/array.md "Load", plugin-reference/ajax.md "Request project
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

Two checks before choosing: a Timer is state with transitions, list them
([pitfalls: Timer](pitfalls/timer.md)); an Array *Load* reads Construct's own JSON layout, so the
file comes from the Array editor, not a hand-written JSON (the JSON plugin
reads those).

A behavior that exists can still be the wrong one. An existing project may
keep a superseded feature; a new one takes what replaced it. Fade is a fixed
series of opacity tweens, so it is a *Tween (one property)* on Opacity. Pin
is a hierarchy, *Add child* on the parent, which holds up where chains of
pinned objects do not. The Solid behavior's own *Tags* property is instance
tags, which is what *Use instance tags* turns on by default. Z axis scale
*Normalized* is deprecated rather than superseded: a new project is
*Regular*, where Z is a co-ordinate on the same scale as X and Y, and 3D
sizes read as they look.
[manual: tips-and-guides/superseded-features.md,
tips-and-guides/deprecated-features.md]

## Feel

Screen shake, hit stop, squash, hit flash, a choreographed sequence, a
following camera, a fade between layouts, a keyframed motion such as a
weapon swing, effects layered on one body, a dragged thing that lags: the
recipe for each is in [references/feel.md](references/feel.md). Which
sounds play, when and how loud, and how a placeholder file is made and
checked, is in [references/sound.md](references/sound.md). Read them when
generating a game, or before writing events for any of these.

## Layout of the sheet

Generating a project, or adding a layout, layer, event sheet, group or
object type to one: read [references/new-project.md](references/new-project.md)
first, how the examples split the sheets and groups and build the rest.

## Smell table

One hit means redesign, not patch.

| The draft has | Why it is wrong | Replace with |
|---------------|-----------------|--------------|
| Instance variables holding another object's UID | A relation stored as pointers | Container, hierarchy, family, or a spatial condition |
| `Pick all` inside a trigger's sub-events | The trigger's pick discarded and rebuilt | Narrowing sub-events; a family for the second instance |
| Globals such as `DragUID`, `Selected` | The trigger's pick copied out | The picked instance; snapshot only what the engine cannot recover, such as a start position |
| Local variables filled by one block, then an `Else` chain on them | A program transcribed into events | Trigger, narrowing sub-events, `Else` |
| A boolean such as `occupied`, `busy` written from several events | State mirroring a condition | `Is overlapping another object`, `Is dragging`, `Is playing` |
| Custom actions named `attach`, `detach`, `sync` that write two variables | Two copies of one fact | One source, usually the engine's |
| `Pick by unique ID` for the object the trigger already picked | Re-picking what is picked | Delete the condition |
| `For each` before actions that already run per picked instance | A redundant loop | Delete it, unless a function call or a pick by one instance's position follows (see [pitfalls: Triggers and Else](pitfalls/triggers-and-else.md)) |
| `Every tick` stepping a progress variable by `dt` and feeding it to `lerp` between fixed ends | A tween written by hand, with its own "finished" bookkeeping. `lerp` toward a moving target, or from a value the engine owns, is not this | Tween behavior, *On any finished* |
| Per-level numbers in variable names, expression constants or a ladder of `Compare` blocks | A lookup table transcribed into events | Array or Dictionary project file, loaded once; Advanced Random for weights |
| A global `state` or `paused` compared at the top of many events | A phase switch or a pause written as a flag | A Group and *Set group active*; *Set time scale* for pause; a layout of its own for another screen |
| A boolean set by one event and a Timer or `Every tick` elsewhere waiting to finish what that event started | A sequence split across events | *Wait* or *Wait for previous actions* in the block that started it |

## Before proposing a structure

1. One line per relation: what touches what, what owns what, which instance
   the trigger hands over.
2. Find an official example with the same behaviors: filter
   `data/c3-examples/{locale}/*.json` on `used-addons` (`"DragnDrop"` under
   `behaviors` for a drag case) and, with `Construct-Example-Projects` cloned
   alongside, copy the event shape from `example-projects/{id}/eventSheets/`.
   Read a sheet as events, not as JSON: `python
   <Construct3-RAG>/skills/construct3-agent-plugin/scripts/print_sheet.py --project
   <Construct-Example-Projects>/example-projects/{id}` prints it as the
   editor words it, at about a quarter of the length.
   The drop pattern in `family-tree` and `alchemist` is `On drop`, a sub-event
   `Is overlapping another object`, narrowing conditions, then `Else`.
3. Walk the Native first table, and the [Feel](references/feel.md) table
   for an effect it names: for each delay, motion, table, phase, sequence or
   effect in the draft, name the built-in that owns it. Place a new sheet,
   group or object type by [references/new-project.md](references/new-project.md);
   when the events go into a project, group, name and comment them as
   [event-sheet-style.md](event-sheet-style.md) says.
4. Read the manual page for each mechanism you are about to use.
5. Draft, then run the smell table and the
   [pitfalls](event-sheet-pitfalls.md), with the topic file of every group
   the draft touches.
6. Only then verify names, with `lookup_ace.py` as
   [event-sheet-assistant.md](event-sheet-assistant.md) says; shared
   world-object ACEs are in `plugins/_common.json`.

## Worked case: pieces on a slot grid

Dragging pieces onto slots or a grid, to merge, swap, move or return them,
or a draft that hit the smell table: read
[references/worked-case-slot-grid.md](references/worked-case-slot-grid.md),
the interaction written natively and then as a transcribed program.
