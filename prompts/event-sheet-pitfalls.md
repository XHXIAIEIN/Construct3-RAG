# Event Sheet Pitfalls

Runtime facts that general programming intuition gets wrong. Read with
[event-sheet-thinking.md](event-sheet-thinking.md) before writing events. Each
bullet ends with its source: a manual page under `Construct3-Manual/`, a schema
file, an official example id, a page of the community cheat sheet at
fed-4.gitbook.io/c3-cheat-sheets, or an observation in a game project with its date. No
source, no entry. Editing `eventSheets/*.json`, `layouts/*.json` or clipboard JSON by hand?
Read [references/hand-editing-project-files.md](references/hand-editing-project-files.md)
first.

Picking and Triggers and Else come up in almost every event sheet and are
here in full. Every other group is one line per pitfall, its conclusion;
when the events touch what a group names, open its topic file for the
cases and the sources before writing them.

## Picking

- Collisions disabled = the instance fails every overlap and collision test, in
  both directions. Use it to take a dragged or tweening instance out of the
  world instead of adding an `isMoving` flag. [manual: plugin-reference/sprite.md
  "Set collisions enabled"; scripting/scripting-reference/object-interfaces/iworldinstance.md
  `isCollisionEnabled`]
- A type and its family are picked separately: narrowing Sprite `Piece` never
  narrows its family `Pieces`. Use that for two picks of one type in one
  event, and refer to the name the caller narrowed (see [Functions](pitfalls/functions.md)). [manual:
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

## Triggers and Else

- One trigger per event, and one per branch of sub-events: no event above a
  trigger may hold another. A function and a custom action count as the
  trigger of their branch, so no trigger goes inside one: a function that
  starts a tween cannot hold the tween's *On finished*. That is a top-level
  event of its own, which calls the next function. Only an OR block lists
  several triggers. The editor refuses the whole project otherwise, with
  `cannot add another trigger to event branch`. [manual:
  project-primitives/events/how-events-work.md "Triggers", sub-events.md
  "Triggers in sub-events"; editor bundle `projectResources.js`, function
  blocks report a trigger; observed in a game project, 2026-09-17]
- *On collision with another object*, Timer *On timer* and the Gamepad
  button conditions are triggers to the editor, green arrow and every rule
  above, although the runtime tests them in sheet order each tick. The schema
  marks them `isTrigger` with `isFakeTrigger`. [Addon SDK guide
  defining-aces.md "isFakeTrigger"; schema: plugins/_common.json,
  behaviors/timer.json]
- A trigger, a loop, *Else*, *Trigger once* and the conditions that only pick
  (*Pick all*, *Pick by comparison*, *Pick last created*, *Pick
  nearest/furthest*, *Pick children*) cannot be inverted; "not on collision"
  is *Is overlapping* inverted. The schema says
  which: `isTrigger`, `isLooping`, `isInvertible: false`. [manual:
  project-primitives/events/conditions.md "Inverting conditions"; editor
  bundle, `condition not invertible`]
- *Trigger once* and *Every X seconds* do nothing useful under a trigger:
  they are tested only in the tick the trigger fires, and the editor does not
  offer them there. [Addon SDK guide defining-aces.md
  "isCompatibleWithTriggers"; schema: `isCompatibleWithTriggers: false`]
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
- Touch *On tap* skips a tap released within 666 ms and 25 px of the tap
  before it: that one fires *On double-tap* instead, and the tap after it is
  single again. A button on *On tap object* loses every second press of a
  player tapping fast. A button that counts every press reacts to *On touched
  object* (start), or also to *On double-tap object*. A tap is itself a
  release within 333 ms and 15 px of the touch start. [manual:
  plugin-reference/touch.md "On tap", "On double-tap"; runtime: exported
  c3runtime.js r503, `ShouldTriggerTap`; observed in a game project, r503
  preview, 2026-09-28: 7 mouse clicks 0.3 s apart on the button made 4
  pieces, 8 clicks 0.7 s apart made 8; on *On touched object* (start), 7
  clicks 0.3 s apart made 7]

## Topics

### Functions

Read [pitfalls/functions.md](pitfalls/functions.md) when the events define
or call a function or a custom action.

- Function locals are out of scope for the function block's own top-level actions.
- Without *Copy picked* a function runs with every object reset to all picked.
- With *Copy picked*, type and family picks are copied separately; logic on the caller's picks is a custom action.
- Parameters are bare identifiers in expressions: `OffsetX`, not `Functions.OffsetX`.

### Timer

Read [pitfalls/timer.md](pitfalls/timer.md) when the events use the Timer
behavior.

- *Start timer* on an existing tag restarts it; after *Stop* or a *Once* timer's end its expressions return 0.
- A timer is state you start and stop: list every transition before choosing it.
- A timer and a tween scheduled to end together end a tick apart.

### Wait and time scale

Read [pitfalls/wait-and-time-scale.md](pitfalls/wait-and-time-scale.md)
when the events use *Wait*, *Wait for previous actions*, time scale, or a
group turned off to pause.

- *Wait* does not stop a loop: the remaining iterations run on in the same tick.
- *Wait for previous actions* waits only for asynchronous actions.
- A *Wait* with *Use time scale* on never ends while the time scale is 0.
- *Wait 0* resumes at the start of the next tick, not at the end of the event or sheet; leave it out.
- Deactivating a group stops its events, not its behaviors, timers or tweens: it does not pause.
- A hit stop is *Set time scale* 0.1, *Wait*, *Set time scale* 1; a smooth ramp is a value tween.

### Expressions

Read [pitfalls/expressions.md](pitfalls/expressions.md) when writing
expressions or naming and placing variables.

- `Self` has no object in a System condition or action, and the editor refuses the project.
- A variable named like a system expression (`mid`, `left`, `max`) is read as the expression.
- Variable names ignore case and the nearest scope wins: a local `count` hides a global `COUNT`.
- `lerp(a, b, 0.1)` each tick depends on the framerate: write `lerp(a, b, 1 - f^dt)`.
- `lerp` needs no time of its own when the factor comes from the engine, such as a tween's value.
- `lerp` and `unlerp` do not clamp.
- `%` keeps the sign of the left operand: `-1 % 5` is `-1`.
- There is no null: what is missing reads as 0, so ask *Has key* or the size first.
- A local variable at sub-event level is visible to its siblings, not to the parent's own actions.
- *Set mesh point* in *Relative* mode adds to the current position, so a per-tick derivation accumulates.

### Coordinates and angles

Read [pitfalls/coordinates-and-angles.md](pitfalls/coordinates-and-angles.md)
when the events place, move or rotate objects or read the viewport.

- The origin (0, 0) is the top-left of the layout and Y grows downwards.
- Angles are degrees, 0 faces right, clockwise; compare them with `anglediff`, never `<`.
- A sprite is drawn facing right at angle 0: paint art facing right.
- A Bullet's angle of motion and the object's angle are two values; at speed 0 the first cannot be set.
- The origin is image point 0, at the centre by default, so a sprite at the layout's edge shows half.
- `ViewportLeft` and the rest take a layer; `LayoutWidth` and `ViewportWidth(layer)` differ.

### Animation

Read [pitfalls/animation.md](pitfalls/animation.md) when the events use
image points, animations or frames.

- Image point 0 is the origin; the first point added is 1, and `ImagePointCount` leaves out the origin.
- *Set animation* to the animation already playing does nothing.
- Frames used as looks rather than as an animation need the animation's *Speed* at 0.
- *Set frame* to a frame of another image size resizes the instance and swaps its collision polygon.

### Rendering

Read [pitfalls/rendering.md](pitfalls/rendering.md) when the events colour
or size Text, draw bars, Drawing Canvas polygons or blend modes.

- A Text object has no *Set color*; its colour is *Set font color*, or the project does not open.
- *Set width* stretches a Sprite, repeats a Tiled Background and stretches a 9-patch's middle.
- A bar grows from its origin: put the origin on the edge it grows from.
- Drawing Canvas *Fill polygon* draws nothing when two consecutive points coincide.
- A blend mode touches only the pixels under the object's own quad, and the layer needs *Force own texture*.
- A Text object draws only the lines that fit its height: size the box for the longest text.
- A single line taller than its Text box draws with the bottom of its glyphs cut off.
- *Move to top* leaves a hierarchy's children where they were: move each part.
- *Set color* multiplies: draw a tinted part white and keep highlights on an untinted child.

### Tween

Read [pitfalls/tween.md](pitfalls/tween.md) when a tween must drive
something Tween has no property for, when a tween's end starts the next
step, or when several animations share one property.

- A value tween read under *Is playing* drives what Tween cannot address, a full 360° turn included.
- *On finished* runs before *Destroy on complete* destroys the instance, and *On any finished* runs for that tween too.
- `Tween.Value(tag)` reads 0 once the tween ends: animate a channel as what is left of it, from the full amount to 0.
- A property tween adds each tick's change: a *Set* on that property while it plays is kept and the tween's rest lands on top; guard it with *NOT Is playing*.

### Creating objects

Read [pitfalls/creating-objects.md](pitfalls/creating-objects.md) when the
events create or spawn instances, or a Particles object spawns a Sprite.

- *Create object* picks only the new instance; reach it through a family with *Pick last created*.
- *Create object* runs once per event, however many instances are picked.
- A runtime-created instance copies an existing instance or template: keep one per object in a layout that never runs.
- A Particles object given a Sprite spawns real instances that are not the emitter's children.
- A created instance is found outside its own event only by UID, until the top-level event ends.

### Restarting a layout

Read [pitfalls/restarting-a-layout.md](pitfalls/restarting-a-layout.md)
when the events restart a layout or go to one, such as a new round.

- *Restart layout* and *Go to layout* keep every global variable and static local at its current value.

### Storage and preview

Read [pitfalls/storage-and-preview.md](pitfalls/storage-and-preview.md)
when the project saves data, has a loader layout, is exported for the web
or uses File System.

- *Preview* starts from the layout open in the editor, so a loader layout is skipped.
- Local Storage is keyed by the project's `uniqueId`, which a rewritten `project.c3proj` must keep.
- A web export looks for an update only when the page loads.
- File System writes only through a picker tag; the known folders exist only in desktop exports.
- No tag names the Construct project folder; saves go to `<current-app-data>`.
- In a browser File System needs desktop Chromium and a user input trigger, and a save picker erases the file.
- Android and iOS exports have no File System: save with Local Storage and hand files over with Share.
- A scripted drag in preview needs `pointerrawupdate` before each `pointermove`, in CSS pixels.

## Adding an entry

One bullet: fact, consequence, source. Manual wording beats an observation, an
observation beats intuition, intuition is not an entry. Would the agent get it
wrong without the line? If not, do not add it.

The bullet goes into the topic file of its group, and the group here gets
its conclusion as one line, in the same place in the order. Picking and
Triggers and Else take the whole bullet here. A fact that fits no group gets
a topic file of its own and a group here that says when to read it.
