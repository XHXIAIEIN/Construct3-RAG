# Event Sheet Pitfalls: Picking

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- An instance with collisions disabled fails every overlap and collision
  test, in both directions. Disable collisions on a dragged or tweening
  instance to take it out of these tests, instead of an `isMoving` flag.
  [manual: plugin-reference/sprite.md "Set collisions enabled";
  scripting/scripting-reference/object-interfaces/iworldinstance.md
  `isCollisionEnabled`]
- A Solid blocks while its behavior is enabled, through the collision
  polygon of its current frame. So a door that only plays an open
  animation keeps blocking wherever its frames' polygons reach. When the
  door opens, disable its Solid with *Set enabled*, or destroy it. [manual:
  behavior-reference/solid.md "Is enabled", "Set enabled";
  behavior-reference/platform.md, the collision polygon changing as an
  animation plays]
- A Solid stops a Platform object at its edge, so the two touch and do not
  overlap. *Is overlapping* stays false while the player stands on a Solid
  floor or walks into a Solid wall. So an event that pushes a crate the
  player is against never runs. Test touching with *Is overlapping at
  offset*, 1 pixel towards the Solid. That is (1, 0) for a wall on the
  right and (0, 1) for the floor. The offset moves the object the condition
  belongs to, so a test from the crate's side takes the opposite sign.
  [manual: plugin-reference/common-features/common-conditions.md "Is
  overlapping at offset"; observed in a copy of the official example
  follow-rewind-time, stable r495.2 preview, 2026-10-04: a Platform player
  held against a Solid wall on a Solid floor, *Is overlapping* false, at
  offset (1, 0) and (0, 1) true]
- While a dragged or tweening instance has collisions disabled, the slot
  where it will land reads empty until it lands, the slot it is flying back
  to included. The
  drop events expect that. But an event that fills empty slots on its own (a
  buy button or a spawn) puts a new instance there, and the returning one
  lands on top of it. Make such an event wait while any instance is being
  dragged or its landing tween is playing. [observed in a game project, r504
  preview, 2026-10-01: a piece dropped back on its slot, the buy button
  pressed within its 0.2 s snap, the bought weapon landed on the piece]
- A type and its family are picked separately, so narrowing Sprite `Piece`
  never narrows its family `Pieces`. Use this for two picks of one type in
  one event. Refer to the name the caller narrowed (see
  [Functions](functions.md)). [manual: project-primitives/objects/families.md
  "Picking families in events"]
- Container members are created, destroyed and picked together. Hierarchy
  children are not picked with their parent, so use *Pick children*. [manual:
  project-primitives/objects/containers.md;
  plugin-reference/common-features/common-conditions.md "Hierarchy"]
