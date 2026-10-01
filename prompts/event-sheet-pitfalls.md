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
what a group names, open its topic file for the cases and the sources
before writing them.

## Topics

### Picking

Read [pitfalls/picking.md](pitfalls/picking.md) when the events narrow
instances: families, containers, hierarchy children, overlap and collision
tests, or sub-events that rely on the parent's picks.

- Collisions disabled fails every overlap and collision test in both directions: use it to take a dragged or tweening instance out of the world, not an `isMoving` flag.
- The slot a dragged or tweening instance will land on reads empty until it lands: an event that fills empty slots on its own waits for it.
- A type and its family are picked separately: narrowing `Piece` never narrows `Pieces`; refer to the name the caller narrowed.
- Container members are created, destroyed and picked together; hierarchy children are not picked with their parent: use *Pick children*.
- Picking a family never picks a type's container: pick the type from the family in a sub-event, `Enemy: Pick by unique ID Enemies.UID`, one per member type.
- *Pick children* picks only among the child type's current picks, which its container may have narrowed: give the child type a family of its own with the one member, and pick through it.
- *Pick parent* with *Own* looks one level up only: a grandparent needs *All*, or the event silently picks nothing.
- A Dictionary or JSON in a container gives each instance its own copy: use it instead of a growing list of instance variables.
- Sub-events run after the parent's actions, so their conditions see what those actions changed.
- A hierarchy child may sit on another layer than its parent and stays its child: a lifted parent can be drawn above everything while its parts stay under an outline.
- `ChildCount`, *Compare child count* and *Has children* count children of every type: count the type you mean with *Pick children* plus `PickedCount`.
- A destroyed child still counts as a child until the top-level event ends: count from a later top-level event, or with *Pick children* plus `PickedCount`.

### Triggers and Else

Read [pitfalls/triggers-and-else.md](pitfalls/triggers-and-else.md) when
the events use a trigger, a function or custom action, *Else*, an inverted
condition, *Trigger once*, *Every X seconds* or Touch taps.

- One trigger per event and per branch of sub-events, and a function or custom action is the trigger of its branch: a tween's *On finished* is a top-level event of its own that calls the next function. Only an OR block lists several triggers.
- *On collision with another object*, Timer *On timer* and the Gamepad button conditions are triggers to the editor, with every rule above, though the runtime tests them in sheet order.
- A trigger, a loop, *Else*, *Trigger once* and the conditions that only pick cannot be inverted: "not on collision" is *Is overlapping* inverted.
- *Trigger once* and *Every X seconds* do nothing useful under a trigger, and the editor does not offer them there.
- A trigger can fire with several instances picked, Timer *On timer* included: add *For each* after it when a *Pick nearest* or a function call is written for one.
- Else is decided per block, not per instance: branch per instance with a second event and the inverted condition, or default then override.
- Else does not narrow, and cannot directly follow a trigger block, only a normal sub-event inside one.
- Touch *On tap* skips a tap within 666 ms and 25 px of the one before it, which fires *On double-tap*: a button that counts every press uses *On touched object* (start).

### Functions

Read [pitfalls/functions.md](pitfalls/functions.md) when the events define
or call a function or a custom action.

- Function locals are out of scope for the function block's own top-level actions.
- Without *Copy picked* a function runs with every object reset to all picked.
- With *Copy picked*, type and family picks are copied separately; logic on the caller's picks is a custom action.
- A custom action runs once with all the caller's picks: a System condition in it reads the first, so put *For each* first when it decides per instance.
- Parameters are bare identifiers in expressions: `OffsetX`, not `Functions.OffsetX`.
- A function without parameters is called without parentheses: `Functions.name`, not `Functions.name()`.

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
- A *Wait* holds back only the rest of its own block and its sub-events; sibling events run at once.
- A *Wait* with *Use time scale* on never ends while the time scale is 0.
- *Wait 0* resumes at the start of the next tick, not at the end of the event or sheet; leave it out, unless a trigger fires before the tick applies what it reports.
- Deactivating a group stops its events, not its behaviors, timers or tweens: it does not pause.
- A hit stop is *Set time scale* 0.1, *Wait*, *Set time scale* 1; a smooth ramp is a value tween.

### Expressions

Read [pitfalls/expressions.md](pitfalls/expressions.md) when writing
expressions or naming and placing variables.

