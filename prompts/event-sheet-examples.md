# Event Sheet Output Examples

Reference examples for [event-sheet-assistant.md](event-sheet-assistant.md). All ACE names verified against `data/c3-schemas/en-US/` schema files.

---

## Basic: Jump and landing

**Event 1** — Jump when pressing Space

> Conditions

| Object | Name | Parameters |
|--------|------|------------|
| Keyboard | On key pressed | Key: `Space` |

> Actions

| Object | Name | Parameters |
|--------|------|------------|
| Player | Set animation | Animation: `"Jump"`, From: `beginning` |
| Player | Simulate control (Platform) | Control: `Jump` |

**Event 2** — Return to idle on landing

> Conditions

| Object | Name | Parameters |
|--------|------|------------|
| Player | Is on floor (Platform) | — |

> Actions

| Object | Name | Parameters |
|--------|------|------------|
| Player | Set animation | Animation: `"Idle"`, From: `beginning` |

## Sub-events: Speed-based animation

**Event 3** — Track speed every tick

> Conditions

| Object | Name | Parameters |
|--------|------|------------|
| System | Every tick | — |

> Actions

| Object | Name | Parameters |
|--------|------|------------|
| System | Set value | speed = `Player.Platform.Speed` |

> **Event 3.1** — Fast run animation

> Conditions

| Object | Name | Parameters |
|--------|------|------------|
| Player | Compare speed (Platform) | Comparison: ≥, Speed: `200` |

> Actions

| Object | Name | Parameters |
|--------|------|------------|
| Player | Set animation | Animation: `"FastRun"`, From: `beginning` |

> **Event 3.2** — Idle when slow and grounded

> Conditions

| Object | Name | Parameters |
|--------|------|------------|
| Player | Is on floor (Platform) | — |
| System | Compare two values | `speed` < `50` |

> Actions

| Object | Name | Parameters |
|--------|------|------------|
| Player | Set animation | Animation: `"Idle"`, From: `beginning` |

## Collision and win condition

**Event 4** — Destroy enemy on collision

> Conditions

| Object | Name | Parameters |
|--------|------|------------|
| Player | On collision with another object | Object: `Enemy` |

> Actions

| Object | Name | Parameters |
|--------|------|------------|
| Enemy | Destroy | — |

> **Event 4.1** — Win when all enemies gone

> Conditions

| Object | Name | Parameters |
|--------|------|------------|
| System | Compare two values | `Enemy.Count` = `0` |

> Actions

| Object | Name | Parameters |
|--------|------|------------|
| System | Go to layout | Layout: `"WinScreen"` |

## Common mistakes

| Wrong | Why | Correct |
|-------|-----|---------|
| `if (Keyboard.isPressed("Space"))` | Pseudocode, not event sheet | Condition: On key pressed, Key: `Space` |
| `Sprite.setAnimation("Run")` | JavaScript API, not event sheet | Action: Set animation, Animation: `"Run"` |
| `health = health - 10` | Assignment syntax | Action: Set value, health = `health - 10` |
| `Sprite.CurrentFrame` | Invented expression name | `Sprite.AnimationFrame` — always verify in schema |
| `playerHP` with `enemy_count` | Inconsistent naming style | Pick one convention: `playerHP`, `enemyCount` |
