# Construct 3 Clipboard Format

## Clipboard Types

```json
{"is-c3-clipboard-data": true, "type": "events", "items": []}
{"is-c3-clipboard-data": true, "type": "conditions", "items": []}
{"is-c3-clipboard-data": true, "type": "actions", "items": []}
```

---

## Events

### variable

```json
{"eventType": "variable", "name": "Score", "type": "number", "initialValue": "0", "comment": "", "isStatic": false, "isConstant": false}
{"eventType": "variable", "name": "SPEED", "type": "number", "initialValue": "100", "comment": "", "isStatic": true, "isConstant": true}
```

- type: `"number"` | `"string"` | `"boolean"`
- `isConstant: true` = constant (ALL_CAPS naming convention)
- `isStatic: true` = static (persists across layouts)

### comment

```json
{"eventType": "comment", "text": "Comment text"}
```

### group

```json
{"eventType": "group", "disabled": false, "title": "Title", "description": "", "isActiveOnStart": true, "children": []}
```

### block (AND conditions)

```json
{"eventType": "block", "conditions": [], "actions": []}
```

### block (OR conditions)

```json
{"eventType": "block", "conditions": [], "actions": [], "isOrBlock": true}
```

### block with children (nested sub-events)

```json
{"eventType": "block", "conditions": [], "actions": [], "children": []}
```

### function-block

```json
{"eventType": "function-block", "functionName": "MyFunc", "functionDescription": "", "functionCategory": "", "functionReturnType": "none", "functionCopyPicked": false, "functionIsAsync": false, "functionParameters": [], "conditions": [], "actions": [], "children": []}
{"eventType": "function-block", "functionName": "RuleOfThree", "functionReturnType": "number", "functionParameters": [{"name": "A", "type": "number", "initialValue": "0", "comment": ""}, {"name": "B", "type": "number", "initialValue": "0", "comment": ""}, {"name": "C", "type": "number", "initialValue": "0", "comment": ""}], "conditions": [], "actions": [{"id": "set-function-return-value", "objectClass": "Functions", "parameters": {"value": "C * B / A"}}]}
```

- `functionReturnType`: `"none"` | `"number"` | `"string"` | `"any"`
- `functionParameters`: array of `{name, type, initialValue, comment}`
- Parameters used directly by name in expressions (e.g., `A`, `B`, `C`)

### custom-ace-block (custom action for object)

```json
{"eventType": "custom-ace-block", "aceType": "action", "aceName": "PlayAnimation", "objectClass": "piggy", "functionDescription": "", "functionCategory": "", "functionReturnType": "none", "functionCopyPicked": false, "functionIsAsync": false, "functionParameters": [], "conditions": [], "actions": []}
```

---

## Conditions