- `Self` has no object in a System condition or action, and the editor refuses the project.
- A variable or function parameter named like a system expression (`mid`, `left`, `max`, `round`) is read as the expression.
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
- *Scale outer* keeps a parallax-0 HUD centred on the design area: pin screen-edge HUD with Anchor, and stretch a backdrop to the screen with Anchor's left and right edges.
- Drag & Drop moves the instance only on pointer moves: put a trailing or lifted look on a child.

### Input

Read [pitfalls/input.md](pitfalls/input.md) when the events use Mouse and
Touch together, or must tell a finger from a mouse.

- Mouse ignores fingers: tell a finger drag from a mouse drag by *Mouse button is down* per tick, not in *On drag start*.
- Touch with *Use mouse input* on fires for clicks too: detect the input method with it off.

### Audio

Read [pitfalls/audio.md](pitfalls/audio.md) when the events schedule
sounds, change their rate, volume or effects, or keep music on a beat.

- With *Use worker* on, scheduled sounds jitter by a message delay: set it to *No* for sample-accurate scheduling.
- The audio clock stands still until the first release, click or key: start music when `CurrentTime` moves, not on a touch.
- `PlaybackTime` of a scheduled sound runs ahead by its lead: build a beat grid from `CurrentTime` and integer steps.
- *Set playback rate* retunes every instance with the tag: give each play a one-off tag.
- A sound uses the effect chain of its first tag; an action on `"a b"` acts on each tag.
- *Set effect parameter* cancels the ramp still running: merge overlapping ducks into one release.
- Gain effect values are dB ramped linearly; compressor parameters cannot change after it is added.
- Delay `mix` is 0 to 100 and scales only the echoes: first echo = mix × feedback.
- *Fade volume* also reaches instances scheduled but not started.
- On resume every suspended sound restarts at once: *Stop all* in *On resumed* and restart the schedule.
- Stereo pan folds a stereo sound's channels, +2.3 dB at ±20: narrow the pan of loud sounds and keep them off each other's grid point.
- Dictionary *Set key* ignores a missing key: write with *Add key*.
- A sound is heard `OutputLatency` after its scheduled time.
- A WebM Opus file encoded to an exact length decodes to that length at 48 kHz in Chrome.

### Animation

Read [pitfalls/animation.md](pitfalls/animation.md) when the events use
image points, animations or frames.

- Image point 0 is the origin; the first point added is 1, and `ImagePointCount` leaves out the origin.
- *Set animation* to the animation already playing does nothing.
- Frames used as looks rather than as an animation need the animation's *Speed* at 0.
- *Set frame* to a frame of another image size resizes the instance and swaps its collision polygon.

### Rendering

Read [pitfalls/rendering.md](pitfalls/rendering.md) when the events colour
or size Text, scale or scroll a Tiled Background's image, draw bars,
Drawing Canvas polygons or blend modes.

- A Text object has no *Set color*; its colour is *Set font color*, or the project does not open.
- *Set width* stretches a Sprite, repeats a Tiled Background and stretches a 9-patch's middle.
- A Tiled Background's image scale is a percentage in events and a fraction in the layout file, and a growing Y offset moves the image down: multiply the fraction by 100, and scroll upward with a falling offset.
- A bar grows from its origin: put the origin on the edge it grows from.
- Drawing Canvas *Fill polygon* draws nothing when two consecutive points coincide.
- A blend mode touches only the pixels under the object's own quad, and the layer needs *Force own texture*.
- A Text object draws only the lines that fit its height: size the box for the longest text.
- A single line taller than its Text box draws with the bottom of its glyphs cut off.
- *Move to top* leaves a hierarchy's children where they were: move each part.
- *Set color* multiplies: draw a tinted part white and keep highlights on an untinted child.
- Changing a Text's font size redraws and re-uploads its texture: animate position, angle or opacity, or use a Sprite Font and tween its scale.
- A Sprite Font draws whole cells and tints its outline with its colour: draw glyphs left in the cell, one image per colour, a box that fits the largest scale.

### Tween

Read [pitfalls/tween.md](pitfalls/tween.md) when a tween must drive
something Tween has no property for, when a tween's end starts the next
step, or when several animations share one property.

