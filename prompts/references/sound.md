# Sound

This file says which sounds play, when, how loud, and how to make and
check placeholder files. Read it before adding sounds or music, and when a
user says their game is too loud, too busy, or that every sound is the
same. It adds to the Audio plugin's runtime facts in
[pitfalls: Audio](../pitfalls/audio.md). The rules come from a game
project with automatic combat, drag-and-drop merging and three music
stems. It verified them in an r504 preview and an offline mix, 2026-09-30
to 2026-10-02. Its numbers are starting points, not constants.

## One entry for every sound

When the game has more than a handful of sounds, the events that make
things happen name the moment, not the file: `cue("merge", X, tier, 0)`.
One sheet decides what each moment plays, when, how often and where in
the stereo field. Then a new set of sounds, or a new rule, changes that
sheet only. In the source project, replacing every sound and rule changed
the sound sheet throughout and the four gameplay sheets in about 130
lines.

- If every moment plays its own file at once, the entry needs no map.
  Name the files after the moments and play them with Audio *Play by
  name*, as the official examples do.
- If moments follow different rules, such as at once, on the grid, at most
  once in a gap, or one reward per cell, the entry is a function
  `cue(name, x, a, b)` that runs *Call mapped function* on map `"cue"`
  with the string `name`, forwarding from index 0. Each rule is one
  function with the same four parameters, so it reads `name` and serves
  every moment mapped to it: one function for the immediate sounds, one
  for the gated ones, one per rewarded moment. Group the *Map function to
  string* actions by the function they map to, in *On start of layout*.
  Each group then lists the moments that share a rule.
- Map the default to a function that plays nothing. Then gameplay can
  call a moment before its sound exists, and the sound arrives later
  without touching gameplay. The default gets the whole parameter list
  ([pitfalls: Functions](../pitfalls/functions.md)), the same four.
- Write the meaning of `a` and `b` per moment in one table of the
  project's sound document, because each moment uses them differently
  (a level, a weapon kind, a count, a switch).

[example: function-maps; observed in a game project, r504, 2026-10-04 to
2026-10-07: 37 moments, 20 rule functions and a silent default; the sound
system replaced on 2026-10-05]

## Three roles

Every sound is a reward, an impact or a music stem. A reward is a pitched
sound: a merge chord, a kill chord, a level-clear arpeggio. An impact is
unpitched: hit, land, pick up, button. A music stem is one layer of the
music. The role decides the rule:

- Play one reward at a time. A global holds the time, priority and one-off
  tag of the last scheduled reward. A new reward for the same 16th-note
  cell replaces the old one if it has higher priority and the old one has
  not started (*Stop* on its tag cancels a scheduled instance). Otherwise
  it moves to the next cell, at most a beat, or is dropped.
- Play one impact per cell. If a crit comes for a cell with a hit
  scheduled, drop the hit. While a kill holds the cell, drop both.
- A sound on the grid that is not an impact (an enemy appearing, the first
  landing of a stage) holds its cell too. Hits, crits and auto-merges skip
  that cell, or two files start on one sample and their peaks add. Claim
  the cell when its time is first known, as the stage is laid out, not in
  the frame it plays: impacts are queued for their cell before then.
- Music stems duck only for the Key tier, through a gain effect on the
  music tags, not *Set volume*, which the stems' fades use. Merge
  overlapping ducks into one release (the deeper depth, the later
  release), because *Set effect parameter* cancels the ramp still running.
  Hits never duck: five a second make the music pulse.

## Immediate or on the grid

- Answer the player's input in the same frame: pick up, drop, a button, an
  error, the first kill of a streak. These are unpitched, or use only the
  notes every chord of the progression allows.
- Schedule what happens by itself on the grid: automatic attacks,
  auto-merges, held-button spawns, the chord after a merge, stem fades on
  the bar. A 16th at 100 BPM is 0.15 s: too short to feel a delayed attack,
  long enough to hear as rhythm.
- The grid is integer steps from `Audio.CurrentTime` minus the stored
  start of the music. A scheduled time is
  `start + ceil((now + lead - start) / step) * step`, with a lead of
  0.03 s. Never use `%` on float seconds
  ([pitfalls: Audio](../pitfalls/audio.md)). Before the music starts, a
  time in the past plays at once, so grid sounds become immediate.
