# Top Conditions Reference

Condition usage frequency based on 490 official example projects.

## Contents

- [Data Source](#data-source)
- [Top 20 Conditions](#top-20-conditions)
- [Conditions by Category](#conditions-by-category)

---

## Data Source

Full data: `data/project_analysis/sorted_indexes.json` → `top_50_conditions`

## Top 20 Conditions

| # | ID | Usage Count | Parameters |
|---|-----|-------------|------------|
| 1 | `System.else` | 1261 | - |
| 2 | `System.evaluate-expression` | 1195 | `value` |
| 3 | `Keyboard.key-is-down` | 618 | `key` |
| 4 | `System.for-each` | 497 | `object` |
| 5 | `Keyboard.on-key-pressed` | 488 | `key` |
| 6 | `System.on-start-of-layout` | 477 | - |
| 7 | `System.compare-eventvar` | 469 | `variable`, `comparison`, `value` |
| 8 | `System.compare-two-values` | 402 | `first-value`, `comparison`, `second-value` |
| 9 | `System.every-tick` | 391 | - |
| 10 | `Gamepad.is-button-down` | 370 | `gamepad`, `button` |
| 11 | `System.compare-boolean-eventvar` | 361 | `variable` |
| 12 | `Gamepad.on-button-pressed` | 268 | `gamepad`, `button` |
| 13 | `System.for` | 261 | `name`, `start-index`, `end-index` |
| 14 | `System.pick-by-evaluate` | 237 | `object`, `expression` |
| 15 | `System.every-x-seconds` | 216 | `interval-seconds` |
| 16 | `System.repeat` | 183 | `count` |
| 17 | `System.pick-by-comparison` | 161 | `object`, `expression`, `comparison`, `value` |
| 18 | `Platform.is-on-floor` | 106 | - |
| 19 | `System.trigger-once-while-true` | 103 | - |
| 20 | `Sprite.on-collision-with-another-object` | 103 | `object` |

## Conditions by Category

### Input Detection
```json
// Keyboard key down
{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 87}}

// Keyboard key pressed
{"id": "on-key-pressed", "objectClass": "Keyboard", "parameters": {"key": 32}}

// Gamepad button
{"id": "is-button-down", "objectClass": "Gamepad", "parameters": {"gamepad": 0, "button": 0}}

// Mouse hover
{"id": "cursor-is-over-object", "objectClass": "Mouse", "parameters": {"object": "Button"}}

// Touch object
{"id": "is-touching-object", "objectClass": "Touch", "parameters": {"object": "Button"}}
```

### Collision Detection
```json
// Collision trigger
{"id": "on-collision-with-another-object", "objectClass": "Player", "parameters": {"object": "Enemy"}}

// Overlap check
{"id": "is-overlapping-another-object", "objectClass": "Player", "parameters": {"object": "Coin"}}
```

### Lifecycle
```json
// Layout start
{"id": "on-start-of-layout", "objectClass": "System", "parameters": {}}

// Object created
{"id": "on-created", "objectClass": "Bullet", "parameters": {}}
```

### Loops
```json
// For Each
{"id": "for-each", "objectClass": "System", "parameters": {"object": "Enemy"}}

// For loop
{"id": "for", "objectClass": "System", "parameters": {"name": "\"i\"", "start-index": "0", "end-index": "10"}}

// Repeat
{"id": "repeat", "objectClass": "System", "parameters": {"count": "5"}}
```

### Comparison
```json
// Compare variable
{"id": "compare-eventvar", "objectClass": "System", "parameters": {"variable": "Score", "comparison": 4, "value": "100"}}

// Compare two values
{"id": "compare-two-values", "objectClass": "System", "parameters": {"first-value": "Player.X", "comparison": 4, "second-value": "400"}}

// Boolean check
{"id": "compare-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "IsAlive"}}
```

### Behavior State
```json
// Platform on floor
{"id": "is-on-floor", "objectClass": "Player", "behaviorType": "Platform", "parameters": {}}

// Platform jumping
{"id": "is-jumping", "objectClass": "Player", "behaviorType": "Platform", "parameters": {}}

// Tween playing
{"id": "is-playing", "objectClass": "Sprite", "behaviorType": "Tween", "parameters": {"tags": "\"fade\""}}

// Timer trigger
{"id": "on-timer", "objectClass": "GameManager", "behaviorType": "Timer", "parameters": {"tag": "\"spawn\""}}
```
