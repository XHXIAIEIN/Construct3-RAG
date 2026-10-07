# Event Sheet Pitfalls: Triggers and Else

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- Use one trigger per event and per branch of sub-events: no event above
  a trigger may hold another. A function and a custom action count as the
  trigger of their branch, so no trigger goes inside one. A function that
  starts a tween cannot hold the tween's *On finished*, so put that in its
  own top-level event, which calls the next function. Only an OR block
  lists several triggers. Otherwise the editor refuses the whole project,
  with `cannot add another trigger to event branch`. [manual:
  project-primitives/events/how-events-work.md "Triggers", sub-events.md
  "Triggers in sub-events"; editor bundle `projectResources.js`, function
  blocks report a trigger; observed in a game project, 2026-09-17]
- *On collision with another object*, Timer *On timer* and the Gamepad
  button conditions are triggers to the editor, with the green arrow and
  every rule above. The runtime still tests them in sheet order each tick.
  The schema marks them `isTrigger` with `isFakeTrigger`. [Addon SDK guide
  defining-aces.md "isFakeTrigger"; schema: plugins/_common.json,
  behaviors/timer.json]
- A trigger, a loop, *Else*, *Trigger once* and the conditions that only
  pick (*Pick all*, *Pick by comparison*, *Pick last created*, *Pick
  nearest/furthest*, *Pick children*) cannot be inverted. For "not on
  collision", invert *Is overlapping*. The schema marks them `isTrigger`,
  `isLooping` or `isInvertible: false`. [manual:
  project-primitives/events/conditions.md "Inverting conditions"; editor
  bundle, `condition not invertible`]
- *Trigger once* and *Every X seconds* do nothing useful under a trigger,
  because they are tested only in the trigger's tick. The editor does not
  offer them there. [Addon SDK guide defining-aces.md
  "isCompatibleWithTriggers"; schema: `isCompatibleWithTriggers: false`]
- An event runs every tick unless a trigger, *Every X seconds* or *Trigger
  once* is in it or above it. If the event flips a variable, with *Toggle*
  or *Set* to `1 - x`, `3 - x`, `-x` or `x = 1 ? 2 : 1`, it flips the
  variable back on the next tick. The variable then changes on every tick,
  so the value a tap reads depends on the tick it lands in. Flip the
  variable in the event whose trigger causes the change, or in a sub-event
  of it: a pause flag in *On key pressed*, a turn in the tap that makes the
  move. *Trigger once* does not fix it: under conditions that test values,
  the flip happens once each time they turn true, not once per tap. An
  event whose actions change what it tests runs once, such as one that
  resets the flag a tap raised. A turn that also passes when its time runs
  out keeps that flip in the event that tests the time left, which sets
  the time back in the same actions. `check_project.py` warns about the flip,
  and `edit_sheet.py` refuses it in an event a plan creates. [manual:
  project-primitives/events/how-events-work.md "Events run top to bottom";
  observed in a generated board game, 2026-10-04: the turn change in a
  top-level *Else* after a test of the game state flipped the turn every
  tick]
- Events with the same trigger run one after the other on the same input,
  so a later one sees what an earlier one set. A switch written as two
  events, "tapped and frame 0: set frame 1" and "tapped and frame 1: set
  frame 0", turns on in the first and off again in the second, and never
  changes. *Else* cannot follow the first, because each event holds its own
  trigger. Write one event with the trigger and the cases as its
  sub-events, the second starting with *Else*, or flip the value in one
  action. A *Wait* before the change keeps it from the later event.
  `check_project.py` warns about the second event, and `edit_sheet.py`
  refuses it in an event a plan creates. [manual:
  project-primitives/events/how-events-work.md "Events run top to bottom";
  observed in a light switch a local model generated, 2026-10-06]
- A trigger can fire with several instances picked. Timer *On timer* does
  this when timers elapse in the same tick. A *Pick nearest* or a function
  call written for one instance then runs once. Add *For each* after such
  triggers. [manual: behavior-reference/timer.md, note under "On timer"]
- Else is decided per block: it runs only if the previous sibling ran for
  no instance. With three picked and one passing, Else does not run for
  the other two. To branch per instance, use a second event with the
  inverted condition, or the default-then-override pattern.
  [manual: system-reference/system-conditions.md "Else"]
- Else does not narrow; it starts from the parent's picks. It cannot
  directly follow a trigger block, only a normal sub-event inside one.
  [same]
- Touch *On tap* skips a tap released within 666 ms and 25 px of the tap
  before it. That tap fires *On double-tap* instead, and the tap after it
  is single again. So a button on *On tap object* loses every second press
  of a player tapping fast. To count every press, use *On touched object*
  (start), or add *On double-tap object*. A tap is itself a release within
  333 ms and 15 px of the touch start. [manual:
  plugin-reference/touch.md "On tap", "On double-tap"; runtime: exported
  c3runtime.js r503, `ShouldTriggerTap`; observed in a game project, r503
  preview, 2026-09-28: 7 mouse clicks 0.3 s apart on the button made 4
  pieces, 8 clicks 0.7 s apart made 8; on *On touched object* (start), 7
  clicks 0.3 s apart made 7]
- One tap on an object fires Touch *On any touch start* first, then *On
  touched object* (start), then, at the release, *On tap*, whatever the
  order of their events in the sheet. So a restart on *On any touch start*
  runs before an *On touched object* event ends the game, and does not fire
  on that tap. A restart on *On tap*, or on *On touched object* in a later
  event, runs after it and fires. Make that restart test a value that the
  end sets after a *Wait*. [observed in a game project,
  editor preview, 2026-10-04: events that each appended a letter to a
  global gave "SO" for one tap on a cell, *On any touch start* and *On
  touched object* in either order, by touch and by mouse, and "SOT" with an
  *On tap* event added first in the sheet]
