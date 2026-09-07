# Construct 3 Event Sheet — Design Guide

> Load this together with [event-sheet-assistant.md](event-sheet-assistant.md).
> That file says how to write an event down. This file says how to decide what
> the events are. Apply it before proposing any structure, and check the draft
> against the smell table before answering.

A sheet that stores UIDs to link objects, resets picking with `Pick all` in
several places, or copies picked results into variables and then branches on
the numbers is a program transcribed into events. It works, and an experienced
Construct user will reject it. Redesign it.

## The model

Events filter instances. Everything below follows from that one fact. Sources
are the official manual: the path is relative to the `Construct3-Manual`
repository cloned alongside this one, the link is the live page.

| # | Fact | What it means for a design |
|---|------|----------------------------|
| 1 | A condition narrows the picked instances. Actions run only on the instances left. An object that no condition references has all its instances picked. | "Which instance" is answered by conditions. You rarely need to store it. |
| 2 | A trigger such as `On drop` or `On collision with another object` fires with the instances involved already picked. | Inside the trigger, the object name already means "the one this happened to". |
| 3 | Sub-events continue from the parent's picked set. Sibling sub-events all start from that same set. Top-level events start over from all instances. | Narrow step by step with sub-events. One sibling never sees what another sibling picked. |
| 4 | `Else` runs when the previous event did not run. It picks nothing: in the `Else` block every instance is picked again. | An `Else` branch that needs "the same instance" must re-pick it, or the structure must not need it there. |
| 5 | A family picks its instances independently of the object types in it. The manual: this "can be taken advantage of if you need a single event to pick two separate lists of instances from the same object type". | Two instances of one type in one event: put the type in a family and use the family as the second name. |
| 6 | Instances in a container are created, destroyed, and picked together. Hierarchy children and parents are reached with `Pick children` and `Pick parent`. | Composition is a container or a hierarchy, not a pair of UID variables. |
| 7 | `Is overlapping another object`, `Pick overlapping point`, `Pick nearest/furthest`, `Pick by comparison` are conditions. They pick. | Spatial relations are queries, not stored state. Ask the engine every time. |
| 8 | With collisions disabled, no collision event registers for the instance, and an overlap test against it returns false. | To hide an instance from spatial queries while it is being dragged or animated, take it out of the collision world instead of adding a flag. |
| 9 | `For Each` is "commonly mis-used or used redundantly": actions already apply to every picked instance. | Use it only when one event must run once per instance in sequence. |

