# Event Sheet Pitfalls

Runtime facts that general programming intuition gets wrong. Read with
[event-sheet-thinking.md](event-sheet-thinking.md) before writing events. Each
bullet ends with its source: a manual page under `Construct3-Manual/`, a schema
file, an official example id, a page of the community cheat sheet at
fed-4.gitbook.io/c3-cheat-sheets, or an observation in a game project with its date. No
source, no entry. Editing `eventSheets/*.json`, `layouts/*.json` or clipboard JSON by hand?
Read [references/hand-editing-project-files.md](references/hand-editing-project-files.md)
first.

Each group is one line per pitfall, its conclusion. When the events touch
what a group names, open its topic file for the cases and the sources before
writing them.

## Topics

### Picking

Read [pitfalls/picking.md](pitfalls/picking.md) when the events narrow
instances: families, containers, hierarchy children, overlap and collision
tests, or sub-events that rely on the parent's picks.

- Collisions disabled fails every overlap and collision test; use it instead of an `isMoving` flag.
- A type and its family are picked separately: narrowing one never narrows the other.
- Container members are created, destroyed and picked together; hierarchy children need *Pick children*.
- Picking a family never picks a type's container: pick the type by `UID` in a sub-event first.
- *Pick children* picks only among the child type's current picks, which its container may have narrowed; pick through a one-member family.
- A Dictionary or JSON in a container gives each instance its own copy.
- Sub-events run after the parent's actions and see what they changed.
- A hierarchy child may sit on another layer than its parent and stays its child.
- `ChildCount`, *Compare child count* and *Has children* count children of every type.
- A destroyed child still counts as a child until the top-level event ends.

### Triggers and Else

Read [pitfalls/triggers-and-else.md](pitfalls/triggers-and-else.md) when
the events use a trigger, a function or custom action, *Else*, an inverted
condition, *Trigger once*, *Every X seconds* or Touch taps.

- One trigger per branch of events, and a function or custom action is its branch's trigger; the editor refuses the project otherwise.
- *On collision*, Timer *On timer* and Gamepad buttons are triggers to the editor, although tested every tick.
- Triggers, loops, *Else*, *Trigger once* and the conditions that only pick cannot be inverted.
- *Trigger once* and *Every X seconds* do nothing useful under a trigger.
- A trigger can fire with several instances picked: add *For each* after it.
- *Else* runs only if the previous sibling ran for no instance; it does not branch per instance.
- *Else* does not narrow, and cannot directly follow a trigger block.
- Touch *On tap* skips a fast second tap, which fires *On double-tap*; a button that counts presses uses *On touched object*.

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

### Tween

Read [pitfalls/tween.md](pitfalls/tween.md) when a tween must drive
something Tween has no property for, when a tween's end starts the next
step, or when several animations share one property.

- A value tween read under *Is playing* drives what Tween cannot address, a full 360° turn included.
- *On finished* runs before *Destroy on complete* destroys the instance, and *On any finished* runs for that tween too.
- `Tween.Value(tag)` reads 0 once the tween ends: animate a channel as what is left of it, from the full amount to 0.

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

## Adding an entry

One bullet: fact, consequence, source. Manual wording beats an observation, an
observation beats intuition, intuition is not an entry. Would the agent get it
wrong without the line? If not, do not add it.

The bullet goes into the topic file of its group, and the group here gets
its conclusion as one line, in the same place in the order. A fact that
fits no group gets a topic file of its own and a group here that says when
to read it.
