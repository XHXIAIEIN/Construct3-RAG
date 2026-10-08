# Event Sheet Pitfalls: Tween

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- A value tween drives what Tween cannot address. Run *Tween (value)* with a
  start, end and time. Then, under an event *Is playing "tag"*, apply
  `Self.Tween.Value("tag")` with *Set effect parameter*, *Set Z height* or
  *Set angle*. The tween computes the eased value, and the action only reads
  it. A one-property angle tween to `Self.Angle + 360` does not turn. So for a
  full turn, use a value tween from `Self.Angle` to `Self.Angle + 360`,
  applied with *Set angle*. [manual: behavior-reference/tween.md "Tween
  (value)", "Value"; example: abductractor ("ReduceLuminosity", "SmashCorn");
  the angle case: github.com/Scirra/Construct-feature-requests/issues/547,
  closed expired]
- *On finished* and *On any finished* fire before *Destroy on complete*
  destroys the instance. So the finish of a death tween can read the
  instance's position, pick its container and spawn objects there. But an
  *On any finished* written for the tweens that settle an instance also runs
  for the tween that destroys it. Give each ending its own tag and react to
  that tag. [runtime: exported c3runtime.js r503, Tween `_FinishTriggers`
  triggers `OnTweensFinished` and `OnAnyTweensFinished`, then calls
  `DestroyInstance` when `GetDestroyInstanceOnComplete()`; observed in a game
  project, r503 preview, 2026-09-29: sparks spawned from
  `On Tween "collapse" finished` at the shrunk enemy's position, its
  container's hitbox still picked]
- A tween started on a property (position, size, angle, opacity, any but
  *Tween (value)*) stops every tween already running on that property of the
  instance, whatever their tags. A stopped tween never finishes, so it runs
  neither *On finished* nor *Destroy on complete*. Any later size tween,
  such as a landing squash, cancels a death tween that shrinks the instance to
  0 and destroys it. The instance then stays permanently. Let a Timer on the
  instance, or a *Wait*, destroy it, and let the tween change only its look.
  Or start no other size tween on a dying instance. [runtime: exported
  c3runtime.js r504, Tween `CreateTween` calls `ReleaseTweens(property)`
  unless `Maps.IsValueId`; observed in a game project, r504 preview,
  2026-10-01: an enemy killed while still falling started `die collapse` (size
  to 0, destroy on complete), its landing squash started a size tween 0.15 s
  later, the collapse was gone from `allTweens()` at once, and the enemy
  stayed at full size with collisions off until the stage was stuck]
- A second *Tween (value)* under a tag that a value tween already plays runs
  beside the first, and `Value(tag)` reads the first until it ends. So a count
  restarted mid-way shows the old count's number for the rest of its time,
  then jumps to the new one. Put *Stop* of the tag before the restart.
  [runtime: exported c3runtime.js r504, Tween `CreateTween` calls
  `ReleaseTweens(property)` unless `Maps.IsValueId`; observed in a minimal
  project, stable editor preview, 2026-10-08: a score counting from 0 to 6
  got a gain of 10 when the count read 5.3; without the *Stop* its text
  stayed 6 for 0.18 s while the second count, from 6 to 16, passed 11, then
  jumped to 12]
- `Tween.Value(tag)` reads 0 once the tween has finished, not its end value.
  The runtime releases a finished tween, and the expression returns 0 when no
  tween of the tag is left. So a finished value tween cannot hold a state,
  such as a piece kept enlarged while it is dragged. Write each animated
  channel as what is left of it: a value tween from the full amount to 0. Then
  add `Value(tag)` into a size or position derived every tick. So a channel
  adds nothing when it has ended or was never started, and channels started by
  different events add up instead of overwriting each other. [runtime:
  exported c3runtime.js r503, Tween `Exps.Value` returns
  `GetTweenIncludingWaitingForRelease(tag)` or 0, `_FinishTriggers` calls
  `ReleaseTween`; observed in a game project, r503 preview, 2026-09-29]
- A one-property or two-property tween changes its property by the step of
  each tick. It does not set the property to the eased value: the properties
  are named `offsetX`, `offsetWidth` and so on, and the runtime calls
  `OffsetWidth(change)`. So a *Set width* or *Set X* made while such a tween
  plays stays, and the tween adds the rest of its change on top. The tween
  then misses its end value by what the *Set* moved it. If an event sets the
  same property while the tween may still run, put *NOT Is playing "tag"* in
  front of it, or *Stop* the tween. A level setup that sets a bar's width
  during its own tween is such an event. [runtime: exported c3runtime.js r503,
  Tween property track `"offsetWidth"` setter calls `t.OffsetWidth(e)` with
  the tick's change; observed in a game project, r503 preview, 2026-09-29: a
  progress bar tweened from 416 to 20 px over 0.55 s, set to 20 by the next
  level's setup at 0.6 s of the tween's 0.67 s, ended at 2 px]
- *Stop* does not zero a channel at once. The stopped tween goes on a list
  that the runtime releases at the end of the tick, so `Value(tag)`,
  `Progress` and `Time` still read it for the rest of that tick. Events after
  the *Stop* in the same tick see the value where it stopped, and the channel
  reads 0 from the next tick. So if one action list stops one channel and
  starts another, one frame draws both. This blends a crouch into the jump
  that releases it, instead of showing the rest pose for a frame. The
  expressions find active tweens first, so after a *Stop* and a restart under
  the same tag, they read the restarted tween at once. [runtime: exported
  c3runtime.js r503, Tween `StopTweens` calls `ReleaseTween`, which moves the
  tween to `_waitingForReleaseTweens`, emptied in `Tick2`; `Exps.Value` reads
  `GetTweenIncludingWaitingForRelease`, whose list puts active tweens first;
  observed in a game project, r503 preview, 2026-09-29: a crouch channel
  stopped as the jump squash started read 1 in that frame, 0 in the next]
- A width tween that ends can leave the width a hair short of its end value,
  so that both print 355.2 and `Width < target` still holds. An event that
  starts the tween with `Width < target` and `NOT Is playing "grow"` then
  starts a tween of no distance each time the last one ends. That empty tween
  reads as playing for its whole 0.3 s, so a real change of the target in
  that time starts no tween. Compare with a tolerance, `Width < target - 0.5`
  starts the tween, and add an event for the gap that the tolerance leaves,
  `Width < target` and `NOT Is playing "grow"`, which sets the width to
  `target`. A trail tested with `Width > target` has the same gap and takes
  the same two events. [observed in a minimal project, stable editor preview,
  2026-10-07: three bars with a growth tween each; two of them held a
  zero-distance tween in a loop, and when a heal raised their target they
  grew 0.19 s late, only after the loop's current tween ended, while the
  third bar, which had no such loop, started at once. Found by listing each
  bar's tweens every tick, `[...inst.behaviors.Tween.allTweens()]`, with the
  `tags` and `progress` of each]
