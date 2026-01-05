# Plugin Patterns Reference

常用插件使用模式，基于 490 个官方示例项目分析。

## 数据源

- 完整插件知识：`data/project_analysis/plugins_knowledge.json`
- 使用排名：`data/project_analysis/sorted_indexes.json` → `top_20_plugins`
- Schema 定义：`data/schemas/plugins/*.json`

## Top 10 插件及常用行为

| # | 插件 | 使用次数 | 常用行为 |
|---|------|---------|----------|
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

## 插件类型

### 世界对象 (World Objects)
需要放置在 Layout 中，有位置、大小等属性。

```json
// Object Type 定义
{"name": "Player", "plugin-id": "Sprite", "isGlobal": false, "behaviorTypes": [...]}
```

### 单例插件 (Singleton)
全局唯一，无需放置。

```json
// Object Type 定义
{"name": "Keyboard", "plugin-id": "Keyboard", "singleglobal-inst": {"type": "Keyboard"}}
```

常见单例：`Keyboard`, `Mouse`, `Touch`, `Gamepad`, `Audio`, `Browser`, `AJAX`

### 数据对象 (Non-World)
不可见，用于存储数据。

```json
{"name": "GameData", "plugin-id": "Arr", "isGlobal": true, "nonworld-inst": {"type": "Array", "properties": {"width": 10}}}
```

常见：`Array`, `Dictionary`, `JSON`, `LocalStorage`

## 常用插件模式

### Sprite - 可视对象
```json
// 条件
{"id": "on-collision-with-another-object", "objectClass": "Player", "parameters": {"object": "Enemy"}}
{"id": "is-overlapping-another-object", "objectClass": "Player", "parameters": {"object": "Coin"}}
{"id": "on-created", "objectClass": "Bullet", "parameters": {}}

// 动作
{"id": "set-animation", "objectClass": "Player", "parameters": {"animation": "\"Walk\"", "from": "beginning"}}
{"id": "set-mirrored", "objectClass": "Player", "parameters": {"state": "mirrored"}}
{"id": "spawn-another-object", "objectClass": "Player", "parameters": {"object": "Bullet", "layer": "0", "image-point": "0"}}
{"id": "destroy", "objectClass": "Enemy", "parameters": {}}
{"id": "set-position", "objectClass": "Player", "parameters": {"x": "400", "y": "300"}}
```

### Keyboard - 键盘输入
```json
// 条件
{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 87}}
{"id": "on-key-pressed", "objectClass": "Keyboard", "parameters": {"key": 32}}
{"id": "on-key-released", "objectClass": "Keyboard", "parameters": {"key": 27}}
```

### Mouse - 鼠标输入
```json
// 条件
{"id": "on-click", "objectClass": "Mouse", "parameters": {"mouse-button": "left", "click-type": "clicked"}}
{"id": "on-object-clicked", "objectClass": "Mouse", "parameters": {"mouse-button": "left", "click-type": "clicked", "object-clicked": "Button"}}
{"id": "cursor-is-over-object", "objectClass": "Mouse", "parameters": {"object": "Button"}}
{"id": "mouse-button-is-down", "objectClass": "Mouse", "parameters": {"mouse-button": "left"}}
```

### Touch - 触摸输入
```json
// 条件
{"id": "on-touched-object", "objectClass": "Touch", "parameters": {"object": "Button", "type": "touch"}}
{"id": "on-tap-object", "objectClass": "Touch", "parameters": {"object": "Button"}}
{"id": "is-touching-object", "objectClass": "Touch", "parameters": {"object": "Joystick"}}
{"id": "on-any-touch-start", "objectClass": "Touch", "parameters": {}}
```

### Gamepad - 手柄输入
```json
// 条件
{"id": "is-button-down", "objectClass": "Gamepad", "parameters": {"gamepad": 0, "button": 0}}
{"id": "on-button-pressed", "objectClass": "Gamepad", "parameters": {"gamepad": 0, "button": 0}}
{"id": "compare-axis", "objectClass": "Gamepad", "parameters": {"gamepad": 0, "axis": "left-x", "comparison": 4, "value": "0.5"}}
```

### Audio - 音频
```json
// 动作
{"id": "play", "objectClass": "Audio", "parameters": {"audio-file": "Jump", "loop": "not-looping", "volume": "0", "tag-optional": "\"\""}}
{"id": "play-by-name", "objectClass": "Audio", "parameters": {"folder": "\"Sounds\"", "audio-file-name": "\"explosion\"", "loop": "not-looping", "volume": "0"}}
{"id": "fade-volume", "objectClass": "Audio", "parameters": {"tag": "\"bgm\"", "db": "-60", "duration": "1"}}
{"id": "stop", "objectClass": "Audio", "parameters": {"tag": "\"bgm\""}}
```

### Text - 文本显示
```json
// 动作
{"id": "set-text", "objectClass": "ScoreText", "parameters": {"text": "\"Score: \" & Score"}}
{"id": "append-text", "objectClass": "LogText", "parameters": {"text": "\"\\nNew line\""}}
```

### Array - 数组
```json
// 动作
{"id": "push-back", "objectClass": "Inventory", "parameters": {"where": "back", "value": "\"sword\"", "axis": "x"}}
{"id": "set-at-xy", "objectClass": "Grid", "parameters": {"x": "0", "y": "0", "value": "1"}}

// 表达式
"value": "Inventory.At(0)"
"value": "Grid.At(x, y)"
"value": "Inventory.Width"
```

### Dictionary - 字典
```json
// 动作
{"id": "add-key", "objectClass": "Settings", "parameters": {"key": "\"volume\"", "value": "0.8"}}
{"id": "set-key", "objectClass": "Settings", "parameters": {"key": "\"volume\"", "value": "0.5"}}

// 条件
{"id": "has-key", "objectClass": "Settings", "parameters": {"key": "\"volume\""}}
{"id": "compare-value", "objectClass": "Settings", "parameters": {"key": "\"volume\"", "comparison": 4, "value": "0"}}

// 表达式
"value": "Settings.Get(\"volume\")"
```

### AJAX - 网络请求
```json
// 动作
{"id": "request-project-file", "objectClass": "AJAX", "parameters": {"tag": "\"data\"", "file": "\"data.json\""}}
{"id": "request-url", "objectClass": "AJAX", "parameters": {"tag": "\"api\"", "url": "\"https://api.example.com\""}}

// 条件
{"id": "on-completed", "objectClass": "AJAX", "parameters": {"tag": "\"data\""}}

// 表达式
"value": "AJAX.LastData"
```

### LocalStorage - 本地存储
```json
// 动作
{"id": "set-item", "objectClass": "LocalStorage", "parameters": {"key": "\"highscore\"", "value": "Score"}}

// 条件
{"id": "on-item-get", "objectClass": "LocalStorage", "parameters": {"key": "\"highscore\""}}
{"id": "on-item-exists", "objectClass": "LocalStorage", "parameters": {"key": "\"highscore\""}}

// 表达式（在 on-item-get 后）
"value": "LocalStorage.ItemValue"
```

### Camera3D - 3D 相机
```json
// 动作
{"id": "look-at-position", "objectClass": "Camera3D", "parameters": {
  "cam-x": "Player.X", "cam-y": "Player.Y - 200", "cam-z": "500",
  "look-x": "Player.X", "look-y": "Player.Y", "look-z": "0"
}}
{"id": "move-forward", "objectClass": "Camera3D", "parameters": {"distance": "10"}}
```
