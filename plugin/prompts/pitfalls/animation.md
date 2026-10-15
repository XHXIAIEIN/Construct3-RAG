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
  set to play from the beginning. So set the animation from the state in
  one event, without an `anim` variable compared before every *Set
  animation* to keep the animation from restarting. To restart it, use
  *Start animation* from the beginning. [manual:
  plugin-reference/sprite.md "Set animation"; observed in a game
  project, 2026-09-22]
- A 3D model's *Set progress*, the script's `animationProgress` setter and
  `setAnimationProgress` change nothing while the clip plays or is paused,
  although the manual says they set the progress of the current animation.
  They work once the clip is stopped or has finished. In r505, *Play* of a
  playing clip also leaves it where it is, whatever progress it is given.
  An attack that plays a clip longer than its interval then shows a swing
  only every other time. r506 starts the clip at the given progress. To
  restart a clip in r505 and r506, stop it with *Stop*, the script's
  `stop()` or `setAnimationPlaying(false, clip)`, then *Play* it. A clip
  stays playing after *Play* switches to another clip, and *Stop* and
  `stop()` then stop only the clip played last, although the description
  of *Stop* says it stops any animations: *Is playing* with the first
  clip's name and `isAnimationPlaying` stay true, and so does the script's
  `isPlaying`. *Play* cuts to the new clip in one tick unless its
  *Transition duration* (r505) is set, and a clip cannot cross over into
  itself. So consecutive attacks that should blend take turns between two
  copies of the clip. In r505 and r506 the script's
  `getAnimationProgress(name)` throws a TypeError; read
  `animationProgress`. [manual: plugin-reference/3d-model.md "Set
  progress"; scripting/scripting-reference/plugin-interfaces/3d-model.md
  "animationProgress"; schema r506: *Stop* "Stop any animations"; observed
  in a minimal project with a generated glTF, r505 beta and r506,
  2026-10-14: progress stayed at 0.399 after each setter, *Set progress*
  with the clip named included, and in r505 also after *Play* with
  progress 0 or 0.25, which in r506 gave 0 and 0.25; after *Play* "Rest",
  *Play* "Swing" and then *Stop* or `stop()`, `isAnimationPlaying("Rest")`
  stayed true, and in r506 *Is playing* "Rest" too, and `isAnimationPlaying("Swing")` read false; and in a game
  project, r505 beta, 2026-10-14: a 2.0 s attack clip played every 1.6 s
  started at 1.603 s on every second attack, and a frame-by-frame capture
  showed the sword jump 57 to 72 px in one tick at each clip change]
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
