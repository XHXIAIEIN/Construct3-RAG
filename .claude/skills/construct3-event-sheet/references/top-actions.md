# Top Actions Reference

Action usage frequency based on 490 official example projects.

## Contents

- [Data Source](#data-source)
- [Top 20 Actions](#top-20-actions)
- [Actions by Category](#actions-by-category)

---

## Data Source

Full data: `data/project_analysis/sorted_indexes.json` → `top_50_actions`

## Top 20 Actions

| # | ID | Usage Count | Parameters |
|---|-----|-------------|------------|
| 1 | `System.set-eventvar-value` | 1726 | `variable`, `value` |
| 2 | `System.create-object` | 781 | `object-to-create`, `layer`, `x`, `y` |
| 3 | `System.wait` | 411 | `seconds` |
| 4 | `System.set-boolean-eventvar` | 405 | `variable`, `value` |
| 5 | `System.wait-for-previous-actions` | 267 | - |
| 6 | `Sprite.set-animation` | 243 | `animation`, `from` |
| 7 | `Audio.play` | 226 | `audio-file`, `loop`, `volume` |
| 8 | `System.restart-layout` | 225 | - |
| 9 | `System.set-group-active` | 212 | `group-name`, `state` |
| 10 | `System.add-to-eventvar` | 199 | `variable`, `value` |
| 11 | `Tween.tween-one-property` | 174 | `tags`, `property`, `end-value`, `time`, `ease` |
| 12 | `Platform.simulate-control` | 157 | `control` |
| 13 | `Functions.set-function-return-value` | 144 | `value` |
| 14 | `System.reset-global-variables` | 116 | - |
| 15 | `Timer.start-timer` | 103 | `duration`, `type`, `tag` |
| 16 | `Sprite.spawn-another-object` | 97 | `object`, `layer`, `image-point` |
| 17 | `System.go-to-layout` | 87 | `layout` |
| 18 | `Text.set-text` | 80 | `text` |
| 19 | `Audio.fade-volume` | 76 | `tag`, `db`, `duration` |
| 20 | `Camera3D.look-at-position` | 73 | `cam-x/y/z`, `look-x/y/z` |

## Actions by Category

### Variable Operations
```json
// Set variable
{"id": "set-eventvar-value", "objectClass": "System", "parameters": {"variable": "Score", "value": "100"}}

// Add to variable
{"id": "add-to-eventvar", "objectClass": "System", "parameters": {"variable": "Score", "value": "10"}}

// Set boolean
{"id": "set-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "IsAlive", "value": "true"}}

// Set instance variable
{"id": "set-instvar-value", "objectClass": "Player", "parameters": {"instance-variable": "Health", "value": "100"}}
```

### Object Creation/Destruction
```json
// Create object
{"id": "create-object", "objectClass": "System", "parameters": {"object-to-create": "Bullet", "layer": "0", "x": "Player.X", "y": "Player.Y"}}

// Spawn object
{"id": "spawn-another-object", "objectClass": "Player", "parameters": {"object": "Particle", "layer": "0", "image-point": "0"}}

// Destroy object
{"id": "destroy", "objectClass": "Enemy", "parameters": {}}
```

### Layout Control
```json
// Go to layout
{"id": "go-to-layout", "objectClass": "System", "parameters": {"layout": "\"Game\""}}

// Restart layout
{"id": "restart-layout", "objectClass": "System", "parameters": {}}
```

### Animation
```json
// Set animation
{"id": "set-animation", "objectClass": "Player", "parameters": {"animation": "\"Walk\"", "from": "beginning"}}

// Set mirrored
{"id": "set-mirrored", "objectClass": "Player", "parameters": {"state": "mirrored"}}
```

### Tween Animation
```json
// Property tween
{"id": "tween-one-property", "objectClass": "Sprite", "behaviorType": "Tween", "parameters": {
  "tags": "\"fade\"",
  "property": "opacity",
  "end-value": "0",
  "time": "1",
  "ease": "in-out-sine",
  "destroy-on-complete": "no",
  "loop": "no",
  "ping-pong": "no",
  "repeat-count": "1"
}}

// Value tween
{"id": "tween-value", "objectClass": "GameManager", "behaviorType": "Tween", "parameters": {
  "tags": "\"counter\"",
  "start-value": "0",
  "end-value": "100",
  "time": "2",
  "ease": "linear"
}}
```

### Audio
```json
// Play sound
{"id": "play", "objectClass": "Audio", "parameters": {"audio-file": "Jump", "loop": "not-looping", "volume": "0"}}

// Fade volume
{"id": "fade-volume", "objectClass": "Audio", "parameters": {"tag": "\"bgm\"", "db": "-60", "duration": "1"}}
```

### Behavior Control
```json
// Platform simulate control
{"id": "simulate-control", "objectClass": "Player", "behaviorType": "Platform", "parameters": {"control": "jump"}}

// 8Direction simulate control
{"id": "simulate-control", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {"control": "up"}}

// Set vector
{"id": "set-vector-y", "objectClass": "Player", "behaviorType": "Platform", "parameters": {"vector-y": "-500"}}

// Start timer
{"id": "start-timer", "objectClass": "GameManager", "behaviorType": "Timer", "parameters": {"duration": "2", "type": "once", "tag": "\"spawn\""}}
```

### Hierarchy System
```json
// Add child
{"id": "add-child", "objectClass": "Player", "parameters": {
  "child": "Weapon",
  "transform-x": "yes",
  "transform-y": "yes",
  "transform-a": "yes",
  "destroy-with-parent": "yes"
}}
```

### Wait/Async
```json
// Wait seconds
{"id": "wait", "objectClass": "System", "parameters": {"seconds": "1"}}

// Wait for previous actions
{"id": "wait-for-previous-actions", "objectClass": "System", "parameters": {}}
```