```json
{"id": "on-start-of-layout", "objectClass": "System"}
{"id": "every-tick", "objectClass": "System"}
{"id": "every-x-seconds", "objectClass": "System", "parameters": {"interval-seconds": "1"}}
{"id": "compare-two-values", "objectClass": "System", "parameters": {"first-value": "1 + 1", "comparison": 0, "second-value": "2"}}
{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 32}}
{"id": "on-collision-with-another-object", "objectClass": "Player", "parameters": {"object": "Enemy"}}
{"id": "layer-is-empty", "objectClass": "System", "parameters": {"layer": "0"}, "isInverted": true}
{"id": "trigger-once-while-true", "objectClass": "System"}
{"id": "else", "objectClass": "System"}
{"id": "on-click", "objectClass": "Mouse", "parameters": {"mouse-button": "left", "click-type": "clicked"}}
{"id": "on-object-clicked", "objectClass": "Mouse", "parameters": {"mouse-button": "left", "click-type": "clicked", "object-clicked": "piggy"}}
{"id": "on-any-touch-start", "objectClass": "Touch"}
{"id": "on-nth-touch-start", "objectClass": "Touch", "parameters": {"touch-number": "0"}}
{"id": "has-nth-touch", "objectClass": "Touch", "parameters": {"touch-number": "0"}}
{"id": "on-nth-touch-end", "objectClass": "Touch", "parameters": {"touch-number": "0"}}
{"id": "is-touching-object", "objectClass": "Touch", "parameters": {"object": "Button"}}
{"id": "compare-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "IsActive"}}
{"id": "evaluate-expression", "objectClass": "System", "parameters": {"value": "Touch.TouchCount = 1"}}
{"id": "on-mouse-wheel", "objectClass": "Mouse", "parameters": {"direction": "any"}}
{"id": "mouse-button-is-down", "objectClass": "Mouse", "parameters": {"mouse-button": "left"}}
{"id": "compare-instance-variable", "objectClass": "Enemy", "parameters": {"instance-variable": "Health", "comparison": 3, "value": "0"}}
{"id": "is-on-floor", "objectClass": "Player", "behaviorType": "Platform"}
{"id": "is-moving", "objectClass": "Player", "behaviorType": "Platform"}
{"id": "is-jumping", "objectClass": "Player", "behaviorType": "Platform"}
{"id": "is-falling", "objectClass": "Player", "behaviorType": "Platform"}
{"id": "on-animation-finished", "objectClass": "Sprite", "parameters": {"animation": "\"Attack\""}}
{"id": "is-button-down", "objectClass": "Gamepad", "parameters": {"gamepad": "0", "button": "d-pad-left"}}
{"id": "compare-eventvar", "objectClass": "System", "parameters": {"variable": "HorizontalAxis", "comparison": 0, "value": "1"}}
{"id": "on-key-pressed", "objectClass": "Keyboard", "parameters": {"key": 83}}
{"id": "on-save-complete", "objectClass": "System"}
{"id": "on-load-complete", "objectClass": "System"}
{"id": "on-load-failed", "objectClass": "System"}
{"id": "is-outside-layout", "objectClass": "Goblin"}
{"id": "for", "objectClass": "System", "parameters": {"name": "\"i\"", "start-index": "0", "end-index": "10"}}
{"id": "for-each", "objectClass": "System", "parameters": {"object": "Block"}}
{"id": "repeat", "objectClass": "System", "parameters": {"count": "4"}}
{"id": "pick-by-comparison", "objectClass": "System", "parameters": {"object": "Block", "expression": "Block.Y", "comparison": 0, "value": "100"}}
{"id": "pick-by-unique-id", "objectClass": "Block", "parameters": {"unique-id": "BlockUID"}}
{"id": "pick-all", "objectClass": "System", "parameters": {"object": "Block"}}
{"id": "while", "objectClass": "System"}
{"id": "is-playing", "objectClass": "Sprite", "behaviorType": "Tween", "parameters": {"tags": "\"Move\""}}
{"id": "is-timer-running", "objectClass": "Block", "behaviorType": "Timer", "parameters": {"tag": "\"SelfDestroy\""}}
{"id": "on-timer", "objectClass": "Block", "behaviorType": "Timer", "parameters": {"tag": "\"SelfDestroy\""}}
{"id": "is-overlapping-another-object", "objectClass": "Player", "parameters": {"object": "Enemy"}}
{"id": "is-on-screen", "objectClass": "Sprite"}
{"id": "on-item-exists", "objectClass": "LocalStorage", "parameters": {"key": "\"PlayerData\""}}
{"id": "on-item-get", "objectClass": "LocalStorage", "parameters": {"key": "\"PlayerData\""}}
{"id": "on-item-missing", "objectClass": "LocalStorage", "parameters": {"key": "\"PlayerData\""}}
{"id": "is-sleeping", "objectClass": "Ball", "behaviorType": "Physics"}
{"id": "on-path-found", "objectClass": "Enemy", "behaviorType": "Pathfinding"}
{"id": "on-failed-to-find-path", "objectClass": "Enemy", "behaviorType": "Pathfinding"}
{"id": "on-arrived", "objectClass": "Enemy", "behaviorType": "Pathfinding"}
{"id": "is-calculating-path", "objectClass": "Enemy", "behaviorType": "Pathfinding"}
{"id": "has-los-to-object", "objectClass": "Guard", "behaviorType": "LineOfSight", "parameters": {"object": "Player"}}
{"id": "has-los-to-position", "objectClass": "Guard", "behaviorType": "LineOfSight", "parameters": {"x": "100", "y": "200"}}
{"id": "has-parent", "objectClass": "Child"}
{"id": "has-children", "objectClass": "Parent"}
{"id": "on-created", "objectClass": "Sprite"}
{"id": "on-destroyed", "objectClass": "Sprite"}
{"id": "compare-tile-at", "objectClass": "Tilemap", "parameters": {"tile-x": "0", "tile-y": "0", "comparison": 0, "value": "5"}}
```

Empty conditions `[]` = always run (unconditional block)

