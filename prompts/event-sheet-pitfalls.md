# Event Sheet Pitfalls

Runtime facts that general programming intuition gets wrong. Read with
[event-sheet-thinking.md](event-sheet-thinking.md) before writing events. Each
bullet ends with its source: a manual page under `Construct3-Manual/`, a schema
file, an official example id, or an observation (project, date). No source, no
entry. Editing `eventSheets/*.json`, `layouts/*.json` or clipboard JSON by hand?
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
- Sub-events run after the parent's actions, so a change made there (collisions
  re-enabled) is visible to the sub-event's conditions. [manual:
  project-primitives/events/sub-events.md]

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

## Adding an entry

One bullet: fact, consequence, source. Manual wording beats an observation, an
observation beats intuition, intuition is not an entry. Would the agent get it
wrong without the line? If not, do not add it.
