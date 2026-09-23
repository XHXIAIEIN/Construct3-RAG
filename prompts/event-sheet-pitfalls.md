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
  observed: mergeGame, 2026-09-17]
- Sub-events run after the parent's actions, so a change made there (collisions
  re-enabled) is visible to the sub-event's conditions. [manual:
  project-primitives/events/sub-events.md]

- Hierarchy children may live on a different layer than their parent; the
  connection is per instance, not per layer. A child on a lower layer stays
  a child, so a lifted parent can be drawn above everything while its parts
  stay under an outline. [releases: beta.json, "hierarchy information not
  duplicated properly if connections were setup between instances in
  different layers"; observed: WaterSort, 2026-09-17, unverified at runtime]
- *ChildCount*, *Compare child count* and *Has children* count every attached
  child whatever its type. A second child type on the same parent (a Stream
  added to the pouring Tube) shifts every count that meant one type. Get the
  top index from *Pick children* plus *Pick highest* on that type, or count in
  a *For each* over the picked children. [manual:
  plugin-reference/common-features/common-expressions.md "ChildCount",
  common-conditions.md "Compare child count"; observed: WaterSort, 2026-09-17]
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
  observed: WaterSort, 2026-09-17]

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
  blocks report a trigger; observed: Water Sort (DeepSeek), 2026-09-17]
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
  observed: mergeGame, 2026-09-17]
- Parameters are bare identifiers in expressions: `Self.X + OffsetX`, not
  `Functions.OffsetX` or `Self.OffsetX`. [example: 3d-castle-maze, function
  OffsetHand]

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
  instance whose tween it is. [observed: WaterSort, 2026-09-18]

## Wait and time scale

