# Object Type Templates

## Generate Custom imageData

Use the script to generate any color/size/shape:

```bash
# Rectangle
python3 scripts/generate_imagedata.py --color red --width 32 --height 32

# Circle
python3 scripts/generate_imagedata.py --color blue --width 16 --height 16 --shape circle

# Rounded rectangle
python3 scripts/generate_imagedata.py --color green --width 64 --height 16 --shape rounded

# From existing image
python3 scripts/generate_imagedata.py --file sprite.png
```

**Available colors**: red, green, blue, yellow, cyan, magenta, white, black, gray, orange, purple, brown, pink, or `#RRGGBB`

## Quick Reference

| Need | Color | Size | Shape |
|------|-------|------|-------|
| Player | blue | 32x32 | rect |
| Enemy | red | 32x32 | rect |
| Ball | yellow | 16x16 | circle |
| Paddle | green | 64x16 | rounded |
| Wall/Ground | gray | 32x32 | rect |
| Bullet | orange | 8x8 | circle |
| Coin | yellow | 24x24 | circle |

## Sprite Template

Generate imageData first, then use this structure:

```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"{NAME}","plugin-id":"Sprite","isGlobal":false,"editorNewInstanceIsReplica":true,"instanceVariables":[],"behaviorTypes":[],"effectTypes":[],"animations":{"items":[{"frames":[{"width":{WIDTH},"height":{HEIGHT},"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":0,"useCollisionPoly":true,"duration":1,"tag":""}],"name":"Animation 1","isLooping":false,"isPingPong":false,"repeatCount":1,"repeatTo":0,"speed":5}],"subfolders":[],"name":"Animations"}}],"folders":[],"imageData":["{IMAGEDATA}"]}
```

**With Behavior** (add to behaviorTypes array):
```json
"behaviorTypes":[{"behaviorId":"Platform","name":"Platform"}]
"behaviorTypes":[{"behaviorId":"EightDir","name":"8Direction"}]
"behaviorTypes":[{"behaviorId":"Bullet","name":"Bullet"}]
"behaviorTypes":[{"behaviorId":"solid","name":"Solid"}]
```

---

## Single-Global Plugins (no imageData)

**Keyboard**
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Keyboard","plugin-id":"Keyboard","singleglobal-inst":{"type":"Keyboard","properties":{},"tags":""}}],"folders":[]}
```

**Mouse**
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Mouse","plugin-id":"Mouse","singleglobal-inst":{"type":"Mouse","properties":{},"tags":""}}],"folders":[]}
```

**Touch**
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Touch","plugin-id":"Touch","singleglobal-inst":{"type":"Touch","properties":{},"tags":""}}],"folders":[]}
```

**Audio**
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Audio","plugin-id":"Audio","singleglobal-inst":{"type":"Audio","properties":{"timescale-audio":false,"playback-rate-clamp-lo":0.5,"playback-rate-clamp-hi":4,"panning-model":"HRTF","distance-model":"inverse","ref-distance":600,"max-distance":10000,"rolloff-factor":1,"speed-of-sound":5000},"tags":""}}],"folders":[]}
```

---

## Non-World Objects (no imageData)

**Text**
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Text","plugin-id":"Text","isGlobal":false,"instanceVariables":[],"behaviorTypes":[],"effectTypes":[]}],"folders":[]}
```

**Array**
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Array","plugin-id":"Arr","isGlobal":true,"nonworld-inst":{"type":"Array","properties":{"width":10,"height":1,"depth":1},"tags":""}}],"folders":[]}
```

**Dictionary**
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Dictionary","plugin-id":"Dictionary","isGlobal":true,"nonworld-inst":{"type":"Dictionary","properties":{},"tags":""}}],"folders":[]}
```
