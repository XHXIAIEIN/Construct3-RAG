# Deprecated and Superseded Features

废弃和被取代的功能警告。新项目应避免使用这些功能。

---

## 已弃用 (Deprecated)

以下功能已被弃用，应避免在新项目中使用：

### Function 插件

| 状态 | 已弃用 |
|------|--------|
| 替代方案 | 内置 `Functions` 系统 |
| 说明 | 旧的 Function 插件使用 `callFunction` 动作，新的内置 Functions 系统更强大 |

**旧方式（避免）**:
```json
{"callFunction": "MyFunction", "parameters": ["param1"]}
```

**新方式（推荐）**:
```json
// 在事件表中定义函数
{"eventType": "function-block", "functionName": "MyFunction", "functionReturnType": "number",
 "functionParameters": [{"name": "param1", "type": "number"}],
 "conditions": [], "actions": [...]}

// 调用函数（动作）
{"callFunction": "MyFunction", "parameters": ["100"]}

// 调用函数（表达式中）
"value": "Functions.MyFunction(100)"
```

---

## 被取代 (Superseded)

以下功能已被更好的替代方案取代，建议新项目使用替代方案：

### Pin 行为 → Hierarchies

| 旧功能 | Pin 行为 |
|--------|----------|
| 替代方案 | Hierarchies (Add child) |
| 说明 | 层级系统更可靠，支持对象链，可通过 `add-child` 动作实现 |

**旧方式（Pin）**:
```json
{"id": "pin-to-object", "objectClass": "Weapon", "behaviorType": "Pin",
 "parameters": {"pin-to": "Player", "mode": "position-angle"}}
```

**新方式（Hierarchies）**:
```json
{"id": "add-child", "objectClass": "Player",
 "parameters": {
   "child": "Weapon",
   "transform-x": "yes",
   "transform-y": "yes",
   "transform-a": "yes",
   "destroy-with-parent": "yes"
 }}
```

### Fade 行为 → Tween 行为

| 旧功能 | Fade 行为 |
|--------|----------|
| 替代方案 | Tween 行为 |
| 说明 | Tween 更通用，可控制任意属性，不仅限于透明度 |

**旧方式（Fade）**:
```json
// 需要在对象上添加 Fade 行为，通过属性配置
"behaviors": {
  "Fade": {
    "properties": {
      "fade-in-time": 0.5,
      "wait-time": 1,
      "fade-out-time": 0.5,
      "destroy": true
    }
  }
}
```

**新方式（Tween）**:
```json
{"id": "tween-one-property", "objectClass": "Sprite", "behaviorType": "Tween",
 "parameters": {
   "tags": "\"fade\"",
   "property": "opacity",
   "end-value": "0",
   "time": "0.5",
   "ease": "in-out-sine",
   "destroy-on-complete": "yes"
 }}
```

### solid 行为的 tags 属性 → Instance tags

| 旧功能 | solid 行为的 `tags` 属性 |
|--------|--------------------------|
| 替代方案 | Instance tags (实例标签系统) |
| 说明 | 使用实例标签系统更灵活 |

---

## 使用检测

如果在生成的代码中检测到以下模式，应发出警告：

```json
// 检测 Function 插件（已弃用）
"objectClass": "Function"

// 检测 Pin 行为（被取代）
"behaviorType": "Pin"
"id": "pin-to-object"

// 检测 Fade 行为（被取代）
"behaviorType": "Fade"
```

---

## 迁移建议

### Function → Functions

1. 创建新的函数定义块
2. 迁移函数逻辑
3. 更新所有调用点

### Pin → Hierarchies

1. 移除 Pin 行为
2. 使用 `add-child` 动作建立父子关系
3. 配置适当的变换选项

### Fade → Tween

1. 添加 Tween 行为
2. 使用 `tween-one-property` 动作控制 `opacity`
3. 配置 `destroy-on-complete` 如需销毁
