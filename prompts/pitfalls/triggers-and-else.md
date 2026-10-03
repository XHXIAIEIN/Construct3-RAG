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
