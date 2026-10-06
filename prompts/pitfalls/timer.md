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
- The Timer behavior has no expression for the tag that fired, and *Start
  timer* on a running tag restarts it. So a timed buff that stacks cannot
  have a timer of its own. Shields (护盾) are the usual case: several skills
  each grant a shield with its own duration and amount, any number of them
  on one instance at once, and the one that expires first is spent first.
  A tag per skill restarts when the skill is cast again, and *On timer*
  cannot tell which shield expired. A delimiter string read with `tokenat`
  holds the shields in the order they were granted, so its first item is
  the oldest, not the one that expires first. Keep the shields in a 2-D
  Array in the type's container, one Array type per member type. A family
  event picks it with `Unit: Pick by unique ID Units.UID` (see
  [Picking](picking.md)). The Array is sized 0 × 2 × 1 at start: one column
  per shield, row 0 its expiry `time + duration`, row 1 its amount. To
  grant one: *Push* back on the X axis, *Set at XY* (`Width - 1`, 0) to the
  expiry and (`Width - 1`, 1) to the amount, *Sort* the X axis (by column),
  then *Start timer* "shield" for `At(0, 0) - time`. After the sort, column
  0 is the shield that expires first, and the restart arms the timer for
  it. In *On timer* "shield", under *For each*: *While* `Width > 0` and
  `At(0, 0) <= time`, *Delete* index 0 on X; then, if `Width > 0`, *Start
  timer* "shield" for `At(0, 0) - time` again. On damage: *While* `Width >
  0` and the damage left `> 0`: if the damage left is at least `At(0, 1)`,
  subtract it and *Delete* index 0 on X; else *Set at XY* (0, 1) to
  `At(0, 1)` minus the damage, and set the damage to 0. A timer still armed
  for a spent column runs the expiry loop early and re-arms. The total to
  show is the sum of row 1 over *For each element*. [manual:
  behavior-reference/timer.md "Timer expressions", "Start timer";
  plugin-reference/array.md "Sort", "Push", "Set size";
  project-primitives/objects/containers.md "Data storage objects in a
  container"; runtime: an exported c3runtime.js, release not recorded,
  `Push(where, value, axis)` on X inserts a column of `height` values and
  `Sort(axis)` on X compares `[0][0]` of each column; QQ bot question,
  2026-10-06: a family with attack, health and shield variables and a
  Timer, several skills grant stacking shields, the shortest remaining
  expires first]
