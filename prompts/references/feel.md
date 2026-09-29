# Feel

Screen shake, hit stop, squash, hit flash, a choreographed sequence, a
following camera and a fade between layouts, as the official examples
build them. It carries the Native first table of
[event-sheet-thinking.md](../event-sheet-thinking.md) over to the effects.

The same rule for what the player notices first. Each row is what the
official examples do.

| Need | Use | Example |
|------|-----|---------|
| Screen shake on impact | Scroll To *Shake*, *Reducing magnitude*, duration tied to the effect (`Timeline.TotalTime(tag)`) | cave-bridge, three-cups |
| Hit stop, slow motion | *Set time scale* 0.1, *Wait*, *Set time scale* 1; a *Tween (value)* driving *Set time scale* for a smooth ramp | segmented-boss-fight, samuroof, eventide |
| Squash, pop, bounce on impact | Tween *Size* or *X Scale*/*Y Scale* from `On collision`, *Ping pong* for a pop that returns, an *In Back* ease for a wind-up | gold-mining, cannon-launch, gravity-portal |
| Hit feedback | Flash *Flash* from `On collision`; Tween *Color* to `rgbEx(...)` and back | bewitched-torches, turret-predictive-aim; pinball, shifting-dungeon |
| A choreographed sequence over several objects: opening, level clear, a bridge rebuilding | Timeline *Play*, *Set instance* for runtime-created objects | cave-bridge, 17 examples |
| Camera that follows, clamped to a zone | Scroll To on the target when plain following is enough; System *Scroll to position* with `lerp(scrollx, clamp(target, zone edges), …)` every tick for bounds and smoothing | dynamic-camera-system |
| Fade between layouts | A *Fader* sprite on the parallax-0 layer, Tween opacity, *Wait for previous actions*, *Go to layout* | avalanche, airborne-explorer |

[manual: behavior-reference/scroll-to.md "Shake",
system-reference/system-actions.md "Set time scale", behavior-reference/tween.md,
behavior-reference/flash.md, project-primitives/timelines.md]
