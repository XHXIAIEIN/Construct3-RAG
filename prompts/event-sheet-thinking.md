# Construct 3 Event Sheet — Design Guide

Decides what the events are before any is written. [event-sheet-assistant.md](event-sheet-assistant.md)
says how to write one down; [event-sheet-pitfalls.md](event-sheet-pitfalls.md)
lists the runtime facts intuition gets wrong. Run every draft through the smell
table below before showing it.

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

Manual paths are relative to `Construct3-Manual/` cloned alongside this
repository; the same path without `.md` after
`https://www.construct.net/en/make-games/manuals/construct-3/` is the live page.

## Rules

1. **A relation is the condition that tests it.** "Is this slot taken?" is
   `Slot: Is overlapping Piece`; "which slot did it land on?" is `Pick Slot
   overlapping point (Piece.X, Piece.Y)`; "belongs to" is a container,
   hierarchy or family. Add an instance variable only when no condition can
   answer the question.
2. **The engine owns the state it already has.** Position, overlap, dragging,
   tween progress, animation frame, parent and child all have conditions and
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
| A fixed-duration change of something Tween has no property for: an effect parameter, a behavior property, Z height, a full 360° turn | *Tween (value)*, then *Is playing* with *Set …* to `Self.Tween.Value(tag)` (pitfalls, "Tween") | The same progress variable, or a one-property angle tween asked for a full turn |
| Smooth follow of a target that keeps moving: camera, cursor, aim angle | `lerp(a, b, 1 - f^dt)` (`anglelerp` for angles) in `Every tick`; the target is read fresh each tick and nothing finishes | A Tween restarted every tick; `lerp(a, b, 0.1)` with a constant factor, which is framerate-dependent |
| A value derived from another live value: colour from health, zoom from speed, a slider position | `lerp(lo, hi, t)` with `t` from `unlerp`, a ratio, `Tween.Value(tag)` or a timeline; no time of its own | A variable holding the mapped value, updated from several events |
| Continuous motion toward a target or along a heading | MoveTo, Bullet, Pathfinding, Platform, 8 Direction | `Set X`/`Set Y` from your own velocity variables |
| Repeating or periodic movement, flashing, fading out | Sine, Flash, Fade, Rotate | Hand-written oscillation |
| Level data, loot tables, stat curves, any lookup table | Array or Dictionary project file (Project Bar: *New - Array / Dictionary*), loaded at start with AJAX *Request project file* then *Load* from `AJAX.LastData`; nested or hand-written data through the JSON plugin | Per-level instance variables, `level1Hp`, chained conditions or nested ternaries that encode the table in expressions |
| Weighted random, seeded random, noise | Advanced Random: probability tables, `Weighted`, `Seed`, `Classic2d` | A cascade of `random()` comparisons with hand-tuned thresholds |
| Data that survives a reload | Local Storage: *Set item*, *Get item*, *On item get* | Globals, which reset on reload; the Persist behavior, which keeps instances across layout changes, not across sessions |
| Logic shared by several events | Functions with parameters and return values; a *custom action* on the object or family when it acts on picked instances | The same action block pasted into several events, or a global "mode" variable that other events branch on |
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
project-primitives/objects/families.md,
project-primitives/objects/containers.md]

Two checks before choosing: a Timer is state with transitions, list them
(pitfalls, "Timer"); an Array *Load* reads Construct's own JSON layout, so the
file comes from the Array editor, not a hand-written JSON (the JSON plugin
reads those).

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
| `For each` before actions that already run per picked instance | A redundant loop | Delete it, unless a function call or a pick by one instance's position follows (see pitfalls) |
| `Every tick` stepping a progress variable by `dt` and feeding it to `lerp` between fixed ends | A tween written by hand, with its own "finished" bookkeeping. `lerp` toward a moving target, or from a value the engine owns, is not this | Tween behavior, *On any finished* |
| Per-level numbers in variable names, expression constants or a ladder of `Compare` blocks | A lookup table transcribed into events | Array or Dictionary project file, loaded once; Advanced Random for weights |

## Before proposing a structure

1. One line per relation: what touches what, what owns what, which instance
   the trigger hands over.
2. Find an official example with the same behaviors: filter
   `data/c3-examples/{locale}/*.json` on `used-addons` (`"DragnDrop"` under
   `behaviors` for a drag case) and, with `Construct-Example-Projects` cloned
   alongside, copy the event shape from `example-projects/{id}/eventSheets/`.
   The drop pattern in `family-tree` and `alchemist` is `On drop`, a sub-event
   `Is overlapping another object`, narrowing conditions, then `Else`.
3. Walk the Native first table: for each delay, motion, table or shared
   piece of logic in the draft, name the built-in that owns it.
4. Read the manual page for each mechanism you are about to use.
5. Draft, then run the smell table and the pitfalls.
6. Only then verify names as [event-sheet-assistant.md](event-sheet-assistant.md)
   says; shared world-object ACEs are in `plugins/_common.json`.

## Worked case: pieces on a slot grid

`Slot` sprites form a grid. `Piece` (Drag & Drop, Tween) sits on slots; family
`Pieces` has the single member `Piece` and carries `level`, `startX`, `startY`.
Drop on an empty slot moves in; on a same-level piece merges; on another piece
swaps; anywhere else returns.

```
Piece: On drag start
  -> Piece: Move to top; Set startX to Self.X; Set startY to Self.Y;
     Set collisions disabled
Piece: On drop
  -> Piece (Drag & Drop): Set disabled
  System: Pick Slot overlapping point (Piece.X, Piece.Y)
    Slot: Is overlapping Pieces
      System: Compare two values  Pieces.level = Piece.level
        -> Pieces: Set level to Pieces.level + 1; Piece: Destroy
      Else
        -> Pieces: Tween position to (Piece.startX, Piece.startY)
           Piece: Tween position to (Slot.X, Slot.Y)
    Else
      -> Piece: Tween position to (Slot.X, Slot.Y)
  Else
    -> Piece: Tween position to (Self.startX, Self.startY)
Piece (Tween): On any finished
  -> Piece (Drag & Drop): Set enabled; Piece: Set collisions enabled
(no condition)                -> Slot: Set frame to 0
Slot: Is overlapping Pieces   -> Slot: Set frame to 1
```

`Piece` is the dropped piece for the whole trigger; `Pieces` is whatever else
is on the target slot. No UID, no `Pick all`, no global. The same interaction
written as a transcribed program, with each smell named, is in
[references/worked-case-slot-grid.md](references/worked-case-slot-grid.md);
read it when a draft has hit the smell table and you need to see the mapping.
