# Attack feel

An attack feels right when its wind-up, its animation, its sounds and its
hit effect land on the same moments. This file gives the numbers and the
Construct way for each, for an action game with a click-to-attack hero, a
melee swing or a ranged shot. For the general effects (shake, hit stop,
squash), read [feel.md](feel.md), and for the loudness and the mix,
[sound.md](sound.md).

The numbers come from a studied published action game. Each rule ends
with its evidence:

- `data`: read from that game's data files (its gameplay settings, attack
  and animation data, sound banks, effect and UI definitions);
- `documented`: stated in the game's player-written reference;
- `derived`: computed from values in the data;
- `inferred`: a reading that the data does not state, so a starting point
  to tune.

A distance is given as a multiple of the hero's move speed, because the
game measures in its own units. The Construct way in each rule is written
from the schemas. It has not been played in a preview unless the rule
says so.

## The timing of one attack

- The attack cycle is `1 / attackSpeed`. The wind-up runs from the start
  of the attack to the hit, and is the cycle times a wind-up share. Use a
  share of 18 to 20 % by default. Use 25 to 30 % for a heavy weapon, and
  16 to 18 % for a ranged or caster hero. [derived]
- A base attack speed of 0.625 to 0.7 a second gives a cycle of 1.4 to
  1.6 s and a wind-up at that speed, `baseWindup`, of 0.25 to 0.35 s.
  [derived]
- Deal the damage, or launch the projectile, when the wind-up ends, not
  when the animation ends. A melee hit lands at that moment, with no delay
  for distance. [data, derived]
- When the attack speed rises, the wind-up shrinks with the cycle. To keep
  the weight of a heavy weapon, shrink it by half as much:
  `windup = baseWindup + 0.5 × (cycle × share − baseWindup)`.
  [documented, data]
- Clamp the attack speed between 0.2 and 3.0 a second. Above about 1.6 a
  second (1.3 to 2.1, by hero), switch to a shorter attack animation
  rather than speed up the long one further. [documented, data]
- In Construct, run the attack on a Timer behavior. When the attack
  starts, *Start timer* "windup" for the wind-up and "cycle" for the
  cycle. *On timer* "windup" deals the damage or creates the projectile.
  *On timer* "cycle" starts the next attack while the target is in range.
  [inferred]
- An empowered strike from a skill has its own wind-up, about 0.30 to
  0.34 s, which shrinks only a little with attack speed. Keep it as its
  own number, not as a share of the cycle. [derived]

## The attack animation

- Make one animation per attack that holds the wind-up, the release and
  the recovery, not three animations. In one studied 60-frame attack at
  30 fps, the release is frame 10 and the 50 frames after it are the
  recovery. [data]
- Put the release frame where `baseWindup` ends: frame 8 to 11 at 30 fps.
  Most of the game's attacks match this within ±20 %. [derived]
- Scale the playback so the release frame lands on the current wind-up:
  Sprite *Set speed* to `Self.OriginalAnimationSpeed * baseWindup /
  windup`. Then the next attack cuts the recovery: at about 90 % of it at
  the base attack speed, and at about 45 % at 2 attacks a second.
  [derived, inferred]
- Draw the last frames of the recovery close to the first pose of the
  wind-up, because the next attack can cut the recovery at any frame.
  [inferred]
- Start each attack from its first frame, with no blend from the last
  attack. For a Sprite, *Set animation* to the chosen attack from the
  beginning. If that animation is already playing, *Set animation* does
  nothing, so use *Start animation* from the beginning
  ([pitfalls: Animation](../pitfalls/animation.md)). [data]
- Pick one of two attack animations at random on every attack, 50 % each,
  rather than alternate them: `choose("Attack1", "Attack2")`. To make one
  rarer, weight it: `random(1) < 0.75 ? "Attack1" : "Attack2"`.
  [data, inferred]
- An attack that a state chooses, such as an empowered strike or another
  form, stays outside the random pick. Before the pick, test the state
  variable that names such an attack, and play that attack if it is set.
  [data, inferred]
- When the hero stops attacking, let the attack animation finish, then
  idle: Sprite *On finished* "Attack1" sets the idle animation. A move
  order during the recovery switches to the run animation at once.
  [derived, documented]
- On a 3D model, cut from one attack to the next with no transition. Use
  0.1 s from an attack to idle or run, and from an empowered strike to a
  basic attack. These are the commonest values in the game's animation
  graphs. Set them in 3D Model *Set animation*, *Transition duration*.
  To restart a clip that is playing, read
  [pitfalls: Animation](../pitfalls/animation.md). [derived]

## Cancelling and resets

- A move order during the wind-up cancels the attack: *Stop timer*
  "windup" and carry out the move. [data, documented]
