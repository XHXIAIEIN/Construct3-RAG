# Construct 3 Clipboard Format

> **用途**：通过 JSON 粘贴内容到 Construct 3 编辑器
> **验证状态**：2026-01-03 实测验证通过

---

## 基本结构

```json
{"is-c3-clipboard-data": true, "type": "TYPE", "items": [...]}
```

### Type 类型
| type | 用途 | 粘贴位置 |
|------|------|----------|
| `"events"` | 完整事件块 | 事件表边距 |
| `"conditions"` | 仅条件 | 选中条件后粘贴 |
| `"actions"` | 仅动作 | 选中动作后粘贴 |
| `"object-types"` | 对象类型定义 | Object types 文件夹 |
| `"world-instances"` | 场景实例 | Layout 视图 |
| `"layouts"` | 布局/场景 | Layouts 文件夹 |
| `"event-sheets"` | 事件表 | Event sheets 文件夹 |

---

## 获取正确格式的方法

### 方法1：复制现有项目（推荐）
在 C3 编辑器中复制已有的事件/对象，然后用 JS 读取剪贴板：
```javascript
// 在 C3 编辑器控制台执行
navigator.clipboard.readText().then(t => console.log(t))
```

### 方法2：查询 Schema 文件
Schema 文件是权威来源：
- 插件：`data/schemas/plugins/*.json`
- 行为：`data/schemas/behaviors/*.json`

```bash
# 查找条件/动作 ID
grep -n "every-x-seconds\|create-object" data/schemas/plugins/system.json

# 查找行为动作
grep -n "simulate-control" data/schemas/behaviors/eightdir.json
```

---

## 关键注意事项

### 1. 程序化写入剪贴板
```javascript
// ❌ 错误 - C3 无法识别
navigator.clipboard.writeText(json);

// ✅ 正确 - 必须用 ClipboardItem + Blob
const blob = new Blob([json], {type: 'text/plain'});
await navigator.clipboard.write([new ClipboardItem({'text/plain': blob})]);
```

### 2. 字符串参数需要内嵌引号
```json
"animation": "\"Walk\""           // 动画名
"layer": "\"HUD\""                // 图层名（字符串方式）
"layer": "0"                      // 图层索引（数字方式）
"text": "\"Score: \" & Score"     // 字符串拼接
```

### 3. variable 必须有 comment 字段
```json
{"eventType": "variable", "name": "Score", "comment": ""}
```

### 4. 比较运算符值
| 值 | 运算符 |
|----|--------|
| 0 | = |
| 1 | ≠ |
| 2 | < |
| 3 | ≤ |
| 4 | > |
| 5 | ≥ |

### 5. simulate-control 用字符串
```json
// ✅ 正确
{"id": "simulate-control", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {"control": "up"}}

// ❌ 错误 - 不能用数字
{"parameters": {"control": 0}}
```
值：`"up"` | `"down"` | `"left"` | `"right"` (8Direction)，`"left"` | `"right"` | `"jump"` (Platform)

### 6. 函数调用
- 无返回值函数：用 `callFunction` 动作
- 有返回值函数：用表达式 `Functions.FuncName(params)`

---

## 事件结构

### eventType 类型
```json
// 变量
{"eventType": "variable", "name": "Score", "type": "number", "initialValue": "0", "comment": "", "isStatic": false, "isConstant": false}

// 注释
{"eventType": "comment", "text": "注释内容"}

// 分组
{"eventType": "group", "disabled": false, "title": "标题", "description": "", "isActiveOnStart": true, "children": []}

// 事件块
{"eventType": "block", "conditions": [...], "actions": [...]}

// 带子事件
{"eventType": "block", "conditions": [...], "actions": [...], "children": [...]}

// OR 块
{"eventType": "block", "conditions": [...], "actions": [...], "isOrBlock": true}

// 函数
{"eventType": "function-block", "functionName": "MyFunc", "functionReturnType": "none", "functionParameters": [], "conditions": [], "actions": []}
```

### 条件/动作结构
```json
// 条件
{"id": "条件ID", "objectClass": "对象名", "parameters": {...}}

// 带行为的条件
{"id": "条件ID", "objectClass": "对象名", "behaviorType": "行为名", "parameters": {...}}

// 动作
{"id": "动作ID", "objectClass": "对象名", "parameters": {...}}

// 函数调用动作
{"callFunction": "函数名", "parameters": ["参数1", "参数2"]}
```

---

## Object Types 结构

### 单例插件（Keyboard, Mouse, Audio 等）
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[
  {"name":"Keyboard","plugin-id":"Keyboard","singleglobal-inst":{"type":"Keyboard","properties":{},"tags":""}}
],"folders":[]}
```

### 世界对象（Sprite, Text）
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[
  {"name":"Text","plugin-id":"Text","isGlobal":false,"instanceVariables":[],"behaviorTypes":[],"effectTypes":[]}
],"folders":[]}
```

