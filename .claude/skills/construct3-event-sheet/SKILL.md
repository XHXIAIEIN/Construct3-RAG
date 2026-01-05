---
name: construct3-event-sheet
description: >
  Generates Construct 3 event sheet JSON that can be pasted into the C3 editor.
  Invoked when generating clipboard-ready event blocks, querying ACE IDs and
  parameter formats, implementing game logic patterns (movement, collision, timers),
  or converting between Schema and editor ID formats. Based on 490 official examples.
---

# Construct 3 Event Sheet Code Generation Guide

本指南提供生成 Construct 3 事件表 JSON 代码所需的完整知识。基于 490 个官方示例项目分析。

## 快速开始

### 剪贴板 JSON 基本结构

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [...]}
```

### type 类型
| type | 用途 | 粘贴位置 |
|------|------|----------|
| `"events"` | 完整事件块 | 事件表边距 |
| `"conditions"` | 仅条件 | 选中条件后 |
| `"actions"` | 仅动作 | 选中动作后 |

### 如何写入剪贴板

```javascript
// 必须用 ClipboardItem + Blob，不能用 writeText()
const blob = new Blob([json], {type: 'text/plain'});
await navigator.clipboard.write([new ClipboardItem({'text/plain': blob})]);
```

### 最小示例：每2秒创建对象

```json
{"is-c3-clipboard-data":true,"type":"events","items":[
  {"eventType":"block",
   "conditions":[{"id":"every-x-seconds","objectClass":"System","parameters":{"interval-seconds":"2"}}],
   "actions":[{"id":"create-object","objectClass":"System","parameters":{"object-to-create":"Sprite","layer":"0","x":"400","y":"300"}}]}
]}
```

## 核心概念

### 事件块结构

```json
{
  "eventType": "block",
  "conditions": [
    {"id": "条件ID", "objectClass": "对象名", "parameters": {...}}
  ],
  "actions": [
    {"id": "动作ID", "objectClass": "对象名", "parameters": {...}}
  ],
  "children": [...]  // 可选：子事件
}
```

### 带行为的 ACE

```json
{"id": "simulate-control", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {"control": "up"}}
```

### 其他 eventType

| eventType | 用途 |
|-----------|------|
| `"variable"` | 变量定义 |
| `"comment"` | 注释 |
| `"group"` | 事件组 |
| `"function-block"` | 函数定义 |

### 参数类型速查

| 类型 | 格式 | 示例 |
|------|------|------|
| 数字 | 直接写 | `"x": "400"` |
| 字符串 | 内嵌引号 | `"text": "\"Hello\""` |
| 表达式 | 直接写 | `"x": "Player.X + 100"` |
| 字符串拼接 | & 连接 | `"text": "\"Score: \" & Score"` |
| 比较运算符 | 数字 0-5 | `"comparison": 0` (=) |
| 键码 | 数字 | `"key": 87` (W键) |

### 比较运算符值
0=等于, 1=不等于, 2=小于, 3=小于等于, 4=大于, 5=大于等于

详见 [parameter-types.md](references/parameter-types.md#comparison-cmp---比较运算符)

## 关键参考索引

根据需求查阅详细参考文档：

### 格式与 ID
- **[clipboard-format.md](references/clipboard-format.md)** - 剪贴板 JSON 完整格式
- **[parameter-types.md](references/parameter-types.md)** - 参数类型详解
- **[id-mappings.md](references/id-mappings.md)** - ID 格式转换表

### ACE 参考
- **[system-reference.md](references/system-reference.md)** - System 完整 ACE (56条件+81动作)
- **[top-conditions.md](references/top-conditions.md)** - Top 50 常用条件
- **[top-actions.md](references/top-actions.md)** - Top 50 常用动作

### 插件与行为
- **[plugin-patterns.md](references/plugin-patterns.md)** - 常用插件使用模式
- **[behavior-config.md](references/behavior-config.md)** - 行为属性配置表

### 其他
- **[deprecated-features.md](references/deprecated-features.md)** - 废弃/取代功能警告

## Top 10 常用模式

### 1. WASD 控制 (8Direction)

```json
{"is-c3-clipboard-data":true,"type":"events","items":[
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":87}}],"actions":[{"id":"simulate-control","objectClass":"Player","behaviorType":"8Direction","parameters":{"control":"up"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":65}}],"actions":[{"id":"simulate-control","objectClass":"Player","behaviorType":"8Direction","parameters":{"control":"left"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":83}}],"actions":[{"id":"simulate-control","objectClass":"Player","behaviorType":"8Direction","parameters":{"control":"down"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":68}}],"actions":[{"id":"simulate-control","objectClass":"Player","behaviorType":"8Direction","parameters":{"control":"right"}}]}
]}
```

### 2. 平台跳跃控制 (Platform)

```json
{"eventType":"block",
 "conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":32}}],
 "actions":[{"id":"simulate-control","objectClass":"Player","behaviorType":"Platform","parameters":{"control":"jump"}}]}
```

### 3. 碰撞检测

```json
{"eventType":"block",
 "conditions":[{"id":"on-collision-with-another-object","objectClass":"Player","parameters":{"object":"Enemy"}}],
 "actions":[{"id":"destroy","objectClass":"Enemy","parameters":{}}]}
```

### 4. 定时器

```json
{"eventType":"block",
 "conditions":[{"id":"every-x-seconds","objectClass":"System","parameters":{"interval-seconds":"1"}}],
 "actions":[{"id":"add-to-eventvar","objectClass":"System","parameters":{"variable":"Timer","value":"1"}}]}
