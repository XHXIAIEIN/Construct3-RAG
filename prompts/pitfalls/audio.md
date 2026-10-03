# Event Sheet Pitfalls: Audio

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md). The runtime sources
below name functions of an exported r503/r504 web build, in
`scripts/c3runtime.js` (the runtime) and `scripts/main.js` (the DOM side,
which runs Web Audio).

- If *Use worker* is on, `Audio.CurrentTime` is the worker's
  `performance.now()`. *Schedule next play* then sends only an offset, and
  the DOM side adds it to its own audio clock when the message arrives. So
  the message delay adds jitter to every scheduled sound, and layers
  scheduled "together" can start a render block apart. For sample-accurate
  scheduling, set the project property *Use worker* to *No*
  (`"useWorker": "dom"`). Then `CurrentTime` is `audioContext.currentTime`,
  and Play calls `start(when)`.
  [manual: plugin-reference/audio.md "Schedule next play", note on *Use
  worker*; runtime: c3runtime.js `ScheduleNextPlay`, main.js `_Play` adds
  `GetAudioCurrentTime()`; example: audio-scheduling uses `dom`; observed in
  a game project, r504 preview with `dom`, 2026-09-30: music passes queued
  1 s ahead on a 100 BPM grid logged at beat 32n − 1.65 for n = 1 to 3, one
  frame from the exact 32n − 1.67, no drift; measured on the audio-scheduling
  example, r504 preview, 195 sounds on a 25 ms grid, `when` read at the page's
  `AudioBufferSourceNode.start`, 2026-10-03: `dom` 25.000 ms every gap,
  `worker` gaps 15.8 to 36.3 ms, 3.7 ms mean and 11.5 ms worst off the grid]
- A scheduled play is exact only for a file in the Sounds folder that is
  loaded when *Play* runs. *Play* waits for the file to download and decode,
  then starts it at the scheduled time. If that time is already past, the
  file plays at once, from its start. So with *Preload sounds* off, the
  first play of each sound starts late, and layers scheduled together start
  apart. A file in the Music folder streams through an `<audio>` element.
  Its play takes no start time and begins when the stream is ready. Keep
  beat-locked music in Sounds with *Preload sounds* on. Or *Preload* every
  scheduled file, and start the schedule in *On preloads complete*. [manual:
  plugin-reference/audio.md "Categorise audio files correctly", "Preloading
  sounds", "Schedule next play"; runtime: main.js `_Play` adds the offset to
  the clock when the message arrives and awaits `_GetAudioInstance` before
  the instance's `Play`, the buffer instance calls `start(when, offset)`,
  the media instance's `Play` ignores its time argument; read from the
  r504 runtime, not observed in play]
- In a browser, no sound is heard until the player first touches, clicks
  or presses a key. The Audio object queues the sounds played before then
  and starts them at that input. So a sound played in *On start of layout*
  needs no events of its own. Open a web game on a "tap anywhere to start"
  screen whose tap goes to the game, so the game's music and sounds play
  from its first frame. Put *Request fullscreen*, and the other requests
  that the browser grants only after input, on the same tap
  ([input.md](input.md)). Music played on that screen starts at the same
  tap, as the game begins. So a track meant for the title screen needs a
  screen that waits for a second tap. A mobile app export has no
  such limit, and an installed web app may have none.
  [manual: plugin-reference/audio.md "Autoplay restrictions"; example:
  detecting-input-method, `Title events`: a flashing prompt, then one event
  per input method that sets a global and goes to the game]
- The audio clock does not run until the first `pointerup`, `touchend`,
  `click`, `keydown` or gamepad input. So in *On any touch start*,
  `CurrentTime` is still stopped. Sounds played before then queue and all
  start together when the browser unblocks audio. Start music when
  `CurrentTime` advances, not from a touch trigger, and limit what plays
  before the clock moves. [manual: plugin-reference/audio.md "Autoplay
  restrictions"; runtime: main.js `_AttachUnblockEvents`,
  `_UnblockAudioContext`]