`key-is-down` = continuous, `on-key-pressed` = trigger once
`loopindex` = current loop index, `loopindex("name")` = named loop index
`Array.At(x,y)` = 2D array access, `Array.Width/Height/Depth` = dimensions
`Object.Count` = number of instances of object type
`AdvancedRandom.Permutation(index)` = get shuffled index from permutation table
`LocalStorage.ItemValue` = retrieved value
`"str1"&"str2"` = string concatenation
`LayerToLayerX/Y("from", "to", x, y)` = convert coords between layers
`scrollx`, `scrolly` = current scroll position
`LayerScrollX("layer")`, `LayerScrollY("layer")` = scroll position of specific layer
`lerp(a, b, t)` = linear interpolation (smooth movement)
`clamp(val, min, max)` = constrain value to range
`distance(x1, y1, x2, y2)` = distance between two points
`angle(x1, y1, x2, y2)` = angle from point 1 to point 2
`sign(x)` = returns -1, 0, or 1
`abs(x)` = absolute value
`round(x)` = round to nearest integer
`floor(x)` = round down, `ceil(x)` = round up
`random(min, max)` = random float between min and max
`x % y` = modulo (remainder)
`Infinity`, `-Infinity` = infinity constants
`Object.Tween.Progress("tag")` = tween progress 0-1
`Touch.TouchCount` = number of active touches
`Touch.XAt(index, "layer")`, `Touch.YAt(index, "layer")` = touch position on layer
`Mouse.WheelDeltaY` = mouse wheel scroll amount
`Functions.FuncName(params)` = call function with return value
`condition ? valueIfTrue : valueIfFalse` = ternary operator
`Self.X`, `Self.Y`, `Self.Width`, `Self.Height` = current object properties
`Object.X`, `Object.Y`, `Object.UID` = other object properties
`Tilemap.TileAt(tx, ty)` = tile index at position
`Tilemap.PositionToTileX(x)`, `Tilemap.PositionToTileY(y)` = convert to tile coords
`Tilemap.TileToPositionX(tx)`, `Tilemap.TileToPositionY(ty)` = convert to world coords

mouse-button: `"left"` | `"right"` | `"middle"`
click-type: `"clicked"` | `"double-clicked"`

- Comparison: 0=, 1!=, 2<, 3<=, 4>, 5>=
- `"isInverted": true` = NOT (negate condition)

---

## Actions

