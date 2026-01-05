# Behavior Configuration Reference

行为属性配置，基于 490 个官方示例项目分析。

## Contents

- [数据源](#数据源)
- [Top 10 行为](#top-10-行为)
- [行为配置详解](#行为配置详解) - Tween, Platform, EightDir, Bullet, Timer, Sin, solid, Physics, Fade, Flash
- [行为组合模式](#行为组合模式) - 平台角色、俯视角、子弹、UI元素

---

## 数据源

- 完整行为知识：`data/project_analysis/behaviors_knowledge.json`
- 使用排名：`data/project_analysis/sorted_indexes.json` → `top_20_behaviors`
- Schema 定义：`data/schemas/behaviors/*.json`

## Top 10 行为

| # | 行为 ID | 使用次数 | 主要用途 |
|---|---------|---------|----------|
| 1 | Tween | 1018 | 属性动画 |
| 2 | solid | 310 | 固体碰撞 |
| 3 | Timer | 238 | 定时器 |
| 4 | Sin | 214 | 正弦运动 |
| 5 | Fade | 183 | 淡入淡出 |
| 6 | Bullet | 181 | 子弹运动 |
| 7 | Flash | 97 | 闪烁效果 |
| 8 | Platform | 81 | 平台跳跃 |
| 9 | Physics | 78 | 物理模拟 |
| 10 | EightDir | 66 | 八方向移动 |

## 行为配置详解

### Tween - 属性动画
```json
"behaviorTypes": [{"behaviorId": "Tween", "name": "Tween"}]
```
属性：`enabled`

常用动作：
```json
{"id": "tween-one-property", "objectClass": "Sprite", "behaviorType": "Tween", "parameters": {
  "tags": "\"fade\"",
  "property": "opacity",     // x, y, width, height, angle, opacity, z-elevation, etc.
  "end-value": "0",
  "time": "1",
  "ease": "in-out-sine",     // linear, in-sine, out-sine, in-out-sine, etc.
  "destroy-on-complete": "no",
  "loop": "no",
  "ping-pong": "no",
  "repeat-count": "1"
}}
```

### Platform - 平台跳跃
```json
"behaviorTypes": [{"behaviorId": "Platform", "name": "Platform"}]
```
属性：
| 属性 | 常用值 | 说明 |
|------|--------|------|
| `max-speed` | 330-480 | 最大移动速度 |
| `acceleration` | 1024-2048 | 加速度 |
| `deceleration` | 1024-1600 | 减速度 |
| `jump-strength` | 768-1200 | 跳跃力度 |
| `gravity` | 1000-2048 | 重力 |
| `max-fall-speed` | 1000-5000 | 最大下落速度 |
| `double-jump` | true/false | 二段跳 |
| `default-controls` | true/false | 默认键盘控制 |

常用 ACE：
```json
// 条件
{"id": "is-on-floor", "objectClass": "Player", "behaviorType": "Platform", "parameters": {}}
{"id": "is-jumping", "objectClass": "Player", "behaviorType": "Platform", "parameters": {}}
{"id": "is-falling", "objectClass": "Player", "behaviorType": "Platform", "parameters": {}}
{"id": "on-landed", "objectClass": "Player", "behaviorType": "Platform", "parameters": {}}

// 动作
{"id": "simulate-control", "objectClass": "Player", "behaviorType": "Platform", "parameters": {"control": "jump"}}
{"id": "set-vector-y", "objectClass": "Player", "behaviorType": "Platform", "parameters": {"vector-y": "-800"}}
{"id": "set-max-speed", "objectClass": "Player", "behaviorType": "Platform", "parameters": {"max-speed": "400"}}
```

### EightDir - 八方向移动
```json
"behaviorTypes": [{"behaviorId": "EightDir", "name": "8Direction"}]
```
属性：
| 属性 | 常用值 | 说明 |
|------|--------|------|
| `max-speed` | 200-400 | 最大速度 |
| `acceleration` | 600-1500 | 加速度 |
| `deceleration` | 500-1000 | 减速度 |
| `directions` | dir-8, dir-4 | 方向数 |
| `set-angle` | no, smooth | 角度设置 |
| `default-controls` | true/false | 默认控制 |

常用 ACE：
```json
// 动作
{"id": "simulate-control", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {"control": "up"}}
{"id": "set-max-speed", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {"max-speed": "300"}}
{"id": "set-enabled", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {"state": "disabled"}}

// 条件
{"id": "is-moving", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {}}
```

### Bullet - 子弹运动
```json
"behaviorTypes": [{"behaviorId": "Bullet", "name": "Bullet"}]
```
属性：
| 属性 | 常用值 | 说明 |
|------|--------|------|
| `speed` | 200-1200 | 速度 |
| `acceleration` | 0 或负值 | 加速度 |
| `gravity` | 0-2048 | 重力 |
| `bounce-off-solids` | true/false | 碰撞反弹 |
| `set-angle` | true/false | 设置角度 |

### Timer - 定时器
```json
"behaviorTypes": [{"behaviorId": "Timer", "name": "Timer"}]
```
常用 ACE：
```json
// 动作
{"id": "start-timer", "objectClass": "GameManager", "behaviorType": "Timer", "parameters": {
  "duration": "2",
  "type": "once",      // once, regular
  "tag": "\"spawn\""
}}

// 条件
{"id": "on-timer", "objectClass": "GameManager", "behaviorType": "Timer", "parameters": {"tag": "\"spawn\""}}
```

### Sin - 正弦运动
```json
"behaviorTypes": [{"behaviorId": "Sin", "name": "Sine"}]
```
属性：
| 属性 | 常用值 | 说明 |
|------|--------|------|
| `movement` | size, width, angle, x, y | 运动类型 |
| `wave` | sine, sawtooth, triangle | 波形 |
| `period` | 1-4 | 周期(秒) |
| `magnitude` | 1-50 | 幅度 |

### solid - 固体碰撞
```json
"behaviorTypes": [{"behaviorId": "solid", "name": "Solid"}]
```
属性：`enabled`, `tags`

### Physics - 物理引擎
```json
"behaviorTypes": [{"behaviorId": "Physics", "name": "Physics"}]
```
属性：
| 属性 | 常用值 | 说明 |
|------|--------|------|
| `immovable` | true/false | 不可移动 |
| `collision-mask` | circle, bounding-box | 碰撞形状 |
| `density` | 1-100 | 密度 |
| `friction` | 0.1-1 | 摩擦力 |
| `elasticity` | 0.1-0.5 | 弹性 |

### Fade - 淡入淡出 (已被 Tween 取代)
```json
"behaviorTypes": [{"behaviorId": "Fade", "name": "Fade"}]
```
属性：`fade-in-time`, `wait-time`, `fade-out-time`, `destroy`

### Flash - 闪烁
```json
"behaviorTypes": [{"behaviorId": "Flash", "name": "Flash"}]
```
动作：
```json
{"id": "flash", "objectClass": "Player", "behaviorType": "Flash", "parameters": {"on-time": "0.1", "off-time": "0.1", "duration": "1"}}
```

## 行为组合模式

### 平台游戏角色
```json
"behaviorTypes": [
  {"behaviorId": "Platform", "name": "Platform"},
  {"behaviorId": "Tween", "name": "Tween"},
  {"behaviorId": "Flash", "name": "Flash"}
]
```

### 俯视角角色
```json
"behaviorTypes": [
  {"behaviorId": "EightDir", "name": "8Direction"},
  {"behaviorId": "Tween", "name": "Tween"},
  {"behaviorId": "LOS", "name": "LineOfSight"}
]
```

### 子弹/投射物
```json
"behaviorTypes": [
  {"behaviorId": "Bullet", "name": "Bullet"},
  {"behaviorId": "destroy", "name": "DestroyOutsideLayout"}
]
```

### 带动画的 UI 元素
```json
"behaviorTypes": [
  {"behaviorId": "Tween", "name": "Tween"},
  {"behaviorId": "Anchor", "name": "Anchor"}
]
```
