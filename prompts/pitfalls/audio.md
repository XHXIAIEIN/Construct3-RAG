# Event Sheet Pitfalls: Audio

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md). The runtime sources
below are the functions of an exported r503/r504 web build,
`scripts/c3runtime.js` (the runtime) and `scripts/main.js` (the DOM side,
where Web Audio lives).

- With *Use worker* on, `Audio.CurrentTime` is the worker's
  `performance.now()`, and *Schedule next play* sends only an offset that the
  DOM side adds to its own audio clock when the message arrives: every
  scheduled sound carries the message delay as jitter, and layers scheduled
  "together" can land a render block apart. Sample-accurate scheduling needs
  the project property *Use worker* set to *No* (`"useWorker": "dom"`), where
  `CurrentTime` is `audioContext.currentTime` and Play calls `start(when)`.
  [manual: plugin-reference/audio.md "Schedule next play", note on *Use
  worker*; runtime: c3runtime.js `ScheduleNextPlay`, main.js `_Play` adds
  `GetAudioCurrentTime()`; example: audio-scheduling uses `dom`; observed in
  a game project, r504 preview with `dom`, 2026-09-30: music passes queued
  1 s ahead on a 100 BPM grid logged at beat 32n − 1.65 for n = 1 to 3, one
  frame from the exact 32n − 1.67, no drift]
- The audio clock does not run until the first `pointerup`, `touchend`,
  `click`, `keydown` or gamepad input: in *On any touch start* `CurrentTime`
  is still stopped, and sounds played before then queue and start together at
  the unblock. Start music by watching `CurrentTime` advance each tick, not
  from a touch trigger, and cap what plays before it moves. [manual:
  plugin-reference/audio.md "Autoplay restrictions"; runtime: main.js
  `_AttachUnblockEvents`, `_UnblockAudioContext`]
- `Audio.PlaybackTime(tag)` of a sound scheduled in the future counts from
  the Play call, not from its start, so it runs ahead by the scheduling lead.
  Compute a beat grid from `CurrentTime` minus a stored start time, and test
  grid points by integer step numbers, never by `%` on float seconds.
  [runtime: main.js `Play()` sets `_playStartTime` at the call]
- *Set playback rate* changes every instance whose tags match, including
  sounds still ringing from earlier plays: a pitch per play needs a one-off
  tag per play (`"sfx p" & Serial`), and no rate action when the rate is 1.
  `Audio.PlaybackRate(tag)` read in the tick of the Play reads 1: the state
  updates on the DOM side's next report. [runtime: main.js
  `_SetPlaybackRate` loops over all matching instances; c3runtime.js
  `_MaybeMarkAsPlaying` inserts `"playbackRate": 1`, `_OnUpdateState`]
- A sound goes through the effect chain of its first tag only. An *Add ...
  effect* or *Set effect parameter* whose tag is `"mus lead"` acts on each
  tag in turn, so two chains built in the same order are changed by one
  action. [manual: plugin-reference/audio.md "Tags"; runtime: main.js
  `GetDestinationForTag`, `_SetEffectParam` loops over the tags]
- *Set effect parameter* first cancels every scheduled value of the
  parameter and ramps from its current value: a second call cancels the rest
  of the first ramp. Overlapping ducks must be merged into one release time,
  not released with a *Wait* each. [runtime: main.js `SetAudioParam`,
  `cancelScheduledValues(0)`]
- The gain effect's parameter is in dB and ramps on the linear gain: use a
  linear ramp, an exponential one to silence throws. The compressor's
  parameters cannot change after it is added (`SetParam` is empty).
  [runtime: main.js `C3AudioGainFX.SetParam` uses `DbToLinear`,
  `C3AudioCompressorFX.SetParam`]
- The delay effect's `mix` is a percentage, 0 to 100, in *Add delay effect*
  and in *Set effect parameter* alike; its wet path carries the dry signal,
  so the dry level stays 1 and `mix` scales only the echoes: the first echo
  is `mix × feedback`, the k-th `mix × feedback^k`. Feedback is
  `filterdelaygain-gain`, in dB; the longest delay is the one it was created
  with. [runtime: c3runtime.js `AddDelayEffect` divides by 100; main.js
  `C3AudioDelayFX` node graph and `SetParam` cases 0, 4, 5]
- *Fade volume* ramps the gain linearly from its current value and also
  reaches instances scheduled but not started yet, so a layer faded in just
  before its next scheduled pass starts that pass faded in. [runtime: main.js
  instance `FadeVolume`, `linearRampToValueAtTime`, and `FadeVolume` over
  `audioInstancesMatchingTags`]
- Suspending (tab hidden, app backgrounded) stops each source and records its
  position; resuming restarts all of them at once, scheduled sounds included,
  and a scheduled one resumes ahead by its lead. A game that schedules on a
  grid handles *On resumed* with *Stop all* and a fresh start of its
  schedule; *Stop* in *On suspended* does not help. [runtime: main.js
  `_SetSuspended` calls each instance's `SetSuspended`; `Stop()` leaves
  `_resumeMe`]
- *Stereo pan* goes through a `StereoPannerNode`, which on a stereo sound
  folds one channel into the other: at ±20 the near channel gets the far one
  at cos(0.4π) ≈ 0.31, so a file limited to −3 dBFS can peak near −1 dBFS,
  and two loud sounds on the same grid point add over 0 dBFS. With no master
  limiter, keep loud transients off each other's grid point (one replaces the
  other) rather than trusting per-file ceilings. [runtime: main.js
  `createStereoPanner` per instance; Web Audio spec, StereoPannerNode
  stereo-input algorithm; observed in an offline mix of a game project's
  rules, 2026-09-30]
- Dictionary *Set key* only changes a key that exists and silently does
  nothing otherwise; *Add key* creates or overwrites. Write gates and counters
  with *Add key*. [runtime: c3runtime.js `SetKey(t,e){this._data.has(t)&&...}`,
  `AddKey`]
- A sound is heard at its scheduled time plus `Audio.OutputLatency`, for
  immediate plays too. [runtime: c3runtime.js `OutputLatency`, main.js tick
  reports `outputLatency`; observed 0.04 s in a headless Chrome r504
  preview, 2026-09-30]
- In Chrome 155, a WebM Opus file encoded to an exact length (ffmpeg
  `libopus`, 96 kb/s) decodes with `decodeAudioData` to exactly the source's
  sample count at 48 kHz, and one sample short at 44.1 kHz; the encoder's
  pre-skip is removed. Loops re-scheduled on a grid do not depend on it.
  [observed with a test page, Chrome 155, 2026-09-30]
