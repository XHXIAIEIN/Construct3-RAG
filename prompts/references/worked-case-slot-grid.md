# Worked case: pieces on a slot grid

This page writes one interaction twice: natively, then as the program
transcribed into events that an agent tends to draft first, with each smell
named. Read it if the events drag pieces onto slots or a grid to merge,
swap, move or return them. Also read it if a draft has hit the smell table
of [../event-sheet-thinking.md](../event-sheet-thinking.md) and you want to
see which construct each smell came from.

## Native

`Slot` sprites form a grid. `Piece` (Drag & Drop, Tween) sits on slots. The
family `Pieces` has the single member `Piece` and carries `level`,
`startX`, `startY`. A piece dropped on an empty slot moves in. On a piece
of the same level it merges, on another piece it swaps, and anywhere else
it returns.

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

`Piece` is the dropped piece for the whole trigger, and `Pieces` is the
piece already on the target slot. The events use no UID, no `Pick all` and
no global.

## As a transcribed program

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
| `DragUID`, `DragFrom` | The trigger's pick copied into globals | `Piece` inside `On drop` is the dropped piece; it stores only `startX`/`startY`, because the start position is the one thing the engine cannot recover |
| `Pick all Piece` then `Pick by comparison` / `Pick by unique ID` | The pick discarded and rebuilt | Family `Pieces` as the second, independent pick of the same type |
| `Pick nearest Slot` after `Is overlapping Slot` | Picks the dragged piece's own slot if the piece overlaps that slot and the target, so the swap branch needs a guard | `Pick Slot overlapping point (Piece.X, Piece.Y)` plus collisions disabled during the drag |
| `toSlot` local, then an `Else` chain on numbers | A program transcribed into events | Trigger, narrowing sub-events, `Else` |
| `detach` / `attach` custom actions | Two copies of one fact kept equal | Slot frames derived every tick from the overlap, with no stored occupancy |

The native version uses these names, verified against
`data/c3-schemas/en-US/`: `Pick overlapping point`, `Compare two values`,
`Else` (System); `Is overlapping another object`, `Move to top`,
`Set value`, `Destroy` (`plugins/_common.json`); `Set collisions enabled`,
`Set frame` (Sprite); `On drag start`, `On drop`, `Set enabled`
(Drag & Drop); `Tween (two properties)`, `On any finished` (Tween). The
drop pattern comes from the `family-tree` and `alchemist` example projects.
