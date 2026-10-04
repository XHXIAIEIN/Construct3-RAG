# Event Sheet Pitfalls

These are runtime facts that general programming intuition gets wrong.
Read them with [event-sheet-thinking.md](event-sheet-thinking.md) before
writing events. Every entry must end with its source: a manual page under
`Construct3-Manual/`, a schema file, an official example id, a page of the
community cheat sheet at fed-4.gitbook.io/c3-cheat-sheets, or an
observation in a game project with its date. If you edit
`eventSheets/*.json`, `layouts/*.json` or clipboard JSON by hand, read
[references/hand-editing-project-files.md](references/hand-editing-project-files.md)
first.

Each group lists one conclusion per pitfall. If the events touch what a
group names, open its topic file for the cases and the sources before
writing them.

## Topics

### Picking

If the events narrow instances through families, containers, hierarchy
children, overlap and collision tests, or sub-events that rely on the
parent's picks, read [pitfalls/picking.md](pitfalls/picking.md).

- An instance with collisions disabled fails every overlap and collision test, both ways. Use this for a dragged or tweening instance, not an `isMoving` flag.
- A Solid blocks while its behavior is enabled, so a door that only plays an open animation keeps blocking. Disable its Solid with *Set enabled*, or destroy it.
- The slot a dragged or tweening instance will land on reads empty until it lands. An event that fills empty slots on its own waits for it.
- A type and its family are picked separately, so narrowing `Piece` never narrows `Pieces`. Refer to the name the caller narrowed.
- Container members are created, destroyed and picked together. Hierarchy children are not picked with their parent. Use *Pick children*.
- Picking a family never picks a type's container. Pick the type from the family in a sub-event, `Enemy: Pick by unique ID Enemies.UID`, one per member type.
- *Pick children* picks only among the child type's current picks, which its container may have narrowed. Give the child type a family of its own with the one member and pick through it.
- *Pick parent* with *Own* looks one level up only. A grandparent needs *All*, or the event silently picks nothing.
- A Dictionary or JSON in a container gives each instance its own copy. Use it instead of a growing list of instance variables.
- Sub-events run after the parent's actions, so their conditions see what those actions changed.
- A hierarchy child can be on another layer than its parent and stay its child. So a lifted parent can be drawn above everything while its parts stay under an outline.
- `ChildCount`, *Compare child count* and *Has children* count children of every type. Count one type with *Pick children* plus `PickedCount`.
- A destroyed instance still counts in `Count` until the top-level event ends. Test "none left" in a top-level event of its own.
- A pick of no instance stops its event, *Pick all* included, so `PickedCount = 0` never holds below a pick of that type. Test "none left" with `Count = 0` in an event that does not pick the type.
- A destroyed child still counts as a child until the top-level event ends. Count from a later top-level event or with *Pick children* plus `PickedCount`.
- Turret *Add object to target* takes the whole type or family, whatever the event picked. To target only some instances, leave it out and run *Acquire target* on one picked instance.

### Triggers and Else

If the events use a trigger, a function or custom action, *Else*, an
inverted condition, *Trigger once*, *Every X seconds* or Touch taps, read
[pitfalls/triggers-and-else.md](pitfalls/triggers-and-else.md).

- An event or a branch of sub-events holds one trigger, and a function or custom action is the trigger of its branch. So a tween's *On finished* is a top-level event of its own that calls the next function. Only an OR block lists several triggers.
- The editor treats *On collision with another object*, Timer *On timer* and the Gamepad button conditions as triggers, with every rule above, but the runtime tests them in sheet order.
- A trigger, a loop, *Else*, *Trigger once* and the conditions that only pick cannot be inverted. For "not on collision", invert *Is overlapping*.
- *Trigger once* and *Every X seconds* do nothing useful under a trigger, and the editor does not offer them there.
- A trigger can fire with several instances picked, Timer *On timer* included. If a *Pick nearest* or a function call is written for one, add *For each* after the trigger.
- Else is decided per block, not per instance. Branch per instance with a second event and the inverted condition, or override a default.
- Else does not narrow. It cannot directly follow a trigger block, only a normal sub-event inside one.
- Touch *On tap* skips a tap within 666 ms and 25 px of the one before it, which fires *On double-tap*. A button that counts every press uses *On touched object* (start).

