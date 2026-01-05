---
name: construct3-event-sheet
description: >
  Generates Construct 3 event sheet JSON that can be pasted into the C3 editor.
  Invoked when generating clipboard-ready event blocks, querying ACE IDs and
  parameter formats, implementing game logic patterns (movement, collision, timers),
  or converting between Schema and editor ID formats. Based on 490 official examples.
---

# Construct 3 Event Sheet Code Generation Guide

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

## 参考文档

| 文档 | 用途 |
|------|------|
| [clipboard-format.md](references/clipboard-format.md) | 完整 JSON 格式、Object Types、World Instances |
| [parameter-types.md](references/parameter-types.md) | 参数类型、键码、比较运算符 |
| [id-mappings.md](references/id-mappings.md) | behaviorId ↔ behaviorType 转换 |
| [system-reference.md](references/system-reference.md) | System 对象 ACE |
| [plugin-patterns.md](references/plugin-patterns.md) | Sprite/Keyboard/Audio 等插件用法 |
| [behavior-config.md](references/behavior-config.md) | Platform/Tween/Timer 等行为配置 |
| [deprecated-features.md](references/deprecated-features.md) | 废弃功能警告 |

## 代码模板

生成事件表时，直接复制并修改以下模板。将 `{占位符}` 替换为实际值。

### WASD 键盘控制
用于：8Direction 移动。替换 `{Object}` 为对象名。
```json
{"is-c3-clipboard-data":true,"type":"events","items":[
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":87}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"8Direction","parameters":{"control":"up"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":65}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"8Direction","parameters":{"control":"left"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":83}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"8Direction","parameters":{"control":"down"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":68}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"8Direction","parameters":{"control":"right"}}]}
]}
```

### 平台跳跃
用于：Platform 行为跳跃。Space=32。
```json
{"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":32}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"Platform","parameters":{"control":"jump"}}]}
```

### 碰撞检测
用于：两对象碰撞时触发。
```json
{"eventType":"block","conditions":[{"id":"on-collision-with-another-object","objectClass":"{Object1}","parameters":{"object":"{Object2}"}}],"actions":[{"id":"destroy","objectClass":"{Object2}","parameters":{}}]}
```

### 定时执行
用于：每隔 N 秒执行。
```json
{"eventType":"block","conditions":[{"id":"every-x-seconds","objectClass":"System","parameters":{"interval-seconds":"{N}"}}],"actions":[...]}
```

### 场景初始化
用于：场景开始时执行。
```json
{"eventType":"block","conditions":[{"id":"on-start-of-layout","objectClass":"System","parameters":{}}],"actions":[{"id":"set-eventvar-value","objectClass":"System","parameters":{"variable":"{VarName}","value":"0"}}]}
```

### 变量定义
用于：定义事件变量。**必须包含 comment 字段**。
```json
{"eventType":"variable","name":"{VarName}","type":"number","initialValue":"0","comment":""}
```

### 条件分支
用于：if/else 逻辑。comparison: 0=等于, 4=大于。
```json
{"eventType":"block","conditions":[{"id":"compare-eventvar","objectClass":"System","parameters":{"variable":"{VarName}","comparison":4,"value":"0"}}],"actions":[...]},
{"eventType":"block","conditions":[{"id":"else","objectClass":"System","parameters":{}}],"actions":[...]}
```

### 循环遍历
用于：遍历所有实例。
```json
{"eventType":"block","conditions":[{"id":"for-each","objectClass":"System","parameters":{"object":"{ObjectType}"}}],"actions":[...]}
```

### 函数调用
用于：调用自定义函数。
```json
{"callFunction":"{FunctionName}","parameters":["{param1}","{param2}"]}
```
有返回值时用表达式：`"Functions.{FunctionName}({params})"`

### Tween 动画
用于：属性补间动画。property: x/y/width/height/angle/opacity。
```json
{"id":"tween-one-property","objectClass":"{Object}","behaviorType":"Tween","parameters":{"tags":"\"{tag}\"","property":"{property}","end-value":"{value}","time":"{seconds}","ease":"in-out-sine","destroy-on-complete":"no","loop":"no","ping-pong":"no","repeat-count":"1"}}
```

## 最佳实践

### 避免废弃功能

详见 [deprecated-features.md](references/deprecated-features.md)

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

## 数据来源

基于 490 个官方示例项目分析。详细统计见 `data/project_analysis/sorted_indexes.json`。
