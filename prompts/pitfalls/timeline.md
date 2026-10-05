# Event Sheet Pitfalls: Timeline

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md). If you read or write
a timeline or a custom ease in the project files, read "Timelines and custom
eases" in
[references/hand-editing-project-files.md](../references/hand-editing-project-files.md).

- A numeric property track in *Relative* mode changes its property by the step
  of each tick, `Offset…(value − last value)`. The last value starts at 0 when
  playback starts forward. So a keyframe's value is an offset from the
  instance's value when playback began, not a position. On a hierarchy child
  with the timeline's *Transform* on, X, Y and angle are offsets in the
  parent's frame. So the child keeps following a parent that events move every
  tick, and two relative timelines on one instance add up. An event that sets
  the same property every tick keeps only that tick's step of the timeline.
  Animate a part's position and angle relative to its parent, and leave its
  size to events. Author each move to start and end at 0, so that layered and
  replayed moves leave no offset. [runtime: exported c3runtime.js r504,
  `NumericInterpolationAdapterForTimeline.ChangeProperty` calls
  `_Setter(t - GetLastValue())` in relative mode, `SetInitialState` sets the
  last value to 0 when playing forward, the `offsetX` setter calls
  `OffsetX(e, GetTransformWithSceneGraph())`, which adds to the local offset
  of a child; observed in a game project, r504 preview, 2026-09-30: a sword
  parented to a body placed by events every tick kept its slash pose, and an
  idle sway and a slash timeline on the same sword added up]
- An angle keyframe's direction, `clockwise` or `anti-clockwise`, holds for
  the segment that starts at that keyframe, whatever its two values are. If it
  disagrees with the shorter way to the next value, the instance turns the
  long way round: from 0 to +90° *Anti-clockwise* turns −270°. *Closest* takes
  the shorter way, and *Revolutions* adds full turns. So a generator sets each
  keyframe's direction to the sign of the change to the next keyframe:
  positive is clockwise. [runtime: exported c3runtime.js r504, the angle
  adapter's `Interpolate` switches on `GetDirection()` to `C3.angleLerp`,
  `C3.angleLerpClockwise` or `C3.angleLerpAntiClockwise`; observed in a game
  project, r504 preview, October 2026: a bow keyframe from 300° to 390° set
  *Anti-clockwise* spun the bow 270° backwards]
- *Set instance* applies to the next *Play* only. With several instances
  picked, one *Play* starts a copy of the timeline for each, all with the same
  tags. So every copy answers the same *Set time* or *Stop*. Set one instance
  at a time, in a *For each*, and give each copy its own tag, such as
  `"slash-" & Self.UID`. Do not use a timeline's name as a tag, because
  `Time`, `TotalTime` and `KeyframeTime` look up names before tags. A later
  *Play* of the same timeline for the same instance reuses its copy, and does
  nothing while that copy plays. To restart the copy, *Set time* 0, then
  *Resume*. [runtime: r504 preview, Timeline plugin
  `_PlayTimelineSyncAndReturnPromises` takes one picked instance per track at
  a time, finds a copy with `GetTimelineOfTemplateForInstances` or makes one
  with `CreateFromTemplate`, then `SetTags(tags)` and `Play()`;
  `TimelineState.Play` returns false while `_IsPlaying()`; `Exps.Time` tries
  `GetTimelinesByName` before `GetTimelinesByTags`; observed in a game
  project, r504 preview, 2026-09-30: three swords, one copy of each of two
  timelines per sword, each reached by its own tag]
- The runtime finds an instance's copy as one whose name (`HeroAttack:3`)
  contains the timeline's name. So a timeline named `Attack` also matches the
  copies of `HeroAttack` played on that instance. If two timelines play on the
  same object, neither name may contain the other. [runtime: exported
  c3runtime.js r504, `TimelineManager.GetTimelineOfTemplateForInstances` tests
  `t.GetName().includes(e.GetName())`; reported as Scirra/Construct-bugs#9288,
  closed 2026-10-01 as fixed in the next beta after r504]
