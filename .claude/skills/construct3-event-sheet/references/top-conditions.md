# Top Conditions Reference

基于 490 个官方示例项目的条件使用频率统计。

## 数据源

完整数据：`data/project_analysis/sorted_indexes.json` → `top_50_conditions`

## Top 20 条件

| # | ID | 使用次数 | 参数 |
|---|-----|---------|------|
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

## 按类型分类

### 输入检测
```json
// 键盘按住
{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 87}}

// 键盘按下瞬间
{"id": "on-key-pressed", "objectClass": "Keyboard", "parameters": {"key": 32}}

// 手柄按钮
{"id": "is-button-down", "objectClass": "Gamepad", "parameters": {"gamepad": 0, "button": 0}}

// 鼠标悬停
{"id": "cursor-is-over-object", "objectClass": "Mouse", "parameters": {"object": "Button"}}

// 触摸对象
{"id": "is-touching-object", "objectClass": "Touch", "parameters": {"object": "Button"}}
```

### 碰撞检测
```json
// 碰撞触发
{"id": "on-collision-with-another-object", "objectClass": "Player", "parameters": {"object": "Enemy"}}

// 重叠检测
{"id": "is-overlapping-another-object", "objectClass": "Player", "parameters": {"object": "Coin"}}
```

### 生命周期
```json
// 场景开始
{"id": "on-start-of-layout", "objectClass": "System", "parameters": {}}

// 对象创建
{"id": "on-created", "objectClass": "Bullet", "parameters": {}}
```

### 循环
```json
// For Each
{"id": "for-each", "objectClass": "System", "parameters": {"object": "Enemy"}}

// For 循环
{"id": "for", "objectClass": "System", "parameters": {"name": "\"i\"", "start-index": "0", "end-index": "10"}}

// 重复
{"id": "repeat", "objectClass": "System", "parameters": {"count": "5"}}
```

### 比较
```json
// 比较变量
{"id": "compare-eventvar", "objectClass": "System", "parameters": {"variable": "Score", "comparison": 4, "value": "100"}}

// 比较两值
{"id": "compare-two-values", "objectClass": "System", "parameters": {"first-value": "Player.X", "comparison": 4, "second-value": "400"}}

// 布尔判断
{"id": "compare-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "IsAlive"}}
```

### 行为状态
```json
// Platform 在地面
{"id": "is-on-floor", "objectClass": "Player", "behaviorType": "Platform", "parameters": {}}

// Platform 跳跃中
{"id": "is-jumping", "objectClass": "Player", "behaviorType": "Platform", "parameters": {}}

// Tween 播放中
{"id": "is-playing", "objectClass": "Sprite", "behaviorType": "Tween", "parameters": {"tags": "\"fade\""}}

// Timer 触发
{"id": "on-timer", "objectClass": "GameManager", "behaviorType": "Timer", "parameters": {"tag": "\"spawn\""}}
```
