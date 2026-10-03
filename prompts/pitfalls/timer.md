# Event Sheet Pitfalls: Timer

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- *Start timer* on an existing tag restarts it. After *Stop* or a *Once*
  timer's end, its expressions return 0. Remaining time is
  `Duration(tag) - CurrentTime(tag)`. `CurrentTime` resets at every *On timer*.
  [manual: behavior-reference/timer.md]
- A timer is state you start and stop, so list every transition before
  choosing it. Settling starts or stops it by overlap, and pickup or
  displacement stops it. A `dt` countdown gated by an overlap condition has
  no transitions but needs *compare + For each* to fire. Both are valid.
  [observed in a game project, 2026-09-15]
- Timers and tweens each round their end to the first tick at or past it,
  counted from their own start. A tween started by *On timer* at `D` and a
  timer set for `D + T` where `T` is the tween's length do not end together.
  They overlap by a tick or leave a tick's gap, and *Destroy on complete*
  leaves the instance in place for the rest of that tick. Logic that assumes
  the schedule (a sum of heights that is "always at least one unit", a count
  of children) fails for that tick. Derive state from *Is playing* and from
  the instance whose tween it is. [observed in a game project, 2026-09-18]
