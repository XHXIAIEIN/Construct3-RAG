# Event Sheet Pitfalls: Picking

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- Collisions disabled = the instance fails every overlap and collision test, in
  both directions. Use it to take a dragged or tweening instance out of the
  world instead of adding an `isMoving` flag. [manual: plugin-reference/sprite.md
  "Set collisions enabled"; scripting/scripting-reference/object-interfaces/iworldinstance.md
  `isCollisionEnabled`]
- The other side of that: the slot a dragged or tweening instance will land
  on reads empty until it lands, the slot it is flying back to included. The
  drop events expect that; an event that fills empty slots on its own, a buy
  button or a spawn, puts a new instance there, and the returning one lands on
  top of it. Let such an event wait while any instance is being dragged or its
  landing tween is playing. [observed in a game project, r504 preview,
  2026-10-01: a piece dropped back on its slot, the buy button pressed within
  its 0.2 s snap, the bought weapon landed on the piece]
- A type and its family are picked separately: narrowing Sprite `Piece` never
  narrows its family `Pieces`. Use that for two picks of one type in one
  event, and refer to the name the caller narrowed (see [Functions](functions.md)). [manual:
  project-primitives/objects/families.md "Picking families in events"]
- Container members are created, destroyed and picked together; hierarchy
  children are not picked with their parent, use *Pick children*. [manual:
  project-primitives/objects/containers.md; plugin-reference/common-features/common-conditions.md
  "Hierarchy"]
- A container belongs to an object type, and picking a family never picks
  it: with `HPBar` in `Enemy`'s container, `On clicked Enemies` then
  `HPBar: Set width` sets every bar. Pick the type from the family in a
  sub-event, `Enemy: Pick by unique ID Enemies.UID`, and the container comes
  with it; one such sub-event per member type, under `For each Enemies` when
  several are picked. The same bridge reaches a second family of the
  instance, whose variables and behaviors the first family's events cannot
  see. [Construct-bugs#7485, open; example: elemental-conveyors event 35,
  `Draggable` picked by `Base.UID`]
- *Pick children* picks only among the child type's instances already
  picked, and a child type in the parent's container is narrowed as soon as
  the parent is. In `Piece: On drop`, `PieceArt` sits in `Piece`'s container
  and is already the dragged piece's art, so `Pieces: Pick children
  PieceArt` finds nothing on the piece under it. Give the child type a family
  of its own, `Arts` with the one member `PieceArt`, and pick children of
  the family: its picks are kept apart from the container's. [runtime:
  exported c3runtime.js r503, `AnySDK.PickChildren` keeps the child class's
  current picks unless they are all of it, then applies the result to the
  child's container; observed in a game project, r503 preview, 2026-09-28:
  the merge target's body was not picked until the pick went through a
  one-member family]
- *Pick parent* with *Which* set to *Own* looks one level up only. With
  `base → view → body`, `Bodies: Pick parent base (own)` picks nothing,
  because `body`'s own parent is `view`, and the event's actions never run
  without an error. Set *Which* to *All* whenever the parent you name is
  not the direct one; *Pick children* with *All* is the same the other
  way down. [manual: plugin-reference/common-features/common-conditions.md
  "Pick parent"; observed in a game project, r504 preview, 2026-09-30: a
  deploy flag cleared from `On Tween "hop" finished` through `Pick parent
  base (own)` stayed set, and the piece never started attacking until the
  pick was changed to *All*]
- A data object (Dictionary, JSON) in a container gives each instance its own
  copy, picked with its type as above. Use it instead of a growing list of
  instance variables when stats come from a data file. [manual:
  project-primitives/objects/containers.md "data storage objects"]
- Sub-events run after the parent's actions, so a change made there (collisions
  re-enabled) is visible to the sub-event's conditions. [manual:
  project-primitives/events/sub-events.md]
- Hierarchy children may live on a different layer than their parent; the
  connection is per instance, not per layer. A child on a lower layer stays
  a child, so a lifted parent can be drawn above everything while its parts
  stay under an outline. [releases: beta.json, "hierarchy information not
  duplicated properly if connections were setup between instances in
  different layers"; observed in a game project, 2026-09-17, unverified at runtime]
- *ChildCount*, *Compare child count* and *Has children* count every attached
  child whatever its type. A second child type on the same parent shifts
  every count that meant one type. Get the
  top index from *Pick children* plus *Pick highest* on that type, or count in
  a *For each* over the picked children. [manual:
  plugin-reference/common-features/common-expressions.md "ChildCount",
  common-conditions.md "Compare child count"; observed in a game project, 2026-09-17]
- *Destroy* does not detach a child from its parent. The instance is only
  released at the end of the top-level event, and until then *Compare child
  count*, *Has children*, `ChildCount` and *Pick children* still see it.
  Destroying a child in one sub-event and counting children in the next
  sub-event of the same trigger counts the destroyed one. Count the type you
  mean with *Pick children* plus `PickedCount`, or do the count from a
  later top-level event. [manual: system-reference/system-actions.md "Unload
  images" note "destroying objects does not really release them until the
  end of the next top-level event"; runtime: exported c3runtime.js,
  `DestroyInstance` defers, `GetChildCount` is `GetChildren().length`;
  observed in a game project, 2026-09-17]