```json
{"id": "create-object", "objectClass": "System", "parameters": {"object-to-create": "Cursor", "layer": "\"HUD\"", "x": "Touch.X", "y": "Touch.Y", "create-hierarchy": false, "template-name": "\"\""}}
{"id": "destroy", "objectClass": "Enemy"}
{"id": "set-position", "objectClass": "Player", "parameters": {"x": "100", "y": "200"}}
{"id": "set-x", "objectClass": "Sprite", "parameters": {"x": "100"}}
{"id": "set-y", "objectClass": "Sprite", "parameters": {"y": "Self.Y - 0.1"}}
{"id": "set-eventvar-value", "objectClass": "System", "parameters": {"variable": "Score", "value": "Score + 10"}}
{"id": "set-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "IsActive", "value": "true"}}
{"id": "reset-global-variables", "objectClass": "System", "parameters": {"reset-static": false}}
{"id": "restart-layout", "objectClass": "System"}
{"id": "spawn-another-object", "objectClass": "Player", "parameters": {"object": "Bullet", "layer": "0", "image-point": "1", "create-hierarchy": false, "template-name": "\"\""}}
{"id": "set-angle-toward-position", "objectClass": "Player", "parameters": {"x": "Mouse.X", "y": "Mouse.Y"}}
{"id": "tween-one-property", "objectClass": "Sprite", "behaviorType": "Tween", "parameters": {"tags": "\"\"", "property": "offsetWidth", "end-value": "-Self.Width", "time": "0.5", "ease": "easeinoutsine", "destroy-on-complete": "no", "loop": "no", "ping-pong": "no", "repeat-count": "1"}}
{"id": "move-to-position", "objectClass": "Sprite", "behaviorType": "MoveTo", "parameters": {"x": "Touch.X", "y": "Touch.Y", "mode": "direct"}}
{"id": "rotate-clockwise", "objectClass": "Bullet", "parameters": {"degrees": "random(-4, 4)"}}
{"id": "move-at-angle", "objectClass": "Sprite", "parameters": {"angle": "90 * loopindex", "distance": "16"}}
{"id": "start-timer", "objectClass": "Block", "behaviorType": "Timer", "parameters": {"duration": "0.1", "type": "once", "tag": "\"SelfDestroy\""}}
{"id": "subtract-from-instvar", "objectClass": "Enemy", "parameters": {"instance-variable": "Health", "value": "10"}}
{"id": "simulate-control", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {"control": "up"}}
{"id": "set-vector-y", "objectClass": "Player", "behaviorType": "Platform", "parameters": {"vector-y": "-384"}}
{"id": "set-width", "objectClass": "Sprite", "parameters": {"width": "Self.ImageWidth * sign(Player.Platform.VectorX)"}}
{"id": "set-image-offset-x", "objectClass": "TiledBg", "parameters": {"offset-x": "Self.ImageOffsetX + 2 * 60 * dt"}}
{"id": "set-image-offset-y", "objectClass": "TiledBg", "parameters": {"offset-y": "random(-1024, 1024)"}}
{"id": "set-velocity", "objectClass": "Ball", "behaviorType": "Physics", "parameters": {"x-component": "0", "y-component": "0"}}
{"id": "apply-force", "objectClass": "Ball", "behaviorType": "Physics", "parameters": {"force-x": "100", "force-y": "0", "image-point": "0"}}
{"id": "apply-force-at-angle", "objectClass": "Ball", "behaviorType": "Physics", "parameters": {"force": "100", "angle": "angle(Self.X, Self.Y, Touch.X, Touch.Y)", "image-point": "0"}}
{"id": "apply-force-towards-position", "objectClass": "Ball", "behaviorType": "Physics", "parameters": {"force": "100", "x": "Target.X", "y": "Target.Y", "image-point": "0"}}
{"id": "apply-impulse", "objectClass": "Ball", "behaviorType": "Physics", "parameters": {"x-component": "100", "y-component": "-50", "image-point": "0"}}
{"id": "apply-impulse-at-angle", "objectClass": "Ball", "behaviorType": "Physics", "parameters": {"impulse": "100", "angle": "45", "image-point": "0"}}
{"id": "apply-torque", "objectClass": "Ball", "behaviorType": "Physics", "parameters": {"force": "50"}}
{"id": "find-path", "objectClass": "Enemy", "behaviorType": "Pathfinding", "parameters": {"x": "Player.X", "y": "Player.Y"}}
{"id": "move-along-path", "objectClass": "Enemy", "behaviorType": "Pathfinding"}
{"id": "stop", "objectClass": "Enemy", "behaviorType": "Pathfinding"}
{"id": "add-child", "objectClass": "Parent", "parameters": {"child": "ChildSprite", "transform-x": true, "transform-y": true}}
{"id": "remove-child", "objectClass": "Parent", "parameters": {"child": "ChildSprite"}}
{"id": "set-tile", "objectClass": "Tilemap", "parameters": {"tile-x": "0", "tile-y": "0", "tile-index": "5"}}
{"id": "erase-tile", "objectClass": "Tilemap", "parameters": {"tile-x": "0", "tile-y": "0"}}
{"id": "wait", "objectClass": "System", "parameters": {"seconds": "0.5", "use-timescale": true}}
{"id": "save", "objectClass": "System", "parameters": {"slot": "\"mysave\""}}
{"id": "load", "objectClass": "System", "parameters": {"slot": "\"mysave\""}}
{"callFunction": "MyFunction"}
{"callFunction": "MyFunction", "parameters": ["100", "200"]}
{"id": "set-text", "objectClass": "Text", "parameters": {"text": "\"Hello\""}}
{"id": "set-visible", "objectClass": "Sprite", "parameters": {"visibility": "visible"}}
{"id": "set-animation", "objectClass": "Sprite", "parameters": {"animation": "\"Walk\"", "from": "beginning"}}
{"id": "restart-fade", "objectClass": "Sprite", "behaviorType": "Fade"}
{"id": "rotate-toward-position", "objectClass": "Sprite", "parameters": {"degrees": "1", "x": "Player.X", "y": "Player.Y"}}
{"id": "set-size", "objectClass": "Canvas", "parameters": {"width": "LayoutWidth", "height": "LayoutHeight"}}
{"id": "paste-object", "objectClass": "DrawingCanvas", "parameters": {"object": "Sprite", "effects": "with-effects"}}
{"id": "stop-tweens", "objectClass": "Sprite", "behaviorType": "Tween", "parameters": {"tags": "\"Move\""}}
{"id": "remove-from-parent", "objectClass": "Child"}
{"id": "sort-z-order", "objectClass": "System", "parameters": {"object": "Sprite", "instance-variable": {"name": "ZOrder", "objectClass": "Sprite"}}}
{"id": "check-item-exists", "objectClass": "LocalStorage", "parameters": {"key": "\"PlayerData\""}}
{"id": "get-item", "objectClass": "LocalStorage", "parameters": {"key": "\"PlayerData\""}}
{"id": "load", "objectClass": "Array", "parameters": {"json": "LocalStorage.ItemValue"}}
{"id": "clear", "objectClass": "Array", "parameters": {"value": "0"}}
{"id": "set-size", "objectClass": "Array", "parameters": {"width": "10", "height": "3", "depth": "1"}}
{"id": "set-at-xy", "objectClass": "Array", "parameters": {"x": "loopindex", "y": "0", "value": "Card.UID"}}
{"id": "createPermutationTable", "objectClass": "AdvancedRandom", "parameters": {"length": "Array.Width", "offset": "0"}}
{"id": "move-to-layer", "objectClass": "Sprite", "parameters": {"layer": "\"HUD\""}}
{"id": "scroll-to-position", "objectClass": "System", "parameters": {"x": "Player.X", "y": "Player.Y"}}
{"id": "set-function-return-value", "objectClass": "Functions", "parameters": {"value": "InputFocus = Index ? 1 : 0"}}
{"id": "set-layer-effect-parameter", "objectClass": "System", "parameters": {"layer": "\"Gameplay\"", "effect": "\"BlurHorizontal\"", "parameter-index": "0", "value": "50"}}
{"id": "tween-two-properties", "objectClass": "Sprite", "behaviorType": "Tween", "parameters": {"tags": "\"Move\"", "property": "position", "end-x": "Target.X", "end-y": "Target.Y", "time": "0.5", "ease": "easeinoutsine", "destroy-on-complete": "yes", "loop": "no", "ping-pong": "no", "repeat-count": "1"}}
{"customAction": "PlayAnimation", "objectClass": "Sprite"}
{"type": "comment", "text": "Inline comment in actions array"}
```

