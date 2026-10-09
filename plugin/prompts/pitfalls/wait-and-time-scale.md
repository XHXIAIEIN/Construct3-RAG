# Event Sheet Pitfalls: Wait and time scale

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- *Wait* does not stop a loop. The remaining iterations run in the same tick,
  and the actions after the *Wait* run later, once per iteration, with that
  iteration's picked instances. A staggered effect is `Wait 0.1 * loopindex`.
  If a loop must pause between iterations, use a Timer or a function called
  from *On timer*. [manual: system-reference/system-actions.md "Wait";
  examples: arcade-shooter, layout-transition]
- A *Wait* keeps the instances its event picked. The actions after it act on
  those instances, even if other events pick or create instances in the
  meantime, and an instance destroyed during the wait drops out. So
  *Wait 2 seconds* then *Destroy* in one action list destroys the instance
  that started the wait, with no UID to store and no *Pick by UID*. If the
  event picked several instances, the actions after the wait run on all of
  them. [runtime: exported c3runtime.js r503, `ScheduledWait._Init` saves the
  SOL of every object type and the wait restores it when it resumes; read
  from source, not observed; construct.net tutorial system-wait-action-63,
  "Wait remembers picked objects"]
- *Wait for previous actions* (the manual's "Wait for previous actions to
  complete") waits only for asynchronous actions, marked with an icon in the
  editor: Tween actions, AJAX requests, Local Storage, *Snapshot canvas*.
  Other actions before it are already done. A function call counts only if
  the function is marked *Asynchronous* and itself ends with *Wait for
  previous actions*. [manual: system-reference/system-actions.md "Wait for
  previous actions to complete", project-primitives/events/functions.md
  "Asynchronous functions"; example: avalanche, sheets Stalagmite and
  Credits]
- A *Wait* delays only the actions after it in its own block and that block's
  sub-events. A sibling event, or the next sub-event of the same parent, runs
  at once. So with a *Wait for previous actions* alone in sub-event 1 and
  *Destroy* in sub-event 2, *Destroy* runs before the tween ends. Put the
  asynchronous action, the wait and what follows in one action list. [manual:
  system-reference/system-actions.md "Wait", "Wait for previous actions to
  complete": "before continuing on to the next action or sub-events. Other
  events continue to run in the meantime."]
- A *Wait* with *Use time scale* on never ends while the time scale is 0. So
  turn *Use time scale* off on the wait that resumes the game. For the UI
  tweens of the pause, use *Set object time scale* 1 on the fader, the
  buttons and the manager object. [manual: system-reference/system-actions.md
  "Wait", "Set object time scale"; example: airborne-explorer, In-Game Menu]
- *Wait 0* resumes at the start of the next tick, not at the end of the event
  or the sheet. The current tick first runs all its events and is drawn. Then
  the rest of the event runs one frame late, before the next tick's behaviors
  and events, in an included sheet or a function alike. It keeps the picks
  saved at the *Wait*, minus destroyed instances, and restores function
  parameters and function locals. It also runs at time scale 0, and a layout
  change cancels it. *Wait for previous actions* with nothing to wait for
  resumes at the same point. Leave *Wait 0* out, because the next top-level
  event can pick a created instance and a destroyed one is gone by then (see
  [Creating objects](creating-objects.md)). Instead, initialise in *On
  created* or the creating event, pass `UID`, or put the dependent step in a
  later top-level event or trigger. Use *Wait 0* only if a trigger fires
  before the tick finishes what it reports. For example, *On keyframe
  reached* fires before the keyframe's values are written (see
  [Timeline](timeline.md)). Ashley's tutorial says "until the end of the
  event sheet", which is Construct 2 wording. [runtime: exported c3runtime.js
  r503, `Wait` calls `AddScheduledWait`, `RunScheduledWaits` is called only
  from `Step_BeforePreTick`, ahead of `Step_RunEventsEtc` and `Render`;
  `ScheduledWait._Init` saves SOL, parameters and locals;
  `ClearAllScheduledWaits` on layout end; read from source, not observed.
  Ashley: "rarely any need to use Wait 0 seconds", forum
  construct-2/general-discussion-17/wait-59374; *Wait for previous actions*
  "always runs at the end of the tick", Scirra/Construct-bugs#3948;
  construct.net tutorial system-wait-action-63, updated 2019]
- Deactivating a group stops its events, including its triggers, and nothing
  else. Behaviors, timers and tweens it started keep running. So it turns a
  phase off but does not pause. [manual: system-reference/system-actions.md
  "Set group active"; examples: every pause is *Set time scale* 0]
