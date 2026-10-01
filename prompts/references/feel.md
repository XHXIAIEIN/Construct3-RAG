# Feel

Screen shake, hit stop, squash, hit flash, a choreographed sequence, a
following camera, a fade between layouts, a keyframed motion of one part,
effects layered on one body, a dragged thing that lags: as the official
examples build them, and as a game project settled them in a preview. It
carries the Native first table of
[event-sheet-thinking.md](../event-sheet-thinking.md) over to the effects.
What plays with them, when and how loud, is in [sound.md](sound.md).

The same rule for what the player notices first. Each row names its
source: an official example, or `observed` for a game project's r504
preview, 2026-09-30 to 2026-10-01.

| Need | Use | Example |
|------|-----|---------|
| Screen shake on impact | Scroll To *Shake*, *Reducing magnitude*, duration tied to the effect (`Timeline.TotalTime(tag)`); the magnitude graded by the event, about 0.5, 1 and 2 % of the viewport's short side for a crit, a merge and a kill | cave-bridge, three-cups; observed |
| Hit stop, slow motion | *Set time scale* 0.1, *Wait*, *Set time scale* 1; a *Tween (value)* driving *Set time scale* for a smooth ramp. A scheduled sound still plays on time; a timeline with *Use system timescale* on stops with the game ([pitfalls: Timeline](../pitfalls/timeline.md)) | segmented-boss-fight, samuroof, eventide |
| Squash, pop, bounce on impact | Tween *Size* or *X Scale*/*Y Scale* from `On collision`, *Ping pong* for a pop that returns, an *In Back* ease for a wind-up | gold-mining, cannon-launch, gravity-portal |
| Squash that fires again before the last one has returned | Record the rest width and height at creation; set the deformation at once, tween back to the rest size, so repeats never drift. The ease is the material: `easeoutelastic` over 0.5 s wobbles like jelly, `easeoutback` over 0.3 s bounces once like something hard | observed |
| Several effects on one body at once: squash, breath, charge, lift, flash, a lunge | Each effect a *Tween (value)* channel from its full amount to 0; every tick the body's size, position, angle and brightness are recomputed from rest as a product or sum of the channels. A new effect starts while the last is still fading and nothing jumps; a channel that ended reads 0 and drops out ([pitfalls: Tween](../pitfalls/tween.md)). An idle breath is Sine in value-only mode, read into the same sum, so it never fights the squash for the Size property | observed |
| A keyframed motion of one part: a weapon swing, a wind-up and strike, a skill | A Timeline on the part as a hierarchy child, *Relative* tracks that start and end at 0, so it layers over whatever the parent's channels do and repeats without drift; a copy per instance tagged with its UID; the weight in custom Eases from the Eases folder on each keyframe, not in numbers in events. *Set time* 0 before a replay, and to take a finished timeline's offsets off the part ([pitfalls: Timeline](../pitfalls/timeline.md)) | observed |
| Hit feedback | Flash *Flash* from `On collision`; Tween *Color* to `rgbEx(...)` and back; a Brightness effect set to its peak at once and tweened back to 100 | bewitched-torches, turret-predictive-aim; pinball, shifting-dungeon; observed |
| Telegraph what a drop will do | While the dragged instance hovers a target that will take it, the target wobbles (two sines summed into its angle) and brightens, and the slot shows its highlight frame; the slot is larger than the piece so the hint shows around it | observed |
| A dragged thing that lags and overshoots like a spring | An invisible base takes Drag & Drop, the drop test and the snap; the visible parts, hierarchy children of a follower, chase it with a damped spring stepped every tick, and lean by how far they lag. Step the spring implicitly (acceleration from the lag, then divide the velocity by `1 + damping·dt + stiffness·dt²`), or the lag differs between 30 and 144 fps. Moving the base itself breaks the drag: Drag & Drop writes its position only while the pointer moves | observed |
| A choreographed sequence over several objects: opening, level clear, a bridge rebuilding | Timeline *Play*, *Set instance* for runtime-created objects; branches that must start together go in sibling sub-events, since a *Wait* holds the sub-events after it | cave-bridge, 17 examples; observed |
| Camera that follows, clamped to a zone | Scroll To on the target when plain following is enough; System *Scroll to position* with `lerp(scrollx, clamp(target, zone edges), …)` every tick for bounds and smoothing | dynamic-camera-system |
| Fade between layouts | A *Fader* sprite on the parallax-0 layer, Tween opacity, *Wait for previous actions*, *Go to layout* | avalanche, airborne-explorer |

[manual: behavior-reference/scroll-to.md "Shake",
system-reference/system-actions.md "Set time scale", behavior-reference/tween.md,
behavior-reference/flash.md, behavior-reference/sine.md,
project-primitives/timelines.md, interface/dialogs/ease-editor.md]