### Functions

If the events define or call a function or a custom action, read
[pitfalls/functions.md](pitfalls/functions.md).

- A function with a return type is the expression `Functions.MyFunction`; parentheses only carry parameters.
- Function locals are out of scope for the function block's own top-level actions.
- Without *Copy picked* a function runs with every object reset to all picked.
- With *Copy picked*, type and family picks are copied separately. Logic on the caller's picks is a custom action.
- A custom action runs once with all the caller's picks, and a System condition in it reads the first. If it decides per instance, put *For each* first.
- Parameters are bare identifiers in expressions: `OffsetX`, not `Functions.OffsetX`.
- A function without parameters is called without parentheses: `Functions.name`, not `Functions.name()`.

### Timer

If the events use the Timer behavior, read [pitfalls/timer.md](pitfalls/timer.md).

- *Start timer* on an existing tag restarts it. After *Stop* or a *Once* timer's end its expressions return 0.
- A timer is state you start and stop, so list every transition before choosing it.
- A timer and a tween scheduled to end together end a tick apart.

### Wait and time scale

If the events use *Wait*, *Wait for previous actions*, time scale, or a
group turned off to pause, read
[pitfalls/wait-and-time-scale.md](pitfalls/wait-and-time-scale.md).

- *Wait* does not stop a loop, so the remaining iterations run in the same tick.
- A *Wait* keeps the instances its event picked: *Wait 2 seconds* then *Destroy* destroys the instance that started it, with no UID stored.
- *Wait for previous actions* waits only for asynchronous actions.
- Of two overlapping *Wait* hit stops, the shorter ends both. Count the stops under way, and restore the time scale when the count is back to 0. A `wallclocktime` deadline runs on another clock than the *Wait* and leaves the game slowed.
- A hit stop slows tweens and `dt` too. If a tween must end on an audio beat, set its object's time scale to 1 and restore it in *On finished*. If a blend must keep real time, use `dt / timescale`.
- Scroll To *Shake* replaces the running shake and is scaled by the object's time scale. Call it only if the new magnitude is not smaller than the remaining one. To shake through a hit stop, set the camera object's time scale to 1.
- A *Wait* delays only the rest of its own block and its sub-events. Sibling events run at once.
- A *Wait* with *Use time scale* on never ends while the time scale is 0.
- *Wait 0* resumes at the start of the next tick, not at the end of the event or sheet. Leave it out unless a trigger fires before the tick applies what it reports.
- Deactivating a group stops its events, not its behaviors, timers or tweens, so it does not pause.
- A hit stop is *Set time scale* 0.1, *Wait*, *Set time scale* 1. A smooth ramp is a value tween.

### Expressions

If you write expressions or name and place variables, read
[pitfalls/expressions.md](pitfalls/expressions.md).

- `Self` has no object in a System condition or action, and the editor refuses the project.
- A variable or function parameter named like a system expression (`mid`, `left`, `max`, `round`) is read as the expression.
- Variable names ignore case and the nearest scope applies, so a local `count` hides a global `COUNT`.
- `lerp(a, b, 0.1)` each tick depends on the framerate. Write `lerp(a, b, 1 - f^dt)`.
- If the factor comes from the engine, such as a tween's value, `lerp` needs no time of its own.
- `lerp` and `unlerp` do not clamp.
- `%` keeps the sign of the left operand, so `-1 % 5` is `-1`.
- There is no null, and a missing value reads as 0. Ask *Has key* or the size first.
- JSON `Type(path)` is `"undefined"` for a missing path, so it can test presence inside an expression.
- *For* counts down when its end is below its start. Before `For 0 to count - 1`, test the count, or start ≤ end.
- A local variable at sub-event level is visible to its siblings, not to the parent's own actions.
- *Set mesh point* in *Relative* mode adds to the current position, so deriving it every tick accumulates.

