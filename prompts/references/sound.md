# Sound

Which sounds play, when, how loud, and how a placeholder file is made and
checked, over the Audio plugin's runtime facts in
[pitfalls/audio.md](../pitfalls/audio.md). Read it before adding sounds or
music to a project, and when a user says the game is too loud, too busy, or
that every sound is the same. The rules are what a game project with
automatic combat, drag-and-drop merging and three music stems settled on
and verified in an r504 preview and an offline mix, 2026-09-30 to
2026-10-01; its numbers are starting points, not constants.

## Three roles

Every sound sings, strikes or beds. A sound that sings is a pitched reward:
a merge chord, a kill chord, a level-clear arpeggio. A sound that strikes
is an unpitched impact: hit, land, pick up, button. A bed is a music stem.
The role decides the rule:

- One singer at a time. A global holds the time, priority and one-off tag
  of the last scheduled singer. A new singer wanting the same 16th-note cell
  either replaces it (higher priority and the old one not started: *Stop*
  on its tag cancels a scheduled instance) or is pushed to the next cell,
  at most a beat, or dropped.
- One strike per cell. A hit scheduled for a cell is dropped when a crit
  comes for it, and both are dropped while a kill holds the cell.
- Beds give way to the first tier only, through a gain effect on the music
  tags, not *Set volume*, which the stems' fades already own. Overlapping
  ducks merge into one release (the deeper depth, the later release)
  because *Set effect parameter* cancels the ramp still running. Hits never
  duck: five a second make the music pump.

## Immediate or on the grid

- What the finger did answers in the same frame: pick up, drop, a button,
  an error, the first kill of a streak. These are unpitched, or use only
  the notes every chord of the progression allows.
- What happens by itself waits for the grid: automatic attacks, auto-merges,
  held-button spawns, the chord after a merge, stem fades on the bar. A
  16th at 100 BPM is 0.15 s, fine enough that a delayed attack is not felt,
  coarse enough to hear as rhythm.
- The grid is integer steps from `Audio.CurrentTime` minus the stored
  start of the music; a scheduled time is `start + ceil((now + lead -
  start) / step) * step`, with a lead of 0.03 s. Never `%` on float seconds
  ([pitfalls: Audio](../pitfalls/audio.md)). Before the music starts, a
  time in the past plays at once, so grid sounds degrade to immediate.
- What the sound marks moves with it: damage, squash and the floating
  number land on the same cell as the hit. The attack timer only records
  the due cell; the charge-up pose stays at full until the cell, so the
  body does not stand up before it lunges.
- A hit stop at time scale 0.1 does not delay a scheduled sound; the audio
  clock is its own. A timeline with *Use system timescale* on does slow
  ([pitfalls: Timeline](../pitfalls/timeline.md)).

## Tiers and loudness

Measure every file the same way: K-weighted (ITU-R BS.1770), above 150 Hz
only, the loudest 400 ms (3 s for music). The music with every stem on is
the reference M; the game set M at −30 LUFS.

| Tier | Sounds | Over M | Rule |
|------|--------|--------|------|
| Key | kill, the rare merge tiers, level clear, stage start, an error | +8 to +14 dB | never skipped, immediate, ducks the music |
| Action | merges, crit, pick up, land, equip, a switch | 0 to +9 dB | one per cell or per 8th; the automatic version of an action 3 dB under the hand-made one |
| Repeat | hit, hover, held spawn, auto-merge | −7 to +1 dB | each repeat within its window 1 dB under the last, to a floor; an attack rate above 4 a second lowers impacts by 10·log10(rate / 4) dB |

- A repeat that starts within 0.25 s after a key sound plays 3 dB lower at
  *Play*: the foreground stays clear without touching ringing instances.
- There is no master limiter, so peaks add. File ceilings leave the room:
  −3 dBFS for effects, −12 dBFS for music. The stereo panner folds the far
  channel into the near one and lifts an attack 1.3, 2.3 and 3.2 dB at ±10,
  ±20 and ±30: keep the loudest sounds within ±10 and off each other's cell.
- Pitched sounds are not randomly retuned; variation comes from three
  variants and a random −1.5 to 0 dB. A retune is a whole number of
  semitones (`rate = 2^(n/12)`), per play on a one-off tag.
