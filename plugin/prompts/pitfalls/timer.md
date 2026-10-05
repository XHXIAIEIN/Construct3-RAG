# Event Sheet Pitfalls: Timer

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- *Start timer* on an existing tag restarts it. After *Stop timer*, or after
  a *Once* timer fires, the tag's expressions return 0. Remaining time is
  `Duration(tag) - CurrentTime(tag)`. `CurrentTime` resets at every *On
  timer*. [manual: behavior-reference/timer.md]
- A timer is state that events start and stop. Before choosing one, list
  every transition. For example, an instance's timer starts or stops by
  overlap when the instance settles, and stops when it is picked up or
  displaced. A `dt` countdown gated by an overlap condition has no
  transitions, but acting on each instance whose countdown ends needs a
  comparison and *For each*. Both are valid. [observed in a game project,
  2026-09-15]
- Timers and tweens each round their end to the first tick at or past it,
  counted from their own start. A tween started by *On timer* at `D` and a
  timer set for `D + T`, where `T` is the tween's length, do not end together.
  They overlap by a tick or leave a tick's gap, and *Destroy on complete*
  leaves the instance in place for the rest of that tick. Logic that assumes
  the schedule (a sum of heights that is "always at least one unit", a count
  of children) gives a wrong result for that tick. Derive state from *Is
  playing* and from the instance whose tween it is. [observed in a game
  project, 2026-09-18]