- Ignore move orders in the last 0.033 s of the wind-up and for 0.033 s
  after the release, so a late click does not cancel the hit. At 60 Hz
  this is two ticks. Read the time left as
  `Self.Timer.Duration("windup") - Self.Timer.CurrentTime("windup")`.
  [data, documented]
- A skill that resets the attack does *Stop timer* "cycle", so the next
  attack can start at once. A reset during the wind-up also cancels that
  attack. Do the reset in the skill's own event. A "can reset" flag on the
  skill is then only a label, for filters such as which skills an AI may
  use. [documented, data]
- A skill used during the wind-up acts by its kind:
  1. A skill with a cast time cancels the attack. If the wind-up has less
     than 0.033 s left, the skill waits for the hit.
  2. An instant skill that does not reset leaves the attack running.
  3. A resetting skill cancels the attack, stops the cycle and makes the
     next hit the empowered strike.

  [documented, derived]
- A skill's default cast time is 0.25 s. During it the hero cannot move,
  attack or cast, and the player cannot cancel it. Big skills take 0.4 to
  1.0 s, and buffs, dashes and skills centred on the hero take none. Time
  the effect of the skill by its cast-time timer, and let the animation
  only show it. [data, derived]
- If a skill is pressed during its cooldown or a lock and will be ready
  within 0.5 s, keep the press and cast the skill the moment it is ready.
  Otherwise drop the press. Fast combo skills use a window of 0.05 to
  0.3 s, so store the window as a number on each skill. Never queue a
  basic attack. [data]

## Projectiles

- A ranged basic attack is a homing projectile at a constant speed. It
  deals its damage when it reaches the target, then is destroyed. Its
  speed is 6 to 9 times the move speed for a marksman and 4.5 to 5 times
  for a caster. Launch it from the weapon, and aim it at the chest of the
  target, not its feet. [data; ratios derived]
- In Construct, create the projectile at the weapon's image point. Give it
  Bullet, then *Set speed* and after it *Set angle of motion*, because the
  other order flies right
  ([pitfalls: Coordinates and angles](../pitfalls/coordinates-and-angles.md)).
  Every tick, set the angle of motion to `angle(Self.X, Self.Y, Target.X,
  Target.Y)`. Deal the damage when the distance to the target is less than
  the distance the projectile moves in one tick. [inferred]
- A ranged attack with a short range, 0.9 to 1.3 times the move speed, can
  do without a projectile: the damage lands at the release, and only the
  hit effect plays. [data, inferred]
- A melee weapon with a long reach, such as a whip or a chain, shows the
  reach as an effect in the animation. It still deals its damage at the
  release, with no projectile. [data, inferred]
- A skill projectile either stops at the first enemy it touches or flies to
  its end point and resolves there. Common speeds are 3.5 to 6 times the
  move speed, and fast ones 6.5 to 10 times. [data; ratios derived]

## Sounds of an attack

- Play up to three sounds per attack, each from the event of its moment,
  not from an animation frame. A swing plays when the wind-up starts, a
  launch when a projectile is created, and a hit when the damage lands.
  [data]
- The hit sound has no delay after the damage in every studied hero. A
  bow draw can start 0.04 to 0.3 s into the wind-up. [data]
- If the game's sounds follow the music grid ([sound.md](sound.md),
  "Immediate or on the grid"), the damage moves to its cell, and the hit
  sound moves with it.
- Choose the hit sound by the target's material. The material replaces the
  default set and is not a layer on top of it. The sets are flesh by
  default, then metal, stone and wood, with 4 variants each. Melee attacks
  and physical projectiles use them, and spells and arrows do not. [data]
- In Construct, give the target an instance variable `material`, and play
  `"hit_" & material & "_" & n` with Audio *Play (by name)*. Use flesh
  when the variable is empty. A critical hit adds one fixed heavy layer.
  [data, inferred]
- Play the variants from a shuffled list, as [sound.md](sound.md) says
  ("Tiers and loudness"). In Construct, keep the variant numbers in an
  Array and *Shuffle* it. Read the next index on each play, and *Shuffle*
  again when the list is used up. [data]
- An unpitched sound with only 2 variants can add a random rate within ±2
  to 3 semitones: *Set playback rate* to `2 ^ (random(-2.5, 2.5) / 12)` on
  its own tag. [data]
- Lengths: a swing 0.4 to 0.7 s, a hit 0.7 to 1.2 s, a critical layer 1.0
  to 1.6 s, a skill cast 2.3 to 3.3 s. [data]
- Let the last hit sound play to its end when the next one plays, and do
  not *Stop* it. A hit outlasts the shortest attack interval, so the two
  overlap. [derived]
- One moment can play several layers with delays. An empowered strike can
  start its wind-up sound at once and a longer impact 0.2 to 0.25 s later,
  about 0.1 s before the damage, with no separate hit sound. [data;
  offset derived]