- *Stop* puts the playhead back to 0 and applies that pose in the same tick.
  So a relative timeline stopped midway takes its offsets back. This also
  holds while paused, set by *Set time*, playing backwards or layered with
  another relative timeline on the instance. A finished timeline ignores
  *Stop* and keeps its end pose, so a relative track's offsets stay on the
  instance. *Set time* 0 takes them back. *Pause* keeps the pose where it is.
  *Resume* does nothing once a non-looping timeline has reached its end, so
  move the playhead back with *Set time* first. [runtime: r504 preview,
  Timeline plugin `StopTimeline` calls `Reset()`, `PauseTimeline` calls
  `Stop()`; `TimelineState.Reset` returns when `IsComplete()`, `_CanResume` is
  false when the time is at the total time; observed in a game project, r504
  preview, 2026-09-30: the second slash only started after *Set time* 0 moved
  the playhead off the end; observed in a minimal project, r495.2 and r504
  preview, 2026-10-01: a relative X track at +121 px and an angle track at
  −57°, on a hierarchy child too, read 0 in the tick of *Stop* from each of
  those states, and a finished one kept +484 px after *Stop* and read 0 after
  *Set time* 0. The finished case was reported as Scirra/Construct-bugs#9287,
  closed 2026-09-30: the next beta after r504 sets the time to 0 on *Stop* of
  a timeline that is not playing; *Set time* 0 works in both]
- *Set time* pauses a playing timeline at the time it sets. After a *Play* in
  the same action list, it takes the timeline off the schedule and applies the
  pose. *Play* then *Set time* thus creates an instance's copy without
  playing it. *Set time* triggers *On time set*, never *On keyframe
  reached*. So moving the playhead across a tagged keyframe with *Set time*
  does not run its events. [runtime: exported
  c3runtime.js r504, `TimelineState.SetTime` stops a playing timeline and
  deschedules a scheduled one, then interpolates with the ticking flag off;
  `TrackState.MaybeTriggerKeyframeReachedConditions` returns when not ticking;
  observed in a game project, r504 preview, 2026-09-30]
- *On keyframe reached* picks no instance. If copies play on several
  instances, put the instance's UID in the tags and pick it back from
  `Timeline.TimelineTags`. For tags `sword-move-146`, use
  `Pick by unique ID int(tokenat(Timeline.TimelineTags, 2, "-"))`. [manual:
  plugin-reference/timeline-controller.md "On keyframe reached",
  "TimelineTags"; runtime: r504 preview, `Cnds.OnKeyframeReached` only
  compares the reached keyframe's tags; observed in a game project, r504
  preview, 2026-09-30]
- *On keyframe reached* runs before the track writes that tick's values. So in
  the trigger, the instance still holds the previous tick's pose, part of the
  way into the segment that ends at the keyframe. If actions must read the
  keyframe's pose, such as to launch a sprite from a sword held overhead, put
  *Wait 0* before them. They then run at the start of the next tick, after the
  runtime applied and drew the keyframe pose. *Wait 0* exists for this case
  (see [Wait and time scale](wait-and-time-scale.md)). [runtime: exported
  c3runtime.js r504, `TrackState.Interpolate` calls
  `MaybeTriggerKeyframeReachedConditions`, which fires the triggers
  synchronously through `OnKeyframeReached`, before the property tracks'
  `Interpolate`; observed in a game project, r504 preview, 2026-10-01: a
  sprite created at a sword's position in the trigger started 12 px off the
  pose drawn at the keyframe, and after *Wait 0* matched it within 1 px;
  reported as Scirra/Construct-bugs#9291: in the trigger `Time` reads the
  keyframe's time while a discrete track still holds the value before the
  keyframe; closed 2026-10-01, to be fixed in the first beta after the next
  stable release, where the *Wait 0* is no longer needed]
- A negative playback rate plays a timeline back to 0, where it finishes.
  *Set playback rate* −3 on a windup cancelled midway takes the pose back
  smoothly, and a relative timeline ends with its offsets gone. Set a positive
  rate again before the next *Resume*, which otherwise restarts it backwards
  from the end. [runtime: exported c3runtime.js r504, `TimelineState.Tick`
  stops at 0 when the rate is negative; `SetInitialState` starts a complete
  timeline from 0 or from its total time by the sign of the rate; observed in
  a game project, r504 preview, 2026-09-30: a slash stopped at 0.206 s, set to
  −3, was back at 0 and finished 0.08 s later]