| Fact | Manual page |
|------|-------------|
| 1, 2, 3 | `project-primitives/events/how-events-work.md`, [How events work](https://www.construct.net/en/make-games/manuals/construct-3/project-primitives/events/how-events-work) |
| 3 | `project-primitives/events/sub-events.md`, [Sub-events](https://www.construct.net/en/make-games/manuals/construct-3/project-primitives/events/sub-events) |
| 4, 7, 9 | `system-reference/system-conditions.md`, [System conditions](https://www.construct.net/en/make-games/manuals/construct-3/system-reference/system-conditions) |
| 5 | `project-primitives/objects/families.md`, [Families](https://www.construct.net/en/make-games/manuals/construct-3/project-primitives/objects/families), section "Picking families in events" |
| 6 | `project-primitives/objects/containers.md`, [Containers](https://www.construct.net/en/make-games/manuals/construct-3/project-primitives/objects/containers); `plugin-reference/common-features/common-conditions.md`, section "Hierarchy" |
| 7 | `plugin-reference/common-features/common-conditions.md`, [Common conditions](https://www.construct.net/en/make-games/manuals/construct-3/plugin-reference/common-features/common-conditions) |
| 8 | `plugin-reference/sprite.md`, "Set collisions enabled"; `scripting/scripting-reference/object-interfaces/iworldinstance.md`, `testOverlap` |

## Design rules

1. **Model a relation with the condition that tests it.** "Is this slot taken?" is `Slot: Is overlapping Piece`. "Which slot did it land on?" is `System: Pick Slot overlapping point (Piece.X, Piece.Y)`. "Does this belong to that?" is a container, a hierarchy, or a family. Add an instance variable only when no condition can answer the question.
2. **Let the engine own the state it already has.** Position, overlap, dragging, tween progress, animation frame, Z order, parent and child all have conditions and expressions. A boolean that mirrors one of them (`occupied`, `isDragging`, `moving`) drifts as soon as instances move, and every event that writes it is a place to forget. A mirror written once, for a fact that never changes back, is acceptable; official examples do that.
3. **Store only what nothing can ask.** Level, score, the position a drag started from, a chosen target. Put them on the instance that owns them. If a family's events must read them, declare them on the family.
4. **Use the trigger's pick.** Inside `On drop`, `Piece` is the dropped piece. Do not copy its UID into a variable and re-pick it later. Narrow with sub-events.
5. **Second instance of the same type: a family.** The dropped `Piece` and the `Pieces` already on the slot are two independent picks in one event. `Pieces.level = Piece.level`, `Pieces: Tween to (Piece.startX, Piece.startY)`, `Piece: Destroy` all read naturally. UID plus local variables is the same logic with the engine switched off.
6. **Take an instance out of the world instead of flagging it.** At `On drag start`: `Set collisions disabled`. Re-enable when it settles, for example on the Tween `On any finished`. Every overlap test now ignores it, so its old slot reads empty and the slot under it reports whatever else is there. Dropping back on the origin becomes the same branch as dropping on an empty slot.
7. **Shape: trigger, narrowing sub-events, `Else`.** Each branch reads as a sentence. On drop; over a slot; slot holds a piece; same level: merge. Else: swap. Else: move in. Else: go back. If the draft first collects values into variables and then branches on numbers, the shape is wrong.
8. **Derive appearance every tick.** One unconditioned event sets the default look. The next event picks the exceptions and overrides. No flag, no reset action, nothing to forget.
9. **Custom actions and functions package behavior, not synchronization.** `snapTo(slot)` that tweens a piece into a slot is a good custom action. `detach` and `attach` that keep two variables agreeing are rule 2 broken.
10. **UID, `Pick all`, and global variables come last.** They are right for references that cross events (an inventory array of UIDs, a persisted selection) and for singletons. Inside one interaction they usually mean the trigger's pick was thrown away and is being rebuilt by hand.

## Smell table

Run the draft against this table before answering. One hit means redesign,
not patch.

| The draft has | It usually means | Replace with |
|---------------|------------------|--------------|
| Instance variables holding another object's UID, in both directions | A relation encoded as pointers | Container, hierarchy, family, or a spatial condition |
| `Pick all` in several sub-events of one trigger | The trigger's pick is discarded and rebuilt | Sub-events that narrow; a family for the second instance |
| Global variables such as `DragUID`, `DragFrom`, `Selected` | The trigger's pick copied out | The trigger's picked instance; a snapshot only of values the engine cannot recover, such as the start position |
| Local variables filled by one block, then an `Else` chain comparing them | A program transcribed into events | Trigger, narrowing sub-events, `Else` |
| A boolean such as `occupied`, `Active`, `busy` written from several events | State mirroring a condition | `Is overlapping another object`, `Is dragging`, `Is playing` |
| Custom actions named `detach`, `attach`, `sync`, `moveBack` that write two variables | Two copies of one fact | One source, usually the engine's |
| `Pick by unique ID` inside a trigger, for the object the trigger already picked | Re-picking what is picked | Delete the condition |
| `For Each` before actions that already apply to every picked instance | A redundant loop | Delete it |

## Before proposing a structure

1. Write one line per relation: what touches what, what owns what, which instance the trigger hands over.
2. Find an official example that uses the same behaviors. Filter `data/c3-examples/{locale}/*.json` on `used-addons`: it holds `plugins`, `behaviors`, and `effects` lists of CDN ids, so a drag-and-drop case is `"DragnDrop"` under `behaviors`. If `Construct-Example-Projects` is cloned alongside, open `example-projects/{id}/eventSheets/*.json` and copy the event shape. The `open` field launches the example in the editor.
3. Read the manual page for each mechanism you are about to use. The table above lists them.
4. Draft, then run the smell table.
5. Only then verify names with [event-sheet-assistant.md](event-sheet-assistant.md). Conditions and actions shared by every world object (overlap, collisions, instance variables, hierarchy, UID, nearest, Z order) live in `plugins/_common.json`, not in the plugin's own file.

The official drop pattern, from `family-tree` and `alchemist` in the example
browser, is `On drop`, a sub-event `Is overlapping another object`, further
narrowing conditions, then `Else`. No UID, no `Pick all`, no global variable.

## Worked case: pieces on a slot grid

A merge game. `Slot` sprites form a grid. `Piece` sprites sit on slots and
have the Drag & Drop and Tween behaviors. Dropping a piece on an empty slot
moves it there. Dropping it on a piece of the same level merges them. Dropping
it on any other piece swaps them. Dropping it anywhere else sends it back.

Events below use outline notation to keep the comparison short. Answer users
in the table format from event-sheet-assistant.md.

### Transcribed program

```
Slot.occupant = UID or -1      Piece.slot = UID or -1
Global DragUID, DragFrom

Piece: On drag start
  -> Set DragUID = Piece.UID, Set DragFrom = Piece.slot, Piece: Set slot to -1
Piece: On drop
  Local toSlot = -1
  Piece: Is overlapping Slot; System: Pick nearest Slot -> Set toSlot = Slot.UID
  System: Pick all Piece; System: Pick Piece by comparison Piece.slot = toSlot
    System: Compare two values ... -> merge
      System: Pick all Piece; Pick Piece by UID DragUID -> Destroy
    Else -> swap: snapTo(DragFrom), then Pick all, Pick by UID DragUID, snapTo(toSlot)
  Else -> snapTo(toSlot)
Custom actions detach / attach keep occupant and slot in step
```

Every `Pick all` and every UID exists because the pick from `On drop` was
copied into numbers and then rebuilt. `Pick nearest` after `Is overlapping`
finds the dragged piece itself when both objects overlap the same slot, which
is why the swap branch needed a guard. `occupant` and `slot` are the same fact
stored twice.

### Native

Family `Pieces` with the single member `Piece`. Family instance variables
`level` (number, 1), `startX`, `startY` (number, 0). No variable on `Slot`.

```
Piece: On drag start
  -> Piece: Move to top, Set startX to Self.X, Set startY to Self.Y,
     Set collisions disabled

Piece: On drop
  -> Piece (Drag & Drop): Set disabled
  System: Pick Slot overlapping point (Piece.X, Piece.Y)
    Slot: Is overlapping Pieces
      System: Compare two values  Pieces.level = Piece.level
        -> Pieces: Set level to Pieces.level + 1
           Piece: Destroy
      Else
        -> Pieces: Tween position to (Piece.startX, Piece.startY)
           Piece: Tween position to (Slot.X, Slot.Y)
    Else
      -> Piece: Tween position to (Slot.X, Slot.Y)
  Else
    -> Piece: Tween position to (Self.startX, Self.startY)

Piece (Tween): On any finished
  -> Piece (Drag & Drop): Set enabled, Piece: Set collisions enabled

(no condition)                -> Slot: Set frame to 0
Slot: Is overlapping Pieces   -> Slot: Set frame to 1
```

`Piece` is the dropped piece for the whole trigger. `Pieces` is whatever else
is on the target slot, picked independently because it is a family. Disabling
collisions during the drag removes the dropped piece from `Is overlapping
Pieces`, so the slot it came from reads empty and dropping back onto it is the
"empty slot" branch. The last two events redraw slot state each tick from the
overlap itself, so nothing has to be reset when a piece leaves.

Names used above, verified against `data/c3-schemas/en-US/`: `Pick
overlapping point`, `Compare two values`, `Else` (System); `Is overlapping
another object`, `Move to top`, `Set value`, `Destroy`
(`plugins/_common.json`); `Set collisions enabled`, `Set frame` (Sprite);
`On drag start`, `On drop`, `Set enabled` (Drag & Drop); `Tween (two
properties)`, `On any finished` (Tween).
