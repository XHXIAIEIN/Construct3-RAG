# Published Construct Games as Visual and Game-Feel Evidence

Date: 2026-09-27
Schema: Construct 3 r495.2; sampled exports span older Construct 2 and Construct 3 releases

## Problem

The greybox template needs visual hierarchy, motion and level pacing that a
small model can reproduce with plain shapes. Adjectives such as “polished” or
“juicy” do not define which objects receive outlines, how long a squash lasts,
or when a level should release tension.

[author], [author] and [author] publish small Construct games whose exported
projects expose those choices as object data, event-sheet constants and effect
parameters. The study asks which choices repeat across games, which belong to
one author, and which can become theme-neutral defaults without copying their
characters or finished art.

## Evidence

### Sample

The catalog contains 38 public web exports:

- 9 [author] games, 7 [author] games and 18 [author] games;
- 3 collaborations between two or three of those authors;
- 1 [author] and [author] collaboration;
- 21 and 17 releases from public sites.

The decoder found 4,231 object types, 2,040 layouts and 520 event sheets. It
recovered readable ACE names from 27 exports. Eleven older or aggressively
minified exports retained object names, variables, groups and constants but not
readable ACE names. Claims that depend on an action name exclude those eleven.

The source catalog is `scripts/reference_games/catalog.json`. The ignored local
workspace is `.local/docs/evidence/c3-reference-games/`. It contains downloaded
exports, decoded event sheets, image contact sheets, generated statistics and
the three author-level reading notes. None of those third-party exports or
derived image sheets is required to use the repository.

### Shared visual construction

All three authors use white source images as tintable material. White accounts
for 21–89% of sampled opaque atlas pixels. Level geometry, patterns, UI and
effects receive color at runtime; characters more often keep finished colors.
This separates shape vocabulary from a world palette and lets one asset set
support many level themes.

Outlines are heavy:

- [author] commonly bakes a 4 px black edge into geometry around 74 px high.
- [author] applies a 10–16 px outline to a whole 1080p game layer.
- [author] uses layer outlines from 0.4% to 1.25% of the viewport short edge,
  with a median near 0.75%.

Hard offset shadows are also deliberate. Twelve of 18 [author] games and two
of nine [author] games use an unblurred silhouette with one direction for the
whole scene. [author]’s median offset is about 2.7% of the viewport short edge;
opacity ranges from 0.35 to 1. A soft translucent cast shadow was not found.

Background patterns act as rulers without becoming objects. [game] uses a
checker at 2.5% opacity; [game] uses 15%; [game] uses a white pattern
at 2–8%. Their effective contrast is about 1.05–1.2, which contains the draft
checker’s 1.16 ratio.

Palette changes mark progress. [author] commonly changes a color row every five
levels. [author] groups colors by world. [author] keeps a grey or saturated
ground and a small stable accent family. The transferable rule is a fixed role
table whose values change per world, not any one author’s colors.

### Shared motion and game feel

The common motion is an immediate deformation followed by a return to a stored
rest state. The implementation differs:

- [author] sets a squash or stretch in one event and returns with a Size tween,
  commonly 0.5 s `easeoutelastic`; jump recovery can take 0.75 s.
- [author] uses `easeoutelastic` for 294 of 508 tweens. Its common forms are
  a 0.5 s Size return and a 0.5–1 s Y return.
- [author] often sets the size directly and approaches the rest value every
  tick at 5–10 units per second. Its tweens are used more for Color and Scale.

Impact feedback is composed from size, color, particles, sound, camera shake
and a short time-scale change. It is not delegated to the Flash behavior:
[author] uses no Flash actions in the seven solo games; [author] uses Flash
sparingly, mostly for repeated glints rather than hit feedback.

Slow motion usually sets time scale to 0.1–0.2. [author]’s recurring juice API
contains screen shake, zoom by percentage, zoom to a position and slow motion.
The same function family appears from its 2020 projects through [game] in 2025.

Camera regions are project data rather than hand-authored camera code. Across
the authors, the recurring fields are target zoom, zoom speed, X/Y locks,
offset, target object or weight, and local game speed. [author] names this
object `CameraZone`; [author] uses `CamDirector` or `CameraDirector`.

### Author signatures

#### [author]

Across nine solo games, 591 tweens have a median constant duration of 0.5 s.
Size is the most common tween property (31%). The main easing families are
`easeinoutsine` (25%) and `easeoutelastic` (18%).