```

### 5. 场景开始初始化

```json
{"eventType":"block",
 "conditions":[{"id":"on-start-of-layout","objectClass":"System","parameters":{}}],
 "actions":[
   {"id":"set-eventvar-value","objectClass":"System","parameters":{"variable":"Score","value":"0"}},
   {"id":"create-object","objectClass":"System","parameters":{"object-to-create":"Player","layer":"0","x":"400","y":"300"}}
 ]}
```

### 6. 变量定义

```json
{"eventType":"variable","name":"Score","type":"number","initialValue":"0","comment":"","isStatic":false,"isConstant":false}
```

### 7. 条件分支 (Else)

```json
{"eventType":"block","conditions":[{"id":"compare-eventvar","objectClass":"System","parameters":{"variable":"Health","comparison":4,"value":"0"}}],"actions":[...]},
{"eventType":"block","conditions":[{"id":"else","objectClass":"System","parameters":{}}],"actions":[...]}
```

### 8. 循环遍历

```json
{"eventType":"block",
 "conditions":[{"id":"for-each","objectClass":"System","parameters":{"object":"Enemy"}}],
 "actions":[{"id":"set-instvar-value","objectClass":"Enemy","parameters":{"instance-variable":"Health","value":"100"}}]}
```

### 9. 函数调用

```json
// 调用无返回值函数
{"callFunction":"MyFunction","parameters":["param1","param2"]}

// 调用有返回值函数（在表达式中）
"value": "Functions.Calculate(10, 20)"
```

### 10. Tween 动画

```json
{"eventType":"block",
 "conditions":[{"id":"on-start-of-layout","objectClass":"System","parameters":{}}],
 "actions":[{"id":"tween-one-property","objectClass":"Sprite","behaviorType":"Tween","parameters":{
   "tags":"\"fade\"","property":"opacity","end-value":"0","time":"1","ease":"in-out-sine",
   "destroy-on-complete":"no","loop":"no","ping-pong":"no","repeat-count":"1"
 }}]}
```

## 最佳实践

### 避免废弃功能

| 废弃功能 | 替代方案 |
|----------|----------|
| `Function` 插件 | 内置 `Functions` 系统 |
| `Pin` 行为 | Hierarchies (Add child) |
| `Fade` 行为 | `Tween` 行为 |
| `solid.tags` 属性 | Instance tags |

### ID 命名规范

- ACE ID 使用 `kebab-case`: `"set-animation"`, `"on-collision-with-another-object"`
- 对象名使用 PascalCase: `"Player"`, `"GameManager"`
- 行为名与编辑器显示一致: `"8Direction"`, `"Platform"`

### 字符串参数

```json
// 错误 - 字符串参数缺少内嵌引号
"animation": "Walk"

// 正确 - 必须有内嵌引号
"animation": "\"Walk\""
```

## 故障排除

### 粘贴无反应

| 原因 | 解决 |
|------|------|
| 用了 `writeText()` | 改用 `ClipboardItem + Blob` |
| 焦点不在目标区域 | 先点击事件表边距再粘贴 |
| JSON 格式错误 | 检查 JSON 语法 |

### 动作/条件报错

| 原因 | 解决 |
|------|------|
| ID 错误 | 查阅 [top-actions.md](references/top-actions.md) 或 [system-reference.md](references/system-reference.md) |
| 参数名错误 | 检查 Schema 定义 |
| 缺少 behaviorType | 行为 ACE 必须指定行为名 |

### 字符串失败

| 原因 | 解决 |
|------|------|
| 缺少内嵌引号 | 用 `"\"value\""` 格式 |
| 特殊字符 | 正确转义 |

## 统计概览

基于 490 个官方示例项目分析：

| 类别 | 数量 |
|------|------|
| 分析文件数 | 9,491 |
| 插件类型 | 56 |
| 行为类型 | 30 |
| 条件定义 | 2,493 |
| 动作定义 | 6,204 |

### Top 5 常用插件
1. **Sprite** (3,404次) - 核心可视对象
2. **Shape3D** (831次) - 3D 形状
3. **TiledBg** (704次) - 平铺背景
4. **Text** (573次) - 文本显示
5. **Keyboard** (252次) - 键盘输入

### Top 5 常用行为
1. **Tween** (1,018次) - 属性动画
2. **solid** (310次) - 固体碰撞
3. **Timer** (238次) - 定时器
4. **Sin** (214次) - 正弦运动
5. **Fade** (183次) - 淡入淡出

### Top 5 常用条件
1. **System.else** (1,261次) - 否则
2. **System.evaluate-expression** (1,195次) - 表达式求值
3. **Keyboard.key-is-down** (618次) - 按键检测
4. **System.for-each** (497次) - 遍历对象
5. **Keyboard.on-key-pressed** (488次) - 按键触发

### Top 5 常用动作
1. **System.set-eventvar-value** (1,726次) - 设置变量
2. **System.create-object** (781次) - 创建对象
3. **System.wait** (411次) - 等待
4. **System.set-boolean-eventvar** (405次) - 设置布尔变量
5. **System.wait-for-previous-actions** (267次) - 等待前置动作

## 相关资源

- **Schema 文件**: `data/schemas/plugins/*.json`, `data/schemas/behaviors/*.json`
- **完整知识库**: `data/project_analysis/complete_knowledge_base.json`
- **官方文档**: https://www.construct.net/en/make-games/manuals/construct-3
