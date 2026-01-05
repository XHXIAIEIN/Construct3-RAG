# Construct 3 Complete Knowledge Base

> 最后更新: 2026-01-05T11:23:44.404225
> 分析文件数: 9491

## 统计概览

| 类别 | 数量 |
|------|------|
| 项目 | 490 |
| 对象类型 | 7656 |
| 布局 | 841 |
| 事件表 | 504 |
| 事件块 | 14003 |
| 实例 | 26777 |

| 知识类型 | 数量 |
|----------|------|
| 插件 | 56 |
| 行为 | 30 |
| 条件 | 2493 |
| 动作 | 6204 |

---

## Top 20 常用插件

1. **Sprite** (3404次) - 常用行为: Anchor, Bullet, Car, DragnDrop, EightDir
1. **Shape3D** (831次) - 常用行为: Bullet, Car, EightDir, Fade, Flash
1. **TiledBg** (704次) - 常用行为: Anchor, Bullet, DragnDrop, Fade, Flash
1. **Text** (573次) - 常用行为: Anchor, Bullet, Fade, Flash, Sin
1. **Spritefont2** (339次) - 常用行为: Bullet, Fade, Flash, Timer, Tween
1. **Keyboard** (252次) - 常用行为: 无
1. **Particles** (207次) - 常用行为: Bullet, DragnDrop, Pin, Timer, Tween
1. **Button** (164次) - 常用行为: 无
1. **Tilemap** (142次) - 常用行为: Physics, Tween, solid
1. **Mouse** (111次) - 常用行为: 无
1. **gamepad** (107次) - 常用行为: 无
1. **Touch** (99次) - 常用行为: 无
1. **NinePatch** (92次) - 常用行为: Rotate, Sin, Timer, Tween, solid
1. **Arr** (85次) - 常用行为: 无
1. **Camera3D** (72次) - 常用行为: 无
1. **Browser** (52次) - 常用行为: 无
1. **TextBox** (49次) - 常用行为: 无
1. **List** (42次) - 常用行为: 无
1. **AJAX** (35次) - 常用行为: 无
1. **DrawingCanvas** (34次) - 常用行为: DragnDrop, Fade, MoveTo, Timer, Tween

## Top 20 常用行为

1. **Tween** (1018次) - 属性: enabled
1. **solid** (310次) - 属性: enabled, tags
1. **Timer** (238次) - 属性: 无属性
1. **Sin** (214次) - 属性: movement, wave, period
1. **Fade** (183次) - 属性: fade-in-time, wait-time, fade-out-time
1. **Bullet** (181次) - 属性: speed, acceleration, gravity
1. **Flash** (97次) - 属性: 无属性
1. **Platform** (81次) - 属性: max-speed, acceleration, deceleration
1. **Physics** (78次) - 属性: immovable, collision-mask, prevent-rotation
1. **scrollto** (74次) - 属性: enabled
1. **Rotate** (74次) - 属性: speed, acceleration, enabled
1. **EightDir** (66次) - 属性: max-speed, acceleration, deceleration
1. **destroy** (65次) - 属性: 无属性
1. **Pin** (64次) - 属性: destroy
1. **LOS** (50次) - 属性: obstacles, range, cone-of-view
1. **MoveTo** (34次) - 属性: max-speed, acceleration, deceleration
1. **bound** (32次) - 属性: bound-by
1. **DragnDrop** (27次) - 属性: axes, enabled
1. **TileMovement** (15次) - 属性: grid-width, grid-height, grid-offset-x
1. **Pathfinding** (14次) - 属性: cell-size, cell-border, obstacles

## Top 20 常用条件

1. **System.else** (1261次) - 无参数
1. **System.evaluate-expression** (1195次) - value
1. **Keyboard.key-is-down** (618次) - key
1. **System.for-each** (497次) - object
1. **Keyboard.on-key-pressed** (488次) - key
1. **System.on-start-of-layout** (477次) - 无参数
1. **System.compare-eventvar** (469次) - variable, comparison, value
1. **System.compare-two-values** (402次) - first-value, comparison, second-value
1. **System.every-tick** (391次) - 无参数
1. **Gamepad.is-button-down** (370次) - gamepad, button
1. **System.compare-boolean-eventvar** (361次) - variable
1. **Gamepad.on-button-pressed** (268次) - gamepad, button
1. **System.for** (261次) - name, start-index, end-index
1. **System.pick-by-evaluate** (237次) - object, expression
1. **System.every-x-seconds** (216次) - interval-seconds
1. **System.repeat** (183次) - count
1. **System.pick-by-comparison** (161次) - object, expression, comparison
1. **PlayerCollision:Platform.is-on-floor** (106次) - 无参数
1. **System.trigger-once-while-true** (103次) - 无参数
1. **PlayerCollision.on-collision-with-another-object** (103次) - object