- *Wait* does not stop a loop: the remaining iterations run on in the same
  tick, and the actions after the *Wait* run later, once per iteration, with
  that iteration's picked instances. A staggered effect is `Wait 0.1 *
  loopindex`; a loop that must pause between iterations is a Timer or a
  function called from *On timer*. [manual:
  system-reference/system-actions.md "Wait"; examples: arcade-shooter,
  layout-transition]
- *Wait for previous actions* (the manual's "Wait for previous actions to
  complete") waits only for asynchronous actions, marked with an icon in the
  editor: Tween actions, AJAX requests, Local Storage, *Snapshot canvas*.
  Anything else before it is already done.
  A function call counts only when the function is marked *Asynchronous* and
  itself ends with *Wait for previous actions*. [manual:
  system-reference/system-actions.md "Wait for previous actions to complete",
  project-primitives/events/functions.md "Asynchronous functions"; example:
  avalanche, sheets Stalagmite and Credits]
- A *Wait* with *Use time scale* on never ends while the time scale is 0.
  The wait that resumes the game, and the UI tweens shown while paused, run
  on their own clock: *Use time scale* off, *Set object time scale* 1 on the
  fader, the buttons and the manager object. [manual:
  system-reference/system-actions.md "Wait", "Set object time scale";
  example: airborne-explorer, In-Game Menu]
- Deactivating a group stops its events, including its triggers, and
  nothing else: behaviors, timers and tweens started by it keep running. It
  turns a phase off; it does not pause. [manual:
  system-reference/system-actions.md "Set group active"; examples: every
  pause is *Set time scale* 0]
- A hit stop is *Set time scale* 0.1, *Wait*, *Set time scale* 1 in one
  block; a smooth ramp is a *Tween (value)* on any object read into *Set
  time scale* while *Is playing*. [examples: segmented-boss-fight BossHeath;
  samuroof Credits `Camera.Tween.Value("TimeScaleChange")`; eventide
  `1 - PauseUI.Tween.Progress("ShowPause")`]

## Expressions

- `Self` is the object of the condition or action the expression sits in. In
  a System condition or action, *For each ordered* included, there is no such
  object and the editor refuses to open the project: `Invalid use of 'self'`.
  Write the object: order *For each SnakeBody* by `SnakeBody.IID`, not
  `Self.IID`. [editor bundle `projectResources.js`, `.invalid-self`;
  observed: Doubao snake project, 2026-09-22]
- `lerp(Self.X, Target.X, 0.1)` moves a different fraction per second at
  different framerates and ignores the time scale. When the third argument is a
  constant and the first is last tick's result, write `lerp(a, b, 1 - f^dt)`
  with `f` in (0, 1); `f * dt` is the common approximation and is not
  exact. The same holds for `anglelerp`.
  [manual: system-reference/system-expressions.md "dt", linking the
  delta-time tutorial, section "Lerp"; examples: magic-feather, surface-jump]
- `lerp` needs no time of its own when the factor comes from the engine:
  `Self.Tween.Value("Attack")` in labyrinth, a timeline value, `unlerp` of a
  slider thumb, `Car.Speed / Car.MaxSpeed` in abductractor. Those are
  mappings, not tweens, and there is nothing to replace. [examples: labyrinth,
  abductractor]
- `lerp` and `unlerp` do not clamp: `lerp(0, 100, 1.5)` is 150, and `unlerp`
  of a value outside its range goes past 0 or 1. Remap with
  `lerp(lo, hi, unlerp(a, b, v))` and wrap it in `clamp` when `v` can leave
  `[a, b]`. [manual: system-reference/system-expressions.md "lerp", "unlerp",
  "clamp"; cheat sheet "Useful expressions and formulas", Remapping a range]
- `%` is the remainder and keeps the sign of the left operand, so `-1 % 5` is
  `-1`. An index that steps backwards wraps with `(n % max + max) % max`.
  [manual: project-primitives/events/expressions.md "%"; cheat sheet "Useful
  expressions and formulas", Wrapping around a number]
- There is no null or undefined: an expression is a number or a text, and
  what is missing reads as the number 0. `Array.At` outside the array,
  `Dictionary.Get` of a key that is not there, `Functions.ReturnValue` when
  nothing set it and a Timer's `CurrentTime` after a one-off timer fired all
  give 0, `Array.IndexOf` gives -1, `int("33xx")` is 33 and `int("xx33")` is
  0. So `= 0` cannot tell an empty slot from a missing one: ask *Has key*,
  *Contains value* or `Array.Width` first, or `Dictionary.GetDefault(key,
  fallback)`. [manual: plugin-reference/array.md "At", "IndexOf";
  plugin-reference/dictionary.md "Get", "GetDefault", "Has key";
  plugin-reference/function.md "ReturnValue"; behavior-reference/timer.md
  "CurrentTime"; system-reference/system-expressions.md "int", "float"]

- A local variable placed as a sub-event or in a group is visible to every
  event at its level, whichever comes first, and to their sub-events; not to
  the parent's own actions. Set it in a sibling block with no conditions,
  then read it in the others; it resets to its initial value every time the
  scope is entered unless static. [manual:
  project-primitives/events/variables.md "Local variables", "Static and
  constant variables"; example: galactic-blocks, group Controls, `StoredY`]
- *Set mesh point* in *Relative* mode adds to the point's current position,
  not to its default, so a per-tick derivation accumulates. Derive with
  *Absolute* and normalised coordinates (0..1 across the object box, which may
  be exceeded); texture -1 leaves the texture position alone. [manual:
  plugin-reference/common-features/common-actions.md "Set mesh point"]

## Coordinates and angles

- The origin (0, 0) is the top-left of the layout and Y grows downwards:
  up is `Y - n`, gravity pulls towards +Y, and the top of the screen is the
  smallest Y. [manual: tips-and-guides/common-conventions.md "Units"]
- Angles are degrees, 0 faces right and they increase clockwise, so 90 points
  down, 180 left and 270 (or -90) up; 360 is 0 again, so a bullet fired at
  360 goes right, and `random(360)` is a full turn. `sin`, `cos` and `angle`
  take and return degrees. Some expressions return -180..180 and others
  0..360: compare angles with `anglediff`, *Is between angles* or *Is
  clockwise from*, never with `<`, and normalise with `(a + 360) % 360` only
  where a value must land in 0..360. [manual:
  tips-and-guides/common-conventions.md "Units";
  system-reference/system-expressions.md "Math";
  system-reference/system-conditions.md "Is between angles"]
- A sprite is drawn facing right at angle 0. Art painted pointing up appears
  turned a quarter clockwise the moment *Set angle towards position* runs:
  paint it facing right, or add the same 90 in every *Set angle*, never a
  correction per event. [consequence of the same convention; Rotate's speed
  is positive clockwise: manual behavior-reference/rotate.md "Speed"]
- A Bullet's angle of motion and the object's angle are two values; they
  move together only while the behavior's *Set angle* property is on, and
  8 Direction and Car have the same property. At speed 0 the angle of motion
  is 0 and cannot be set: set the speed first, then the angle. [manual:
  behavior-reference/bullet.md "Set angle", "Set angle of motion",
  "AngleOfMotion"; behavior-reference/8-direction.md "Set angle"]
- The origin is image point 0 and the point X, Y and rotation refer to; the
  editor puts it at the centre (`originX`, `originY` 0.5 in the layout
  file), so a sprite at the layout's edge shows half. Position by an image
  point (*Spawn another object* takes one) for a muzzle or a hinge, and move
  the origin in the image editor, not by an offset in events. [manual:
  interface/animations-editor.md "Image points"; official example layouts]
- `ViewportLeft`, `ViewportWidth` and the rest take a layer, since a
  parallaxed or scaled layer sees a different rectangle: write
  `ViewportLeft("HUD")`. `LayoutWidth` is the whole layout,
  `ViewportWidth(layer)` the part on screen in layout coordinates, and
  `OriginalViewportWidth` the project's *Viewport size* property. [manual:
  system-reference/system-expressions.md "Viewport", "Layout";
  plugins/system.json: every `Viewport*` expression has a `layer` parameter]

## Animation

- *Set animation* to the animation already playing does nothing, even when
  set to play from the beginning. An `anim` variable compared before every
  *Set animation*, to keep the animation from restarting, guards against
  nothing: set the animation from the state in one event, and *Start
  animation* from the beginning when a restart is wanted. [manual:
  plugin-reference/sprite.md "Set animation"; observed: RaftSurvivor,
  2026-09-22]

## Rendering

- *Set width* stretches a Sprite's whole image, repeats a Tiled Background's,
  and on a 9-patch stretches or tiles the middle while the corners keep their
  size. A bar with a painted fill is therefore a Tiled Background, which
  shows a cut of the painting below its own width, and a bar with caps is a
  9-patch, whose width must stay positive. [manual:
  plugin-reference/tiled-background.md "display an image in a repeating
  pattern"; plugin-reference/9-patch.md "a Sprite object, which just stretches
  its entire image", "useful for representing things like progress bars";
  reference: references/progress-bars.md]
- A bar grows from its origin. Every filling bar in the examples has its
  origin on the edge it grows from, (0, 0) or (0, 0.5); a cover that hides
  from the right has (1, 0.5); a 0.5 origin grows both ways from the middle.
  [examples: berry-harvester ProgressBar, jetpack FuelBar, flatland-golf
  PowerBarCover, test-your-might MightLevelBar (0.5, 1)]

- A blend mode such as *Destination in* only touches the pixels under the
  object's own quad: a mask sprite the size of the shape it reveals leaves
  everything outside its bounding box untouched, and the layer needs *Force
  own texture* or the blend hits the whole screen. Size the mask to cover
  everything it must erase, or keep the content inside its box. [manual:
  project-primitives/layers.md "Force own texture"; example:
  mask-effect-puzzle, layer HiddenWorld; observed: WaterSort, 2026-09-17]
- A Text object wraps at its own width and draws only the lines that fit its
  height. Text longer than the box sized for the placeholder gains a line
  that is cut off, and with centre or bottom vertical alignment the lines
  already shown move up as it does. Size the box for the longest text at the
  font size and line height, or after *Set text* resize it from
  `Self.TextHeight` plus a margin, with the width fixed: `TextWidth` and
  `TextHeight` measure the text as wrapped inside the current box, so
  `TextWidth` never grows the box past its width. Both are current in the
  action right after *Set text*. Check what else moves the lines before
  choosing the size:
  - Origin: a resize keeps the origin still and grows the box away from it.
    With a top origin the first line stays put; with a centre origin the
    box grows both ways and the first line moves even under top alignment.
    Put the origin on the edge the text must keep, as a bar keeps the edge
    it grows from.
  - Wrapping: *Word* breaks only at spaces and hyphens, so Chinese,
    Japanese or Korean text needs *CJK*, which breaks between characters
    and wraps CJK punctuation properly. The same string takes a
    different number of lines under each mode; size for the mode set.
  - Direction and horizontal alignment decide the edge a line starts from:
    an RTL or right-aligned text widened with a left origin moves.
    [inference from the manual's property descriptions, unverified at
    runtime]

  [manual: plugin-reference/text.md "Wrapping", "Vertical alignment",
  "Text direction", "Origin", "TextWidth"; examples: text-based-adventure
  `Set height to min(Self.TextHeight + 4, 644)`, flowchart-questionnaire
  sizes a background from `TextWidth + 10`, `TextHeight + 10`; observed:
  2026-09-23]

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
  instance variable. [example: child-particles; observed: WaterSort,
  2026-09-17, unverified at runtime]

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
  `_GetProjectStorage`; manual:
  scripting/scripting-reference/interfaces/istorage.md "unique to the
  specific project"]

## Adding an entry

One bullet: fact, consequence, source. Manual wording beats an observation, an
observation beats intuition, intuition is not an entry. Would the agent get it
wrong without the line? If not, do not add it.
