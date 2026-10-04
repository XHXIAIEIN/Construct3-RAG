# Published Construct Games as Visual and Game-Feel Evidence

Date: 2026-09-27
Schema: Construct 3 r495.2; the exports span Construct 2 and Construct 3
releases

## Problem

The generator template needs visual hierarchy, motion and level pacing that
a small model can reproduce with plain shapes. "Polished" or "juicy" does not
say which objects get outlines, how long a squash lasts, or when a level
releases tension.

Several authors publish small Construct games whose web exports carry those
choices as object data, event-sheet constants and effect parameters. The
question is which choices repeat across the authors, which belong to one,
and which can become theme-neutral defaults without copying characters or
finished art.

## Evidence

38 public web exports, listed in a local game list and decoded by
`python -m scripts.reference_games` (`docs/dev/published-game-analysis.md`).
Eleven older or heavily minified exports keep object names, variables and
constants but not ACE names; claims about actions leave them out. The
downloads, decoded sheets and contact sheets stay in
`.local/docs/evidence/c3-reference-games/`; nothing there is needed to use
the repository.

### Visual construction

- Source images are white and tinted at runtime. Level geometry, patterns,
  UI and effects take their colour from a world palette; characters more
  often keep finished colours. One asset set serves many level themes.
- Outlines are heavy: a black edge baked into geometry at about 5% of its
  height, or an outline on a whole layer of about 0.4% to 1.5% of the
  viewport's short edge.
- Hard offset shadows are deliberate: an unblurred silhouette, one direction
  for the whole scene, offset about 2.7% of the short edge, opacity 0.35 to
  1. No soft translucent cast shadow was found.
- Background patterns are rulers, not objects: a checker or stripes at a
  contrast of about 1.05 to 1.2.
- Palettes mark progress: a fixed set of roles whose values change per
  world, often every five levels.

### Motion and feel

- The shared motion is an immediate deformation, then a return to a stored
  rest state: a squash or stretch set in one event and a Size tween back,
  most often 0.5 s `easeoutelastic`, 0.75 s after a jump. The alternative
  approaches the rest value every tick.
- A hit is composed of size, colour, particles, sound, shake and a short
  time-scale change. The Flash behavior is not used for hits.
- Slow motion sets the time scale to 0.1 to 0.2. Shake runs about 0.4 s
  with a falling magnitude, and the magnitude says how big the event is,
  in steps from a small hit to an explosion.
- A player is often an invisible collision mask with its art pinned to it,
  so the art squashes, turns or lags while the collision stays still.
- Camera regions are data: objects carrying target zoom, zoom speed, X and
  Y locks, offset, a target, and a local game speed.

### Pacing

The recurring beat is a short, complete level. A mechanic appears alone
near the start, then returns in combinations. Difficulty rises in a saw
tooth across levels, often grouped five to a world; the victory is the rest
between attempts, about 1 to 3.5 s, up to about 6 s at the end of a world.
A failure returns control in about 0.75 to 1.25 s. Inside a larger level,
camera zones set framing and local speed; they do not make every viewport a
separate beat.

## Options

1. **Copy one studio's style.** Coherent at once, and it ties a general
   template to recognisable characters, colours and production choices.
2. **Keep a purely functional greybox.** Neutral, and it leaves hierarchy,
   feedback and pacing to each generation; the mock-ups read as a debug
   screen.
3. **Transfer the structural rules**: tintable geometry, role-based
   palettes, proportional outlines, one motion grammar, reusable juice
   functions, explicit camera regions. Subjects, finished assets and a
   studio's palette stay out.

## Decision

Option 3. No characters, skins, fonts, shaders, exact palettes, ads or
progression systems are copied.

The generator template holds these (`greybox-blockout.md`):

- outline `UNIT / 4`, drawn into the image;
- checker contrast at most 1.2;
- a hard shadow at 45°, offset 2.7% of the short edge, opacity 0.5, drawn
  into the image;
- squash set at once and a Size tween back, for a hit, a landing and a
  jump;
- a hit as a flash frame for 0.08 s, not the Flash behavior.

Proposed, not in the template:

- juice functions: shake, size impact, slow motion, zoom impact;
- shake magnitudes in tiers of about 0.3%, 1%, 2.8% and 5% of the short
  edge;
- camera region fields: zoom, zoom speed, X and Y locks and offsets, target,
  local game speed;
- pacing: five short levels a world, a victory of 1 to 2 s, a world victory
  of 4 to 6 s, a failure restart of 0.75 to 1 s.

The template keeps a light neutral ground until a mock-up shows that a
mid-grey ground reads better.

## Re-evaluate when

- A live preview of the template's outline and shadow, at the design
  resolution and at a small embedded size, reads worse than the mock-ups.
- Audio timing and input latency can be measured alongside the event data.
- A Construct release changes the export format, the Tween property order
  or the runtime reference table: the decoder needs updating.
- A larger sample contradicts the five-level world, the one-second restart
  or the proportional feedback ranges.
