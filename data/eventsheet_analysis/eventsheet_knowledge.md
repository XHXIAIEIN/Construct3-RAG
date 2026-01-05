# Construct 3 Event Sheet Knowledge Base

> 最后更新: 
> 分析文件数: 497

## 统计概览

- 事件块总数: 11,424
- 条件使用次数: 15,179 (2491 种)
- 动作使用次数: 26,208 (6199 种)

---

## 参数类型规则

| Schema 类型 | 主要格式 | 示例 | 规则说明 |
|-------------|----------|------|----------|
| `animationframe` | plain_string | `loopindex`, `ColorFrame` | 参考样例值：loopindex, ColorFrame |
| `any` | expression_dot | `"go"`, `POINTS_TO_WIN` | 任意值，通常是字符串或数字表达式 |
| `audiofile` | plain_string | `impulsewarehouse`, `impulsedensehall` | 参考样例值：impulsewarehouse, impulsedensehall |
| `boolean` | boolean | `False`, `True` | 布尔值或字符串 "true"/"false" |
| `cmp` | number_native | `0`, `1` | 比较运算符索引：0(=) 1(≠) 2(<) 3(≤) 4(>) 5(≥) |
| `combo` | plain_string | `to-destination`, `with-effects` | 使用 Schema 中定义的 items 值（kebab-case 字符串） |
| `ease` | plain_string | `easeinsine`, `easeinoutcubic` | 参考样例值：easeinsine, easeinoutcubic |
| `eventvar` | plain_string | `VectorZ`, `objCounter` | 参考样例值：VectorZ, objCounter |
| `eventvarany` | plain_string | `CaptureStatus`, `playerWon` | 参考样例值：CaptureStatus, playerWon |
| `eventvarbool` | plain_string | `DebugLines`, `areYouSureMenu` | 参考样例值：DebugLines, areYouSureMenu |
| `flowchart` | plain_string | `GameLogic` | 参考样例值：GameLogic |
| `groupname` | quoted_string | `"Host"`, `"Player"` | 带内嵌引号的字符串值 |
| `keyb` | number_native | `32`, `86` | 参考样例值：32, 86 |
| `layer` | quoted_string | `"World"`, `0` | 图层索引字符串 "0" 或带引号的名称 "\"UI\"" |
| `layereffect` | quoted_string | `"Swirl"`, `"BlurHorizontal"` | 带内嵌引号的字符串值 |
| `layout` | plain_string | `Game`, `Main` | 参考样例值：Game, Main |
| `layouteffect` | quoted_string | `"WarpRipple"`, `"Swirl"` | 带内嵌引号的字符串值 |
| `number` | number_string | `Disc.Y + random(-Dis`, `Ground.TileToPositio` | 数字字符串或表达式，如 "100" 或 "Player.X" |
| `object` | plain_string | `Enemy_Red`, `PauseUI` | 对象类型名称，如 "Sprite" 或 "Player" |
| `objectname` | expression_dot | `otherPortalType = 0 `, `Base.TemplateName = ` | 对象属性表达式，如 "Object.Property" |
| `objinstancevar` | other:dict | `{"name": "health", "`, `{"name": "colorAnim"` | 参考样例值：{"name": "health", "objectClass": "Peer"}, { |
| `projectfile` | expression_dot | `Scenery.json`, `EVARealizations.json` | 对象属性表达式，如 "Object.Property" |
| `string` | quoted_string | `"maestroZ"`, `"fruitFlash"` | 带内嵌引号的字符串，如 "\"Hello\"" 或表达式 |
| `template` | quoted_string | `int(DictComplexity.G`, `""` | 带内嵌引号的字符串值 |
| `timeline` | plain_string | `FireBall`, `Walk` | 参考样例值：FireBall, Walk |

---

## Top 30 常用条件

1. **System.else** (1260次) - 无参数
1. **System.evaluate-expression** (1195次) - `value:any`
1. **Keyboard.key-is-down** (618次) - `key:keyb`
1. **System.for-each** (496次) - `object:object`
1. **Keyboard.on-key-pressed** (488次) - `key:keyb`
1. **System.on-start-of-layout** (476次) - 无参数
1. **System.compare-eventvar** (469次) - `variable:eventvar`, `comparison:cmp`, `value:any`
1. **System.compare-two-values** (402次) - `first-value:any`, `comparison:cmp`, `second-value:any`
1. **System.every-tick** (391次) - 无参数
1. **Gamepad.is-button-down** (370次) - `gamepad:number`, `button:combo`
1. **System.compare-boolean-eventvar** (360次) - `variable:eventvarbool`
1. **Gamepad.on-button-pressed** (268次) - `gamepad:number`, `button:combo`
1. **System.for** (261次) - `name:string`, `start-index:number`, `end-index:number`
1. **System.pick-by-evaluate** (237次) - `object:object`, `expression:number`
1. **System.every-x-seconds** (216次) - `interval-seconds:number`
1. **System.repeat** (183次) - `count:number`
1. **System.pick-by-comparison** (161次) - `object:object`, `expression:any`, `comparison:cmp`, `value:any`
1. **PlayerCollision:Platform.is-on-floor** (106次) - 无参数
1. **System.trigger-once-while-true** (103次) - 无参数
1. **PlayerCollision.on-collision-with-another-object** (103次) - `object:None`
1. **PlayerCollision:Platform.is-moving** (92次) - 无参数
1. **GameManager:Timer.on-timer** (76次) - `tag:string`
1. **Touch.is-touching-object** (67次) - `object:object`
1. **Player.is-boolean-instance-variable-set** (64次) - `instance-variable:None`
1. **Player.compare-instance-variable** (59次) - `instance-variable:None`, `comparison:None`, `value:None`
1. **PlayerGraphics.on-created** (58次) - 无参数
1. **System.while** (56次) - 无参数
1. **PlayerCollision.is-overlapping-another-object** (55次) - `object:None`
1. **PlayerCollision:Platform.is-falling** (51次) - 无参数
1. **Player.is-overlapping-another-object** (49次) - `object:None`

## Top 30 常用动作

1. **Unknown.callFunction** (1948次) - 无参数
1. **System.set-eventvar-value** (1715次) - `variable:eventvar`, `value:any`
1. **System.create-object** (780次) - `object-to-create:object`, `layer:layer`, `x:number`, `y:number`, `create-hierarchy:boolean`, `template-name:template`
1. **System.wait** (411次) - `seconds:number`, `use-timescale:boolean`
1. **System.set-boolean-eventvar** (403次) - `variable:eventvarbool`, `value:combo`
1. **System.wait-for-previous-actions** (267次) - 无参数
1. **PlayerGraphics.set-animation** (243次) - `animation:None`, `from:None`
1. **Audio.play** (226次) - `audio-file:audiofile`, `loop:combo`, `volume:number`, `stereo-pan:number`, `tag-optional:string`
1. **System.restart-layout** (225次) - 无参数
1. **System.set-group-active** (212次) - `group-name:groupname`, `state:combo`
1. **System.add-to-eventvar** (199次) - `variable:eventvar`, `value:any`
1. **Fader:Tween.tween-one-property** (174次) - `tags:string`, `property:combo`, `end-value:number`, `time:number`, `ease:ease`, `destroy-on-complete:combo`, `loop:combo`, `ping-pong:combo`, `repeat-count:number`
1. **PlayerCollision:Platform.simulate-control** (157次) - `control:combo`
1. **Functions.set-function-return-value** (144次) - `value:None`
1. **System.reset-global-variables** (116次) - `reset-static:boolean`
1. **GameManager:Timer.start-timer** (103次) - `duration:number`, `type:combo`, `tag:string`
1. **PlayerGraphics.spawn-another-object** (97次) - `object:None`, `layer:None`, `image-point:None`, `create-hierarchy:None`, `template-name:None`
1. **System.go-to-layout** (87次) - `layout:layout`
1. **Text.set-text** (80次) - `text:any`
1. **Audio.fade-volume** (76次) - `tag:string`, `db:number`, `duration:number`, `ending:combo`
1. **3DCamera.look-at-position** (73次) - `cam-x:None`, `cam-y:None`, `cam-z:None`, `look-x:None`, `look-y:None`, `look-z:None`, `up-x:None`, `up-y:None`, `up-z:None`
1. **PlayerCollision.add-child** (70次) - `child:None`, `transform-x:None`, `transform-y:None`, `transform-w:None`, `transform-h:None`, `transform-a:None`, `transform-z-elevation:None`, `destroy-with-parent:None`, `transform-o:None`, `transform-visibility:None`
1. **PlayerGraphics.set-mirrored** (66次) - `state:None`
1. **PlayerCollision:Platform.set-vector-y** (63次) - `vector-y:number`
1. **PlayerCollision.spawn-another-object** (61次) - `object:None`, `layer:None`, `image-point:None`, `create-hierarchy:None`, `template-name:None`
1. **Player.set-animation** (59次) - `animation:None`, `from:None`
1. **GameManager:Tween.tween-value** (58次) - `tags:string`, `start-value:number`, `end-value:number`, `time:number`, `ease:ease`, `destroy-on-complete:combo`, `loop:combo`, `ping-pong:combo`, `repeat-count:number`
1. **AJAX.request-project-file** (58次) - `tag:string`, `file:projectfile`
1. **System.set-layer-visible** (57次) - `layer:layer`, `visibility:combo`
1. **PlayerGraphics.set-position-to-another-object** (56次) - `object:None`, `image-point-optional:None`

---

## 详细 JSON 示例

### 条件

#### `System.else`

<details>
<summary>JSON 模板</summary>

```json
{
  "id": "else",
  "objectClass": "System"
}
```
</details>

#### `System.evaluate-expression`

| 参数 | 类型 | 示例值 |
|------|------|--------|
| value | any | `lowercase(trim(currentInp`, `CurrentTile = 4`, `int(tokenat(upgradeLevels` |

<details>
<summary>JSON 模板</summary>

```json
{
  "id": "evaluate-expression",
  "objectClass": "System",
  "parameters": {
    "value": "InstructionsAreVisible = 1"
  }
}
```
</details>

#### `Keyboard.key-is-down`

| 参数 | 类型 | 示例值 |
|------|------|--------|
| key | keyb | `32`, `83`, `107` |

<details>
<summary>JSON 模板</summary>

```json
{
  "id": "key-is-down",
  "objectClass": "Keyboard",
  "parameters": {
    "key": 90
  }
}
```
</details>

#### `System.for-each`

| 参数 | 类型 | 示例值 |
|------|------|--------|
| object | object | `Enemy_Red`, `Pixel`, `TutorialText` |

<details>
<summary>JSON 模板</summary>

```json
{
  "id": "for-each",
  "objectClass": "System",
  "parameters": {
    "object": "guard"
  }
}
```
</details>

#### `Keyboard.on-key-pressed`

| 参数 | 类型 | 示例值 |
|------|------|--------|
| key | keyb | `32`, `86`, `52` |

<details>
<summary>JSON 模板</summary>

```json
{
  "id": "on-key-pressed",
  "objectClass": "Keyboard",
  "parameters": {
    "key": 37
  }
}
```
</details>

#### `System.on-start-of-layout`

<details>
<summary>JSON 模板</summary>

```json
{
  "id": "on-start-of-layout",
  "objectClass": "System"
}
```
</details>

#### `System.compare-eventvar`

| 参数 | 类型 | 示例值 |
|------|------|--------|
| variable | eventvar | `CurrentAngle`, `RemainingGroundBlocks`, `health` |
| comparison | cmp | `0`, `1`, `3` |
| value | any | `"go"`, `POINTS_TO_WIN`, `0` |

<details>
<summary>JSON 模板</summary>

```json
{
  "id": "compare-eventvar",
  "objectClass": "System",
  "parameters": {
    "variable": "EnemySpawnTime",
    "comparison": 4,
    "value": "0.5"
  }
}
```
</details>

#### `System.compare-two-values`

| 参数 | 类型 | 示例值 |
|------|------|--------|
| first-value | any | `distance(ZombieCollision.`, `MainBuilding.Count`, `Dot.Count` |
| comparison | cmp | `0`, `1`, `4` |
| second-value | any | `0`, `"3_Temple"`, `"Inspecting"` |

<details>
<summary>JSON 模板</summary>

```json
{
  "id": "compare-two-values",
  "objectClass": "System",
  "parameters": {
    "first-value": "distance(gX,gY,guard.X,guard.Y)",
    "comparison": 3,
    "second-value": "512"
  }
}
```
</details>

#### `System.every-tick`

<details>
<summary>JSON 模板</summary>

```json
{
  "id": "every-tick",
  "objectClass": "System"
}
```
</details>

#### `Gamepad.is-button-down`

| 参数 | 类型 | 示例值 |
|------|------|--------|
| gamepad | number | `0`, `Functions.FilterGamepadIn` |
| button | combo | `button-a`, `right-shoulder-trigger`, `button-x` |

<details>
<summary>JSON 模板</summary>

```json
{
  "id": "is-button-down",
  "objectClass": "Gamepad",
  "parameters": {
    "gamepad": "0",
    "button": "button-a"
  }
}
```
</details>

### 动作

#### `Unknown.callFunction`

<details>
<summary>JSON 模板</summary>

```json
{
  "callFunction": "setAggro",
  "parameters": [
    "guard.UID",
    "1"
  ]
}
```
</details>

#### `System.set-eventvar-value`

| 参数 | 类型 | 示例值 |
|------|------|--------|
| variable | eventvar | `CoordinateX`, `RoomName`, `meanX` |
| value | any | `BallVectorX + cos(AimingA`, `Bluetooth.DeviceID`, `DesiredMovementAngle` |

<details>
<summary>JSON 模板</summary>

```json
{
  "id": "set-eventvar-value",
  "objectClass": "System",
  "parameters": {
    "variable": "gX",
    "value": "guard.X"
  }
}
```
</details>

#### `System.create-object`

| 参数 | 类型 | 示例值 |
|------|------|--------|
| object-to-create | object | `DarkFog`, `Ground1`, `Flash` |
| layer | layer | `0`, `"Cups"`, `"Text"` |
| x | number | `CoordinateX`, `meanX`, `Missile.X` |
| y | number | `-WPNDIST`, `loopindex("row") * gCell.`, `Disc.Y + random(-Disc.Hei` |
| create-hierarchy | boolean | `False`, `True` |
| template-name | template | `int(DictComplexity.Get(Ar`, `"Floor0"`, `"bush" & floor(random(10)` |

<details>
<summary>JSON 模板</summary>

```json
{
  "id": "create-object",
  "objectClass": "System",
  "parameters": {
    "object-to-create": "Firework",
    "layer": "\"World\"",
    "x": "DestinationX + random(-16, 16)",
    "y": "LayoutHeight",
    "create-hierarchy": false,
    "template-name": "\"\""
  }
}
```
</details>

#### `System.wait`

| 参数 | 类型 | 示例值 |
|------|------|--------|
| seconds | number | `0`, `0.15`, `0.3` |
| use-timescale | boolean | `False`, `True` |

<details>
<summary>JSON 模板</summary>

```json
{
  "id": "wait",
  "objectClass": "System",
  "parameters": {
    "seconds": "PlayerSegment.SegmentIndex  / 10"
  }
}
```
</details>

#### `System.set-boolean-eventvar`

| 参数 | 类型 | 示例值 |
|------|------|--------|
| variable | eventvarbool | `LevelHasStarted`, `Scrolling`, `WalkDown` |
| value | combo | `true`, `false` |

<details>
<summary>JSON 模板</summary>

```json
{
  "id": "set-boolean-eventvar",
  "objectClass": "System",
  "parameters": {
    "variable": "switch",
    "value": "true"
  }
}
```
</details>

#### `System.wait-for-previous-actions`

<details>
<summary>JSON 模板</summary>

```json
{
  "id": "wait-for-previous-actions",
  "objectClass": "System"
}
```
</details>

#### `PlayerGraphics.set-animation`

| 参数 | 类型 | 示例值 |
|------|------|--------|
| animation | ? | `"TeleportOut"`, `"Fade"`, `"Climb"` |
| from | ? | `beginning` |

<details>
<summary>JSON 模板</summary>

```json
{
  "id": "set-animation",
  "objectClass": "PlayerGraphics",
  "parameters": {
    "animation": "\"Move\"&PlayerCollision.AngleOfMotion",
    "from": "beginning"
  }
}
```
</details>

#### `Audio.play`

| 参数 | 类型 | 示例值 |
|------|------|--------|
| audio-file | audiofile | `fanfare`, `RetroLaser1`, `BossLaser` |
| loop | combo | `looping`, `not-looping` |
| volume | number | `savedSound = 1 ? 0 : -Inf`, `-30`, `0` |
| stereo-pan | number | `0`, `(Player.X - Elevator.X )/` |
| tag-optional | string | `"rain"`, `"SFXGong"`, `"bass2"` |

<details>
<summary>JSON 模板</summary>

```json
{
  "id": "play",
  "objectClass": "Audio",
  "parameters": {
    "audio-file": "Boulder",
    "loop": "not-looping",
    "volume": "0",
    "stereo-pan": "0",
    "tag-optional": "\"SFX\""
  }
}
```
</details>

#### `System.restart-layout`

<details>
<summary>JSON 模板</summary>

```json
{
  "id": "restart-layout",
  "objectClass": "System"
}
```
</details>

#### `System.set-group-active`

| 参数 | 类型 | 示例值 |
|------|------|--------|
| group-name | groupname | `"Host"`, `"Requirements"`, `"Menu navigation"` |
| state | combo | `deactivated`, `activated` |

<details>
<summary>JSON 模板</summary>

```json
{
  "id": "set-group-active",
  "objectClass": "System",
  "parameters": {
    "group-name": "\"Next level\"",
    "state": "deactivated"
  }
}
```
</details>