- Move what a sound marks to its cell: damage, squash and the floating
  number land on the same cell as the hit. The attack timer only records
  the due cell. The charge-up pose stays at full until that cell, so the
  body does not stand up before it lunges.
- A hit stop at time scale 0.1 does not delay a scheduled sound: the audio
  clock ignores time scale. A timeline with *Use system timescale* on does
  slow ([pitfalls: Timeline](../pitfalls/timeline.md)).

## Tiers and loudness

Measure every file the same way: K-weighted (ITU-R BS.1770), above 150 Hz
only, the loudest 400 ms (3 s for music). The reference M is the music
with every stem on, set at −30 LUFS in the game.

| Tier | Sounds | Over M | Rule |
|------|--------|--------|------|
| Key | kill, the rare merge tiers, level clear, stage start, an error | +8 to +14 dB | never skipped, immediate, ducks the music |
| Action | merges, crit, pick up, land, equip, a switch | 0 to +9 dB | one per cell or per 8th; the automatic version of an action 3 dB under the player's |
| Repeat | hit, hover, held spawn, auto-merge | −7 to +1 dB | each repeat within its window 1 dB under the last, to a floor; an attack rate above 4 a second lowers impacts by 10·log10(rate / 4) dB |

- A Repeat sound that starts within 0.25 s after a Key sound plays 3 dB
  lower at *Play*, so the foreground stays clear without changing playing
  instances.
- A dialogue voice is a Repeat sound: one short file per speaker, played
  once per character shown ([scripted-sequences.md](scripted-sequences.md),
  "Dialogue"). Play it on one tag per speaker, *Stop* the tag and then
  *Play*, so a fast line never piles the plays up. Skip it on a space and
  while the player skips the line, because a voice at every character of a
  skipped line is a buzz. [a studied project, 2026-10-06]
- There is no master limiter, so peaks add. File ceilings leave room:
  −3 dBFS for effects, −12 dBFS for music. The stereo panner mixes the far
  channel into the near one and raises an attack 1.3, 2.3 and 3.2 dB at
  ±10, ±20 and ±30. So keep the loudest sounds within ±10 and off each
  other's cell.
- Do not retune pitched sounds at random. For variation, use three variants
  and a random −1.5 to 0 dB. Retune by whole semitones
  (`rate = 2^(n/12)`), per play, on a one-off tag.
- Pitched sounds follow the current chord. An immediate sound uses only
  notes that fit every chord. A scheduled chord reads the chord of its
  cell and retunes to it. A scale that climbs with the level is the
  cheapest success sound in games, and the game uses a different root
  each time.

## Bands

- Phone speakers reproduce nothing below 150 Hz. Put a low layer only on
  rare accents. End it on one note (A1 55 Hz in the game) with its 2nd and
  3rd harmonics, so phones still play the drop. Keep it out of the
  compressor, so its tail is not lifted. Frequent sounds get no low layer,
  because the low band is for the bass stem, high-passed at 70 Hz.
- Sustain nothing above 5 kHz. Band-limit baked reverb to 250 Hz to 5 kHz,
  so tails carry no highs. A music low-pass between 1 and 5 kHz, ramped by
  progress, is the cheapest way to make the music show progress. Its Q is
  in dB, −3 for a flat knee.
- The melody shares a band with the merge chords, so it starts notes only
  on the first two beats of a bar and ducks 4 dB under a chord.

## Making placeholder files

- Use four layers per sound: an attack (a burst of filtered noise or a
  thump), a body (a harmonic timbre), a low layer for rare accents, and
  one room for all. Bake the reverb in at a dry-to-wet ratio by how often
  the sound plays: about 28 dB for hits, 11 to 18 dB for rare chords,
  12 dB for music, so the most frequent sound is the driest.
