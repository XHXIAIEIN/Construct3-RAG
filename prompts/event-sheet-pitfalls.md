# Event Sheet Pitfalls

Runtime facts that general programming intuition gets wrong. Read with
[event-sheet-thinking.md](event-sheet-thinking.md) before writing events. Each
bullet ends with its source: a manual page under `Construct3-Manual/`, a schema
file, an official example id, a page of the community cheat sheet at
fed-4.gitbook.io/c3-cheat-sheets, or an observation (project, date). No
source, no entry. Editing `eventSheets/*.json`, `layouts/*.json` or clipboard JSON by hand?
Read [references/hand-editing-project-files.md](references/hand-editing-project-files.md)
first.

## Picking

- Collisions disabled = the instance fails every overlap and collision test, in
  both directions. Use it to take a dragged or tweening instance out of the
  world instead of adding an `isMoving` flag. [manual: plugin-reference/sprite.md
  "Set collisions enabled"; scripting/scripting-reference/object-interfaces/iworldinstance.md
  `isCollisionEnabled`]
- A family and its member type are picked separately. Narrowing `Piece` never
  narrows `Pieces`. Use that to hold two lists of one type in one event, and
  refer to the name the caller narrowed (see Functions). [manual:
  project-primitives/objects/families.md "Picking families in events"]
- Container members are created, destroyed and picked together; hierarchy
  children are not picked with their parent, use *Pick children*. [manual:
  project-primitives/objects/containers.md; plugin-reference/common-features/common-conditions.md
  "Hierarchy"]
- A data object (Dictionary, JSON) in a container gives each instance its own
  copy, and picking the world member through a family picks that copy too:
  `EnemyGroup: Is overlapping AttackRange` then `EnemyStats: Subtract from
  "hp"` hits the right enemy's sheet. Use it instead of a growing list of
  family instance variables when stats come from a data file. [manual:
  project-primitives/objects/containers.md "data storage objects";
  observed: mergeGame, enemyBase + EnemyStats, 2026-09-17]
- Sub-events run after the parent's actions, so a change made there (collisions
  re-enabled) is visible to the sub-event's conditions. [manual:
  project-primitives/events/sub-events.md]

- Hierarchy children may live on a different layer than their parent; the
  connection is per instance, not per layer. A child on a lower layer stays
  a child, so a lifted parent can be drawn above everything while its parts
  stay under an outline. [releases: beta.json, "hierarchy information not
  duplicated properly if connections were setup between instances in
  different layers"; observed: WaterSort, Liquid on layer Liquid under Tube on
  layer Tubes, 2026-09-17, unverified at runtime]
- *ChildCount*, *Compare child count* and *Has children* count every attached
  child whatever its type. A second child type on the same parent (a Stream
  added to the pouring Tube) shifts every count that meant one type. Get the
  top index from *Pick children* plus *Pick highest* on that type, or count in
  a *For each* over the picked children. [manual:
  plugin-reference/common-features/common-expressions.md "ChildCount",
  common-conditions.md "Compare child count"; observed: WaterSort, the top
  unit lost its flat edge while pouring, 2026-09-17]
- *Destroy* does not detach a child from its parent. The instance is only
  released at the end of the top-level event, and until then *Compare child
  count*, *Has children*, `ChildCount` and *Pick children* still see it.
  Destroying a child in one sub-event and counting children in the next
  sub-event of the same trigger counts the destroyed one, so an emptied tube
  whose Mask was just destroyed reads as "has children". Count the type you
  mean with *Pick children* plus `PickedCount`, or do the count from a
  later top-level event. [manual: system-reference/system-actions.md "Unload
  images" note "destroying objects does not really release them until the
  end of the next top-level event"; runtime: exported c3runtime.js (Sep
  2026), `DestroyInstance` marks the instance and defers, `GetChildCount`
  is `GetChildren().length`; observed: WaterSort CheckWin never showed the
  win text, 2026-09-17]

## Triggers and Else

- A trigger can fire with several instances picked. Timer *On timer* does when
  timers elapse in the same tick; a *Pick nearest* or a function call written
  for one instance then runs once. Add *For each* after such triggers. [manual:
  behavior-reference/timer.md, note under "On timer"]
- Else is decided per block: it runs only if the previous sibling ran for no
  instance. Three picked, one passing, and Else does not run for the other two.
  Per-instance branching is a second event with the inverted condition, or the
  default-then-override pattern. [manual: system-reference/system-conditions.md
  "Else"]
