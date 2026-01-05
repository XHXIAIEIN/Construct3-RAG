# Behavior Configuration Reference

Behavior property configuration based on 490 official example projects.

## Contents

- [Data Source](#data-source)
- [Top 10 Behaviors](#top-10-behaviors)
- [Behavior Details](#behavior-details)
- [Behavior Combinations](#behavior-combinations)

---

## Data Source

- Full behavior knowledge: `data/project_analysis/behaviors_knowledge.json`
- Usage ranking: `data/project_analysis/sorted_indexes.json` → `top_20_behaviors`
- Schema definitions: `data/schemas/behaviors/*.json`

## Top 10 Behaviors

| # | Behavior ID | Usage Count | Main Purpose |
|---|-------------|-------------|--------------|
| 1 | Tween | 1018 | Property animation |
| 2 | solid | 310 | Solid collision |
| 3 | Timer | 238 | Timer |
| 4 | Sin | 214 | Sine motion |
| 5 | Fade | 183 | Fade in/out |
| 6 | Bullet | 181 | Bullet movement |
| 7 | Flash | 97 | Flash effect |
| 8 | Platform | 81 | Platform jumping |
| 9 | Physics | 78 | Physics simulation |
| 10 | EightDir | 66 | 8-directional movement |

## Behavior Details

### Tween - Property Animation
```json
"behaviorTypes": [{"behaviorId": "Tween", "name": "Tween"}]
```
Properties: `enabled`

Common actions:
```json
{"id": "tween-one-property", "objectClass": "Sprite", "behaviorType": "Tween", "parameters": {
  "tags": "\"fade\"",
  "property": "opacity",     // x, y, width, height, angle, opacity, z-elevation, etc.
  "end-value": "0",
  "time": "1",
  "ease": "in-out-sine",     // linear, in-sine, out-sine, in-out-sine, etc.
  "destroy-on-complete": "no",
  "loop": "no",
  "ping-pong": "no",
  "repeat-count": "1"
}}
```

### Platform - Platform Jumping
```json
"behaviorTypes": [{"behaviorId": "Platform", "name": "Platform"}]
```
Properties:
| Property | Common Values | Description |
|----------|---------------|-------------|
| `max-speed` | 330-480 | Max move speed |
| `acceleration` | 1024-2048 | Acceleration |
| `deceleration` | 1024-1600 | Deceleration |
| `jump-strength` | 768-1200 | Jump strength |
| `gravity` | 1000-2048 | Gravity |
| `max-fall-speed` | 1000-5000 | Max fall speed |
| `double-jump` | true/false | Double jump |
| `default-controls` | true/false | Default keyboard control |

Common ACE:
```json
// Conditions
{"id": "is-on-floor", "objectClass": "Player", "behaviorType": "Platform", "parameters": {}}
{"id": "is-jumping", "objectClass": "Player", "behaviorType": "Platform", "parameters": {}}
{"id": "is-falling", "objectClass": "Player", "behaviorType": "Platform", "parameters": {}}
{"id": "on-landed", "objectClass": "Player", "behaviorType": "Platform", "parameters": {}}

// Actions
{"id": "simulate-control", "objectClass": "Player", "behaviorType": "Platform", "parameters": {"control": "jump"}}
{"id": "set-vector-y", "objectClass": "Player", "behaviorType": "Platform", "parameters": {"vector-y": "-800"}}
{"id": "set-max-speed", "objectClass": "Player", "behaviorType": "Platform", "parameters": {"max-speed": "400"}}
```

### EightDir - 8-Directional Movement
```json
"behaviorTypes": [{"behaviorId": "EightDir", "name": "8Direction"}]
```
Properties:
| Property | Common Values | Description |
|----------|---------------|-------------|
| `max-speed` | 200-400 | Max speed |
| `acceleration` | 600-1500 | Acceleration |
| `deceleration` | 500-1000 | Deceleration |
| `directions` | dir-8, dir-4 | Direction count |
| `set-angle` | no, smooth | Angle setting |
| `default-controls` | true/false | Default control |

Common ACE:
```json
// Actions
{"id": "simulate-control", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {"control": "up"}}
{"id": "set-max-speed", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {"max-speed": "300"}}
{"id": "set-enabled", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {"state": "disabled"}}

// Conditions
{"id": "is-moving", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {}}
```

### Bullet - Bullet Movement
```json
"behaviorTypes": [{"behaviorId": "Bullet", "name": "Bullet"}]
```
Properties:
| Property | Common Values | Description |
|----------|---------------|-------------|
| `speed` | 200-1200 | Speed |
| `acceleration` | 0 or negative | Acceleration |
| `gravity` | 0-2048 | Gravity |
| `bounce-off-solids` | true/false | Bounce off solids |
| `set-angle` | true/false | Set angle |

### Timer - Timer
```json
"behaviorTypes": [{"behaviorId": "Timer", "name": "Timer"}]
```
Common ACE:
```json
// Actions
{"id": "start-timer", "objectClass": "GameManager", "behaviorType": "Timer", "parameters": {
  "duration": "2",
  "type": "once",      // once, regular
  "tag": "\"spawn\""
}}

// Conditions
{"id": "on-timer", "objectClass": "GameManager", "behaviorType": "Timer", "parameters": {"tag": "\"spawn\""}}
```

### Sin - Sine Motion
```json
"behaviorTypes": [{"behaviorId": "Sin", "name": "Sine"}]
```
Properties:
| Property | Common Values | Description |
|----------|---------------|-------------|
| `movement` | size, width, angle, x, y | Movement type |
| `wave` | sine, sawtooth, triangle | Wave shape |
| `period` | 1-4 | Period (seconds) |
| `magnitude` | 1-50 | Magnitude |

### solid - Solid Collision
```json
"behaviorTypes": [{"behaviorId": "solid", "name": "Solid"}]
```
Properties: `enabled`, `tags`

### Physics - Physics Engine
```json
"behaviorTypes": [{"behaviorId": "Physics", "name": "Physics"}]
```
Properties:
| Property | Common Values | Description |
|----------|---------------|-------------|
| `immovable` | true/false | Immovable |
| `collision-mask` | circle, bounding-box | Collision shape |
| `density` | 1-100 | Density |
| `friction` | 0.1-1 | Friction |
| `elasticity` | 0.1-0.5 | Elasticity |

### Fade - Fade In/Out (Superseded by Tween)
```json
"behaviorTypes": [{"behaviorId": "Fade", "name": "Fade"}]
```
Properties: `fade-in-time`, `wait-time`, `fade-out-time`, `destroy`

### Flash - Flash Effect
```json
"behaviorTypes": [{"behaviorId": "Flash", "name": "Flash"}]
```
Action:
```json
{"id": "flash", "objectClass": "Player", "behaviorType": "Flash", "parameters": {"on-time": "0.1", "off-time": "0.1", "duration": "1"}}
```

## Behavior Combinations

### Platform Game Character
```json
"behaviorTypes": [
  {"behaviorId": "Platform", "name": "Platform"},
  {"behaviorId": "Tween", "name": "Tween"},
  {"behaviorId": "Flash", "name": "Flash"}
]
```

### Top-Down Character
```json
"behaviorTypes": [
  {"behaviorId": "EightDir", "name": "8Direction"},
  {"behaviorId": "Tween", "name": "Tween"},
  {"behaviorId": "LOS", "name": "LineOfSight"}
]
```

### Bullet/Projectile
```json
"behaviorTypes": [
  {"behaviorId": "Bullet", "name": "Bullet"},
  {"behaviorId": "destroy", "name": "DestroyOutsideLayout"}
]
```

### Animated UI Element
```json
"behaviorTypes": [
  {"behaviorId": "Tween", "name": "Tween"},
  {"behaviorId": "Anchor", "name": "Anchor"}
]
```
