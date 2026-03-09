# Construct 3 Clipboard Schemas — Browser Exploration Log

> **探索版本**: r475.2
> **探索日期**: 2026-03-09
> **方法**: 用 Playwright 自动化在编辑器中逐一操作 + `navigator.clipboard.readText()` 读取

---

## 已验证的 type 列表（完整）

| type | 来源操作 | 状态 |
|------|----------|------|
| `events` | 事件表中复制事件行 | ✅ 已知（见 clipboard-format.md）|
| `conditions` | 复制条件 | ✅ 已知 |
| `actions` | 复制动作 | ✅ 已知 |
| `object-types` | Project bar → 右键对象 → Copy | ✅ 本次验证 |
| `world-instances` | 布局中选中实例 → 右键 → Copy | ✅ 本次验证 |
| `layouts` | Project bar → Layout 1 → Copy | ✅ 本次探索 |
| `event-sheets` | Project bar → Event sheet 1 → Copy | ✅ 本次探索 |
| `timelines` | Project bar → Timeline 1 → Copy | ✅ 本次探索 |
| `flowcharts` | Project bar → Flowchart 1 → Copy | ✅ 本次探索 |

---

## layouts（布局）

```json
{
  "is-c3-clipboard-data": true,
  "type": "layouts",
  "families": [],
  "object-types": [],
  "items": [{
    "name": "Layout 1",
    "layers": [{
      "name": "Layer 0",
      "overriden": 0,
      "subLayers": [],
      "instances": [],
      "effectTypes": [],
      "isInitiallyVisible": true,
      "isInitiallyInteractive": true,
      "isHTMLElementsLayer": false,
      "color": [1, 1, 1, 1],
      "backgroundColor": [1, 1, 1, 1],
      "isTransparent": false,
      "sampling": "auto",
      "parallaxX": 1,
      "parallaxY": 1,
      "scaleRate": 1,
      "forceOwnTexture": false,
      "renderingMode": "3d",
      "drawOrder": "z-order",
      "useRenderCells": false,
      "blendMode": "normal",
      "zElevation": 0,
      "global": false
    }],
    "scene-graphs-folder-root": {
      "items": [],
      "subfolders": [],
      "name": "INSTANCES"
    },
    "effectTypes": [],
    "width": 1708,
    "height": 960,
    "unboundedScrolling": false,
    "sampling": "auto",
    "vpX": 0.5,
    "vpY": 0.5,
    "projection": "perspective",
    "eventSheet": "Event sheet 1",
    "ui-state": {
      "propertiesBar": {},
      "layersBar": {
        "name": "<root>",
        "children": [{"name": "Layer 0", "expanded": true, "children": []}]
      },
      "grid": {"show": false, "snap": false, "width": 32, "height": 32, "offsetX": 0, "offsetY": 0},
      "marginWidth": 1000,
      "marginHeight": 1000,
      "showCollisionPolygons": false,
      "showMeshes": false,
      "showTranslucentInactiveLayers": false,
      "showSceneGraphConnections": true,
      "tabColor": [1.0, 0.95, 0.8, 1],
      "tabTextColor": null,
      "layers": [{
        "name": "Layer 0",
        "propertiesBar": {},
        "visibleInEditor": true,
        "locked": false,
        "parallaxInEditor": false,
        "opacity": 1,
        "translucent": false
      }],
      "instancesRoot": {"expanded": true, "subfolders": [], "misc": {"global": true, "layout": []}},
      "view": {"x": 150, "y": 215, "z": 760.47, "activeLayer": "Layer 0"},
      "selectedInstances": [],
      "lockedInstances": [],
      "instanceCollections": []
    }
  }],
  "folders": []
}
```

### layouts 关键字段说明

| 字段 | 说明 |
|------|------|
| `layers[].renderingMode` | `"3d"` 或 `"2d"` |
| `layers[].drawOrder` | `"z-order"` 或 `"y-order"` |
| `layers[].blendMode` | `"normal"`, `"additive"`, `"multiply"` 等 |
| `layers[].parallaxX/Y` | 视差系数（1=跟随镜头） |
| `projection` | `"perspective"` 或 `"orthographic"` |
| `sampling` | `"auto"`, `"nearest"`, `"bilinear"`, `"trilinear"` |
| `ui-state` | 编辑器 UI 状态，可省略（不影响粘贴） |
| `scene-graphs-folder-root` | 场景层级根节点 |

---

## event-sheets（事件表）

