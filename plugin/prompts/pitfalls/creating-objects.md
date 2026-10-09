# Event Sheet Pitfalls: Creating objects

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- *Create object* picks only the new instance, plus the created children if
  *Create hierarchy* is on. Container siblings are created too. The new
  instance's families are not picked, so a family action after *Create
  object* in the same action list acts on every other instance of the
  family and misses the new one. To act on it through the family, use
  *System: Pick last created* with the family in a sub-event. The manual
  names this as the way to pick a created instance from its family.
  [manual: system-reference/system-actions.md
  "Create object"; system-reference/system-conditions.md "Pick last created";
  observed in a minimal project, r504 preview, 2026-10-02: `Create object
  BladeEnemy` then `Enemies: Set X 777` moved the 19 instances already there
  and not the new one; *Pick last created Enemies* in a sub-event picked the
  new one alone]
- A type can be both in the parent's container and among its children in the
  template's hierarchy. Then creating the parent with *Create hierarchy* on
  creates one instance of that type: the container sibling and the hierarchy
  child are the same new instance. Put a part in both to have it picked with
  the parent and moved with it. [observed in a game project, r504 preview,
  2026-09-30: a `Card` template with four parts in its container and its
  hierarchy, created six times, left six instances of each part]
- *Create object* is a System action, so it runs once per event, however many
  instances are picked. `Slot.X` in its parameters reads the first picked
  one. A custom action runs once with all the caller's picks, so `Slot: Spawn
  enemy` over three picked slots creates one enemy, at the first slot. To
  create one per picked instance, put *For each* among the custom action
  block's conditions (or the event's), or use the object's own *Spawn another
  object*. [manual: system-reference/system-conditions.md "For Each" "force
  the event to apply once per instance";
  project-primitives/events/custom-actions.md "Picking"; observed in a game
  project, r503 preview, 2026-09-28: a custom action on 3 picked slots
  created 1 instance, 3 once the block held *For each*]
- A runtime-created instance takes its properties from an existing instance
  or the named template. An object with no instance in any layout is still
  created, with its image and size, but its behavior properties read 0. A
  Bullet created that way has speed 0 and never moves, while the addon's
  default is 400. Keep one template instance per runtime-created object in a
  layout that never runs. [same; observed in a minimal project, r504 preview,
  2026-10-02: the Laser of the official example families, its one layout
  instance removed, was created 52×27 and visible with Bullet speed 0; with
  the instance kept, speed 400]
- A layout loads the images of the objects placed in it when it starts. An
  object created only by events, its template kept in a layout that never
  runs, loads its images when it is created: the game keeps running and the
  instance draws nothing until they arrive. A picture the size of the screen
  shows a moment late, so an object meant to cover something flickers; a
  small one is ready by the next tick. For a large picture created by
  events, put *Load object images* in *On start of layout*, or place an
  instance in that layout and destroy it at the start. [manual:
  tips-and-guides/memory-usage.md "Layout-by-layout loading",
  tips-and-guides/importing-c2-projects.md, system-reference/system-actions.md
  "Load object images"; observed in a probe project, r495.2 preview,
  2026-10-08: a 1920×1080 Sprite created by a script mid-game had no texture
  for 62 to 100 ms, 6 to 10 ticks, with no tick longer than usual; placed
  in the layout or loaded at the start, it had one at once, and a 160×160
  one by the next tick]
- A Particles object given a Sprite as its *Object* spawns real instances.
  *On created* fires for each, and they are not children of the emitter (the
  example parents them by hand). Per-particle state such as a colour frame
  comes from *On created* plus *Pick nearest* emitter, read from the
  emitter's instance variable. [example: child-particles; observed in a game
  project, 2026-09-17; observed in that example, r504 preview, 2026-10-02:
  with its parenting event turned off, 49 of 50 particle sprites had no
  parent]
- A created instance is picked in its own event and that event's sub-events,
  and *Pick by unique ID* finds it anywhere. No other condition (*Pick all*,
  *Pick random instance*, *Compare instance variable*, overlap) finds it among
  all instances until the top-level event that created it has ended, or the
  outermost trigger. So a function called after the creating function in the
  same event does not see the new instances. Create and initialise in one
  event, pass `UID` to functions, or pick from a later top-level event or
  trigger. *Wait 0* is not needed and runs a tick later (see [Wait and time
  scale](wait-and-time-scale.md)). `check_project.py` warns if one list of
  actions creates instances, directly or through a function, and then calls a
  function that picks them by a condition. [Ashley in
  Scirra/Construct-bugs#3554 (2019) and #5178 (2021); runtime: exported
  c3runtime.js r503, `EventSheet.Run` calls `FlushPendingInstances()` after
  each top-level event, `_ExecuteTrigger` after the outermost trigger]
- When a hierarchy is created, the order of its instances' *On created* is
  not fixed. In one instance's *On created*, the others may not have run
  theirs yet, so code there cannot rely on how the rest of the hierarchy is
  set up. *On hierarchy ready* fires on the root once every instance of the
  hierarchy is created and has run *On created*. Initialise the hierarchy
  there. [manual: plugin-reference/common-features/common-conditions.md "On
  hierarchy ready"; scripting-reference/object-interfaces/iworldinstance.md
  "hierarchyready"; none of the 524 official examples uses the condition]
- A created bullet that hits nothing keeps flying outside the layout
  forever, and the instances pile up and slow the game. A Destroy in its
  hit events removes the bullets that hit, not the ones that miss. Give a
  fired object the Destroy outside behavior, region `layout`, or `viewport`
  when the layout is larger than the screen. It has no conditions or
  actions. In the official examples the bullets without it end on Solid
  walls and ground. `check_project.py` warns when nothing removes a fired
  Bullet object that misses. [manual: behavior-reference/destroy-outside.md;
  observed in a generated shooter, stable r495.2 preview, 2026-10-09: a shot
  through an empty column was at y -658 three seconds later, and with
  Destroy outside it was gone; the 524 official examples: 58 of the 169
  Bullet objects their events create have Destroy outside, and all but four
  of the rest have Fade, Wrap or Tween, are destroyed or placed again by
  events, or hit a Solid]
