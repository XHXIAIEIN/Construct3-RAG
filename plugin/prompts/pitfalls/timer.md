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
  timer* on a running tag restarts it. So one instance cannot time several
  stacked buffs of one kind with tags. Shields (护盾) are the usual case:
  several skills each grant a shield with its own duration and amount, any
  number at once on one character, and the one that expires first is spent
  first. Make each shield an instance of its own: a Shield object with an
  `amount` variable and a Timer, created by the skill, made a child of the
  character with *Add child* (destroy with parent on), and timed with
  *Start timer* "expire" for its duration. *On timer* "expire" picks the
  one shield whose time ran out: *Destroy* it. On damage, *Pick children*
  Shield, then *For each (ordered)* Shield by
  `Shield.Timer.Duration("expire") - Shield.Timer.CurrentTime("expire")`
  ascending, and in its sub-events: if the damage left is 0, *Stop loop*;
  else if `Shield.amount` is at most the damage, subtract it from the
  damage and *Destroy* the shield; else subtract the damage from
  `Shield.amount` and set the damage to 0. What is left comes off health.
  *Pick children* works through the family of the characters, and a new
  skill is one more *Create object* and *Add child*. A delimiter string
  read with `tokenat` keeps the shields in the order they were granted, not
  the order they expire. [manual: behavior-reference/timer.md "Timer
  expressions", "Start timer"; plugin-reference/common-features/
  common-conditions.md "Pick children"; observed in a minimal project,
  editor preview, 2026-10-06: shields of 5 for 10 s, 4 for 20 s and 2 for
  30 s, then a hit of 6, left the 20 s shield at 3 and the 30 s shield at
  2, with health untouched; a user-shared project, 2026-10-06, picks
  children through a family; QQ bot question, 2026-10-06]