effects: `"with-effects"` | `"without-effects"`

visibility: `"visible"` | `"invisible"` | `"toggle"`

`60 * dt` = frame-rate independent (60fps target × delta time)

8Direction simulate-control: `"up"` | `"down"` | `"left"` | `"right"`
Platform simulate-control: `"left"` | `"right"` | `"jump"`
Key codes: W=87, A=65, S=83, D=68, Arrows=37-40
Gamepad buttons: `"d-pad-left"` | `"d-pad-right"` | `"d-pad-up"` | `"d-pad-down"` | `"button-a"` | `"button-b"` | ...

mode: `"direct"` | `"add-to-queue"`

tween property: `"x"` | `"y"` | `"width"` | `"height"` | `"angle"` | `"opacity"` | `"offsetWidth"` | `"offsetHeight"` | ...
ease: `"linear"` | `"easeinoutsine"` | `"easeinsine"` | `"easeoutsine"` | ...
timer type: `"once"` | `"regular"`
animation from: `"beginning"` | `"current-frame"`

---

## Examples

### Paste single condition

```json
{"is-c3-clipboard-data": true, "type": "conditions", "items": [
  {"id": "compare-two-values", "objectClass": "System", "parameters": {"first-value": "1 + 1", "comparison": 1, "second-value": "2"}}
]}
```

### Block with multiple AND conditions

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "block", "conditions": [
    {"id": "compare-two-values", "objectClass": "System", "parameters": {"first-value": "1 + 1", "comparison": 1, "second-value": "2"}},
    {"id": "compare-two-values", "objectClass": "System", "parameters": {"first-value": "tickcount % 2", "comparison": 0, "second-value": "0"}}
  ], "actions": []}
]}
```

### Block with OR conditions

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "block", "conditions": [
    {"id": "compare-two-values", "objectClass": "System", "parameters": {"first-value": "1 + 1", "comparison": 1, "second-value": "2"}},
    {"id": "compare-two-values", "objectClass": "System", "parameters": {"first-value": "tickcount % 2", "comparison": 0, "second-value": "0"}}
  ], "actions": [], "isOrBlock": true}
]}
```