- A timeline that played forward to its end and stopped there cannot be
  *Resume*d backwards. While it is not playing, the runtime counts it as
  playing forward at any playback rate. So a timeline stopped at its total
  time is at the end of a forward pass, and it cannot resume. To take back a
  pose held at the end, *Set time* to `TotalTime(tag) - 0.001` first, then set
  a negative rate and *Resume*. This 1 ms moves a relative track by what its
  last segment covers in that time: nothing under an ease that flattens at the
  end. If the timeline is still playing, set the negative rate and *Resume*
  directly. [runtime: exported c3runtime.js r504,
  `TimelineState.IsForwardPlayBack` returns `!IsPlaying() || playbackRate >
  0`, `_CanResume` returns false when forward and `GetTime() >=
  GetTotalTime()`; observed in a game project, r504 preview, 2026-09-30: a
  sword pose held at the end of its 0.36 s stayed put while events set rate −2
  and *Resume*d it, and after *Set time* 0.359 the same actions took it back
  to 0 in 0.18 s]
- A copy that *Resume* or *Play* starts is playing at once, but its playhead
  reads 0 until the timeline ticks it. So an event later in the same tick, or
  an action resumed after a *Wait*, sees `Time` 0 with *Is playing* true. To
  test whether a move is under way, use *Is playing*, because `Time > 0`
  misses a move started this tick. [observed in a game project, r504 preview,
  2026-10-01: a pose timeline resumed in one event read `Time` 0 in a later
  event of the same tick, which took it for idle and did not take it back
  under a new move; sampled after that tick, the copy read `Time` 0 and
  *Is playing* true]
- Do not rewind a copy whose playhead reads 0, even if *Is playing* is true
  because it was resumed earlier in the same tick. A negative rate set before
  the copy starts makes it start backwards from its total time. A relative
  track then takes its end pose as already applied, so it subtracts that pose
  on the way back to 0 and leaves the offset on the instance permanently.
  Rewind only if `Time > 0`. Otherwise *Set time* 0, which takes the copy off
  the schedule without moving the instance. [runtime: exported c3runtime.js
  r504, `TrackState.SetInitialState` starts at `GetLocalTotalTime()` when the
  timeline is not playing forward, and
  `NumericInterpolationAdapterForTimeline.SetInitialState` sets a relative
  track's last value to `GetValueAtTime()` instead of 0; observed in a game
  project, r504 preview, 2026-10-02: a rest pose ending at +40° was resumed
  and, later in the same tick, rewound at −2 by an event that tested
  *Is playing*; each time the sword was left 40° off, 80° after two stage
  clears, and with the `Time > 0` test and *Set time* 0 no sword drifted over
  the same run]
- A negative playback rate fires *On keyframe reached* for every tagged
  keyframe it passes on the way back, with the same tags as the forward pass.
  A cheer rewound at −4 re-ran its `catch` and `jump` events, and a rewound
  raise re-fired its spark burst. The keyframe trigger cannot read the
  playback rate. So if an event must run only on the forward pass, make it
  test a flag (`rewinding`): the event that starts the rewind sets it, and
  the forward *Resume* clears it. [runtime: exported c3runtime.js r504,
  `TrackState.MaybeTriggerKeyframeReachedConditions` has an `else` branch for
  `!IsForwardPlayBack()` that calls `OnKeyframeReached` for the keyframe at or
  above the new time; observed in a game project, r504 preview, 2026-10-02]
- A timeline follows the system time scale while its *Use system timescale* is
  on (the default). So *Set time scale* 0.1 for a hit stop slows it with
  everything else, and a strike stops at the moment it lands. Its playback
  rate multiplies the time scale. [manual:
  project-primitives/timelines/timeline.md "Use system timescale"; runtime:
  exported c3runtime.js r504, `TimelineState.Tick` advances by
  `dt × timeScale × playbackRate` when `GetUseSystemTimescale()`; observed in
  a game project, r504 preview, 2026-09-30: during a 0.1 hit stop the playhead
  advanced 0.005 s while the game time advanced 0.004 s]
