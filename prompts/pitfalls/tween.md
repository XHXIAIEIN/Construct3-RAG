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