### Multiple events at once

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "block", "conditions": [{"id": "every-tick", "objectClass": "System"}], "actions": []},
  {"eventType": "block", "conditions": [{"id": "compare-two-values", "objectClass": "System", "parameters": {"first-value": "tickcount % 2", "comparison": 0, "second-value": "0"}}], "actions": []}
]}
```

### If-else chain

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "block", "conditions": [{"id": "layer-is-empty", "objectClass": "System", "parameters": {"layer": "0"}}], "actions": []},
  {"eventType": "block", "conditions": [{"id": "else", "objectClass": "System"}, {"id": "layer-is-empty", "objectClass": "System", "parameters": {"layer": "1"}}], "actions": []},
  {"eventType": "block", "conditions": [{"id": "else", "objectClass": "System"}], "actions": []}
]}
```

- Block 1: if (layer 0 empty)
- Block 2: else if (layer 1 empty) — `else` + another condition
- Block 3: else — only `else`

### Nested sub-events (children)

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "block",
   "conditions": [{"id": "layer-is-empty", "objectClass": "System", "parameters": {"layer": "0"}}],
   "actions": [],
   "children": [
     {"eventType": "block",
      "conditions": [{"id": "every-x-seconds", "objectClass": "System", "parameters": {"interval-seconds": "0.1"}}],
      "actions": []}
   ]}
]}
```

= if (layer 0 empty) { every 0.1s { ... } }

### WASD keyboard controls

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "block", "conditions": [{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 87}}], "actions": [{"id": "simulate-control", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {"control": "up"}}]},
  {"eventType": "block", "conditions": [{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 65}}], "actions": [{"id": "simulate-control", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {"control": "left"}}]},
  {"eventType": "block", "conditions": [{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 83}}], "actions": [{"id": "simulate-control", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {"control": "down"}}]},
  {"eventType": "block", "conditions": [{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 68}}], "actions": [{"id": "simulate-control", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {"control": "right"}}]}
]}
```

W=87, A=65, S=83, D=68

### Platform animation state machine

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "group", "disabled": false, "title": "PlayerAnimations", "description": "", "isActiveOnStart": true, "children": [
    {"eventType": "block", "conditions": [{"id": "is-on-floor", "objectClass": "Player", "behaviorType": "Platform"}], "actions": [], "children": [
      {"eventType": "block", "conditions": [{"id": "is-moving", "objectClass": "Player", "behaviorType": "Platform"}], "actions": [{"id": "set-animation", "objectClass": "Player", "parameters": {"animation": "\"Walk\"", "from": "beginning"}}]},
      {"eventType": "block", "conditions": [{"id": "else", "objectClass": "System"}], "actions": [{"id": "set-animation", "objectClass": "Player", "parameters": {"animation": "\"Idle\"", "from": "beginning"}}]}
    ]},
    {"eventType": "block", "conditions": [{"id": "is-jumping", "objectClass": "Player", "behaviorType": "Platform"}], "actions": [{"id": "set-animation", "objectClass": "Player", "parameters": {"animation": "\"Jump\"", "from": "beginning"}}]},
    {"eventType": "block", "conditions": [{"id": "is-falling", "objectClass": "Player", "behaviorType": "Platform"}], "actions": [{"id": "set-animation", "objectClass": "Player", "parameters": {"animation": "\"Fall\"", "from": "beginning"}}]}
  ]}
]}
```

### AND conditions vs nested children

```json
// AND: both conditions in same block
{"eventType": "block", "conditions": [
  {"id": "layer-is-empty", "objectClass": "System", "parameters": {"layer": "0"}},
  {"id": "every-x-seconds", "objectClass": "System", "parameters": {"interval-seconds": "0.1"}}
], "actions": []}

// Nested: child only checked when parent true
{"eventType": "block", "conditions": [
  {"id": "layer-is-empty", "objectClass": "System", "parameters": {"layer": "0"}}
], "actions": [], "children": [
  {"eventType": "block", "conditions": [
    {"id": "every-x-seconds", "objectClass": "System", "parameters": {"interval-seconds": "0.1"}}
  ], "actions": []}
]}
```

Both require layer empty + every 0.1s, but timing behavior may differ for triggers.

### Bullet damage + enemy death

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "block",
   "conditions": [{"id": "on-collision-with-another-object", "objectClass": "Bullet", "parameters": {"object": "Enemy"}}],
   "actions": [
     {"id": "subtract-from-instvar", "objectClass": "Enemy", "parameters": {"instance-variable": "Health", "value": "10"}},
     {"id": "destroy", "objectClass": "Bullet"}
   ]},
  {"eventType": "block",
   "conditions": [{"id": "compare-instance-variable", "objectClass": "Enemy", "parameters": {"instance-variable": "Health", "comparison": 3, "value": "0"}}],
   "actions": [{"id": "destroy", "objectClass": "Enemy"}]}
]}
```