- For a sound scheduled in the future, `Audio.PlaybackTime(tag)` counts
  from the Play call, not from the sound's start, so it is ahead by the
  scheduling lead. Compute a beat grid from `CurrentTime` minus a stored
  start time. Test grid points by integer step numbers, never by `%` on
  float seconds. [runtime: main.js `Play()` sets `_playStartTime` at the
  call; reported as Scirra/Construct-bugs#9290, open]
- *Set playback rate* changes every instance whose tags match, including
  sounds still playing from earlier plays. So for a pitch per play, give
  each play a one-off tag (`"sfx p" & Serial`), and skip the rate action
  when the rate is 1. In the tick of the Play, `Audio.PlaybackRate(tag)`
  returns 1, because the state updates on the DOM side's next report.
  [runtime: main.js `_SetPlaybackRate` loops over all matching instances;
  c3runtime.js `_MaybeMarkAsPlaying` inserts `"playbackRate": 1`,
  `_OnUpdateState`]
- A sound goes through the effect chain of its first tag only. An *Add ...
  effect* or *Set effect parameter* with the tag `"mus lead"` acts on each
  tag in turn. So one action changes two chains built in the same order.
  [manual: plugin-reference/audio.md "Tags"; runtime: main.js
  `GetDestinationForTag`, `_SetEffectParam` loops over the tags]
- *Set effect parameter* first cancels every scheduled value of the
  parameter, then ramps from its current value. So a second call cancels
  the rest of the first ramp. Merge overlapping ducks into one release
  time instead of a *Wait* for each. [runtime: main.js `SetAudioParam`,
  `cancelScheduledValues(0)`]
- The gain effect's parameter is in dB and ramps on the linear gain. The
  compressor's parameters cannot change after it is added, because its
  `SetParam` is empty. [runtime: main.js `C3AudioGainFX.SetParam` uses
  `DbToLinear`, `C3AudioCompressorFX.SetParam`]
- An exponential ramp to 0 throws, for every parameter of every effect.
  Web Audio's `exponentialRampToValueAtTime` refuses a target of 0, so each
  such *Set effect parameter* logs `RangeError ... should not be in the
  range (-1.40130e-45, 1.40130e-45)` and leaves the parameter unchanged.
  The dry path of a `mix` of 100 also reaches 0, because its gain is
  `1 - mix`. So does any expression that can reach 0, such as
  `from * (to / from) ^ p` with a large negative `p`. Ramp such a parameter
  linearly, or keep the value above 0 with `max(value, floor)`. [runtime:
  main.js `SetAudioParam` case 2; the filter, delay, convolution, ring modulator
  and distortion effects' `SetParam` set the dry gain to `1 - t`; observed in a game project, r504 preview, 2026-10-02:
  a low-pass frequency computed as `from * (to / from) ^ stageP`, with
  `stageP` near -20000 after a test raised an enemy's hp above the
  stage's total, logged one RangeError per call]
- The delay effect's `mix` is a percentage, 0 to 100, in both *Add delay
  effect* and *Set effect parameter*. Its wet path carries the dry signal,
  so the dry level stays 1 and `mix` scales only the echoes. The first echo
  is `mix × feedback`, and the k-th is `mix × feedback^k`. Feedback is
  `filterdelaygain-gain`, in dB. The longest delay is the one the effect
  was created with. [runtime: c3runtime.js `AddDelayEffect` divides by 100;
  main.js `C3AudioDelayFX` node graph and `SetParam` cases 0, 4, 5]
- *Fade volume* ramps the gain linearly from its current value. It also
  reaches instances scheduled but not started yet. So if a layer
  is faded in just before its next scheduled pass, that pass starts faded
  in. To cancel a one-shot scheduled ahead, fade its one-off tag to -100 dB
  before it starts. [runtime: main.js instance `FadeVolume`,
  `linearRampToValueAtTime`, and `FadeVolume` over
  `audioInstancesMatchingTags`; observed in a game project, r504 export in
  headless Edge 155, 2026-10-02: a play scheduled 0.5 s ahead and faded to
  -100 dB in the same tick, two frames later, or before its file had ever
  played, recorded at the noise floor, -130 dB against -29 dB unfaded, with
  the fade ending in stop or in keep playing; *Stop* cancelled it too]
- On suspend (tab hidden, app backgrounded), Audio stops each source and
  records its position. On resume it restarts all of them at once,
  scheduled sounds included, and a scheduled sound resumes ahead by its
  lead. If a game schedules on a grid, use *Stop all* in *On resumed* and
  restart its schedule. *Stop* in *On suspended* does not help. [runtime:
  main.js `_SetSuspended` calls each instance's `SetSuspended`; `Stop()`
  leaves `_resumeMe`; the *Stop* case reported as
  Scirra/Construct-bugs#9289, open]
- *Stereo pan* goes through a `StereoPannerNode`. On a stereo sound it
  mixes one channel into the other: at ±20 the near channel gets the far
  one at cos(0.4π) ≈ 0.31. So a file limited to −3 dBFS can peak near
  −1 dBFS, and two loud sounds on the same grid point sum above 0 dBFS. A
  transient that is the same in both channels rises by
  1 + sin(|pan| × 90°): 1.3 dB at ±10, 2.3 dB at ±20, 3.2 dB at ±30.
  Without a master limiter, do not rely on per-file ceilings. Keep loud
  transients off each other's grid point, so that one replaces the other,
  and narrow the pan of the loudest sounds. A pan of ±10 instead of ±20
  gave a −3 dBFS kill the same headroom as a −4 dBFS file ceiling, which
  would have cost it 0.5 dB of loudness. [runtime: main.js
  `createStereoPanner` per instance; Web Audio spec, StereoPannerNode
  stereo-input algorithm; observed in an offline mix of a game project's
  rules, 2026-09-30]
- Dictionary *Set key* changes only an existing key and silently ignores
  a missing one. *Add key* creates or overwrites, so write gates and
  counters with *Add key*. [runtime: c3runtime.js
  `SetKey(t,e){this._data.has(t)&&...}`, `AddKey`]
- The runtime finds a sound by its path below the Sounds or Music folder,
  without the extension. So a file in the folder `Board` is `Board/spawn`,
  and *Play by name* with `"spawn"` finds and plays nothing, with no error.
  If a game builds sound names in expressions, keep those files at the top
  of the folder, or put the folder path in every name with matching case.
  Timelines differ: *Play by name* finds a timeline in a folder by its
  bare name. [runtime: c3runtime.js `PlayByName` calls
  `GetProjectAudioFileUrl`, whose `_audioFiles` map held `"Board/spawn"`,
  and `GetTimelineByName` reads `_timelinesByName` by the lowercased bare
  name; observed in a game project, r504 preview, 2026-10-02: after sounds
  moved into folders,
  `GetProjectAudioFileUrl("spawn")` returned null while
  `GetTimelineByName("SwordIdle")` found the timeline in its folder]
- A sound is heard at its scheduled time plus `Audio.OutputLatency`, for
  immediate plays too. [runtime: c3runtime.js `OutputLatency`, main.js tick
  reports `outputLatency`; observed 0.04 s in a headless Chrome r504
  preview, 2026-09-30]
- In Chrome 155, `decodeAudioData` decodes a WebM Opus file encoded to an
  exact length (ffmpeg `libopus`, 96 kb/s) to exactly the source's sample
  count at 48 kHz. At 44.1 kHz it is one sample short. Decoding removes the
  encoder's pre-skip. Loops re-scheduled on a grid do not depend on this
  length. A mono file decodes to one channel, 192 KB a second at 48 kHz,
  half the decoded memory of the same length in stereo. [observed with a
  test page, Chrome 155, 2026-09-30; mono: Edge 155, 2026-10-02, a 64 kb/s
  mono stem decoded to 1 channel of 998,400 samples]