- A value tween read under *Is playing* drives what Tween cannot address, a full 360° turn included.
- *On finished* runs before *Destroy on complete* destroys the instance, and *On any finished* runs for that tween too.
- A new tween on a property stops the ones already on it, which then never finish or destroy: let a Timer destroy a dying instance, not its death tween.
- `Tween.Value(tag)` reads 0 once the tween ends: animate a channel as what is left of it, from the full amount to 0.
- *Stop* releases a tween at the end of the tick: `Value(tag)` reads the stopped value until then.
- A property tween adds each tick's change: a *Set* on that property while it plays is kept and the tween's rest lands on top; guard it with *NOT Is playing*.

### Timeline

Read [pitfalls/timeline.md](pitfalls/timeline.md) when the events play a
timeline on instances created at runtime, layer several timelines on one
instance, or control a timeline by tags, keyframes or playback rate.

- A relative track adds each tick's step from 0: keyframe values are offsets from the pose at play start, so moves that start and end at 0 layer and repeat without drifting.
- *Set instance* covers the next *Play* only and one *Play* starts a copy per picked instance with the same tags: set one instance at a time and tag each copy with its UID.
- A copy is found by the timeline's name contained in the copy's name: keep no timeline name inside another's.
- *Stop* rewinds to 0, *Pause* holds, and a finished timeline ignores both *Stop* and *Resume*: *Set time* 0 before replaying.
- *Stop* leaves a relative track's offset on the instance: *Set time* 0, then *Stop*, to take it back.
- *Set time* pauses and never fires *On keyframe reached*.
- *On keyframe reached* picks nothing: pick the instance back from the UID in `Timeline.TimelineTags`.
- *On keyframe reached* sees the previous tick's pose: *Wait 0* before reading where the keyframe put the instance.
- A negative playback rate rewinds to 0 and finishes there; set it positive again before the next *Resume*.
- A timeline stopped at its end ignores *Resume* at any rate: *Set time* just before the end, then rewind.
- A copy started this tick reads `Time` 0 while *Is playing* is true: test *Is playing* to know a move is under way.
- With *Use system timescale* on, the default, a hit stop slows the timeline too.

### Creating objects

Read [pitfalls/creating-objects.md](pitfalls/creating-objects.md) when the
events create or spawn instances, or a Particles object spawns a Sprite.

- *Create object* picks only the new instance; reach it through a family with *Pick last created*.
- A part in both the parent's container and its template hierarchy is created once: put it in both to have it picked with the parent and follow it.
- *Create object* runs once per event, however many instances are picked.
- A runtime-created instance copies an existing instance or template: keep one per object in a layout that never runs.
- A Particles object given a Sprite spawns real instances that are not the emitter's children.
- A created instance is found outside its own event only by UID, until the top-level event ends.

### Restarting a layout

Read [pitfalls/restarting-a-layout.md](pitfalls/restarting-a-layout.md)
when the events restart a layout or go to one, such as a new round.

- *Restart layout* and *Go to layout* keep every global variable and static local at its current value.

### Storage and export

Read [pitfalls/storage-and-export.md](pitfalls/storage-and-export.md)
when the project saves data, is exported for the web or uses File System.

- A web export looks for an update only when the page loads.
- File System writes only through a picker tag; the known folders exist only in desktop exports.
- No tag names the Construct project folder; saves go to `<current-app-data>`.
- In a browser File System needs desktop Chromium and a user input trigger, and a save picker erases the file.
- Android and iOS exports have no File System: save with Local Storage and hand files over with Share.

## Adding an entry

A pitfall is a runtime behaviour of events that changes which events an
agent writes: without the line, the agent would write them wrong. A lesson
that does not change the events goes elsewhere:

- How a project file is written: [references/hand-editing-project-files.md](references/hand-editing-project-files.md),
  or a rule of the `construct3-project` skill's checker when a script can
  test it.
- What the editor, the preview or a script driving them does: the
  `construct3-project` skill's references, such as [editor-and-preview.md](../skills/construct3-project/references/editor-and-preview.md).
- How the game looks, its art and its colours: [references/new-project.md](references/new-project.md),
  or the look documents listed in the root `AGENTS.md`.

One bullet: fact, consequence, source. Manual wording beats an observation, an
observation beats intuition, intuition is not an entry.

The bullet goes into the topic file of its group, and the group here gets
its conclusion as one line, in the same place in the order. A conclusion
keeps the fix, not only the prohibition. A fact that fits no group gets a
topic file of its own and a group here that says when to read it.
