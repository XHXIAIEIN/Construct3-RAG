# Plugin Patterns Reference

Common plugin usage patterns based on 490 official example projects.

## Contents

- [Data Source](#data-source)
- [Top 10 Plugins](#top-10-plugins)
- [Plugin Types](#plugin-types)
- [Common Plugin Patterns](#common-plugin-patterns)

---

## Data Source

- Full plugin knowledge: `data/project_analysis/plugins_knowledge.json`
- Usage ranking: `data/project_analysis/sorted_indexes.json` → `top_20_plugins`
- Schema definitions: `data/schemas/plugins/*.json`

## Top 10 Plugins

| # | Plugin | Usage Count | Common Behaviors |
|---|--------|-------------|------------------|
| 1 | Sprite | 3404 | Tween, Platform, EightDir, Bullet, Fade, Sin |
| 2 | Shape3D | 831 | Tween, solid, MoveTo, Sin |
| 3 | TiledBg | 704 | Sin, Tween, solid, Fade |
| 4 | Text | 573 | Tween, Flash, Fade, Anchor |
| 5 | Spritefont2 | 339 | Flash, Fade, Tween |
| 6 | Keyboard | 252 | - |
| 7 | Particles | 207 | Tween, Pin, Timer |
| 8 | Button | 164 | - |
| 9 | Tilemap | 142 | Physics, solid |
| 10 | Mouse | 111 | - |

## Plugin Types

### World Objects
Placed in Layout, have position, size, etc.

```json
// Object Type definition
{"name": "Player", "plugin-id": "Sprite", "isGlobal": false, "behaviorTypes": [...]}
```

### Singleton Plugins
Global unique, no placement needed.

```json
// Object Type definition
{"name": "Keyboard", "plugin-id": "Keyboard", "singleglobal-inst": {"type": "Keyboard"}}
```

Common singletons: `Keyboard`, `Mouse`, `Touch`, `Gamepad`, `Audio`, `Browser`, `AJAX`

### Data Objects (Non-World)
Invisible, used for data storage.

```json
{"name": "GameData", "plugin-id": "Arr", "isGlobal": true, "nonworld-inst": {"type": "Array", "properties": {"width": 10}}}
```

Common: `Array`, `Dictionary`, `JSON`, `LocalStorage`

## Common Plugin Patterns

### Sprite - Visual Object
```json
// Conditions
{"id": "on-collision-with-another-object", "objectClass": "Player", "parameters": {"object": "Enemy"}}
{"id": "is-overlapping-another-object", "objectClass": "Player", "parameters": {"object": "Coin"}}
{"id": "on-created", "objectClass": "Bullet", "parameters": {}}

// Actions
{"id": "set-animation", "objectClass": "Player", "parameters": {"animation": "\"Walk\"", "from": "beginning"}}
{"id": "set-mirrored", "objectClass": "Player", "parameters": {"state": "mirrored"}}
{"id": "spawn-another-object", "objectClass": "Player", "parameters": {"object": "Bullet", "layer": "0", "image-point": "0"}}
{"id": "destroy", "objectClass": "Enemy", "parameters": {}}
{"id": "set-position", "objectClass": "Player", "parameters": {"x": "400", "y": "300"}}
```

### Keyboard - Keyboard Input
```json
// Conditions
{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 87}}
{"id": "on-key-pressed", "objectClass": "Keyboard", "parameters": {"key": 32}}
{"id": "on-key-released", "objectClass": "Keyboard", "parameters": {"key": 27}}
```

### Mouse - Mouse Input
```json
// Conditions
{"id": "on-click", "objectClass": "Mouse", "parameters": {"mouse-button": "left", "click-type": "clicked"}}
{"id": "on-object-clicked", "objectClass": "Mouse", "parameters": {"mouse-button": "left", "click-type": "clicked", "object-clicked": "Button"}}
{"id": "cursor-is-over-object", "objectClass": "Mouse", "parameters": {"object": "Button"}}
{"id": "mouse-button-is-down", "objectClass": "Mouse", "parameters": {"mouse-button": "left"}}
```

### Touch - Touch Input
```json
// Conditions
{"id": "on-touched-object", "objectClass": "Touch", "parameters": {"object": "Button", "type": "touch"}}
{"id": "on-tap-object", "objectClass": "Touch", "parameters": {"object": "Button"}}
{"id": "is-touching-object", "objectClass": "Touch", "parameters": {"object": "Joystick"}}
{"id": "on-any-touch-start", "objectClass": "Touch", "parameters": {}}
```

### Gamepad - Controller Input
```json
// Conditions
{"id": "is-button-down", "objectClass": "Gamepad", "parameters": {"gamepad": 0, "button": 0}}
{"id": "on-button-pressed", "objectClass": "Gamepad", "parameters": {"gamepad": 0, "button": 0}}
{"id": "compare-axis", "objectClass": "Gamepad", "parameters": {"gamepad": 0, "axis": "left-x", "comparison": 4, "value": "0.5"}}
```

### Audio - Audio
```json
// Actions
{"id": "play", "objectClass": "Audio", "parameters": {"audio-file": "Jump", "loop": "not-looping", "volume": "0", "tag-optional": "\"\""}}
{"id": "play-by-name", "objectClass": "Audio", "parameters": {"folder": "\"Sounds\"", "audio-file-name": "\"explosion\"", "loop": "not-looping", "volume": "0"}}
{"id": "fade-volume", "objectClass": "Audio", "parameters": {"tag": "\"bgm\"", "db": "-60", "duration": "1"}}
{"id": "stop", "objectClass": "Audio", "parameters": {"tag": "\"bgm\""}}
```

### Text - Text Display
```json
// Actions
{"id": "set-text", "objectClass": "ScoreText", "parameters": {"text": "\"Score: \" & Score"}}
{"id": "append-text", "objectClass": "LogText", "parameters": {"text": "\"\\nNew line\""}}
```

### Array - Array
```json
// Actions
{"id": "push-back", "objectClass": "Inventory", "parameters": {"where": "back", "value": "\"sword\"", "axis": "x"}}
{"id": "set-at-xy", "objectClass": "Grid", "parameters": {"x": "0", "y": "0", "value": "1"}}

// Expressions
"value": "Inventory.At(0)"
"value": "Grid.At(x, y)"
"value": "Inventory.Width"
```

### Dictionary - Dictionary
```json
// Actions
{"id": "add-key", "objectClass": "Settings", "parameters": {"key": "\"volume\"", "value": "0.8"}}
{"id": "set-key", "objectClass": "Settings", "parameters": {"key": "\"volume\"", "value": "0.5"}}

// Conditions
{"id": "has-key", "objectClass": "Settings", "parameters": {"key": "\"volume\""}}
{"id": "compare-value", "objectClass": "Settings", "parameters": {"key": "\"volume\"", "comparison": 4, "value": "0"}}

// Expressions
"value": "Settings.Get(\"volume\")"
```

### AJAX - Network Requests
```json
// Actions
{"id": "request-project-file", "objectClass": "AJAX", "parameters": {"tag": "\"data\"", "file": "\"data.json\""}}
{"id": "request-url", "objectClass": "AJAX", "parameters": {"tag": "\"api\"", "url": "\"https://api.example.com\""}}

// Conditions
{"id": "on-completed", "objectClass": "AJAX", "parameters": {"tag": "\"data\""}}

// Expressions
"value": "AJAX.LastData"
```

### LocalStorage - Local Storage
```json
// Actions
{"id": "set-item", "objectClass": "LocalStorage", "parameters": {"key": "\"highscore\"", "value": "Score"}}

// Conditions
{"id": "on-item-get", "objectClass": "LocalStorage", "parameters": {"key": "\"highscore\""}}
{"id": "on-item-exists", "objectClass": "LocalStorage", "parameters": {"key": "\"highscore\""}}

// Expressions (after on-item-get)
"value": "LocalStorage.ItemValue"
```

### Camera3D - 3D Camera
```json
// Actions
{"id": "look-at-position", "objectClass": "Camera3D", "parameters": {
  "cam-x": "Player.X", "cam-y": "Player.Y - 200", "cam-z": "500",
  "look-x": "Player.X", "look-y": "Player.Y", "look-z": "0"
}}
{"id": "move-forward", "objectClass": "Camera3D", "parameters": {"distance": "10"}}
```
