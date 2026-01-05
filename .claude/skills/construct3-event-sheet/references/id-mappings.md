# ID Mappings Reference

ID 格式转换表，用于在不同上下文中正确使用标识符。

## 数据源

完整映射：`data/project_analysis/id_mappings.json`

## 行为 ID 映射

编辑器显示名称与内部 behaviorId 的对应关系：

| 显示名称 | behaviorId | 说明 |
|----------|------------|------|
| 8Direction | EightDir | 八方向移动 |
| Solid | solid | 固体碰撞 |
| Scroll To | scrollto | 滚动跟随 |
| Line of Sight | LOS | 视线检测 |
| Drag & Drop | DragnDrop | 拖放 |
| Destroy outside layout | destroy | 离开布局销毁 |
| Bound to layout | bound | 限制在布局内 |
| Sine | Sin | 正弦运动 |

### 在事件表 JSON 中使用

```json
// behaviorType 使用显示名称
{"id": "simulate-control", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {...}}
{"id": "is-on-floor", "objectClass": "Player", "behaviorType": "Platform", "parameters": {}}
{"id": "start-timer", "objectClass": "GameManager", "behaviorType": "Timer", "parameters": {...}}
```

### 在 Object Type 定义中使用

```json
// behaviorId 使用内部 ID
"behaviorTypes": [
  {"behaviorId": "EightDir", "name": "8Direction"},
  {"behaviorId": "Platform", "name": "Platform"},
  {"behaviorId": "solid", "name": "Solid"},
  {"behaviorId": "Tween", "name": "Tween"}
]
```

## 插件 ID 映射

| 显示名称 | plugin-id | 说明 |
|----------|-----------|------|
| Sprite font | Spritefont2 | 精灵字体 |
| Array | Arr | 数组 |
| 3D camera | Camera3D | 3D 相机 |
| Gamepad | gamepad | 手柄 |
| 9-patch | NinePatch | 九宫格 |
| Tiled Background | TiledBg | 平铺背景 |
| 3D shape | Shape3D | 3D 形状 |
| Drawing canvas | DrawingCanvas | 绘图画布 |

### 在 Object Type 定义中使用

```json
{"name": "Player", "plugin-id": "Sprite"}
{"name": "Background", "plugin-id": "TiledBg"}
{"name": "ScoreText", "plugin-id": "Spritefont2"}
{"name": "Inventory", "plugin-id": "Arr"}
{"name": "Camera", "plugin-id": "Camera3D"}
```

## 条件/动作 ID 规范

### 命名规则
- 使用 `kebab-case` (小写 + 连字符)
- 示例：`on-start-of-layout`, `set-eventvar-value`, `is-overlapping-another-object`

### 常见 ID 模式

| 模式 | 示例 | 说明 |
|------|------|------|
| `on-*` | `on-created`, `on-collision-with-another-object` | 触发器 |
| `is-*` | `is-on-floor`, `is-moving`, `is-playing` | 状态检测 |
| `compare-*` | `compare-eventvar`, `compare-two-values` | 比较 |
| `set-*` | `set-text`, `set-animation`, `set-position` | 设置属性 |
| `add-*` | `add-to-eventvar`, `add-child` | 添加 |
| `pick-*` | `pick-by-evaluate`, `pick-random-instance` | 实例选择 |

## Schema 查询

### 查找条件/动作 ID
```bash
# 在 Schema 文件中搜索
grep -n "simulate-control" data/schemas/behaviors/*.json
grep -n "create-object" data/schemas/plugins/system.json
```

### Schema 文件位置
- 插件：`data/schemas/plugins/{plugin-id}.json`
- 行为：`data/schemas/behaviors/{behavior-id}.json`

## 常见错误

### 行为名称错误
```json
// ❌ 错误 - 使用了 behaviorId
"behaviorType": "EightDir"

// ✅ 正确 - 使用显示名称
"behaviorType": "8Direction"
```

### 插件 ID 错误
```json
// ❌ 错误 - 使用了显示名称
"plugin-id": "Array"

// ✅ 正确 - 使用 plugin-id
"plugin-id": "Arr"
```

### ACE ID 大小写错误
```json
// ❌ 错误 - 使用了 camelCase
"id": "setAnimation"

// ✅ 正确 - 使用 kebab-case
"id": "set-animation"
```
