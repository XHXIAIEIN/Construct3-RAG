# Parameter Types Reference

How to correctly format ACE parameters.

## Contents

- [Basic Types](#basic-types) - number, string, any
- [Object Types](#object-types) - object, layer, layout
- [Comparison & Selection](#comparison--selection) - comparison, combo
- [Key Codes](#key-codes)
- [Variable Types](#variable-types) - eventvar, instancevar
- [Behavior Parameters](#behavior-parameters) - simulate-control, Tween, Timer
- [Expressions](#expressions) - viewport, object, system
- [Common Errors](#common-errors)

---

## Basic Types

### number
```json
"x": "400"
"speed": "200"
"interval-seconds": "2.5"
```
- Direct number string
- Supports expressions: `"Player.X + 100"`
- Supports system expressions: `"random(0, 100)"`

### string
```json
"text": "\"Hello World\""
"animation": "\"Walk\""
"tag": "\"player\""
```
- **Must have nested quotes**
- Concatenation: `"\"Score: \" & Score"`
- With expression: `"\"HP: \" & Player.Health"`

### any
```json
"value": "100"              // number
"value": "\"text\""         // string
"value": "Player.X"         // expression
```

---

## Object Types

### object
```json
"object": "Player"
"object-to-create": "Bullet"
```
Uses objectClass name.

### layer
```json
"layer": "0"                // by index
"layer": "\"Background\""   // by name (needs quotes)
```

### layout
```json
"layout": "\"Game\""        // layout name
```

---

## Comparison & Selection

### comparison
```json
"comparison": 0   // =  Equal
"comparison": 1   // ≠  Not equal
"comparison": 2   // <  Less than
"comparison": 3   // ≤  Less or equal
"comparison": 4   // >  Greater than
"comparison": 5   // ≥  Greater or equal
```

### combo
```json
// Boolean
"state": "yes"
"state": "no"

// Direction
"control": "up"
"control": "down"
"control": "left"
"control": "right"
"control": "jump"

// Loop
"loop": "no"
"loop": "loop"

// Order
"order": "ascending"
"order": "descending"
```

---

## Key Codes

| Key | Code | Key | Code |
|-----|------|-----|------|
| W | 87 | ↑ | 38 |
| A | 65 | ← | 37 |
| S | 83 | ↓ | 40 |
| D | 68 | → | 39 |
| Space | 32 | Enter | 13 |
| Shift | 16 | Ctrl | 17 |
| Alt | 18 | Esc | 27 |
| 0-9 | 48-57 | A-Z | 65-90 |
| F1-F12 | 112-123 | | |

```json
{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 87}}
```

---

## Variable Types

### eventvar
```json
"variable": "Score"
"variable": "PlayerHealth"
```
Use variable name without quotes.

### instancevar
```json
"instance-variable": "Health"
"instance-variable": "Speed"
```

---

## Behavior Parameters

### simulate-control

**8Direction**:
```json
"control": "up"
"control": "down"
"control": "left"
"control": "right"
```

**Platform**:
```json
"control": "left"
"control": "right"
"control": "jump"
```

### Tween

```json
{
  "tags": "\"mytween\"",
  "property": "x",           // x, y, width, height, angle, opacity, z-elevation
  "end-value": "500",
  "time": "1",
  "ease": "in-out-sine",     // linear, in-sine, out-sine, in-out-sine, in-back, out-back, in-elastic, out-elastic, in-bounce, out-bounce
  "destroy-on-complete": "no",
  "loop": "no",
  "ping-pong": "no",
  "repeat-count": "1"
}
```

### Timer

```json
{
  "duration": "2",
  "type": "once",            // once, regular
  "tag": "\"mytimer\""
}
```

---

## Expressions

### Viewport
```json
"x": "viewportleft(0)"
"x": "viewportright(0)"
"y": "viewporttop(0)"
"y": "viewportbottom(0)"
"x": "random(viewportleft(0), viewportright(0))"
```

### Object
```json
"x": "Player.X"
"y": "Player.Y + 50"
"angle": "angle(Self.X, Self.Y, Player.X, Player.Y)"
"distance": "distance(Self.X, Self.Y, Player.X, Player.Y)"
```

### System
```json
"value": "random(1, 100)"
"value": "choose(1, 2, 3)"
"value": "floor(Player.X / 32)"
"value": "clamp(value, 0, 100)"
"value": "lerp(a, b, 0.5)"
"value": "dt"                  // delta time
"value": "time"                // runtime
"value": "loopindex"           // loop index
```

---

## Common Errors

### Missing nested quotes for string
```json
// ❌ Wrong
"animation": "Walk"

// ✅ Correct
"animation": "\"Walk\""
```

### Quoted number for key code
```json
// ❌ Wrong
"key": "\"87\""

// ✅ Correct
"key": 87
// or
"key": "87"
```

### String comparison operator
```json
// ❌ Wrong
"comparison": "="

// ✅ Correct
"comparison": 0
```