```json
{
  "is-c3-clipboard-data": true,
  "type": "event-sheets",
  "items": [{
    "name": "Event sheet 1",
    "events": [],
    "ui-state": {
      "name": "Event sheet 1",
      "tabColor": [1.0, 0.8, 0.8, 1],
      "tabTextColor": null,
      "uiState": {
        "viewsUIState": [{
          "scroll": 0,
          "eventSheetView": {
            "conditionsColumnWidth": 300,
            "conditionNameCellWidth": 90,
            "actionNameCellWidth": 90,
            "fontSizeEm": 1
          }
        }],
        "bookmark": false,
        "eventsUIState": []
      }
    }
  }],
  "folders": []
}
```

### event-sheets 关键字段说明

| 字段 | 说明 |
|------|------|
| `events` | 事件列表，格式与 `type:"events"` 的 `items` 相同 |
| `ui-state` | 编辑器 UI 状态（可省略） |
| `tabColor` | [r,g,b,a] 归一化颜色，标签颜色 |

---

## object-types（对象类型）— 三种变体

### 1. 世界对象（Sprite，含动画）

【来源: r475.2 源码分析】带行为和效果的完整格式：

```json
{
  "is-c3-clipboard-data": true,
  "type": "object-types",
  "families": [],
  "items": [{
    "name": "Sprite",
    "plugin-id": "Sprite",
    "isGlobal": false,
    "editorNewInstanceIsReplica": true,
    "instanceVariables": [],
    "behaviorTypes": [
      {"behaviorId": "EightDir", "name": "8Direction"}
    ],
    "effectTypes": [
      {"id": "blur", "name": "Blur"}
    ],
    "animations": {
      "items": [{
        "frames": [{
          "width": 250,
          "height": 250,
          "originX": 0.5,
          "originY": 0.5,
          "originalSource": "",
          "exportFormat": "lossless",
          "exportQuality": 0.8,
          "fileType": "image/png",
          "imageDataIndex": 0,
          "useCollisionPoly": true,
          "duration": 1,
          "tag": ""
        }],
        "name": "Animation 1",
        "isLooping": false,
        "isPingPong": false,
        "repeatCount": 1,
        "repeatTo": 0,
        "speed": 5
      }],
      "subfolders": [],
      "name": "Animations"
    }
  }],
  "folders": [],
  "imageData": ["data:image/png;base64,..."]
}
```

### 2. 单例全局对象（Keyboard, Mouse, Audio 等）

```json
{
  "is-c3-clipboard-data": true,
  "type": "object-types",
  "families": [],
  "items": [{
    "name": "Keyboard",
    "plugin-id": "Keyboard",
    "singleglobal-inst": {
      "type": "Keyboard",
      "properties": {},
      "tags": ""
    }
  }],
  "folders": []
}
```

> **注意**: 单例对象没有 `isGlobal`、`instanceVariables`、`behaviorTypes`、`effectTypes` 字段
> plugin-id 用插件的内部 ID（Keyboard 的 ID 就是 "Keyboard"）

### 3. 非世界数据对象（Array, Dictionary 等）

```json
{
  "is-c3-clipboard-data": true,
  "type": "object-types",
  "families": [],
  "items": [{
    "name": "Array",
    "plugin-id": "Arr",
    "isGlobal": true,
    "editorNewInstanceIsReplica": true,
    "instanceVariables": [],
    "nonworld-inst": {
      "type": "Array",
      "properties": {"width": 10, "height": 1, "depth": 1},
      "tags": "",
      "instanceVariables": {}
    }
  }],
  "folders": []
}
```

> **注意**: `nonworld-inst` 替代了 `animations` 字段；`isGlobal: true` 是数据对象的默认值

### behaviorTypes 与 effectTypes 字段说明【来源: r475.2 源码分析】

| 字段 | 结构 | 说明 |
|------|------|------|
| `behaviorTypes` | `[{"behaviorId": "EightDir", "name": "8Direction"}]` | 对象类型上附加的行为列表；`behaviorId` 是内部 ID，`name` 是显示名 |
| `effectTypes` | `[{"id": "blur", "name": "Blur"}]` | 对象类型上附加的效果列表 |
| `instanceVariables` | `[{"name": "...", "type": "number/string/boolean", "value": ...}]` | 实例变量定义列表（空数组=无实例变量） |

> 无行为/效果/实例变量时，这三个字段均为空数组 `[]`，不省略。

### object-types 三种格式判断逻辑

| 判断字段 | 对象类型 |
|----------|----------|
| 有 `singleglobal-inst` | 单例插件（Keyboard, Mouse, Audio, AJAX 等） |
| 有 `nonworld-inst` | 非世界数据对象（Array, Dictionary, LocalStorage 等） |
| 有 `animations` | 世界可视对象（Sprite, Text, TiledBackground 等） |