comparison 3 = `<=` (Health <= 0)

### Function with return value

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "function-block", "functionName": "IsPlayerAlive", "functionReturnType": "number", "functionParameters": [], "conditions": [], "actions": [
    {"id": "set-function-return-value", "objectClass": "Functions", "parameters": {"value": "Player.Health > 0 ? 1 : 0"}}
  ]}
]}
```

Call: `Functions.IsPlayerAlive() = 1`

### Function with parameters

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "function-block", "functionName": "RuleOfThree", "functionReturnType": "number", "functionParameters": [
    {"name": "A", "type": "number", "initialValue": "0", "comment": ""},
    {"name": "B", "type": "number", "initialValue": "0", "comment": ""},
    {"name": "C", "type": "number", "initialValue": "0", "comment": ""}
  ], "conditions": [], "actions": [
    {"id": "set-function-return-value", "objectClass": "Functions", "parameters": {"value": "C * B / A"}}
  ]}
]}
```

Call: `Functions.RuleOfThree(100, 50, 200)` → returns 100

### Function with children (complex logic)

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "function-block", "functionName": "MoveTowards", "functionReturnType": "number", "functionParameters": [
    {"name": "Current", "type": "number", "initialValue": "0", "comment": ""},
    {"name": "Target", "type": "number", "initialValue": "0", "comment": ""},
    {"name": "Speed", "type": "number", "initialValue": "0", "comment": ""}
  ], "conditions": [], "actions": [], "children": [
    {"eventType": "variable", "name": "Dir", "type": "number", "initialValue": "0", "comment": "", "isStatic": false, "isConstant": false},
    {"eventType": "block", "conditions": [], "actions": [
      {"id": "set-eventvar-value", "objectClass": "System", "parameters": {"variable": "Dir", "value": "sign(Target - Current)"}}
    ]},
    {"eventType": "block", "conditions": [{"id": "evaluate-expression", "objectClass": "System", "parameters": {"value": "Current > Target"}}], "actions": [
      {"id": "set-function-return-value", "objectClass": "Functions", "parameters": {"value": "clamp(Current + Dir * abs(Speed) * 60 * dt, Target, Infinity)"}}
    ]},
    {"eventType": "block", "conditions": [{"id": "else", "objectClass": "System"}, {"id": "evaluate-expression", "objectClass": "System", "parameters": {"value": "Current < Target"}}], "actions": [
      {"id": "set-function-return-value", "objectClass": "Functions", "parameters": {"value": "clamp(Current + Dir * abs(Speed) * 60 * dt, -Infinity, Target)"}}
    ]},
    {"eventType": "block", "conditions": [{"id": "else", "objectClass": "System"}], "actions": [
      {"id": "set-function-return-value", "objectClass": "Functions", "parameters": {"value": "Target"}}
    ]}
  ]}
]}
```

- Functions can have `children` for complex internal logic
- Local variables in function scope
- Multiple return paths with if-else chain
- `sign()` = direction (-1, 0, 1), `abs()` = absolute value
- Frame-rate independent: `Speed * 60 * dt`

### Touch pan gesture (1 finger)

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "block", "conditions": [{"id": "evaluate-expression", "objectClass": "System", "parameters": {"value": "Touch.TouchCount = 1"}}], "actions": [], "children": [
    {"eventType": "variable", "name": "RefX", "type": "number", "initialValue": "0", "comment": "", "isStatic": true, "isConstant": false},
    {"eventType": "variable", "name": "RefY", "type": "number", "initialValue": "0", "comment": "", "isStatic": true, "isConstant": false},
    {"eventType": "block", "conditions": [{"id": "trigger-once-while-true", "objectClass": "System"}], "actions": [
      {"id": "set-eventvar-value", "objectClass": "System", "parameters": {"variable": "RefX", "value": "Touch.XAt(0, \"Game\")"}},
      {"id": "set-eventvar-value", "objectClass": "System", "parameters": {"variable": "RefY", "value": "Touch.YAt(0, \"Game\")"}}
    ]},
    {"eventType": "block", "conditions": [], "actions": [
      {"id": "scroll-to-position", "objectClass": "System", "parameters": {"x": "LayerScrollX(\"Game\") + (RefX - Touch.XAt(0, \"Game\"))", "y": "LayerScrollY(\"Game\") + (RefY - Touch.YAt(0, \"Game\"))"}},
      {"id": "set-eventvar-value", "objectClass": "System", "parameters": {"variable": "RefX", "value": "Touch.XAt(0, \"Game\")"}},
      {"id": "set-eventvar-value", "objectClass": "System", "parameters": {"variable": "RefY", "value": "Touch.YAt(0, \"Game\")"}}
    ]}
  ]}
]}
```

