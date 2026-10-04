# Event Sheet Pitfalls: Moving toward a target

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- 8 Direction moves only by its controls: the arrow keys, *Simulate
  control* and *Set vector X/Y*. It has no action that sets an angle of
  motion or moves toward a position, and it does not steer around
  obstacles; a Solid only blocks it. So an enemy that chases the player
  needs another behavior, chosen by the ground between them:
  - Open ground: Move To, with *Move to object* (the player) in *Every
    tick* or on a short *Every X seconds*, because the action takes the
    target's position when it runs and does not track it afterwards.
    *Set angle of motion* belongs to Move To, not to 8 Direction.
  - Walls in the way: Pathfinding, with *Find path* to the player's
    position every second or so and *Move along path* in *On path found*,
    because the path is calculated in the background and is not ready in
    the tick of *Find path*. Finding a path every tick costs a lot of CPU.
  - Keep 8 Direction only if the enemy must move like the player: each
    tick, *Simulate control* left or right and up or down by comparing the
    positions.
  [manual: behavior-reference/8-direction.md, move.md, pathfinding.md]
- Follow does not chase. It replays the target's recorded movement after a
  time or distance delay, so the follower takes the path the target took
  and never cuts toward it. Use it for a trailing companion or a snake's
  body, not for an enemy.
  [manual: behavior-reference/follow.md]
