# Event Sheet Pitfalls: Tween

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- A value tween drives what Tween cannot address: *Tween (value)* with start,
  end and time, then an event *Is playing "tag"* with *Set effect parameter*,
  *Set Z height* or *Set angle* to `Self.Tween.Value("tag")`. The tween owns
  the clock and the ease; the action just reads it. Use it for a full turn: a
  one-property angle tween to `Self.Angle + 360` does not turn, a value tween
  from `Self.Angle` to `Self.Angle + 360` applied with *Set angle* does.
  [manual: behavior-reference/tween.md "Tween (value)", "Value"; example:
  abductractor ("ReduceLuminosity", "SmashCorn"); the angle case:
  github.com/Scirra/Construct-feature-requests/issues/547, closed expired]
- *On finished* and *On any finished* fire while an instance whose tween has
  *Destroy on complete* still exists; it is destroyed after the triggers
  have run. The finish of a death tween can therefore read the instance's
  position, pick its container and spawn at its place, and an *On any
  finished* written for the tweens that settle an instance also runs for the
  one that destroys it: give each ending its tag and react to that tag.
  [runtime: exported c3runtime.js r503, Tween `_FinishTriggers` triggers
  `OnTweensFinished` and `OnAnyTweensFinished`, then calls `DestroyInstance`
  when `GetDestroyInstanceOnComplete()`; observed in a game project, r503
  preview, 2026-09-29: sparks spawned from `On Tween "collapse" finished` at
  the shrunk enemy's position, its container's hitbox still picked]
- Starting a tween on a property (position, size, angle, opacity, any but
  *Tween (value)*) stops every tween already running on that property of the
  instance, whatever its tags. A stopped tween never finishes: no *On
  finished*, and no *Destroy on complete*. A death tween that shrinks the
  instance to 0 and destroys it is cancelled by any later size tween, a
  landing squash for one, and the instance stays for good. Let a Timer on
  the instance, or a *Wait*, destroy it and leave the tween only the look;
  or keep every other size tween off a dying instance. [runtime: exported
  c3runtime.js r504, Tween `CreateTween` calls `ReleaseTweens(property)`
  unless `Maps.IsValueId`; observed in a game project, r504 preview,
  2026-10-01: an enemy killed while still falling started `die collapse`
  (size to 0, destroy on complete), its landing squash started a size tween
  0.15 s later, the collapse was gone from `allTweens()` at once, and the
  enemy stayed at full size with collisions off until the stage was stuck]
- `Tween.Value(tag)` reads 0 once the tween has finished, not its end value:
  a finished tween is released, and the expression returns 0 when no tween
  of the tag is left. A state that must hold (a piece kept enlarged while it
  is dragged) cannot be read from a finished value tween. Write each
  animated channel as what is left of it, a value tween from the full amount
  to 0, and add `Value(tag)` into a size or position derived every tick: the
  channel is neutral when it ends or was never started, and channels started
  by different events add up instead of overwriting each other. [runtime:
  exported c3runtime.js r503, Tween `Exps.Value` returns
  `GetTweenIncludingWaitingForRelease(tag)` or 0, `_FinishTriggers` calls
  `ReleaseTween`; observed in a game project, r503 preview, 2026-09-29]
- A one-property or two-property tween changes its property by the step of
  each tick, not by setting it to the eased value: the properties are named
  `offsetX`, `offsetWidth` and so on, and the runtime calls `OffsetWidth(change)`.
  A *Set width* or *Set X* made while such a tween plays is kept, and the rest
  of the tween's change is added on top, so the tween ends off its end value
  by what the *Set* moved it. An event that places the same property while
  the tween may still run, a level setup that sets a bar's width during the
  bar's own tween, needs *NOT Is playing "tag"* in front of it, or a *Stop*
  of the tween. [runtime: exported c3runtime.js r503, Tween property track
  `"offsetWidth"` setter calls `t.OffsetWidth(e)` with the tick's change;
  observed in a game project, r503 preview, 2026-09-29: a progress bar
  tweened from 416 to 20 px over 0.55 s, set to 20 by the next level's setup
  at 0.6 s of the tween's 0.67 s, ended at 2 px]
- *Stop* does not zero a channel at once: the stopped tween goes on a list
  that is released at the end of the tick, and `Value(tag)`, `Progress` and
  `Time` still read it for the rest of that tick. Events after the *Stop* in
  the same tick see the value it stopped at, and the channel reads 0 from
  the next tick. Stopping one channel and starting another in the same
  action list therefore draws one frame with both, which blends a crouch
  into the jump that releases it rather than popping back to rest. A new
  tween started under the same tag is found first, so a *Stop* followed by
  a restart reads the new tween at once. [runtime: exported c3runtime.js
  r503, Tween `StopTweens` calls `ReleaseTween`, which moves the tween to
  `_waitingForReleaseTweens`, emptied in `Tick2`; `Exps.Value` reads
  `GetTweenIncludingWaitingForRelease`, whose list puts active tweens
  first; observed in a game project, r503 preview, 2026-09-29: a crouch
  channel stopped as the jump squash started read 1 in that frame, 0 in
  the next]