### Coordinates and angles

If the events place, move or rotate objects or read the viewport, read
[pitfalls/coordinates-and-angles.md](pitfalls/coordinates-and-angles.md).

- The origin (0, 0) is the top-left of the layout and Y grows downwards.
- Angles are clockwise degrees from 0 facing right. Compare them with `anglediff`, never `<`.
- A sprite is drawn facing right at angle 0. Paint art facing right.
- A Bullet's angle of motion and the object's angle are two values. At speed 0 the first cannot be set.
- The origin is image point 0, at the centre by default, so a sprite at the layout's edge shows half.
- `ViewportLeft` and the rest take a layer. `LayoutWidth` and `ViewportWidth(layer)` differ.
- *Scale outer* keeps a parallax-0 HUD centred on the design area. Pin a screen-edge HUD with Anchor and stretch a backdrop to the screen with Anchor's left and right edges.
- Drag & Drop moves the instance only on pointer moves. Put a trailing or lifted look on a child.

### Input

If the events use Mouse and Touch together, tell a finger from a mouse,
hide what can be pressed, bind keys, steer a movement behavior, or ask the
browser for fullscreen, a permission or a picker, read
[pitfalls/input.md](pitfalls/input.md).

- Mouse ignores fingers. Tell a finger drag from a mouse drag by *Mouse button is down* per tick, not in *On drag start*.
- Touch with *Use mouse input* on fires for clicks too. Detect the input method with it off.
- Touch and Mouse press an object that is invisible or has collisions disabled. Add *Is visible* to the event or set its layer not interactive.
- Touch and Mouse pick every overlapping instance under the pointer. Add *Pick top/bottom* (top) under the trigger so only the front button reacts; a family for buttons of several types.
- *Simulate control* acts only in the tick it runs. Put it in an event whose condition stays true while the control is held: *Key is down*, not *On key pressed*.
- W, A, S and D alone do not fit an AZERTY keyboard. Give each direction its arrow key too.
- Until the player touches, clicks or presses a key, the browser refuses *Request fullscreen*, *Request permission*, *Request wake lock* and the other requests whose manual page asks for a user input trigger. Put them in an *On tap*, *On click* or *On key pressed* event.

### Audio

If the events play music from the first screen, schedule sounds, change
their rate, volume or effects, or keep music on a beat, read
[pitfalls/audio.md](pitfalls/audio.md).

- With *Use worker* on, scheduled sounds jitter by a message delay. For sample-accurate scheduling, set it to *No*.
- A sound not yet loaded plays late, and a Music file ignores its scheduled time. Keep beat-locked files in Sounds, preloaded.
- In a browser nothing is heard before the first touch, click or key. Open on a "tap anywhere to start" screen that goes to the game and put *Request fullscreen* on that tap. Music on that screen itself starts only at the tap.
- The audio clock does not run until the first release, click or key. Start music when `CurrentTime` moves, not on a touch.
- `PlaybackTime` of a scheduled sound runs ahead by its lead. Build a beat grid from `CurrentTime` and integer steps.
- *Set playback rate* changes every instance with the tag. Give each play a one-off tag.
- A sound uses the effect chain of its first tag. An action on `"a b"` acts on each tag.
- *Set effect parameter* cancels the ramp still running. Merge overlapping ducks into one release.
- Gain effect values are dB, ramped on the linear gain. Compressor parameters are fixed once added.
- An exponential ramp to 0 throws, also on the dry path of a 100 % mix. Ramp linearly or keep the value above 0.
- Delay `mix` is 0 to 100 and scales only the echoes: first echo = mix × feedback.
- *Fade volume* also reaches instances scheduled but not started, so fading a one-off tag to -100 dB cancels a play scheduled ahead.
- On resume every suspended sound restarts at once. Run *Stop all* in *On resumed* and restart the schedule.
- *Play by name* looks a sound up by its folder path, `Board/spawn`. Keep sounds played by computed names out of folders.
- Stereo pan mixes a stereo sound's channels, +2.3 dB at ±20. Narrow the pan of loud sounds and keep them off each other's grid point.
- Dictionary *Set key* ignores a missing key. Write with *Add key*.
- A sound is heard `OutputLatency` after its scheduled time.
- A WebM Opus file encoded to an exact length decodes to that length at 48 kHz in Chrome, and a mono file to one channel.

