# Feel

The table below applies the Native first table of
[event-sheet-thinking.md](../event-sheet-thinking.md) to the effects the
player notices first. Each row names its source in the Example column: an
official example, or `observed` for what a game project settled in its r504
preview, 2026-09-30 to 2026-10-05. Before adding the sounds that go with
these effects, read [sound.md](sound.md), which says which sounds play,
when and how loud.

| Need | Use | Example |
|------|-----|---------|
| Screen shake on impact | Scroll To *Shake* with *Reducing magnitude*, the duration tied to the effect (`Timeline.TotalTime(tag)`). The event sets the magnitude: about 0.5, 1 and 2 % of the viewport's short side for a crit, a merge and a kill | cave-bridge, three-cups; observed |
| Hit stop, slow motion | *Set time scale* 0.1, *Wait*, *Set time scale* 1. A *Tween (value)* driving *Set time scale* gives a smooth ramp. A scheduled sound still plays on time, but a timeline with *Use system timescale* on stops with the game ([pitfalls: Timeline](../pitfalls/timeline.md)) | segmented-boss-fight, samuroof, eventide |
| Squash, pop, bounce on impact | Tween *Size* or *X Scale*/*Y Scale* from `On collision`. *Ping pong* makes a pop that returns, and an *In Back* ease a wind-up | gold-mining, cannon-launch, gravity-portal |
| Squash that fires again before the last one has returned | Record the rest width and height at creation. Set the deformation at once and tween back to the rest size, so repeats never shift it. The ease shows the material: `easeoutelastic` over 0.5 s wobbles like jelly, `easeoutback` over 0.3 s bounces once like something hard | observed |
| Several effects on one body at once: squash, breath, charge, lift, flash, a lunge | Each effect is a *Tween (value)* channel from its full amount to 0. Every tick the body's size, position, angle and brightness are recomputed from rest as a product or sum of the channels. A new effect starts while the last still fades and nothing jumps. A channel that ended reads 0 and has no effect ([pitfalls: Tween](../pitfalls/tween.md)). An idle breath is Sine in value-only mode, read into the same sum, so only the sum sets the Size property | observed |
| A keyframed motion of one part: a weapon swing, a wind-up and strike, a skill | A Timeline on the part as a hierarchy child, *Relative* tracks that start and end at 0, so it adds to what the parent's channels do and repeats without shifting. Each instance has a copy tagged with its UID. The weight is in custom Eases from the Eases folder on each keyframe, not in numbers in events. Use *Set time* 0 before a replay, and to take a finished timeline's offsets off the part ([pitfalls: Timeline](../pitfalls/timeline.md)) | observed |
| Hit feedback | Flash *Flash* from `On collision`; Tween *Color* to `rgbEx(...)` and back; a Brightness effect set to its peak at once and tweened back to 100 | bewitched-torches, turret-predictive-aim; pinball, shifting-dungeon; observed |
| Telegraph what a drop will do | While the dragged instance hovers a target that will take it, the target wobbles (two sines summed into its angle) and brightens, and the slot shows its highlight frame. The slot is larger than the piece, so the highlight shows around it | observed |
| A dragged thing that lags and overshoots like a spring | An invisible base takes Drag & Drop, the drop test and the snap. The visible parts, hierarchy children of a follower, follow it on a damped spring stepped every tick and lean by how far they lag. Step the spring implicitly (acceleration from the lag, then divide the velocity by `1 + damping·dt + stiffness·dt²`), or the lag differs between 30 and 144 fps. Moving the base itself breaks the drag: Drag & Drop writes its position only while the pointer moves | observed |
| A choreographed sequence over several objects: opening, level clear, a bridge rebuilding | Timeline *Play*, *Set instance* for runtime-created objects. Branches that must start together go in sibling sub-events, since a *Wait* delays the sub-events after it | cave-bridge, 17 examples; observed |
| Camera that follows, clamped to a zone | Scroll To on the target if plain following is enough. For bounds and smoothing, System *Scroll to position* with `lerp(scrollx, clamp(target, zone edges), …)` every tick | dynamic-camera-system |
| A chapter or stage title card | The order: dim, banner, a title that drops and lands, a shake with a burst on the landing, a hold, then everything leaves together. One tuned set: dim the play area to 55 % opacity in 0.2 s, and open a banner from the centre, its width tweened from 0 in 0.25 s with `easeoutquart`. 0.15 s after the card's first line appears, the title drops from 2.8 times its rest scale to 1 in 0.22 s with `easeinquad` and fades in as it falls. On landing it squashes to 0.88 and springs back with `easeoutback` over 0.35 s. The screen shakes 6 px for 0.35 s, and stars burst from the title. 1.8 s after the card opened, title, banner and dim rise and fade in 0.35 s with `easeinquad`, and the next stage enters as they leave. Each phase of the title's scale is a *Tween (value)* channel, multiplied every tick ([pitfalls: Tween](../pitfalls/tween.md)) | observed |
| Fade between layouts | A *Fader* sprite on the parallax-0 layer, Tween opacity, *Wait for previous actions*, *Go to layout* | avalanche, airborne-explorer |

[manual: behavior-reference/scroll-to.md "Shake",
system-reference/system-actions.md "Set time scale", behavior-reference/tween.md,
behavior-reference/flash.md, behavior-reference/sine.md,
project-primitives/timelines.md, interface/dialogs/ease-editor.md]