### 已知 plugin-id 对照

| 显示名称 | plugin-id |
|----------|-----------|
| Sprite | Sprite |
| Text | Text |
| Tiled Background | TiledBg |
| Tilemap | Tilemap |
| Array | Arr |
| Dictionary | Dictionary |
| Keyboard | Keyboard |
| Mouse | Mouse |
| Audio | Audio |
| AJAX | AJAX |
| Browser | Browser |
| System | System（内置，不出现在 object-types 中） |

---

## world-instances（场景实例，r475 格式）

```json
{
  "is-c3-clipboard-data": true,
  "type": "world-instances",
  "items": [{
    "type": "Sprite",
    "properties": {
      "initially-visible": true,
      "initial-animation": "Animation 1",
      "initial-frame": 0,
      "enable-collisions": true,
      "live-preview": false
    },
    "tags": "",
    "instanceVariables": {},
    "behaviors": {
      "8Direction": {
        "properties": {
          "max-speed": 200,
          "acceleration": 600,
          "deceleration": 500,
          "directions": "dir-8",
          "set-angle": "smooth",
          "allow-sliding": false,
          "default-controls": false,
          "enabled": true
        }
      }
    },
    "instanceFolderItem": {
      "sid": 477832834406046,
      "expanded": true
    },
    "showing": true,
    "locked": false,
    "world": {
      "x": 400,
      "y": 300,
      "width": 100,
      "height": 100,
      "originX": 0.5,
      "originY": 0.5,
      "color": [1, 1, 1, 1],
      "z": 0,
      "angle": 0
    }
  }],
  "object-types": [...],
  "imageData": ["data:image/png;base64,..."]
}
```

> **⚠️ r475 vs r446 差异**: `world.z` 替代了 `world.zElevation`（字段名变更）

### world-instances behaviors 字段结构【来源: r475.2 源码分析】

`behaviors` 是一个对象（key = 行为显示名称，value = 行为配置）：

```json
"behaviors": {
  "8Direction": {
    "properties": {
      "max-speed": 200,
      "acceleration": 600,
      "deceleration": 500,
      "directions": "dir-8",
      "set-angle": "smooth",
      "allow-sliding": false,
      "default-controls": false,
      "enabled": true
    }
  }
}
```

> **注意**: key 是行为的显示名（与 `object-types.behaviorTypes[].name` 一致），不是 `behaviorId`。无行为时为空对象 `{}`。

### world 字段完整结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `x`, `y` | number | 位置（布局坐标系） |
| `z` | number | Z 高度（r475+，原为 zElevation） |
| `width`, `height` | number | 尺寸 |
| `originX`, `originY` | number | 原点（0-1，0.5=中心） |
| `color` | [r,g,b,a] | 颜色（归一化） |
| `angle` | number | 旋转角度（度） |

---

## timelines（时间线）

```json
{
  "is-c3-clipboard-data": true,
  "type": "timelines",
  "project": "36hn3lmh4kt",
  "items": [{
    "name": "Timeline 1",
    "enabled": true,
    "interpolationMode": "default",
    "resultMode": "default",
    "ease": "noease",
    "pathMode": "line",
    "resizeMode": "size",
    "playheadTime": 1,
    "totalTime": 5,
    "stepTime": 0.1,
    "useStepTime": true,
    "showingInterpolationModes": false,
    "showingResultModes": false,
    "showingEases": false,
    "showingPathModes": false,
    "scale": 1,
    "loop": false,
    "pingPong": false,
    "repeatCount": 1,
    "startOnLayout": "",
    "transformWithSceneGraph": true,
    "ignoreSystemTimescale": true,
    "nestedData": {},
    "childrenNestedData": {},
    "transitionsData": [],
    "tracks": [],
    "tracksRoot": {
      "enabled": true,
      "interpolationMode": "default",
      "resultMode": "default",
      "ease": "default",
      "pathMode": "default",
      "resizeMode": "default",
      "expanded": true,
      "name": "Track Folder",
      "items": [],
      "subfolders": []
    },
    "nestedTimelinesRoot": {
      "enabled": true,
      "interpolationMode": "default",
      "resultMode": "default",
      "ease": "default",
      "pathMode": "default",
      "resizeMode": "default",
      "expanded": true,
      "name": "Timelines",
      "items": [],
      "subfolders": []
    }
  }],
  "folders": []
}
```

### timelines 关键字段说明

