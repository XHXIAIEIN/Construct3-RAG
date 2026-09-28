# Event Sheet Pitfalls: Creating objects

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- *Create object* picks only the new instance, plus the created children when
  *Create hierarchy* is on; container siblings are created too. Whether the new
  instance is also picked in its families is undocumented. To act on it through
  the family, use *System: Pick last created* with the family in a sub-event;
  the manual names that as the way to pick a created instance from its family.
  [manual: system-reference/system-actions.md "Create object";
  system-reference/system-conditions.md "Pick last created"]
- *Create object* is a System action: it runs once per event, however many
  instances are picked, and `Slot.X` in its parameters reads the first
  picked one. A custom action is run once with all the caller's picks, so
  `Slot: Spawn enemy` over three picked slots creates one enemy, at the
  first slot. To create one per picked instance, put *For each* among the
  custom action block's conditions (or the event's), or use the object's
  own *Spawn another object*. [manual: system-reference/system-conditions.md
  "For Each" "force the event to apply once per instance";
  project-primitives/events/custom-actions.md "Picking"; observed in a game
  project, r503 preview, 2026-09-28: a custom action on 3 picked slots
  created 1 instance, 3 once the block held *For each*]
- A runtime-created instance takes its properties from an existing instance or
  the named template. Keep one template instance per runtime-created object in
  a layout that never runs. [same; creation with zero instances anywhere is
  unverified]
- A Particles object given a Sprite as its *Object* spawns real instances:
  *On created* fires for each, and they are not children of the emitter (the
  example parents them by hand). Per-particle state such as a colour frame
  comes from *On created* plus *Pick nearest* emitter, read from the emitter's
  instance variable. [example: child-particles; observed in a game
  project, 2026-09-17, unverified at runtime]
- A created instance is picked in its own event and that event's
  sub-events, and *Pick by unique ID* finds it anywhere; no other condition
  (*Pick all*, *Pick random*, *Compare instance variable*, overlap) finds it
  among all instances until the top-level event that created it has ended,
  or the outermost trigger. A function called after the creating function in
  the same event does not see the new instances. Create and initialise in one
  event, pass `UID` to functions, or pick from a later top-level event or
  trigger; *Wait 0* is not needed and runs a tick later (see [Wait and time
  scale](wait-and-time-scale.md)). [Ashley in Scirra/Construct-bugs#3554 (2019) and #5178 (2021);
  runtime: exported c3runtime.js r503, `EventSheet.Run` calls
  `FlushPendingInstances()` after each top-level event, `_ExecuteTrigger`
  after the outermost trigger]