- Else does not narrow; it starts from the parent's picks. It cannot directly
  follow a trigger block, only a normal sub-event inside one. [same]

## Functions

- Function local variables declared as children of the function block are
  in scope for its sub-events, but NOT for the function block's own
  top-level actions: a `Set value` on the local there makes the editor
  reject the whole project at load with "cannot find event variable".
  Compute the locals in a child block placed after the declarations
  instead. [observed: waterGames, r502 editor, 2026-09-17]
- Without *Copy picked* a function runs with every object reset to all picked:
  "modify this sprite" modifies every instance. [manual:
  interface/dialogs/function.md "Copy picked"]
- With *Copy picked*, type and family picks are copied separately. A function
  that writes `Bases.*` acts on whatever `Bases` happened to hold, even if the
  caller narrowed `base`. Shared logic that only acts on the caller's picked
  instances of one object and returns nothing is a *custom action* on that
  object or family, not a function: it runs on exactly the instances of its
  object the caller picked, and a family custom action called through a member
  type runs the family block on that member's picked instances. Inside a family
  block write the family name (`Bases.X`); the member type is not carried in
  and `base.X` reads the first of all instances. [manual:
  project-primitives/events/functions.md "functions with no return type are
  essentially custom actions"; project-primitives/events/custom-actions.md
  "Picking", "Family custom actions"; example: custom-action-overrides;
  observed: mergeGame `applyStats` and `attack` moved from copy-picked
  functions to `Bases` custom actions, 2026-09-17]
- Parameters are bare identifiers in expressions: `Self.X + OffsetX`. Prefer
  `posX` over `x` for legibility. [example: 3d-castle-maze, function OffsetHand]

## Timer

- *Start timer* on an existing tag restarts it. After *Stop*, or after a *Once*
  timer fires, its expressions return 0. Remaining time is
  `Duration(tag) - CurrentTime(tag)`; `CurrentTime` resets at every *On timer*.
  [manual: behavior-reference/timer.md]
- A timer is state you start and stop: list every transition before choosing it
  (settled: start or stop by overlap; picked up: stop; displaced: stop). A `dt`
  countdown gated by an overlap condition has no transitions but needs
  *compare + For each* to dispatch. Both are valid. [observed: mergeGame,
  2026-09-15]
- Timers and tweens each round their end to the first tick at or past it,
  counted from their own start. A tween started by *On timer* at `D` and a
  timer set for `D + T` where `T` is the tween's length do not end together:
  they overlap by a tick or leave a tick's gap, and *Destroy on complete* leaves
  the instance in place for the rest of that tick. Logic that assumes the
  schedule (a sum of heights that is "always at least one unit", a count of
  children) jumps for that tick; derive state from *Is playing* and from the
  instance whose tween it is. [observed: WaterSort, the tube snapping to its
  end tilt for one frame when the last unit's drain began before the unit
  above it was destroyed, 2026-09-18]

## Expressions

- `lerp(Self.X, Target.X, 0.1)` moves a different fraction per second at
  different framerates and ignores the time scale. When the third argument is a
  constant and the first is last tick's result, write `lerp(a, b, 1 - f^dt)`
  with `f` in (0, 1); `f * dt` is the common approximation and the tutorial
  the manual links says it is not exact. The same holds for `anglelerp`.
  [manual: system-reference/system-expressions.md "dt", linking the
  delta-time tutorial, section "Lerp"; examples: magic-feather, surface-jump]
- `lerp` needs no time of its own when the factor comes from the engine:
  `Self.Tween.Value("Attack")` in labyrinth, a timeline value, `unlerp` of a
  slider thumb, `Car.Speed / Car.MaxSpeed` in abductractor. Those are
  mappings, not tweens, and there is nothing to replace. [examples: labyrinth,
  abductractor, plus 123 of 490 example projects using `lerp`, 2026-09-17]
- `lerp` and `unlerp` do not clamp: `lerp(0, 100, 1.5)` is 150, and `unlerp`
  of a value outside its range goes past 0 or 1. Remap with
  `lerp(lo, hi, unlerp(a, b, v))` and wrap it in `clamp` when `v` can leave
  `[a, b]`. [manual: system-reference/system-expressions.md "lerp", "unlerp",
  "clamp"; cheat sheet "Useful expressions and formulas", Remapping a range]