- *Set time scale* 0 stops every animation as well, so a cutscene, an
  ultimate's full-screen animation or a pause menu's own animation stops
  with the battle. Pause with *Set time scale* 0, then *Set object time
  scale* 1 on the object that must keep playing. In the Sprite's *On
  finished* for that animation, *Set time scale* 1 and *Restore object time
  scale* on the object. *Set object time scale* also drives the object's
  animation, though the manual names only its behaviors and its `dt`.
  [manual: system-reference/system-actions.md "Set object time scale";
  observed in effects-screen-blend, r495.2 preview, 2026-10-09: at time
  scale 0, a 15 fps explosion whose instances got time scale 1 from a
  script, the value the action sets, went from frame 7 to 22
  in 1 s, and the other explosion stayed on frame 7]
- A hit stop is *Set time scale* 0.1, *Wait* and *Set time scale* 1 in one
  block. A smooth ramp is a *Tween (value)* on any object read into *Set time
  scale* while *Is playing*. [examples: segmented-boss-fight BossHeath;
  samuroof Credits `Camera.Tween.Value("TimeScaleChange")`; eventide `1 -
  PauseUI.Tween.Progress("ShowPause")`]
- If two such hit stops overlap (a critical hit that also kills, two lanes
  resolving in one tick), each restores the time scale when its own *Wait*
  ends. So the shorter stop ends the longer one early. Count the running
  stops in a variable: add 1 before the *Wait* and subtract 1 after it. Set
  the time scale to 1 only when the count is back to 0. Do not compare a
  `wallclocktime` deadline after the *Wait* instead. An unscaled *Wait*
  counts the runtime's wall time, the sum of each tick's clamped `dt` taken
  at the start of the tick. But `wallclocktime` is `Date.now()` read
  mid-tick. So if a stop starts a few milliseconds into a busy tick, its
  deadline has not passed when its *Wait* ends, and the time scale stays at
  0.1 until the next hit stop. [manual:
  system-reference/system-expressions.md "wallclocktime"; runtime: exported
  c3runtime.js r504, `wallclocktime` returns `(Date.now() - GetStartTime()) /
  1e3`, `Wait` with *Use time scale* off calls `InitWallTimer`, `_wallTime`
  adds `_dt1`, clamped to `_maxDt` 1/30; observed in a game project, r504
  preview, 2026-10-02: a 0.05 s crit stop and a 0.08 s kill stop in one tick
  lasted 0.05 s with no deadline and 0.08 s with one; a 0.08 s stop called 8
  to 16 ms into a tick stayed at 0.1 in 20 of 20 runs with the
  `wallclocktime` deadline and in 0 of 20 with the count, which still lasted
  0.08 s for the overlapping pair]
- A hit stop slows every tween and every `dt` on game time. So a tween
  started on the audio clock to end on a beat ends late by 0.9 of the length
  of each stop inside it, and overlapping stops add their delays. Set its
  object's time scale to 1 for that tween, and restore it with *Restore
  object time scale* in *On finished*. If a per-tick blend must keep real
  time, divide `dt` by `timescale`. [manual:
  system-reference/system-actions.md "Set object time scale", "Restore
  object time scale"; system-reference/system-expressions.md "dt",
  "timescale"; observed in a game project, r504 preview, 2026-10-02: an
  elite dropped from 0.35 s before a beat to land on it landed 0.13 s late
  when two kills fell inside the drop, and 1 ms early to 7 ms late with its
  time scale at 1; a `1 - exp(-dt / 0.1)` blend on game time kept a progress
  icon nodding at full depth through a 0.1 s kill stop]
- Scroll To *Shake* replaces the running shake: it overwrites the magnitude,
  start and end. So a 3 px tombstone shake 0.45 s after an 8 px kill shake
  ends the kill shake. A 3 px splash shake in the same tick as the kill shake
  also replaces it, by running later. Gate *Shake*: call it only if the new
  magnitude is not smaller than the remaining one, `mag × max(0, 1 − (time −
  start) / duration)`, kept in variables. The runtime also multiplies the
  magnitude by `min(object time scale, 1)` and divides the duration by it. So
  during a 0.1 hit stop it shakes at a tenth and in effect starts when the
  stop ends. *Set object time scale* 1 on the camera object keeps it at full
  strength through the stop. [runtime: exported c3runtime.js r504, scrollto
  `Acts.Shake` calls `SetShakeMagnitude`, `SetShakeStart`, `SetShakeEnd`
  unconditionally; `Tick2` computes `mag × min(n, 1)` and `(end − start) / n`
  with `n` the instance's time scale; observed in a game project, r504
  preview, 2026-10-02: an axe kill shook 3 px before the gate and 7 px after,
  and with the camera's time scale at 1 the 12 px boss shake peaked at 10 px
  inside the 0.1 s stop]