- A sound of a lasting state, such as a buff or a flying projectile,
  starts with the state on its own tag. When the state ends, it fades out
  in 0.25 s, or 0.5 s for a projectile: Audio *Fade volume* to −60 dB, then
  *Stop* in *On fade ended*. [data, inferred]
- Small motion sounds, such as armour, footsteps or a shell ejecting, go
  on animation frames: Sprite *On frame changed* with a test of
  `AnimationFrame`. Most fall in the recovery or a turn. [data]

## Hit effects and damage numbers

- A hit effect is 2 to 8 one-shot layers that end within 0.2 to 0.5 s.
  [data]
  - A flash of 0.3 s that shrinks to nothing, or grows from small.
  - A slash or impact shape of 0.2 s that grows to 4 and then 8 times its
    size as it fades.
  - Optional sparks of 0.3 to 0.45 s that fly outwards.
- Make each layer a Sprite with Tween (one property) on *Size* and on
  *Opacity*. Set *Destroy on complete* on the longer of the two. [inferred]
- Bring a layer to full opacity in the first 10 % of its life, and fade it
  over the other 90 %. [derived]
- Create the effect at the target's chest, an image point above its
  centre, and keep it there with Pin *Pin to image point*. Set about half
  of the layers to the *Additive* blend mode. [data, inferred]
- The game's data holds no tint, flash or outline of the unit that is hit.
  Its only flash is an additive sprite over the chest that shrinks to
  nothing in about 0.3 s, and colour changes on the unit are kept for
  lasting states. [feel.md](feel.md), "Hit feedback", gives the other
  ways. [data]
- Give each attack the name of its hit effect, and leave the name empty
  for none. Add no global default effect, because many plain hits show
  none while their critical hits do. A generic effect is a 0.3 s flash
  that shrinks to nothing. A critical hit adds a 0.5 s ring that grows from
  0.5 to 1.5 times its size. [data, inferred]
- A damage number appears at twice its size and shrinks to its resting
  size in 0.15 s. It flies 50 to 65 px/s sideways, alternating left and
  right, and 150 to 180 px/s up, under a gravity of 500 px/s². It starts
  to fade at 0.4 s, fades over 0.45 s and lives about 0.85 s. The data
  does not name the unit; pixels are a reading. [data, inferred]
- In Construct, give the number Bullet with *Set gravity* 500. *Set
  speed* to the length of the start velocity, then *Set angle of motion*
  to its direction. Draw it with a Sprite Font and tween its *Size*,
  because a Text whose font size changes redraws every frame
  ([pitfalls: Rendering](../pitfalls/rendering.md)). [inferred]
- A critical number is 1.75 times larger and starts within ±20 px of the
  hit. It flies faster, about 100 px/s sideways and 200 px/s up, under a
  gravity of 625 px/s². It stops at the top of its arc, about 0.32 s in
  (`200 / 625`), and fades there on the same schedule. A normal number
  keeps falling as it fades. [data, inferred]
- To stop a critical number, start a Timer for `vy / gravity` seconds when
  it is created, and *Set enabled* its Bullet off in *On timer*.
  [inferred]
- Merge damage over time and rapid hits into one number. A new hit within
  0.35 to 1.3 s adds to it and extends its life. Show at most 20 numbers,
  and queue the rest 0.2 s apart. [data]
- For the ghost of a health bar, the part that shows a loss and then
  closes, read [progress-bars.md](progress-bars.md).

## Orders and the view

- The hero reaches full speed at once: MoveTo *Set acceleration* 0. The
  move speed is about twice the melee range and 5 times the hit radius.
  [data, derived]
- Keep three radii apart. The smallest is for pathing and pushing other
  units. The hit radius is about 1.9 times it, and the radius for picking
  the unit with the mouse about 3.4 times. Attack range counts from the
  edges of the two hit circles, not from the centres. [data, derived]
- An order on an enemy walks into range, then attacks. An order on the
  ground moves and does not attack on the way, and the hero looks for
  targets only once it stops. Scan for targets every 0.2 s, and do not
  change targets during a wind-up. [data]
- The event that accepts a move order creates the ground marker, not the
  mouse click, so a refused order shows none. The marker lives 0.4 s. Four
  arrows slide to the point, flatten and fade, and a ring grows from
  nothing and fades in 0.2 s. Use Tween (one property) on *X*, *Y*, *Y
  Scale* and *Opacity*. [data, inferred]
- Turn the hero to face the target at once when an attack or an aimed
  skill starts, rather than rotate towards it. [data, inferred]
- A 3D camera over this kind of game looks down at 55°. Put it behind the
  point it follows by `0.574 × d` and above it by `0.819 × d`, and use 3D
  Camera *Look at position* on the point. The distance `d` and the field
  of view are the project's to tune, because the data does not give them.
  [data, derived]
