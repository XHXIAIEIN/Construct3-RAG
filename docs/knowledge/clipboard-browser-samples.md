
---

## object-types: Sprite with Platform behavior (r475.2, 2026-03-09)

来源：浏览器直接采集，Sprite 对象 + Platform 行为

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
      {"behaviorId": "Platform", "name": "Platform"}
    ],
    "effectTypes": [],
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
  "imageData": ["data:image/png;base64,...(base64)"]
}
```

### 关键字段说明
- `behaviorTypes[].behaviorId` — 行为系统 ID（如 "Platform", "EightDir", "Physics"）
- `behaviorTypes[].name` — 用户可见名称（可被重命名）
- `effectTypes` — 空数组时表示无特效
- `animations.items[].frames[].imageDataIndex` — 引用 `imageData` 数组的索引
- `imageData` — base64 编码图像数组，支持跨项目粘贴时携带图像

