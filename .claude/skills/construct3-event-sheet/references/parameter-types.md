# Parameter Types Reference

参数类型详解，用于正确构造 ACE 参数。

---

## 基本类型

### number - 数字
```json
"x": "400"
"speed": "200"
"interval-seconds": "2.5"
```
- 直接写数字字符串
- 支持表达式：`"Player.X + 100"`
- 支持系统表达式：`"random(0, 100)"`

### string - 字符串
```json
"text": "\"Hello World\""
"animation": "\"Walk\""
"tag": "\"player\""
```
- **必须有内嵌引号**
- 支持拼接：`"\"Score: \" & Score"`
- 支持表达式：`"\"HP: \" & Player.Health`

### any - 任意类型
```json
"value": "100"              // 数字
"value": "\"text\""         // 字符串
"value": "Player.X"         // 表达式
```

---

## 对象类型

### object - 对象选择器
```json
"object": "Player"
"object-to-create": "Bullet"
```
- 使用对象名（objectClass）

### layer - 图层
```json
"layer": "0"                // 按索引
"layer": "\"Background\""   // 按名称（需要引号）
```

### layout - 布局
```json
"layout": "\"Game\""        // 布局名称
```

---

## 比较与选择

### comparison (cmp) - 比较运算符
```json
"comparison": 0   // =  等于
"comparison": 1   // ≠  不等于
"comparison": 2   // <  小于
"comparison": 3   // ≤  小于等于
"comparison": 4   // >  大于
"comparison": 5   // ≥  大于等于
```

### combo - 下拉选择
```json
// 布尔类型
"state": "yes"
"state": "no"

// 方向类型
"control": "up"
"control": "down"
"control": "left"
"control": "right"
"control": "jump"

// 循环类型
"loop": "no"
"loop": "loop"

// 排序
"order": "ascending"
"order": "descending"
```

---

## 键盘按键

### key - 键码
常用键码：
| 键 | 码 |
|----|-----|
| W | 87 |
| A | 65 |
| S | 83 |
| D | 68 |
| Space | 32 |
| Enter | 13 |
| Shift | 16 |
| Ctrl | 17 |
| Alt | 18 |
| Esc | 27 |
| ↑ | 38 |
| ↓ | 40 |
| ← | 37 |
| → | 39 |
| 0-9 | 48-57 |
| A-Z | 65-90 |
| F1-F12 | 112-123 |

```json
{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 87}}
```

---

## 变量类型

### eventvar - 事件变量
```json
"variable": "Score"
"variable": "PlayerHealth"
```
- 使用变量名，不需要引号

### instancevar - 实例变量
```json
"instance-variable": "Health"
"instance-variable": "Speed"
```

---

## 行为特定参数

### simulate-control 控制值

**8Direction 行为**:
```json
"control": "up"
"control": "down"
"control": "left"
"control": "right"
```

**Platform 行为**:
```json
"control": "left"
"control": "right"
"control": "jump"
```

### Tween 参数

```json
{
  "tags": "\"mytween\"",
  "property": "x",           // x, y, width, height, angle, opacity, etc.
  "end-value": "500",
  "time": "1",
  "ease": "in-out-sine",     // linear, in-sine, out-sine, in-out-sine, etc.
  "destroy-on-complete": "no",
  "loop": "no",
  "ping-pong": "no",
  "repeat-count": "1"
}
```

### Timer 参数

```json
{
  "duration": "2",
  "type": "once",            // once, regular
  "tag": "\"mytimer\""
}
```

---

## 特殊格式

### 视口表达式
```json
"x": "viewportleft(0)"
"x": "viewportright(0)"
"y": "viewporttop(0)"
"y": "viewportbottom(0)"
"x": "random(viewportleft(0), viewportright(0))"
```

### 对象表达式
```json
"x": "Player.X"
"y": "Player.Y + 50"
"angle": "angle(Self.X, Self.Y, Player.X, Player.Y)"
"distance": "distance(Self.X, Self.Y, Player.X, Player.Y)"
```

### 系统表达式
```json
"value": "random(1, 100)"
"value": "choose(1, 2, 3)"
"value": "floor(Player.X / 32)"
"value": "clamp(value, 0, 100)"
"value": "lerp(a, b, 0.5)"
"value": "dt"                  // delta time
"value": "time"                // 运行时间
"value": "loopindex"           // 循环索引
```

---

## 常见错误

### 字符串缺少引号
```json
// ❌ 错误
"animation": "Walk"

// ✅ 正确
"animation": "\"Walk\""
```

### 数字用了引号
```json
// ❌ 错误（除非是表达式）
"key": "\"87\""

// ✅ 正确
"key": 87
// 或
"key": "87"
```

### 比较符用字符串
```json
// ❌ 错误
"comparison": "="

// ✅ 正确
"comparison": 0
```