### Animation

If the events use image points, animations or frames, read
[pitfalls/animation.md](pitfalls/animation.md).

- Image point 0 is the origin. The first point added is 1, and `ImagePointCount` leaves out the origin.
- *Set animation* to the animation already playing does nothing.
- Frames used as looks rather than as an animation need the animation's *Speed* at 0.
- *Set frame* to a frame of another image size resizes the instance and swaps its collision polygon.

### Rendering

If the events colour or size Text, scale or scroll a Tiled Background's
image, or draw bars, Drawing Canvas polygons or blend modes, read
[pitfalls/rendering.md](pitfalls/rendering.md).

- A Text object has no *Set color*. Colour it with *Set font color*, or the project does not open.
- *Set width* stretches a Sprite, repeats a Tiled Background and stretches a 9-patch's middle.
- A Tiled Background's image scale is a percentage in events and a fraction in the layout file, so multiply the fraction by 100. A growing Y offset moves the image down, so scroll upward with a falling offset.
- A bar grows from its origin. Put the origin on the edge it grows from.
- Drawing Canvas *Fill polygon* with *Convex* off draws nothing when two consecutive points coincide. Repeat no point.
- A blend mode changes only the pixels under the object's own quad, and the layer needs *Force own texture*.
- A Text object draws only the lines that fit its height. Size the box for the longest text.
- A single line taller than its Text box draws with the bottom of its glyphs cut off.
- *Move to top* leaves a hierarchy's children where they were. Move each part.
- *Set color* multiplies. Draw a tinted part white and keep highlights on an untinted child.
- Changing a Text's font size redraws and re-uploads its texture. Animate position, angle or opacity, or use a Sprite Font and tween its scale.
- A Sprite Font draws whole cells and tints its outline with its colour. Draw glyphs left in the cell, one image per colour, in a box sized for the largest scale.

### Tween

If a tween must drive something Tween has no property for, if a tween's
end starts the next step, or if several animations share one property,
read [pitfalls/tween.md](pitfalls/tween.md).

- A value tween read under *Is playing* drives what Tween cannot address, a full 360° turn included.
- *On finished* runs before *Destroy on complete* destroys the instance, and *On any finished* runs for that tween too.
- A new tween on a property stops the ones already on it, so they never finish or destroy. Let a Timer destroy a dying instance, not its death tween.
- `Tween.Value(tag)` reads 0 once the tween ends. Animate a channel as what is left of it, from the full amount to 0.
- *Stop* releases a tween at the end of the tick. `Value(tag)` reads the stopped value until then.
- A property tween adds each tick's change. A *Set* on that property while it plays is kept, and the tween's rest adds to it. Guard it with *NOT Is playing*.

### Timeline

If the events play a timeline on instances created at runtime, layer
several timelines on one instance, or control a timeline by tags,
keyframes or playback rate, read [pitfalls/timeline.md](pitfalls/timeline.md).

