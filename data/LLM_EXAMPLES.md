# Event Sheet Output Examples

Reference examples for [LLM_PROMPT.md](LLM_PROMPT.md). All ACE names verified against `en/` schema files.

---

## Basic: Jump and landing

**Event 1** — Jump when pressing Space

| Object | Type | Category | Name | Parameters |
|--------|------|----------|------|------------|
| Keyboard | Condition | Keyboard | On key pressed | Key: `Space` |
| Player | Action | Animations | Set animation | Animation: `"Jump"`, From: `beginning` |
| Player | Action | Platform | Simulate control | Control: `Jump` |

**Event 2** — Return to idle on landing

| Object | Type | Category | Name | Parameters |
|--------|------|----------|------|------------|
| Player | Condition | Platform | Is on floor | — |
| Player | Action | Animations | Set animation | Animation: `"Idle"`, From: `beginning` |

## Sub-events: Speed-based animation

**Event 3** — Track speed every tick

| Object | Type | Category | Name | Parameters |
|--------|------|----------|------|------------|
| System | Condition | General | Every tick | — |
| System | Action | Global & local variables | Set value | Variable: `speed`, Value: `Player.Platform.Speed` |

> **Event 3.1** — Fast run animation

| Object | Type | Category | Name | Parameters |
|--------|------|----------|------|------------|
| Player | Condition | Platform | Compare speed | Comparison: `≥`, Speed: `200` |
| Player | Action | Animations | Set animation | Animation: `"FastRun"`, From: `beginning` |

> **Event 3.2** — Idle when slow and grounded

| Object | Type | Category | Name | Parameters |
|--------|------|----------|------|------------|
| Player | Condition | Platform | Is on floor | — |
| System | Condition | General | Compare two values | First value: `speed`, Comparison: `<`, Second value: `50` |
| Player | Action | Animations | Set animation | Animation: `"Idle"`, From: `beginning` |

## Collision and win condition

**Event 4** — Destroy enemy on collision

| Object | Type | Category | Name | Parameters |
|--------|------|----------|------|------------|
| Player | Condition | Collisions | On collision with another object | Object: `Enemy` |
| Enemy | Action | Misc | Destroy | — |

> **Event 4.1** — Win when all enemies gone

| Object | Type | Category | Name | Parameters |
|--------|------|----------|------|------------|
| System | Condition | General | Compare two values | First value: `Enemy.Count`, Comparison: `=`, Second value: `0` |
| System | Action | Layout | Go to layout | Layout: `"WinScreen"` |

## Common mistakes

| Wrong | Why | Correct |
|-------|-----|---------|
| `if (Keyboard.isPressed("Space"))` | Pseudocode, not event sheet | Condition: On key pressed, Key: `Space` |
| `Sprite.setAnimation("Run")` | JavaScript API, not event sheet | Action: Set animation, Animation: `"Run"` |
| `health = health - 10` | Assignment syntax | Action: Set value, Variable: `health`, Value: `health - 10` |
| `Sprite.动画帧` | Chinese expression identifier | `Sprite.AnimationFrame` |
| `player生命值` | Mixed language variable | `playerHealth` or `玩家生命值` |