### 数据对象（Array, Dictionary）
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[
  {"name":"Array","plugin-id":"Arr","isGlobal":true,"nonworld-inst":{"type":"Array","properties":{"width":10,"height":1,"depth":1},"tags":""}}
],"folders":[]}
```

---

## 常见示例

### WASD 控制（8Direction 行为）
```json
{"is-c3-clipboard-data":true,"type":"events","items":[
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":87}}],"actions":[{"id":"simulate-control","objectClass":"Player","behaviorType":"8Direction","parameters":{"control":"up"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":65}}],"actions":[{"id":"simulate-control","objectClass":"Player","behaviorType":"8Direction","parameters":{"control":"left"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":83}}],"actions":[{"id":"simulate-control","objectClass":"Player","behaviorType":"8Direction","parameters":{"control":"down"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":68}}],"actions":[{"id":"simulate-control","objectClass":"Player","behaviorType":"8Direction","parameters":{"control":"right"}}]}
]}
```

### 生成系统（视口表达式 + 字符串拼接）
```json
{"is-c3-clipboard-data":true,"type":"events","items":[
  {"eventType":"variable","name":"SpawnCount","type":"number","initialValue":"0","comment":""},
  {"eventType":"block",
   "conditions":[{"id":"every-x-seconds","objectClass":"System","parameters":{"interval-seconds":"2"}}],
   "actions":[
     {"id":"create-object","objectClass":"System","parameters":{"object-to-create":"Text","layer":"0","x":"random(viewportleft(0), viewportright(0))","y":"random(viewporttop(0), viewportbottom(0))"}},
     {"id":"set-text","objectClass":"Text","parameters":{"text":"\"Spawned #\" & SpawnCount"}},
     {"id":"add-to-eventvar","objectClass":"System","parameters":{"variable":"SpawnCount","value":"1"}}
   ]}
]}
```

---

## World Instances（场景实例）

在 Layout 视图中粘贴实例。**粘贴后需要点击场景位置来放置实例。**

### 完整格式（必须包含 object-types 和 imageData）
```json
{"is-c3-clipboard-data":true,"type":"world-instances",
  "items":[{
    "type":"Player",
    "properties":{"initially-visible":true,"initial-animation":"Animation 1","initial-frame":0,"enable-collisions":true,"live-preview":false},
    "tags":"",
    "instanceVariables":{},
    "behaviors":{"8Direction":{"properties":{"max-speed":200,"acceleration":600,"deceleration":500,"directions":"dir-8","set-angle":"smooth","allow-sliding":false,"default-controls":false,"enabled":true}}},
    "instanceFolderItem":{"sid":936354517293677,"expanded":true},
    "showing":true,
    "locked":false,
    "world":{"x":600,"y":400,"width":32,"height":32,"originX":0.5,"originY":0.5,"color":[1,1,1,1],"angle":0,"zElevation":0}
  }],
  "object-types":[{
    "name":"Player",
    "plugin-id":"Sprite",
    "isGlobal":false,
    "editorNewInstanceIsReplica":true,
    "instanceVariables":[],
    "behaviorTypes":[{"behaviorId":"EightDir","name":"8Direction"}],
    "effectTypes":[],
    "animations":{"items":[{"frames":[{"width":32,"height":32,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":0,"useCollisionPoly":true,"duration":1,"tag":""}],"name":"Animation 1","isLooping":false,"isPingPong":false,"repeatCount":1,"repeatTo":0,"speed":5}],"subfolders":[],"name":"Animations"}
  }],
  "imageData":["data:image/png;base64,iVBORw0KGgo..."]
}
```

**关键要点**：
- **必须包含 `object-types`** - 即使对象已存在，也需要完整定义
- **必须包含 `imageData`** - base64 编码的 PNG 图像数组
- `behaviors` 是对象格式：`{"行为名": {"properties": {...}}}`
- `instanceFolderItem.sid` 可以是任意数字
- 粘贴后光标变为放置模式，点击场景确认位置

---

## 调试与常见错误

### 验证剪贴板内容
```javascript
// 读取并格式化输出
navigator.clipboard.readText().then(t => console.log(JSON.stringify(JSON.parse(t), null, 2)))
```

### 常见错误及解决

| 现象 | 原因 | 解决 |
|------|------|------|
| 粘贴无反应 | 用了 `writeText()` | 改用 `ClipboardItem + Blob` |
| 粘贴无反应 | 焦点不在目标区域 | 先点击目标区域再粘贴 |
| world-instances 无预览 | 缺少 `object-types` 或 `imageData` | 必须包含完整定义和图像数据 |
| 动作/条件报错 | ID 错误 | 从 Schema 查找正确 ID |
| 字符串参数失败 | 缺少内嵌引号 | 用 `"\"value\""` 格式 |
| 行为动作失败 | 缺少 `behaviorType` | 添加行为名称字段 |

### 粘贴位置要求

| type | 必须在此位置粘贴 |
|------|-----------------|
| `events` | 事件表空白边距区域 |
| `conditions` | 选中已有条件后 |
| `actions` | 选中已有动作后 |
| `object-types` | Project Bar → Object types |
| `world-instances` | Layout 视图（粘贴后点击放置） |

---

## 不支持剪贴板的元素

- **Layers** - 图层（无 Copy 选项）
