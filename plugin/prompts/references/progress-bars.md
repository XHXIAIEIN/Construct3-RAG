# Bars, gauges and life counters

This page covers how the official examples show a number as a bar, a gauge or
a row of icons, and the object the art calls for. Design first with
[event-sheet-thinking.md](../event-sheet-thinking.md); this page expands that
file's row "a number shown as a bar".

## One property from one expression

Wherever the value changes, one action sets one property of one object:
`Set width to value / max × LENGTH`.

- berry-harvester `ProgressBar: Set width to min(quota/objective * 240, 240)`
- jetpack `FuelBar: Set width to PlayerCollision.FuelLeft / JetpackFuelTankSize * FuelBarScaledWidth`
- wood-chopping `TimeBar: Set width to Bar / 100 * 384`
- template-monk-fight `cHPBar: Set width to clamp((cHPBar.maxWidth / Character.hpMax) * Character.hp, 0, cHPBar.maxWidth)`

`LENGTH` is a global constant (`POWERBARLENGTH = 68`, `FuelBarScaledWidth =
64`) or the frame's width. Clamp the expression, as berry-harvester and
template-monk-fight do, so a value past its maximum never grows the bar past
the frame. The bar's origin sits on the edge it grows from. Every filling bar
in the examples has (0, 0) or (0, 0.5). A cover that hides from the right has
(1, 0.5) (flatland-golf `PowerBarCover`), and a meter that rises has (0.5, 1)
(test-your-might `MightLevelBar`). At origin 0.5 the bar grows both ways from
the middle.

To slide a change, Tween the same property: car-selection-screen `StatusBar:
Tween "ChangeWidth" property Width to (14 * Units) + 4 in 0.25 seconds
(easeinoutsine)`, bamboo-strike `TimerBar`, dig-the-way `EnergyBar`. A damage
ghost is a second, wider bar behind the first that is set later:
template-monk-fight `cUnderHPBar` and `eUnderHPBar`, shown for a second by a
Timer. Use a Tween or a ghost bar, not a per-tick lerp of the width.

The ghost can be derived from the fill every tick. `Ghost: Set width to
max(Ghost.Width, Fill.Width)` keeps it at least as wide as the fill, so a
loss leaves the old width showing and a gain never leaves it shorter. One
event with the conditions `Ghost: Compare width > Fill.Width`, `Frame: NOT
Timer "ghost" is running` and `Ghost: NOT Tween "ghost" is playing` starts a
0.5 s Timer, and its *On timer* tweens the ghost's width to `Fill.Width` in
0.4 s. [observed in a minimal project, stable editor preview, 2026-10-07:
the *On timer* event was written above the start event; two hits 0.7 s
apart, the second while the ghost was closing, ended with the ghost equal to
the fill on every bar]

A second value drawn inside the fill, such as poison that will drain the
health or damage not yet applied, is a second bar of the same object type
over the fill, origin on the left, with `X` at `frame.X + (hp - poison) /
maxHp × LENGTH` and `width` at `poison / maxHp × LENGTH`, so it ends
where the fill ends. Clamp the poison to `hp - 1` where it is added, so
draining alone never kills. Drain it with a Timer: *On timer* takes 1 from
both values and restarts the timer with the duration of the current
amount, shorter at a higher amount, rather than an accumulator compared
against a ladder of thresholds every tick. [a studied project, 2026-10-06]

A heal on its way is a part of the same kind as the poison part. It starts
where the fill ends, at `frame.X + hp / maxHp × LENGTH`, has the width
`min(incomingHeal, maxHp - hp) / maxHp × LENGTH` and is drawn behind the fill.
Incoming damage is the poison part with the width `min(incomingDamage, hp) /
maxHp × LENGTH`, drawn over the fill in a dark colour at 55 % opacity so that
the fill's colour still shows. Both numbers are instance variables of the
bar, and a Timer lands them: `hp = clamp(hp - incomingDamage + incomingHeal,
0, maxHp)`, then both are set to 0. [observed in a minimal project, stable
editor preview, 2026-10-07]

