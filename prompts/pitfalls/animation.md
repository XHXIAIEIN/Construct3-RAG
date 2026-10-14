# Event Sheet Pitfalls: Animation

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- Image point index 0 is the origin. The first image point added is index
  1, and `ImagePointCount` does not count the origin. A loop over every
  image point therefore runs from 1 to `ImagePointCount` and reads
  `ImagePointX(loopindex)`. Starting at 0 reads the origin and misses the
  last point. A name, as in `ImagePointX("P1")`, reads the same point
  whatever the order. [manual:
  interface/animations-editor.md "the first image point (number 0) is
  always the origin"; scripting/scripting-reference/plugin-interfaces/sprite.md
  "getImagePointX"; plugin-reference/sprite.md "ImagePointX" says only
  zero-based. observed: r495.2 preview, a Sprite at X 400, 100 px wide,
  origin centred, points P1 and P2 at its left and right edges:
  `ImagePointCount` 2, index 0 400, 1 350, 2 450, 2026-09-23]
- *Set animation* to the animation already playing does nothing, even when
  set to play from the beginning. So an `anim` variable, compared before
  every *Set animation* to keep the animation from restarting, is not
  needed. Set the animation from the state in one event. To restart it,
  use *Start animation* from the beginning. [manual:
  plugin-reference/sprite.md "Set animation"; observed in a game
  project, 2026-09-22]
- A 3D model's *Play* of the clip already playing leaves it where it is,
  whatever progress it is given, and so do *Set progress* and the script's
  `animationProgress`. Each clip keeps its own clock while another plays,
  so a clip played again also goes on from that clock. An attack that
  plays its clip every interval while the clip is longer than the interval
  shows a swing only every other time. To start a playing clip from 0,
  stop it first: in r505, `setAnimationPlaying(false, clip)` and then
  `play(clip, 0, transition)`. *Play* cuts to the new clip in one tick
  unless its *Transition duration* (r505) is set, and a clip cannot cross
  over into itself. So consecutive attacks that should blend take turns
  between two copies of the clip. [observed in a game project, r505 beta
  preview, 2026-10-14: a 2.0 s attack clip played every 1.6 s started at
  1.603 s on every second attack, a frame-by-frame capture showed the
  sword jump 57 to 72 px in one tick at each clip change, and after the
  changes above every attack started at 0 and no frame jumped]
- Frames used as looks rather than as an animation need the animation's
  *Speed* at 0. A one-frame animation at the default speed 5 shows no
  motion. But with more frames, every created instance plays through them
  and stops on the last, whatever *Set frame* chose. [observed in a
  game project, r503 preview, 2026-09-28: frames 0 to 2 of a non-looping
  animation at speed 5, every enemy ended on frame 2 until speed was 0]
- *Set frame* to a frame of another image size resizes the instance by the
  ratio of the two images and keeps its scale. It also swaps in the new
  frame's collision polygon and origin. A frame drawn wider with
  transparent margins therefore widens what the instance overlaps. A boss
  frame three lanes wide is hit by every lane's range, with no change to
  the targeting events. [runtime: exported c3runtime.js r503, Sprite
  `_OnFrameChanged` scales width and height by new/old image size and calls
  `SetSourceCollisionPoly`; observed in a game project, r503 preview,
  2026-09-28: a 72 px enemy set to a 520×216 frame became 260×108 and
  overlapped three 40 px lane ranges]
