# Bars, gauges and life counters

How the official examples show a number as a bar, a gauge or a row of icons,
and which object the art calls for. Read from the 89 objects named bar, meter,
heart, life, energy, power or progress in 55 examples and the events that drive
them (`.local/docs/evidence/example-style-survey/survey_bars.py`, clone
`3c31b236`, 2026-09-23). Design first with
[event-sheet-thinking.md](../event-sheet-thinking.md); this page is the row
"a number shown as a bar" opened up.

## One property from one expression

The value sets one property of one object, in one action, wherever the value
changes: `Set width to value / max × LENGTH`.

- berry-harvester `ProgressBar: Set width to min(quota/objective * 240, 240)`
- jetpack `FuelBar: Set width to PlayerCollision.FuelLeft / JetpackFuelTankSize * FuelBarScaledWidth`
- wood-chopping `TimeBar: Set width to Bar / 100 * 384`
- template-monk-fight `cHPBar: Set width to clamp((cHPBar.maxWidth / Character.hpMax) * Character.hp, 0, cHPBar.maxWidth)`

`LENGTH` is a global constant (`POWERBARLENGTH = 68`, `FuelBarScaledWidth =
64`) or the frame's width; the expression clamps, so a value past its maximum
never grows past the frame. The origin of the bar sits on the edge it grows
from: (0, 0) or (0, 0.5) on every filling bar in the corpus, (1, 0.5) on a
cover that hides from the right (flatland-golf `PowerBarCover`), (0.5, 1) on a
meter that rises (test-your-might `MightLevelBar`). An origin of 0.5 grows both
ways from the middle.

A change slides with Tween on the same property: car-selection-screen
`StatusBar: Tween "ChangeWidth" property Width to (14 * Units) + 4 in 0.25
seconds (easeinoutsine)`, bamboo-strike `TimerBar`, dig-the-way `EnergyBar`.
A damage ghost is a second, wider bar behind the first that is set later:
template-monk-fight `cUnderHPBar` and `eUnderHPBar`, shown for a second by a
Timer. Not a per-tick lerp of the width.

## The object the art calls for

| Art | Object for the fill | Why | Examples |
|-----|---------------------|-----|----------|
| None, a flat colour or a repeating pattern | Tiled Background, over a second Tiled Background or Sprite as the frame | *Set width* repeats the image and never stretches it; 27 of the corpus's bars are Tiled Backgrounds | berry-harvester `ProgressBar` + `ProgressBarBackground`, coral-savior `OxygenAmount` (a 16×2 image) in `Oxygen`, jetpack `FuelBar` in a 9-patch `FuelBarBackground` |
| A painted fill the bar must reveal, not squash: a gradient, a pattern with detail | Tiled Background with the painting as its image, the object as wide as the painting at full; *Set width* then shows the left part of it | The image repeats instead of stretching, so below its own width the object is a cut of it | the Tiled Background rule above; no example paints a gradient fill |
| The same, with the frame's shape irregular | A cover from the empty end: a Tiled Background in the background's colour, origin (1, 0.5), `Set width to lerp(LENGTH, 0, value)`, the painted fill and a frame under and over it | The painting never moves; the cover shrinks | flatland-golf `PowerBarColors` (Sprite, the full gradient), `PowerBarCover` (Tiled Background, 5×5 image), `PowerBarFrame` |
| A fill that should show only where the container's art already is | A plain Tiled Background fill with blend mode *Source atop*, the container drawn first, on a layer with *Force own texture* | The fill is drawn only on pixels the layer already has | artillery-war `PowerMeter`, origin (0, 0.5), `Set width to 1 + 3 * Arrow.CannonPower`, layer `Interface` with *Force own texture* |
| A bar with caps, borders or rounded ends that must survive any length | 9-patch for the fill and for the frame, *Set size* or Tween *Width* | The corners keep their size, the middle stretches or tiles; the manual: "useful for representing things like progress bars with special artwork at the end of the bar", and the width must not go negative | car-selection-screen `StatusBar` in `StatusBarBackground`, both 9-patch, Tween *Width* 0.25 s |
| A count of icons: hearts, stars, bullets | One Tiled Background of the full icon whose width is `count × icon width`, over one Tiled Background of the empty icon at `max × icon width` | Two objects for any count, a constant to change the maximum | tower-defense-game `Hearts` and `HeartsBackground`, 8×8 tiles, `Set width to 8 * PlayerBase.HeathPoints` |
| The same, when each icon animates on its own | Instances of one Sprite with an index variable, picked by `Pick by evaluating Life.lifeID > lives` and destroyed or tweened away; or one Sprite whose animation frame is the count | Each icon can fall, flash or fade; a frame strip needs one image per count | family-tree `Life` (Tween Y then destroy) with `LifeSpot` under it, tile-matcher `Life` |
| A gauge with a needle | A needle Sprite, *Set angle* from the value | One object, one angle | rally-drifting `SpeedometerPointer` |
| A ring or arc that fills | No example drives one. Cheapest is a frame strip, one frame per step, animation frame set from the value. For any fraction: a mesh on a ring texture, *Set mesh size* then *Set mesh point* for the outer and inner points along the arc (`plugins/_common.json`), or two half-ring Sprites rotated behind a cover. Blend-mode masks (*Destination out* holes) are used in the corpus for light and darkness, not for bars | | |

The `progressbar` plugin is a form control, a DOM element over the canvas:
the corpus uses it for a file transfer, not in a game HUD.

## Where it goes

On the UI layer at parallax 0, the fill and its frame in one place; the
frame's size in grid units and the fill's `LENGTH` a constant of the sheet
(`prompts/event-sheet-style.md`, *Project*). In a generator this page is one
call: `hud_bar(frame, fill, where, length)` of the skill's template places
the frame by `anchor()` and the fill inside it with its origin on the left,
`bar_types()` and `bar_images()` make the two Tiled Backgrounds (9-patches
with `caps=True`), and `set_width(fill, bar_width(value, maximum, LENGTH))`
or `tween_width()` is the one action the value drives.
