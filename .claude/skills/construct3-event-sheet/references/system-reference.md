# System Object Reference

System 对象是 Construct 3 引擎核心，无需添加到项目即可使用。

## 数据源

完整 ACE 定义：`data/project_analysis/system_reference.json`

包含：
- 56 个条件 (Conditions)
- 81 个动作 (Actions)
- 135 个表达式 (Expressions)
- 每个 ACE 的使用频率统计

## 分类

| 分类 | 说明 |
|------|------|
| `general` | 通用功能 |
| `global-local-variables` | 变量操作 |
| `loops` | 循环控制 |
| `pick-instances` | 实例选择 |
| `time` | 时间相关 |
| `start-end` | 场景生命周期 |
| `layout` | 布局控制 |
| `layers` | 图层操作 |
| `special-conditions` | 特殊条件 |
| `angles` | 角度计算 |
| `save-load` | 存档读档 |

## 高频条件 (Top 10)

| ID | 用途 | 参数 |
|----|------|------|
| `else` | 否则分支 | 无 |
| `evaluate-expression` | 表达式为真 | `value` |
| `for-each` | 遍历对象 | `object` |
| `on-start-of-layout` | 场景开始 | 无 |
| `compare-eventvar` | 比较变量 | `variable`, `comparison`, `value` |
| `compare-two-values` | 比较两值 | `first-value`, `comparison`, `second-value` |
| `every-tick` | 每帧执行 | 无 |
| `compare-boolean-eventvar` | 布尔判断 | `variable` |
| `for` | 循环 | `name`, `start-index`, `end-index` |
| `every-x-seconds` | 定时执行 | `interval-seconds` |

## 高频动作 (Top 10)

| ID | 用途 | 参数 |
|----|------|------|
| `set-eventvar-value` | 设置变量 | `variable`, `value` |
| `create-object` | 创建对象 | `object-to-create`, `layer`, `x`, `y` |
| `wait` | 等待 | `seconds` |
| `set-boolean-eventvar` | 设置布尔 | `variable`, `value` |
| `wait-for-previous-actions` | 等待异步 | 无 |
| `restart-layout` | 重载场景 | 无 |
| `set-group-active` | 启用事件组 | `group-name`, `state` |
| `add-to-eventvar` | 变量加值 | `variable`, `value` |
| `go-to-layout` | 切换场景 | `layout` |
| `set-layer-visible` | 图层可见 | `layer`, `visibility` |

## 使用示例

```json
// 场景开始
{"id": "on-start-of-layout", "objectClass": "System", "parameters": {}}

// 比较变量
{"id": "compare-eventvar", "objectClass": "System", "parameters": {"variable": "Score", "comparison": 4, "value": "100"}}

// 创建对象
{"id": "create-object", "objectClass": "System", "parameters": {"object-to-create": "Bullet", "layer": "0", "x": "Player.X", "y": "Player.Y"}}

// 等待
{"id": "wait", "objectClass": "System", "parameters": {"seconds": "1"}}
```

## 常用表达式

详见 [parameter-types.md](parameter-types.md#系统表达式) 获取完整列表。

快速参考：
- `dt` - 帧间隔时间
- `time` - 运行时间
- `loopindex` / `loopindex("name")` - 循环索引
- `random(a, b)` / `choose(a, b, c)` - 随机
- `floor/ceil/round/abs/clamp/lerp` - 数学
- `angle/distance` - 几何
- `viewportleft/right/top/bottom(layer)` - 视口
