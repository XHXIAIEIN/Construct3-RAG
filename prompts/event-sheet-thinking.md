# Construct 3 Event Sheet — Design Guide

Decides what the events are before any is written. [event-sheet-assistant.md](event-sheet-assistant.md)
says how to write one down; [event-sheet-pitfalls.md](event-sheet-pitfalls.md)
lists the runtime facts intuition gets wrong. Run every draft through the smell
table below before showing it.

A sheet that links objects through UID variables, resets picking with
`Pick all`, or copies picked results into variables and branches on the numbers
is a program transcribed into events. It works, and an experienced Construct
user rejects it.

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
   events read it.
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

## Before proposing a structure

1. One line per relation: what touches what, what owns what, which instance
   the trigger hands over.
2. Find an official example with the same behaviors: filter
   `data/c3-examples/{locale}/*.json` on `used-addons` (`"DragnDrop"` under
   `behaviors` for a drag case) and, with `Construct-Example-Projects` cloned
   alongside, copy the event shape from `example-projects/{id}/eventSheets/`.
   The drop pattern in `family-tree` and `alchemist` is `On drop`, a sub-event
   `Is overlapping another object`, narrowing conditions, then `Else`.
3. Read the manual page for each mechanism you are about to use.
4. Draft, then run the smell table and the pitfalls.
5. Only then verify names as [event-sheet-assistant.md](event-sheet-assistant.md)
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