- Pitched sounds sing the current chord. An immediate sound uses only the
  notes safe on every chord; a scheduled chord reads the chord of its cell
  and retunes to it. A scale that climbs with the level is the cheapest
  success sound in the medium; the game takes a different root each time.

## Bands

- Phone speakers reproduce nothing below 150 Hz. A low layer goes only on
  the rare accents, ends on one note (A1 55 Hz in the game) with its 2nd
  and 3rd harmonics so the drop is heard without them, and stays out of the
  compressor so its tail is not lifted. Frequent sounds carry no low layer:
  the low band belongs to the bass stem, high-passed at 70 Hz.
- Nothing sustained above 5 kHz; baked reverb is band-limited to 250 Hz to
  5 kHz so tails do not glitter. A music low-pass between 1 and 5 kHz,
  ramped by progress, is the cheapest way to make the music say where the
  level stands; its Q is in dB, −3 for a flat knee.
- The melody shares a band with the merge chords: it starts notes only on
  the first two beats of a bar and ducks 4 dB under a chord.

## Making placeholder files

- Four layers per sound: an attack (a breath of filtered noise or a thump),
  a body (a harmonic timbre), a low layer for rare accents, and the same
  room for all. The reverb is baked in at a dry-to-wet ratio by frequency:
  about 28 dB for hits, 11 to 18 dB for rare chords, 12 dB for music, so the
  most frequent sound is the driest.
- The timbre follows the art. A round, soft look is bars with harmonic
  partials only (1 and about 4 for a soft mallet, 1 and 2 for a damped
  thud), sine bubbles that glide up a few semitones in 30 ms, triangle
  pads; no bell partials (2.76, 5.40 and 8.93 of the fundamental, the sound
  of metal: Fletcher and Rossing, *The Physics of Musical Instruments*), no
  clicks above 1.5 kHz, attacks of at least 3 ms. A hard look inverts the
  choices.
- Normalise each file to its tier's loudness, limit the peak to the
  ceiling, encode WebM Opus: 96 kbps stereo for effects and the stereo
  stem, 64 kbps mono for the rest. A file encoded to an exact length
  decodes to that length at 48 kHz in Chrome.
- Music is one pass plus the reverb tail, rescheduled each pass on the grid
  rather than looped, so a stem can join on a bar. Render each note on its
  own and add it at an integer sample; only linear processing (high-pass,
  reverb) on the whole stem, so a rescheduled pass equals continuous
  playing. A seam test overlays two passes offset by one and requires the
  difference under −60 dB of the peak.
- The generator writes the pitched layers of each file (frequency, start,
  time to −12 dB) to a JSON next to the WAVs, for the offline check.

## Checking

- Offline mix. Copy the sheet's sound functions (grid, gates, singer claim,
  streak, duck) into a script, drive them with fixed-seed scenarios (a
  minute of play, a quiet board, a full board, a boss, the first touch),
  mix the WAVs, and assert: peak ≤ −1 dBFS; any 3 s short-term loudness
  ≤ −18 LUFS; each class's grid delay ≤ step + lead; every pitched play a
  whole number of semitones and inside every chord it rings through; one
  singer per cell; a kill's 400 ms at least 6 dB over the 400 ms before it;
  impacts no more than one per cell. It proves the rules were followed. A
  person listens to the WAVs for whether it sounds good.
- Preview. The browser runs with `--mute-audio`; a sound is heard or
  measured by recording it inside the page, see
  `Construct3-RAG/skills/construct3-agent-plugin/references/editor-and-preview.md`.
  A debug global that logs the beat at each pass shows the grid holds: at
  pass n the beat read `32n − 1.67` within a frame over 62 s.
- On the device: *Use worker* off for sample-accurate scheduling,
  `Audio.OutputLatency` read and recorded, resume after five seconds in the
  background, the first touch before the audio clock runs, the loudness on
  the speaker and in headphones. Each is a row in the project's own risk
  table with a pass mark and what to change when it fails.

[manual: plugin-reference/audio.md "Schedule next play", "Autoplay
restrictions", "Tags"; pitfalls/audio.md; observed in a game project, r504
preview and an offline mix of 73 assertions, 2026-09-30 to 2026-10-01]