- A container belongs to an object type, and picking a family never picks it.
  With `HPBar` in `Enemy`'s container, `On clicked Enemies` then `HPBar: Set
  width` sets every bar. Pick the type from the family in a sub-event,
  `Enemy: Pick by unique ID Enemies.UID`, and the container is picked with
  it. Add one such sub-event per member type, under `For each Enemies` if
  several are picked. The same pick by UID reaches a second family of the
  instance, whose variables and behaviors the first family's events cannot
  see. [Construct-bugs#7485, open; example: elemental-conveyors event 35,
  `Draggable` picked by `Base.UID`]
- Inside a container, an expression that names another member reads the
  member of the same instance in an action, with no condition on a member, no
  pick and no *For each*. So `Fill: Set width to clamp(Frame.hp /
  Frame.maxHp, 0, 1) * (Frame.Width - 4)` in an *Every tick* event sets each
  fill from its own frame. A custom action called with a parameter that reads
  one instance's variable, `SetMax(Frame.maxHp + 300)`, needs *For each*
  `Frame` among the calling event's conditions, so that each bar passes its
  own value. The custom action itself runs once for the picked instances (see
  [Functions](functions.md)). [the manual describes the pairing for picks
  only, project-primitives/objects/containers.md "What containers do";
  observed in a minimal project, stable editor preview, 2026-10-07: seven
  object types in one container, three instances with maximum hp 300, 1000
  and 3000 and a frame 448 px wide; the fills were 222, 377.4 and 421.8 px at
  hp 150, 850 and 2850, and the call under *For each* passed 600, 1300 and
  3300]
- *Pick children* picks only among the child type's instances already picked.
  A child type in the parent's container is narrowed as soon as the parent
  is. In `Piece: On drop`, `PieceArt` is in `Piece`'s container and is
  already the dragged piece's art. So `Pieces: Pick children PieceArt` finds
  nothing on the piece under it. Give the child type a family of its own,
  `Arts` with the one member `PieceArt`, and pick children of the family,
  because its picks are kept apart from the container's. [runtime: exported
  c3runtime.js r503, `AnySDK.PickChildren` keeps the child class's current
  picks unless they are all of it, then applies the result to the child's
  container; observed in a game project, r503 preview, 2026-09-28: the merge
  target's body was not picked until the pick went through a one-member
  family]
- *Pick parent* with *Which* set to *Own* looks only one level up. With
  `Robot → Arm → Hand`, `Hands: Pick parent Robot (own)` picks nothing,
  because `Hand`'s own parent is `Arm`. Then the event's actions never run,
  and no error shows. If the parent you name is not the direct one, set
  *Which* to *All*. *Pick children* with *All* works the same way down the
  hierarchy.
  [manual: plugin-reference/common-features/common-conditions.md "Pick
  parent"; observed in a game project, r504 preview, 2026-09-30: a deploy
  flag cleared from `On Tween "hop" finished` through `Pick parent base
  (own)` stayed set, and the piece never started attacking until the pick was
  changed to *All*]
- A data object (Dictionary, JSON) in a container gives each instance its own
  copy, picked with its type as above. If stats come from a data file, use it
  instead of a growing list of instance variables. [manual:
  project-primitives/objects/containers.md "data storage objects"]
- Sub-events run after the parent's actions, so the sub-event's conditions
  see a change those actions made (collisions re-enabled). [manual:
  project-primitives/events/sub-events.md]
- A hierarchy child can be on another layer than its parent, because the
  connection is per instance, not per layer. A child on a lower layer stays a
  child. So a lifted parent can be drawn above everything while its parts
  stay under an outline. [releases: beta.json, "hierarchy information not
  duplicated properly if connections were setup between instances in
  different layers"; observed in a game project, 2026-09-17; observed in a
  minimal project, r504 preview, 2026-10-02: a child on another layer than
  its parent kept the parent and moved 40 px with it]
- *ChildCount*, *Compare child count* and *Has children* count every attached
  child of any type. So a second child type on the same parent changes every
  count that meant one type. Get the top index from *Pick children* plus
  *Pick highest/lowest* (highest) on that type, or count in a *For each*
  over the picked children.
  [manual: plugin-reference/common-features/common-expressions.md
  "ChildCount", common-conditions.md "Compare child count"; observed in a
  game project, 2026-09-17]
- *Destroy* releases the instance only at the end of the top-level event,
  and until then `Count` still includes it. So the event that destroys the
  last brick still reads `Brick.Count` as 1. Test "none left" in a
  top-level event of its own. [manual: system-reference/system-actions.md
  "Unload images" note "destroying objects does not really release them
  until the end of the next top-level event"; runtime: exported
  c3runtime.js r504, `Count` is `GetInstanceCount()` plus the instances
  pending creation, and `DestroyInstance` defers the removal]
- A condition that picks no instance of a type stops its event, and System
  *Pick all* is false when the type has no instance. So `PickedCount = 0`
  never holds below a pick of that type. Under *Pick all Key*, a sub-event
  that tests `Key.PickedCount = 0` never runs, not even when the last key
  is gone. Test "none left" with `Key.Count = 0` in *Compare two values*,
  in an event that does not pick Key. [manual:
  project-primitives/events/how-events-work.md, the actions "do not run at
  all" when no instance meets the conditions; runtime: exported
  c3runtime.js r504, `PickAll` returns false when `GetInstanceCount()` is 0]
- *Destroy* does not detach a child from its parent. The runtime releases the
  instance only at the end of the top-level event. Until then *Compare child
  count*, *Has children*, `ChildCount` and *Pick children* still see it. So
  if one sub-event destroys a child, the next sub-event of the same trigger
  still counts it. Count the type you mean with *Pick children* plus
  `PickedCount`, or count from a later top-level event. [manual:
  system-reference/system-actions.md "Unload images" note "destroying objects
  does not really release them until the end of the next top-level event";
  runtime: exported c3runtime.js, `DestroyInstance` defers, `GetChildCount`
  is `GetChildren().length`; observed in a game project, 2026-09-17]
- Turret *Add object to target* takes an object type or a family as a
  whole. The instances the event picked do not matter, so a turret given a
  family narrowed to the other team still aims at every member, its own team
  included. To target by an instance variable, leave *Add object to target*
  out and acquire one picked instance: while the turret has no target, *For
  each* turret, narrow the family to the instances it may target, *Pick
  nearest* to the turret, then *Acquire target* that family. *Acquire target*
  takes the picked instance and ignores one out of range. The turret keeps
  the target until it leaves range or is destroyed, and the event then picks
  again. [manual: behavior-reference/turret.md "Add object to target",
  "Acquire target"; observed in a minimal project, stable editor preview,
  2026-10-04: two turrets, two teams in one family told apart by an instance
  variable; with *Add object to target* after narrowing to the other team,
  both turrets aimed at their own team in 240 of 240 samples over 12 s; with
  *Acquire target* on the picked nearest enemy, 0 of 240, while a hull of
  their own team was nearer in 159]
- A condition on an object holds when one instance passes it, and the next
  condition tests only the instances it kept. So a row of three cells
  written as `Cell: Row = 0`, `Cell: Column = 0`, `Cell: Value = 1`,
  `Cell: Column = 1`, ... never holds: no cell has Column 0 and Column 1.
  And `Cell: Value ≠ 0` holds once any cell is filled, not when all are.
  To test that several instances agree, narrow once and count:
  `Cell: Row = 0`, `Cell: Value = 1`, `System: Cell.PickedCount = 3`; the
  board is full when `Cell: Value ≠ 0` keeps `Cell.Count` of them. A
  diagonal is System *Pick by evaluate* `Cell.Row = Cell.Column`, the other
  `Cell.Row + Cell.Column = 2`. [manual:
  project-primitives/events/how-events-work.md, conditions filter the
  picked instances progressively; found in a QQ bot's tic-tac-toe sheet,
  2026-10-06, whose wins and draw were written so; observed in a copy of
  it, stable editor preview, 2026-10-06: row 0 and the diagonal filled, the
  counts held for row 0 and the diagonal and not for row 1 or a full
  board, and `Cell: Value ≠ 0` alone held]
