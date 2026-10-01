# Event Sheet Pitfalls: Timeline

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md). How a timeline and a
custom ease are written in the project files is in
[references/hand-editing-project-files.md](../references/hand-editing-project-files.md).

- A numeric property track in *Relative* mode changes its property by the
  step of each tick, `Offset…(value − last value)`, and the last value
  starts at 0 when playback starts forward. A keyframe's value is therefore
  an offset from the instance's value when playback began, not a position.
  On a hierarchy child with the timeline's *Transform* on, X, Y and angle
  are offsets in the parent's frame, so the child keeps following a parent
  that events move every tick, and two relative timelines on one instance
  add up. An event that sets the same property every tick keeps only that
  tick's step of the timeline. Animate a part's position and angle relative
  to its parent, leave its size to the events, and author each move to start
  and end at 0, so that moves can be layered and replayed without drifting.
  [runtime: exported c3runtime.js r504, `NumericInterpolationAdapterForTimeline.ChangeProperty`
  calls `_Setter(t - GetLastValue())` in relative mode, `SetInitialState`
  sets the last value to 0 when playing forward, the `offsetX` setter calls
  `OffsetX(e, GetTransformWithSceneGraph())`, which adds to the local
  offset of a child; observed in a game project, r504 preview, 2026-09-30:
  a sword parented to a body placed by events every tick kept its slash
  pose, and an idle sway and a slash timeline on the same sword added up]
- *Set instance* applies to the next *Play* only. With several instances
  picked, one *Play* starts a copy of the timeline for each, all with the
  same tags, so every copy answers the same *Set time* or *Stop*. Set one
  instance at a time, in a *For each*, and give each its own tag, such as
  `"slash-" & Self.UID`; do not use a timeline's name as a tag, since
  `Time`, `TotalTime` and `KeyframeTime` look names up before tags. A later
  *Play* of the same timeline for the same instance reuses its copy, and does
  nothing while that copy is playing: to restart it, *Set time* 0, then
  *Resume*. [runtime: r504 preview, Timeline plugin
  `_PlayTimelineSyncAndReturnPromises` takes one picked instance per track at
  a time, finds a copy with `GetTimelineOfTemplateForInstances` or makes one
  with `CreateFromTemplate`, then `SetTags(tags)` and `Play()`;
  `TimelineState.Play` returns false while `_IsPlaying()`; `Exps.Time` tries
  `GetTimelinesByName` before `GetTimelinesByTags`; observed in a game
  project, r504 preview, 2026-09-30: three swords, one copy of each of two
  timelines per sword, each reached by its own tag]
- The copy for an instance is found by the timeline's name contained in the
  copy's name (`SwordSlash:3`), so a timeline named `Slash` also matches the
  copies of `SwordSlash` played on that instance. Keep no timeline name
  inside another's when both play on the same object. [runtime: exported
  c3runtime.js r504, `TimelineManager.GetTimelineOfTemplateForInstances`
  tests `t.GetName().includes(e.GetName())`; not reproduced]
- *Stop* puts the playhead back to 0 and applies it in the same tick, so a
  relative timeline stopped midway takes its offsets back, also while it is
  paused, set by *Set time*, playing backwards or layered with another
  relative timeline on the instance. A timeline that has already finished
  ignores *Stop* and keeps its end pose, with a relative track's offsets
  left on the instance: *Set time* 0 takes them back. *Pause* keeps the
  pose where it is. *Resume* does nothing once a non-looping timeline has
  reached its end: move the playhead back with *Set time* first. [runtime:
  r504 preview, Timeline plugin `StopTimeline` calls `Reset()`,
  `PauseTimeline` calls `Stop()`; `TimelineState.Reset` returns when
  `IsComplete()`, `_CanResume` is false when the time is at the total time;
  observed in a game project, r504 preview, 2026-09-30: the second slash
  only started after *Set time* 0 moved the playhead off the end; observed
  in a minimal project, r495.2 and r504 preview, 2026-10-01: a relative X
  track at +121 px and an angle track at −57°, on a hierarchy child too,
  read 0 in the tick of *Stop* from each of those states, and a finished
  one kept +484 px after *Stop* and read 0 after *Set time* 0]
- *Set time* pauses a playing timeline where it puts it, and on one that
  was just played in the same action list it takes it off the schedule and
  applies the pose, which creates an instance's copy without playing it. It
  triggers *On time set*, never *On keyframe reached*: scrubbing across a
  tagged keyframe with *Set time* does not run the keyframe's events.
  [runtime: exported c3runtime.js r504, `TimelineState.SetTime` stops a
  playing timeline and deschedules a scheduled one, then interpolates with
  the ticking flag off; `TrackState.MaybeTriggerKeyframeReachedConditions`
  returns when not ticking; observed in a game project, r504 preview,
  2026-09-30]