A colour by tier is one *Set color* on a white Tiled Background:
`share < LOW ? c1 : (share < WARN ? c2 : c3)`, with `share` as `hp / maxHp`
and a colour expression for each of `c1` to `c3`. It evaluates for each bar,
so the tiers need no sub-events and no *Else*. Write `<`, not `<=`, because a
share exactly on a threshold then stays in the upper tier. [observed in a
minimal project, stable editor preview, 2026-10-07: three bars at the same
time showed green, yellow and red as their hp differed, with red below 0.25
and yellow below 0.5, and shares of exactly 0.5 and exactly 0.25 stayed in the
upper tier]

## Ticks at a fixed value step

A Tiled Background's *Set image scale X* stretches the tile image, so it
changes the tile pitch and the thickness of a line drawn in the tile
together, and ticks spaced by value cannot keep one width that way. Make each
tick a Sprite and create them in a loop. This is one custom action on the
frame, with the frame's origin on its left edge, `step` the value between two
ticks and `pad` the thickness of the frame's border:

1. Pick the frame's old ticks with *Pick children* and destroy them.
2. In a second event, put the condition `ceil(Frame.maxHp / step) - 1 >= 1`
   before `For i = 1 to ceil(Frame.maxHp / step) - 1`, because *For* counts
   down when its end is below its start
   ([pitfalls/expressions.md](../pitfalls/expressions.md)). Put *For each*
   `Frame` first, so that each frame reads its own `maxHp`.
3. In the loop, create a tick on the frame's layer, with `Frame.LayerName` as
   the layer parameter, at X `round(Frame.X + pad + (Frame.Width - 2 * pad) *
   loopindex("i") * step / Frame.maxHp)`. Set its height from the frame's
   inner height, then *Add child* of the frame with destroy with parent on.

Call the action at layout start and whenever the maximum changes. For a
thicker tick at every 1000, set the width to `loopindex("i") * step % 1000 =
0 ? 4 : 2`. [manual: plugin-reference/tiled-background.md "Set image X
scale"; observed in a minimal project, stable editor preview, 2026-10-07:
with 444 px of bar and a step of 100, a maximum of 3000 gave a
spacing of 14.8 px, and bars with a maximum of 300, 1000 and 3000 held 2, 9
and 29 ticks; after 300 was added to each maximum they held 5, 12 and 32]

## The object the art calls for

