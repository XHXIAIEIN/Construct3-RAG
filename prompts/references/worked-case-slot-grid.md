# Worked case: the slot grid as a transcribed program

Companion to the worked case in [../event-sheet-thinking.md](../event-sheet-thinking.md).
Read it when a draft has hit the smell table and you want to see which
construct each smell came from. The native version is in the guide.

Same interaction: `Slot` grid, `Piece` with Drag & Drop and Tween, drop to
move, merge, swap, or return.

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

| Construct in the draft | Smell | What the native version does instead |
|------------------------|-------|--------------------------------------|
| `Slot.occupant`, `Piece.slot` | A relation stored as pointers, twice | `Slot: Is overlapping Pieces` asks the engine each time |
| `DragUID`, `DragFrom` | The trigger's pick copied out | `Piece` inside `On drop` is the dropped piece; only `startX`/`startY` are stored, because position is the one thing the engine cannot recover |
| `Pick all Piece` then `Pick by comparison` / `Pick by UID` | The pick discarded and rebuilt | Family `Pieces` as the second, independent pick of the same type |
| `Pick nearest Slot` after `Is overlapping Slot` | Finds the dragged piece's own slot when both overlap it, so the swap branch needed a guard | `Pick Slot overlapping point (Piece.X, Piece.Y)` plus collisions disabled during the drag |
| `toSlot` local, then an `Else` chain on numbers | A program transcribed into events | Trigger, narrowing sub-events, `Else` |
| `detach` / `attach` custom actions | Two copies of one fact kept in step | No stored occupancy; slot frames derived every tick from the overlap |

Names in the native version, verified against `data/c3-schemas/en-US/`:
`Pick overlapping point`, `Compare two values`, `Else` (System);
`Is overlapping another object`, `Move to top`, `Set value`, `Destroy`
(`plugins/_common.json`); `Set collisions enabled`, `Set frame` (Sprite);
`On drag start`, `On drop`, `Set enabled` (Drag & Drop); `Tween (two
properties)`, `On any finished` (Tween). Source of the drop pattern: the
`family-tree` and `alchemist` example projects.
