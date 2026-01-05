# Top Actions Reference

基于 490 个官方示例项目的动作使用频率统计。

## Contents

- [数据源](#数据源)
- [Top 20 动作](#top-20-动作)
- [动作详解](#动作详解)

---

## 数据源

完整数据：`data/project_analysis/sorted_indexes.json` → `top_50_actions`

## Top 20 动作

| # | ID | 使用次数 | 参数 |
|---|-----|---------|------|
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

## 按类型分类

### 变量操作
```json
// 设置变量
{"id": "set-eventvar-value", "objectClass": "System", "parameters": {"variable": "Score", "value": "100"}}

// 增加变量
{"id": "add-to-eventvar", "objectClass": "System", "parameters": {"variable": "Score", "value": "10"}}

// 设置布尔
{"id": "set-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "IsAlive", "value": "true"}}

// 设置实例变量
{"id": "set-instvar-value", "objectClass": "Player", "parameters": {"instance-variable": "Health", "value": "100"}}
```

### 对象创建/销毁
```json
// 创建对象
{"id": "create-object", "objectClass": "System", "parameters": {"object-to-create": "Bullet", "layer": "0", "x": "Player.X", "y": "Player.Y"}}

// 生成对象
{"id": "spawn-another-object", "objectClass": "Player", "parameters": {"object": "Particle", "layer": "0", "image-point": "0"}}

// 销毁对象
{"id": "destroy", "objectClass": "Enemy", "parameters": {}}
```

### 场景控制
```json
// 切换场景
{"id": "go-to-layout", "objectClass": "System", "parameters": {"layout": "\"Game\""}}

// 重载场景
{"id": "restart-layout", "objectClass": "System", "parameters": {}}
```

### 动画
```json
// 设置动画
{"id": "set-animation", "objectClass": "Player", "parameters": {"animation": "\"Walk\"", "from": "beginning"}}

// 设置镜像
{"id": "set-mirrored", "objectClass": "Player", "parameters": {"state": "mirrored"}}
```

### Tween 动画
```json
// 属性补间
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

// 值补间
{"id": "tween-value", "objectClass": "GameManager", "behaviorType": "Tween", "parameters": {
  "tags": "\"counter\"",
  "start-value": "0",
  "end-value": "100",
  "time": "2",
  "ease": "linear"
}}
```

### 音频
```json
// 播放音效
{"id": "play", "objectClass": "Audio", "parameters": {"audio-file": "Jump", "loop": "not-looping", "volume": "0"}}

// 淡出音量
{"id": "fade-volume", "objectClass": "Audio", "parameters": {"tag": "\"bgm\"", "db": "-60", "duration": "1"}}
```

### 行为控制
```json
// Platform 模拟控制
{"id": "simulate-control", "objectClass": "Player", "behaviorType": "Platform", "parameters": {"control": "jump"}}

// 8Direction 模拟控制
{"id": "simulate-control", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {"control": "up"}}

// 设置向量
{"id": "set-vector-y", "objectClass": "Player", "behaviorType": "Platform", "parameters": {"vector-y": "-500"}}

// 启动定时器
{"id": "start-timer", "objectClass": "GameManager", "behaviorType": "Timer", "parameters": {"duration": "2", "type": "once", "tag": "\"spawn\""}}
```

### 层级系统
```json
// 添加子对象
{"id": "add-child", "objectClass": "Player", "parameters": {
  "child": "Weapon",
  "transform-x": "yes",
  "transform-y": "yes",
  "transform-a": "yes",
  "destroy-with-parent": "yes"
}}
```

### 等待/异步
```json
// 等待秒数
{"id": "wait", "objectClass": "System", "parameters": {"seconds": "1"}}

// 等待前置动作
{"id": "wait-for-previous-actions", "objectClass": "System", "parameters": {}}
```