| Art | Object for the fill | Why | Examples |
|-----|---------------------|-----|----------|
| None, a flat colour or a repeating pattern | Tiled Background, over a second Tiled Background or Sprite as the frame | *Set width* repeats the image and never stretches it. 27 of the examples' bars are Tiled Backgrounds | berry-harvester `ProgressBar` + `ProgressBarBackground`, coral-savior `OxygenAmount` (a 16×2 image) in `Oxygen`, jetpack `FuelBar` in a 9-patch `FuelBarBackground` |
| A painted fill the bar must reveal, not squash: a gradient, a pattern with detail | Tiled Background with the painting as its image, as wide as the painting when full. *Set width* then shows the left part of it | The image repeats instead of stretching, so below its own width the object is a cut of it | the Tiled Background rule above; no example paints a gradient fill |
| The same, with the frame's shape irregular | A cover from the empty end: a Tiled Background in the background's colour, origin (1, 0.5), `Set width to lerp(LENGTH, 0, value)`, the painted fill under it and a frame over it | The painting never moves; the cover shrinks | flatland-golf `PowerBarColors` (Sprite, the full gradient), `PowerBarCover` (Tiled Background, 5×5 image), `PowerBarFrame` |
| A fill that should show only where the container's art already is | A plain Tiled Background fill with blend mode *Source atop*, drawn after the container, on a layer with *Force own texture* | The fill is drawn only on pixels the layer already has | artillery-war `PowerMeter`, origin (0, 0.5), `Set width to 1 + 3 * Arrow.CannonPower`, layer `Interface` with *Force own texture* |
| A bar with caps, borders or rounded ends that must survive any length | 9-patch for the fill and for the frame, *Set size* or Tween *Width* | The corners keep their size, and the middle stretches or tiles. The manual calls it "useful for representing things like progress bars with special artwork at the end of the bar". The width must not go negative | car-selection-screen `StatusBar` in `StatusBarBackground`, both 9-patch, Tween *Width* 0.25 s |
| A count of icons: hearts, stars, bullets | One Tiled Background of the full icon at `count × icon width`, over one Tiled Background of the empty icon at `max × icon width` | Two objects show any count, and one constant changes the maximum | tower-defense-game `Hearts` and `HeartsBackground`, 8×8 tiles, `Set width to 8 * PlayerBase.HeathPoints` |
| The same, when each icon animates on its own | Instances of one Sprite with an index variable, picked by `Pick Life by evaluating Life.lifeID > lives` and destroyed or tweened away. Or one Sprite whose animation frame is the count | Each icon can fall, flash or fade. A frame strip needs one image per count | family-tree `Life` (Tween Y then destroy) with `LifeSpot` under it, tile-matcher `Life` |
| Icons that show a fraction: a quarter heart, half a shield | A row of icon Sprites, and over it a cover: a Sprite of a 1×1 image in the empty colour, blend mode *Source in*, origin (1, 0) at the row's right end, on a layer with *Force own texture*. Tween its *Width* to `(max − value) × (icon width + gap)` | The cover changes only the icon pixels under it, so one rectangle empties any fraction of any number of icons. A second cover with a slower tween is the damage ghost | No official example; a user-shared project, 2026-10-06: `ui_hpbar` (black, *Source in*) over a row of `ui_heart` |
| A gauge with a needle | A needle Sprite, *Set angle* from the value | One object, one angle | rally-drifting `SpeedometerPointer` |
| A ring or arc that fills | A frame strip, one frame per step, its animation frame set from the value. For any fraction, a mesh on a ring texture: *Set mesh size*, then *Set mesh point* for the outer and inner points along the arc (`plugins/_common.json`). Or two half-ring Sprites rotated behind a cover | The frame strip is the cheapest; the mesh shows any fraction | None drives one. The examples use blend-mode masks (*Destination out* holes) for light and darkness, not for bars |

## A bar on each of many objects

Each enemy or player with its own bar needs the bar to follow its object and
go with it. Two ways:

- **Container.** Put the bar in the object's container. It is created,
  picked and destroyed with its object, and an event on the object reaches
  its own bar. Through a family, pick the type first
  ([pitfalls/picking.md](../pitfalls/picking.md), containers).
- **Hierarchy.** Make the HUD a child of the object, in the layout or with
  *Add child*. It moves with the object and is destroyed with it. Initialise
  it in *On hierarchy ready*
  ([pitfalls/creating-objects.md](../pitfalls/creating-objects.md)).

  To update it, keep `hp` and `maxHp` on a family of the objects. A custom
  action on the family changes them, then calls the HUD's `Update` through
  *Pick children*. `Update` compares `PickedCount` of its icons with the
  value, creates the missing icons and destroys the extra ones. To stagger
  their appear tween, start a Timer on each icon for `loopindex × step`
  seconds. [a user-shared project, 2026-10-06]

Use the container for one bar per object. Use the hierarchy for a HUD of
several parts whose count changes.

A child is placed in layout coordinates, so on a HUD layer with parallax 0
it follows its object only while the camera stands still. To keep a bar on
a UI layer over a moving object, move it every tick. eventide does this for
its player's bar: the frame goes to `3DCamera.LayerToLayerX("World",
"InGameUI", Player.X, Player.Y, Player.ZElevation) - 48` and the matching
`LayerToLayerY`, and the fill is the frame's child.

The `progressbar` plugin is a form control, a DOM element over the canvas.
The examples use it for a file transfer, not in a game HUD.

## Where it goes

Put the fill and its frame together on the UI layer at parallax 0. Size
the frame in grid units, and make the fill's `LENGTH` a constant of the
sheet ([new-project.md](new-project.md)). In a generator, this is one
call of the skill's template: `hud_bar(frame, fill, where, length)` places
the frame by `anchor()` and the fill inside it with its origin on the
left. `bar_types()` and `bar_images()` make the two Tiled Backgrounds
(9-patches with `caps=True`). The value drives one action:
`set_width(fill, bar_width(value, maximum, LENGTH))` or `tween_width()`.