- *On keyframe reached* picks no instance. When copies play on several
  instances, put the instance's UID in the tags and pick it back from
  `Timeline.TimelineTags`: `Pick by unique ID int(tokenat(Timeline.TimelineTags,
  2, "-"))` for tags `sword-move-146`. [manual:
  plugin-reference/timeline-controller.md "On keyframe reached",
  "TimelineTags"; runtime: r504 preview, `Cnds.OnKeyframeReached` only
  compares the reached keyframe's tags; observed in a game project, r504
  preview, 2026-09-30]
- *On keyframe reached* runs before the track writes that tick's values:
  in the trigger the instance still holds the previous tick's pose, part of
  the way into the segment that ends at the keyframe. To act on where the
  keyframe puts it, such as launching a copy from a sword held overhead, put
  *Wait 0* before the actions that read the pose; they run at the start of
  the next tick, after the keyframe pose was applied and drawn. This is the
  case *Wait 0* is for (see [Wait and time scale](wait-and-time-scale.md)).
  [runtime: exported c3runtime.js r504, `TrackState.Interpolate` calls
  `MaybeTriggerKeyframeReachedConditions`, which fires the triggers
  synchronously through `OnKeyframeReached`, before the property tracks'
  `Interpolate`; observed in a game project, r504 preview, 2026-10-01: a
  sprite created at a sword's position in the trigger started 12 px off the
  pose drawn at the keyframe, and after *Wait 0* matched it within 1 px;
  reported as Scirra/Construct-bugs#9291, open, 2026-10-01: in the trigger
  `Time` reads the keyframe's time while a discrete track still holds the
  value before the keyframe]
- A negative playback rate plays a timeline back to 0, where it finishes:
  *Set playback rate* −3 on a windup cancelled midway takes the pose back
  smoothly, and a relative timeline ends with its offsets gone. Set a
  positive rate again before the next *Resume*, which otherwise restarts it
  backwards from the end. [runtime: exported c3runtime.js r504,
  `TimelineState.Tick` stops at 0 when the rate is negative;
  `SetInitialState` starts a complete timeline from 0 or from its total time
  by the sign of the rate; observed in a game project, r504 preview,
  2026-09-30: a slash stopped at 0.206 s, set to −3, was back at 0 and
  finished 0.08 s later]
- A timeline that played forward to its end and stopped there cannot be
  *Resume*d backwards: while it is not playing the runtime counts it as
  playing forward whatever its playback rate, and a forward timeline at its
  total time cannot resume. To take back a pose held at the end, *Set time*
  to `TotalTime(tag) - 0.001` first, then set a negative rate and *Resume*;
  the 1 ms moves a relative track by what its last segment covers in that
  time, nothing under an ease that flattens at the end. A timeline still
  playing takes the negative rate and *Resume* directly. [runtime: exported
  c3runtime.js r504, `TimelineState.IsForwardPlayBack` returns
  `!IsPlaying() || playbackRate > 0`, `_CanResume` returns false when
  forward and `GetTime() >= GetTotalTime()`; observed in a game project, r504
  preview, 2026-09-30: a sword pose held at the end of its 0.36 s stayed put
  while events set rate −2 and *Resume*d it, and after *Set time* 0.359 the same actions took it back to 0
  in 0.18 s]
- A copy that *Resume* or *Play* starts is playing at once, but its playhead
  reads 0 until the timeline ticks it: an event later in the same tick, or
  an action resumed after a *Wait*, sees `Time` 0 with *Is playing* true.
  To ask whether a move is under way, test *Is playing*; `Time > 0` misses a
  move started this tick. [observed in a game project, r504 preview,
  2026-10-01: a pose timeline resumed in one event read `Time` 0 in a later
  event of the same tick, which took it for idle and did not take it back
  under a new move; sampled after that tick, the copy read `Time` 0 and
  *Is playing* true]
- A timeline follows the system time scale when its *Use system timescale*
  is on, the default: *Set time scale* 0.1 for a hit stop slows it with
  everything else, and a strike stops at the moment it lands. Its playback
  rate multiplies on top. [manual: project-primitives/timelines/timeline.md
  "Use system timescale"; runtime: exported c3runtime.js r504,
  `TimelineState.Tick` advances by `dt × timeScale × playbackRate` when
  `GetUseSystemTimescale()`; observed in a game project, r504 preview,
  2026-09-30: during a 0.1 hit stop the playhead advanced 0.005 s while the
  game time advanced 0.004 s]