### Pinch zoom gesture (2 fingers)

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "block", "conditions": [{"id": "evaluate-expression", "objectClass": "System", "parameters": {"value": "Touch.TouchCount = 2"}}], "actions": [], "children": [
    {"eventType": "variable", "name": "RefDist", "type": "number", "initialValue": "0", "comment": "", "isStatic": true, "isConstant": false},
    {"eventType": "block", "conditions": [{"id": "trigger-once-while-true", "objectClass": "System"}], "actions": [
      {"id": "set-eventvar-value", "objectClass": "System", "parameters": {"variable": "RefDist", "value": "distance(Touch.XAt(0, \"HUD\"), Touch.YAt(0, \"HUD\"), Touch.XAt(1, \"HUD\"), Touch.YAt(1, \"HUD\"))"}}
    ]},
    {"eventType": "block", "conditions": [], "actions": [
      {"callFunction": "SetZoom", "parameters": ["(RefDist - distance(Touch.XAt(0, \"HUD\"), Touch.YAt(0, \"HUD\"), Touch.XAt(1, \"HUD\"), Touch.YAt(1, \"HUD\"))) / 1000"]},
      {"id": "set-eventvar-value", "objectClass": "System", "parameters": {"variable": "RefDist", "value": "distance(Touch.XAt(0, \"HUD\"), Touch.YAt(0, \"HUD\"), Touch.XAt(1, \"HUD\"), Touch.YAt(1, \"HUD\"))"}}
    ]}
  ]}
]}
```

### Mouse wheel zoom

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "block", "conditions": [{"id": "on-mouse-wheel", "objectClass": "Mouse", "parameters": {"direction": "any"}}], "actions": [
    {"callFunction": "SetZoom", "parameters": ["- Mouse.WheelDeltaY / 1000"]}
  ]}
]}
```

---

## 实测验证说明

以下内容经过在 Construct 3 编辑器中实际粘贴验证（2026-01-02）。

### 关键发现

1. **variable 的 `comment` 字段必填**
   - 即使为空也需要 `"comment": ""`
   - 缺少此字段会导致粘贴失败

2. **剪贴板格式 vs 项目文件格式**
   | 特性 | 剪贴板格式 | 项目文件格式 |
   |------|------------|--------------|
   | sid | 不需要 | 必须（15位唯一数字） |
   | 标记 | `"is-c3-clipboard-data": true` | 无 |
   | 用途 | 复制粘贴 | .c3proj 内部存储 |

3. **type 字段区分**
   - 复制整个事件块（从边距选中）：`"type": "events"`
   - 仅复制条件单元格：`"type": "conditions"`
   - 仅复制动作单元格：`"type": "actions"`

### 已验证的最小示例

**注释** ✅
```json
{"is-c3-clipboard-data":true,"type":"events","items":[{"eventType":"comment","text":"测试注释"}]}
```

**变量**（注意 comment 字段）✅
```json
{"is-c3-clipboard-data":true,"type":"events","items":[{"eventType":"variable","name":"Score","type":"number","initialValue":"0","comment":"","isStatic":false,"isConstant":false}]}
```

**事件块（无动作）** ✅
```json
{"is-c3-clipboard-data":true,"type":"events","items":[{"eventType":"block","conditions":[{"id":"every-tick","objectClass":"System"}],"actions":[]}]}
```

**事件块（带动作）** ✅
```json
{"is-c3-clipboard-data":true,"type":"events","items":[{"eventType":"block","conditions":[{"id":"on-start-of-layout","objectClass":"System"}],"actions":[{"id":"set-eventvar-value","objectClass":"System","parameters":{"variable":"Score","value":"100"}}]}]}
```