| 字段 | 说明 |
|------|------|
| `project` | 项目唯一 ID（仅出现在编辑器实时复制版本，源码分析版本无此字段） |
| `ease` | 缓动名（`"noease"`, `"linear"`, `"inSinusoidal"` 等） |
| `pathMode` | `"line"` 或 `"cubicBezier"` |
| `resizeMode` | `"size"` 或 `"scale"` |
| `tracks` | 轨道列表（空=无轨道）；❓ 含 keyframe 的完整轨道结构 待采集 |
| `tracksRoot` | 轨道文件夹根节点 |
| `nestedTimelinesRoot` | 嵌套时间线根节点 |
| `showingInterpolationModes` 等 | 编辑器 UI 展开状态，仅出现在实时复制版本，粘贴时可省略 |

> 【来源: r475.2 源码分析】最小可用结构不需要 `project`、`showingInterpolationModes` 等 UI 字段。

---

## flowcharts（流程图）

```json
{
  "is-c3-clipboard-data": true,
  "type": "flowcharts",
  "items": [{
    "sid": 589804076052508,
    "nodes": [],
    "preset-nodes": {
      "items": [],
      "subfolders": [],
      "name": "FLOWCHART_NODE_PRESETS"
    },
    "name": "Flowchart 1",
    "w": 20000,
    "h": 20000
  }],
  "folders": []
}
```

### flowcharts 关键字段说明

【来源: r475.2 源码分析】确认完整空流程图结构。

| 字段 | 说明 |
|------|------|
| `sid` | 流程图唯一 ID（粘贴时会被重新分配） |
| `nodes` | 节点列表（空=空流程图）；❓ 含节点的完整 node 结构 待采集 |
| `preset-nodes` | 预设节点文件夹（`items`/`subfolders`/`name` 三字段） |
| `w`, `h` | 画布尺寸（默认 20000x20000） |

---

## families（族）的使用说明【来源: r475.2 源码分析】

- Family **不能**通过剪贴板 JSON 直接创建（没有独立的 `type:"families"` 剪贴板格式）
- 在事件表中引用 Family 时，`objectClass` 字段直接填 family 名称（与引用普通对象类型相同）
- `layouts` 类型的剪贴板 JSON 中有 `"families": []` 字段，但仅作为引用信息出现

---

## 尚未探索的格式

| type | 状态 | 备注 |
|------|------|------|
| `families` | ✅ 已知限制 | 不能通过剪贴板 JSON 直接创建；事件表中通过 `objectClass` 字段名引用 |
| `object-types` with behaviors | ✅ 已知【r475.2 源码分析】 | `behaviorTypes: [{"behaviorId": "EightDir", "name": "8Direction"}]` |
| `object-types` with effects | ✅ 已知【r475.2 源码分析】 | `effectTypes: [{"id": "blur", "name": "Blur"}]` |
| `object-types` with instance vars | ❓ 待采集 | `instanceVariables` 数组元素完整结构（name/type/value） |
| `world-instances` with behaviors | ✅ 已知【r475.2 源码分析】 | `behaviors` 对象 key=行为名，见上方 world-instances 章节 |
| `timelines` with tracks | ❓ 待采集 | track keyframe 完整结构未知 |
| `flowcharts` with nodes | ❓ 待采集 | flowchart node 完整结构未知 |
| Text object | ❓ 待采集 | 无动画的世界对象格式（预测：无 `animations` 字段） |
| Dictionary object | ❓ 待采集 | 类似 Array 的非世界数据对象 |

---

## 操作技巧（自动化经验）

### Playwright 操作 C3 编辑器的技巧

1. **添加对象后进入放置模式**: 添加 Sprite 等世界对象后，编辑器进入十字光标放置模式，`docCursorOverlayElem cursorCrosshair` 覆盖层阻止所有点击
   - **解法**: 用 JS 在覆盖层上分发 mousedown/mouseup/click 事件（需提供绝对坐标）
   - 鼠标位置超出布局边界也可接受，会在布局外放置实例

2. **canvas 交互需要 `browser_run_code`**: C3 使用 WebGL canvas 渲染，JS dispatch 事件对 C3 的 canvas 通常无效，需要 `page.mouse.click()` 真实鼠标事件

3. **右键菜单**: 在 canvas 上右键会出现布局上下文菜单（Insert/Copy/View/Align 等）

4. **"Select all in project"**: Sprite 右键菜单有此选项，可选中当前布局中所有该类型实例

5. **单例对象无需放置**: Keyboard/Mouse/Audio 双击添加后直接添加成功，不进入放置模式

6. **读取剪贴板**: `navigator.clipboard.readText()` 在编辑器内可正常工作（编辑器有 clipboard 权限）

7. **world.z vs world.zElevation**: r475 版本改为 `z` 字段，r446 文档中是 `zElevation`
