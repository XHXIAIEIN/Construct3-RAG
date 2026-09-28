# Event Sheet Pitfalls: Restarting a layout

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- *Restart layout* and *Go to layout* bring the layout's instances back as
  placed and keep every global variable, and every static local, at its
  current value. A countdown, score or count a round starts from is still at
  its end value when the layout runs again: a global countdown that
  restarted the layout at 0 is 0 on the next run, which restarts it again
  every tick. Set such a value under *On start of layout*, or run *Reset
  global variables* (with *Reset static* for static locals) where the game
  starts over. A countdown is better a Timer on an object of the layout,
  started under *On start of layout*: the restart recreates the object
  with no timer running, and nothing is left to set back. [manual:
  system-reference/system-actions.md "Restart layout", "Go to layout",
  "Reset global variables"; project-primitives/events/variables.md "Static
  and constant variables"; behavior-reference/timer.md; observed in preview,
  2026-09-28]