- The timbre follows the art. A round, soft look uses bars with harmonic
  partials only (1 and about 4 for a soft mallet, 1 and 2 for a damped
  thud), sine bubbles that glide up a few semitones in 30 ms, and triangle
  pads. It avoids bell partials (2.76, 5.40 and 8.93 of the fundamental,
  the sound of metal: Fletcher and Rossing, *The Physics of Musical
  Instruments*), clicks above 1.5 kHz and attacks under 3 ms. A hard look
  inverts the choices.
- Normalise each file to its tier's loudness, limit the peak to the
  ceiling, then encode WebM Opus: 96 kbps stereo for effects and the stereo
  stem, 64 kbps mono for the rest. A file encoded to an exact length
  decodes to that length at 48 kHz in Chrome.
- Music is one pass plus the reverb tail, rescheduled on the grid each
  pass rather than looped, so a stem can join on a bar. Render each note
  on its own and add it at an integer sample. Process the whole stem only
  linearly (high-pass, reverb), so a rescheduled pass equals continuous
  playing. A seam test overlays two passes offset by one and requires the
  difference under −60 dB of the peak.
- The generator writes the pitched layers of each file (frequency, start,
  time to −12 dB) to a JSON next to the WAVs, for the offline check.

## Memory for several songs

A file in the Sounds folder is held decoded once it loads, as 32-bit
samples at the audio context's rate. A second takes the rate × 4 bytes × the
channels: 192 KB in mono at 48 kHz, the rate of the Edge preview measured.
An 18 s mono stem takes about 3.5 MB, so several songs of several stems
each, all preloaded, take tens of MB. A file in the Music
folder streams instead, but it cannot be scheduled on the grid
([pitfalls: Audio](../pitfalls/audio.md)). To hold only the effects and
the songs in use:

1. Turn the project property *Preload sounds* off.
2. *Preload* the effects and the stems of the current song at the start.
3. Start the music in an event that tests *Preloads complete*, as the
   scheduled-play entry of the Audio pitfalls describes.
4. *Preload* the next song a stage or more before it plays, so its decode
   is done when it starts.
5. *Unload audio* the old song only in *On fade ended* of its last fade,
   because an unload stops every instance still playing the file.

A preview can list what is decoded at a moment; see "Reading one value" in
`Construct3-RAG/skills/construct3-agent-plugin/references/reading-the-runtime.md`.
[manual: plugin-reference/audio.md "Preloading sounds", "Categorise audio
files correctly"; Web Audio spec, AudioBuffer: 32-bit linear PCM;
pitfalls/audio.md, the decoding entry and the unload entry; observed in a minimal project, r504
preview in Edge, 2026-10-05: a mono file of the Sounds folder decoded to one
channel at 48 kHz]

## Checking

- Offline mix. It proves the rules were followed; a person judges the
  WAVs by ear.
  1. Copy the sheet's sound functions (grid, gates, reward claim, streak,
     duck) into a script.
  2. Drive them with fixed-seed scenarios: a minute of play, a quiet board,
     a full board, a boss, the first touch.
  3. Mix the WAVs and assert: peak ≤ −1 dBFS; any 3 s short-term loudness
     ≤ −18 LUFS; each class's grid delay ≤ step + lead; every pitched play
     a whole number of semitones and inside every chord it overlaps; one
     reward per cell; a kill's 400 ms at least 6 dB over the 400 ms before
     it; impacts no more than one per cell.
- Preview. The browser runs with `--mute-audio`, so record a sound inside
  the page to hear or measure it; see
  `Construct3-RAG/skills/construct3-agent-plugin/references/editor-and-preview.md`.
  A debug global that logs the beat at each pass shows the grid keeps
  time: at pass n the beat read `32n − 1.67` within a frame over 62 s.
- On the device: *Use worker* off for sample-accurate scheduling,
  `Audio.OutputLatency` read and recorded, resume after five seconds in the
  background, the first touch before the audio clock runs, the loudness on
  the speaker and in headphones. Each is a row in the project's own risk
  table with a pass mark and what to change when it fails.

[manual: plugin-reference/audio.md "Schedule next play", "Autoplay
restrictions", "Tags"; pitfalls/audio.md; observed in a game project, r504
preview and an offline mix of 73 assertions, 2026-09-30 to 2026-10-01]