- A relative track adds each tick's step from 0, so keyframe values are offsets from the pose at play start. Moves that start and end at 0 layer and repeat with no offset left.
- *Set instance* covers the next *Play* only, and one *Play* starts a copy per picked instance with the same tags. Set one instance at a time and tag each copy with its UID.
- A copy is found by the timeline's name inside the copy's name, so keep no timeline name inside another's.
- *Stop* rewinds to 0 and takes a relative track's offsets back, and *Pause* holds. A finished timeline ignores both *Stop* and *Resume* and keeps its offsets. *Set time* 0 before replaying or putting the instance back.
- *Set time* pauses and never fires *On keyframe reached*.
- *On keyframe reached* picks nothing. Pick the instance back from the UID in `Timeline.TimelineTags`.
- A negative playback rate fires *On keyframe reached* again for each keyframe it passes on the way back. Flag the rewind and test the flag in the keyframe event.
- *On keyframe reached* sees the previous tick's pose, so *Wait 0* before reading where the keyframe put the instance.
- A negative playback rate rewinds to 0 and finishes there. Set it positive again before the next *Resume*.
- A timeline stopped at its end ignores *Resume* at any rate. *Set time* just before the end, then rewind.
- A copy started this tick reads `Time` 0 while *Is playing* is true. Test *Is playing* to know a move is under way.
- Rewinding a copy that reads `Time` 0 starts it backwards from its end and leaves a relative track off by its end pose. Rewind only when `Time > 0`, else *Set time* 0.
- With *Use system timescale* on, the default, a hit stop slows the timeline too.

### Creating objects

If the events create or spawn instances, or a Particles object spawns a
Sprite, read [pitfalls/creating-objects.md](pitfalls/creating-objects.md).

- *Create object* picks the new instance in its type, not in its families, so a family action after it moves every other instance. Reach it through the family with *Pick last created*.
- A part in both the parent's container and its template hierarchy is created once. Put it in both to have it picked with the parent and follow it.
- *Create object* runs once per event, however many instances are picked.
- A runtime-created instance copies an existing instance or template, and without one its behavior properties read 0. Keep one per object in a layout that never runs.
- A Particles object given a Sprite spawns real instances that are not the emitter's children.
- A created instance is found outside its own event only by UID, until the top-level event ends.

### Restarting a layout

If the events restart a layout or go to one, such as a new round, read
[pitfalls/restarting-a-layout.md](pitfalls/restarting-a-layout.md).

- *Restart layout* and *Go to layout* keep every global variable and static local at its current value.

### Storage and export

If the project saves data, is exported for the web or uses File System,
read [pitfalls/storage-and-export.md](pitfalls/storage-and-export.md).

- A web export looks for an update only when the page loads.
- The Browser object holds back the browser's install banner. Offer installing with *Request install* after *On install available*.
- File System writes only through a picker tag. The known folders exist only in desktop exports.
- No tag names the Construct project folder. Save to `<current-app-data>`.
- In a browser File System needs desktop Chromium and a user input trigger, and a save picker erases the file.
- Android and iOS exports have no File System. Save with Local Storage and hand files over with Share.

## Adding an entry

A pitfall is a runtime behaviour of events that changes which events an
agent writes. Without the line, the agent would write them wrong. A
lesson that does not change the events goes elsewhere:

- How a project file is written: [references/hand-editing-project-files.md](references/hand-editing-project-files.md),
  or a rule of the `construct3-agent-plugin` skill's checker if a script can
  test it.
- What the editor, the preview or a script driving them does: the
  `construct3-agent-plugin` skill's references, such as [editor-and-preview.md](../skills/construct3-agent-plugin/references/editor-and-preview.md).
- How a change is checked by playing it, the cases, the scene and what to
  read: [verifying-a-change.md](../skills/construct3-agent-plugin/references/verifying-a-change.md).
- How the game looks, its art and its colours: [references/new-project.md](references/new-project.md),
  or the look documents listed in the root `AGENTS.md`.

An entry is a fact, its consequence and its source. Manual wording
outranks an observation, which outranks intuition. Intuition is not an
entry.

The entry goes into the topic file of its group, and the group here gets
its conclusion as one line, in the same place in the order. A conclusion
keeps the fix, not only the prohibition. A fact that fits no group gets a
topic file of its own and a group here that says when to read it.