## Top 20 常用动作

1. **Function-DEPRECATED.call-function-deprecated** (1956次) - 无参数
1. **System.set-eventvar-value** (1726次) - variable, value
1. **System.create-object** (781次) - object-to-create, layer, x
1. **System.wait** (411次) - seconds, use-timescale
1. **System.set-boolean-eventvar** (405次) - variable, value
1. **System.wait-for-previous-actions** (267次) - 无参数
1. **PlayerGraphics.set-animation** (243次) - animation, from
1. **Audio.play** (226次) - audio-file, loop, volume
1. **System.restart-layout** (225次) - 无参数
1. **System.set-group-active** (212次) - group-name, state
1. **System.add-to-eventvar** (199次) - variable, value
1. **Fader:Tween.tween-one-property** (174次) - tags, property, end-value
1. **PlayerCollision:Platform.simulate-control** (157次) - control
1. **Functions.set-function-return-value** (144次) - value
1. **System.reset-global-variables** (116次) - reset-static
1. **GameManager:Timer.start-timer** (103次) - duration, type, tag
1. **PlayerGraphics.spawn-another-object** (97次) - object, layer, image-point
1. **System.go-to-layout** (87次) - layout
1. **Text.set-text** (80次) - text
1. **Audio.fade-volume** (76次) - tag, db, duration

---

## ⚠️ 已弃用和被取代的功能

### 已弃用 (Deprecated)

以下功能已被弃用，应避免在新项目中使用：

| 功能 | 状态 | 说明 |
|------|------|------|
| `Function` 插件 | 已弃用 | 使用内置 `Functions` 系统替代 |

### 被取代 (Superseded)

以下功能已被更好的替代方案取代，建议新项目使用替代方案：

| 旧功能 | 替代方案 | 说明 |
|--------|----------|------|
| `Pin` 行为 | Hierarchies (Add child) | 层级系统更可靠，支持对象链 |
| `Fade` 行为 | `Tween` 行为 | Tween 更通用，可控制任意属性 |
| `solid` 行为的 `tags` 属性 | Instance tags | 使用实例标签系统 |

---

## 行为属性配置示例

### Tween

| 属性 | 常用值 |
|------|--------|
| enabled | `True`, `False` |

### solid

| 属性 | 常用值 |
|------|--------|
| enabled | `True`, `False` |
| tags | ``, `TeleportPlatform`, `geometry` |

### Timer

### Sin

| 属性 | 常用值 |
|------|--------|
| movement | `size`, `width`, `angle` |
| wave | `sine`, `sawtooth`, `triangle` |
| period | `1`, `2`, `4.1` |
| period-random | `0.25`, `0.35`, `1` |
| period-offset | `0.85`, `1`, `2` |
| period-offset-random | `0.25`, `1`, `4` |
| magnitude | `1`, `25`, `1.5` |
| magnitude-random | `4`, `50`, `0` |
| enabled | `True`, `False` |
| live-preview | `False` |

### Fade

| 属性 | 常用值 |
|------|--------|
| fade-in-time | `0.25`, `1`, `2` |
| wait-time | `1`, `2`, `1.5` |
| fade-out-time | `1.75`, `0.25`, `1` |
| destroy | `True`, `False` |
| enabled | `True`, `False` |
| live-preview | `False` |

### Bullet

| 属性 | 常用值 |
|------|--------|
| speed | `512`, `1200`, `0` |
| acceleration | `-32`, `512`, `-50` |
| gravity | `2048`, `1024`, `512` |
| bounce-off-solids | `True`, `False` |
| set-angle | `True`, `False` |
| step | `True`, `False` |
| enabled | `True`, `False` |

### Flash

### Platform

| 属性 | 常用值 |
|------|--------|
| max-speed | `480`, `330`, `450` |
| acceleration | `999999`, `2048`, `1024` |
| deceleration | `999999`, `1024`, `1600` |
| jump-strength | `480`, `768`, `1200` |
| gravity | `2048`, `1000`, `1024` |
| max-fall-speed | `5000`, `1000`, `1024` |
| double-jump | `True`, `False` |
| jump-sustain | `100`, `0`, `150` |
| default-controls | `True`, `False` |
| enabled | `True`, `False` |

### Physics

| 属性 | 常用值 |
|------|--------|
| immovable | `True`, `False` |
| collision-mask | `circle`, `use-collision-polygo`, `bounding-box` |
| prevent-rotation | `True`, `False` |
| density | `2`, `1`, `100` |
| friction | `0.1`, `1`, `0.5` |
| elasticity | `0.5`, `0.2`, `0.1` |
| linear-damping | `0.9`, `0` |
| angular-damping | `1`, `0.01`, `0` |
| bullet | `True`, `False` |
| enabled | `True`, `False` |

### scrollto

| 属性 | 常用值 |
|------|--------|
| enabled | `True` |