Camera shake is unusually consistent: 0.4 s with reducing magnitude dominates,
while magnitude expresses importance. Values around 5, 10, 20, 40 and 60 map
from a small hit to a large explosion; exceptional unlocks can exceed them.

A normal victory runs as a short chain: freeze control, shake, white impact,
particles, large text, then transition. Measured chains take about 1.1–3.4 s;
the end of a five-level world can take about 5.7 s and add a palette change or
unlock. Failure normally restarts after 0.8–1.25 s.

#### [author]

Across seven solo games, 508 tweens use `easeoutelastic` 294 times. Only 14
constant Wait actions appear. Timers and object-specific time scale keep UI and
victory layers moving while gameplay slows or stops.

The author’s level systems expose world palettes, camera zones and reusable
segments. [game] builds a level from a start, three named one-screen ideas and
an end. [game] groups 64 levels into eight worlds. This supports a rising
but saw-toothed difficulty curve rather than a monotonic sequence of harder
rooms.

#### [author]

Across 18 games, the study found 176 tweens. Color (47) and Scale (40) are the
most common properties. Forty percent of the inspected tweens ping-pong; the
median constant duration is 0.5 s.

[author] is closest to the intended blockout language: a low-contrast patterned
background, white or dark modular geometry, one accent family, a heavy layer
outline and a hard layer shadow. Thirteen projects separate an invisible player
mask from a pinned visual object, keeping collision stable while the art
squashes, rotates or lags behind.

Failure is fast and cheap. [game] restarts after about 0.75 s and [game]
Platforming after about 1 s. [game] exposes an immediate restart. The fail
beat combines desaturation, danger color, slow motion and camera zoom.

### Level pacing

The recurring beat is a complete short level. New mechanics appear alone near
the beginning, then return in combinations. Tension changes between levels;
the victory beat is the rest between attempts. Difficulty rises in a saw-tooth
pattern, and a failed attempt returns control in about one second.

Camera zones still matter inside a larger level, but they describe framing and
local speed. They should not force every viewport into a separate gameplay beat.

## Options

### Copy one studio’s style

This gives a coherent result quickly but ties a general-purpose template to
recognizable characters, colors, effects and production assumptions.

### Keep a purely functional greybox

This preserves neutrality but leaves hierarchy, feedback and pacing to each
generation. Earlier mock-ups already showed that the result reads as a debug
screen rather than a designed prototype.

### Transfer the structural rules

Use tintable geometry, role-based palettes, proportional outlines, one motion
grammar, reusable juice functions and explicit camera regions. Keep subjects,
finished assets and studio-specific palettes out of the template.

## Decision

Transfer the structural rules. Do not copy characters, skins, fonts, shaders,
exact palettes, advertisements or progression systems.

The generator template holds these, as `greybox-blockout.md` records:

- outline: `UNIT / 4`, drawn into the image;
- checker contrast: at most 1.2;
- hard shadow: one scene direction at 45°, 2.7% short-edge offset, 0.5
  opacity, drawn into the image;
- squash: the impact size set at once, then a Size tween back, [author]'s hit,
  landing and jump recipes;
- hit color: a white frame for 0.08 s instead of Flash.

Proposed, not in the template:

- juice functions: screen shake, size impact, slow motion and zoom impact;
- shake magnitudes: proportional tiers around 0.3%, 1%, 2.8% and 5% of the
  viewport short edge;
- camera region fields: zoom, zoom speed, X/Y locks, X/Y offsets, target and
  local game speed;
- pacing: five short levels per world, ordinary victory around 1–2 s, world
  victory around 4–6 s, and failure restart around 0.75–1 s.

The template keeps a light neutral ground until a mock-up shows that a
[author]-style mid-grey ground improves readability.

Use `python -m scripts.reference_games` to reproduce the analysis. Keep all
downloaded exports and derived images in the ignored local workspace.

## Re-evaluate when

- A live Construct preview of the template's outline and shadow, at both the
  design resolution and a small embedded size, reads worse than the mock-ups.
- Audio timing and real input latency can be measured alongside the event data.
- A future Construct release changes the export format, Tween property order or
  runtime reference table.
- A larger sample contradicts the five-level world, one-second restart or
  proportional camera-feedback ranges.