- `%` is the remainder and keeps the sign of the left operand, so `-1 % 5` is
  `-1`. An index that steps backwards wraps with `(n % max + max) % max`.
  [manual: project-primitives/events/expressions.md "%"; cheat sheet "Useful
  expressions and formulas", Wrapping around a number]
- Angles are degrees, 0 faces right and they increase clockwise, so 90 points
  down. Some expressions return -180..180 and others 0..360: compare angles
  with `anglediff`, *Is between angles* or *Is clockwise from*, never with
  `<`, and normalise with `(a + 360) % 360` only where a value must land in
  0..360. [manual: system-reference/system-expressions.md "Math";
  system-reference/system-conditions.md "Is between angles"; cheat sheet
  "Coordinate system"]

- A local variable placed as a sub-event is visible to the sibling events
  after it and their sub-events, not to the parent's own actions. Set it in a
  sibling block with no conditions, then read it in the blocks that follow; it
  resets to its initial value every time the scope is entered unless static.
  [manual: project-primitives/events/variables.md "Local variables", "Static
  and constant variables"]
- *Set mesh point* in *Relative* mode adds to the point's current position,
  not to its default, so a per-tick derivation accumulates. Derive with
  *Absolute* and normalised coordinates (0..1 across the object box, which may
  be exceeded); texture -1 leaves the texture position alone. [manual:
  plugin-reference/common-features/common-actions.md "Set mesh point"]

## Rendering

- A blend mode such as *Destination in* only touches the pixels under the
  object's own quad: a mask sprite the size of the shape it reveals leaves
  everything outside its bounding box untouched, and the layer needs *Force
  own texture* or the blend hits the whole screen. Size the mask to cover
  everything it must erase, or keep the content inside its box. [manual:
  project-primitives/layers.md "Force own texture"; example:
  mask-effect-puzzle (layer HiddenWorld); observed: WaterSort, sheared liquid
  past the tube bottom stayed visible next to a cavity-sized mask, 2026-09-17]

## Tween

- A value tween drives what Tween cannot address: *Tween (value)* with start,
  end and time, then an event *Is playing "tag"* with *Set effect parameter*,
  *Set Z height* or *Set angle* to `Self.Tween.Value("tag")`. The tween owns
  the clock and the ease; the action just reads it. Use it for a full turn: a
  one-property angle tween to `Self.Angle + 360` does not turn, a value tween
  from `Self.Angle` to `Self.Angle + 360` applied with *Set angle* does.
  [manual: behavior-reference/tween.md "Tween (value)", "Value"; example:
  abductractor ("ReduceLuminosity", "SmashCorn"); the angle case:
  github.com/Scirra/Construct-feature-requests/issues/547, closed expired]

## Creating objects

- *Create object* picks only the new instance, plus the created children when
  *Create hierarchy* is on; container siblings are created too. Whether the new
  instance is also picked in its families is undocumented. To act on it through
  the family, use *System: Pick last created* with the family in a sub-event;
  the manual names that as the way to pick a created instance from its family.
  [manual: system-reference/system-actions.md "Create object";
  system-reference/system-conditions.md "Pick last created"]
- A runtime-created instance takes its properties from an existing instance or
  the named template. Keep one template instance per runtime-created object in
  a layout that never runs. [same; creation with zero instances anywhere is
  unverified]
- A Particles object given a Sprite as its *Object* spawns real instances:
  *On created* fires for each, and they are not children of the emitter (the
  example parents them by hand). Per-particle state such as a colour frame
  comes from *On created* plus *Pick nearest* emitter, read from the emitter's
  instance variable. [example: child-particles; observed: WaterSort Splash
  and Drop, 2026-09-17, unverified at runtime]

## Storage and preview

- *Preview* (F5, the toolbar button) starts from the layout open in the
  editor, not from the project's first layout; only *Preview project* uses
  that. A loader layout that reads Local Storage and then goes to the game
  layout is skipped whenever the game layout is previewed, and the save
  appears not to work. Read the save in the sheet of the layout that needs
  it, gated by a global such as `loaded`, and build from the trigger.
  [manual: overview/testing-projects.md "Preview project"; observed:
  WaterSort, 2026-09-18]
- Local Storage is an IndexedDB database named `c3-localstorage-` plus the
  project's `uniqueId`, so it survives closing the preview and is separate
  per project. A tool that rewrites `project.c3proj` must keep `uniqueId`
  or the saved data is orphaned. [runtime: exported c3runtime.js
  `_GetProjectStorage`, Sep 2026; manual:
  scripting/scripting-reference/interfaces/istorage.md "unique to the
  specific project"]

## Adding an entry

One bullet: fact, consequence, source. Manual wording beats an observation, an
observation beats intuition, intuition is not an entry. Would the agent get it
wrong without the line? If not, do not add it.
