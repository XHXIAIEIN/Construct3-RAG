# Parameter Format Rules

Rules for formatting ACE parameters in JSON.

## Format Rules

| Type | Rule | Example |
|------|------|---------|
| Number | String, no quotes | `"x": "400"` |
| String | **Nested quotes required** | `"text": "\"Hello\""` |
| Expression | String, no nested quotes | `"x": "Player.X + 100"` |
| String concat | Use `&` operator | `"text": "\"Score: \" & Score"` |
| Comparison | Number 0-5 | `"comparison": 4` |
| Key code | Number | `"key": 87` |
| Layer | Index or quoted name | `"layer": "0"` or `"layer": "\"Main\""` |

## Comparison Operators

| Value | Operator |
|-------|----------|
| 0 | = (Equal) |
| 1 | ≠ (Not equal) |
| 2 | < (Less) |
| 3 | ≤ (Less or equal) |
| 4 | > (Greater) |
| 5 | ≥ (Greater or equal) |

## Key Codes

| Key | Code | Key | Code |
|-----|------|-----|------|
| W | 87 | ↑ | 38 |
| A | 65 | ← | 37 |
| S | 83 | ↓ | 40 |
| D | 68 | → | 39 |
| Space | 32 | Enter | 13 |
| Shift | 16 | Ctrl | 17 |
| Esc | 27 | 0-9 | 48-57 |

## Tween Parameters

| Parameter | Values |
|-----------|--------|
| property | `x`, `y`, `width`, `height`, `angle`, `opacity`, `z-elevation` |
| ease | `linear`, `in-sine`, `out-sine`, `in-out-sine`, `in-back`, `out-back`, `in-elastic`, `out-elastic`, `in-bounce`, `out-bounce` |
| destroy-on-complete | `yes`, `no` |
| loop | `no`, `loop` |

## simulate-control Values

| Behavior | control values |
|----------|----------------|
| Platform | `left`, `right`, `jump` |
| 8Direction | `up`, `down`, `left`, `right` |

## Common Mistakes

| Wrong | Correct | Why |
|-------|---------|-----|
| `"animation": "Walk"` | `"animation": "\"Walk\""` | Strings need nested quotes |
| `"comparison": ">"` | `"comparison": 4` | Comparison must be number |
| `"key": "87"` | `"key": 87` | Key code is number |
| `"behaviorType": "EightDir"` | `"behaviorType": "8Direction"` | Use display name |
