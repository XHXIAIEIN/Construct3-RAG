# Event Sheet Templates

Ready-to-use code templates. Replace `{placeholder}` with actual values.

## Contents

- [Movement](#movement) - 8Direction, Platform, Bullet
- [Events](#events) - Collision, Timer, Layout Start
- [Variables](#variables) - Define, Compare, Modify
- [Flow Control](#flow-control) - Conditions, Loops, Functions
- [Animation](#animation) - Tween, Flash, Set Animation
- [Input](#input) - Keyboard, Mouse, Touch
- [Audio](#audio) - Play, Stop, Fade

---

## Movement

### WASD 8Direction
```json
{"is-c3-clipboard-data":true,"type":"events","items":[
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":87}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"8Direction","parameters":{"control":"up"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":65}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"8Direction","parameters":{"control":"left"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":83}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"8Direction","parameters":{"control":"down"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":68}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"8Direction","parameters":{"control":"right"}}]}
]}
```

### Arrow Keys 8Direction
```json
{"is-c3-clipboard-data":true,"type":"events","items":[
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":38}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"8Direction","parameters":{"control":"up"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":37}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"8Direction","parameters":{"control":"left"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":40}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"8Direction","parameters":{"control":"down"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":39}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"8Direction","parameters":{"control":"right"}}]}
]}
```

### Platform Movement + Jump
```json
{"is-c3-clipboard-data":true,"type":"events","items":[
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":37}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"Platform","parameters":{"control":"left"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":39}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"Platform","parameters":{"control":"right"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":32}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"Platform","parameters":{"control":"jump"}}]}
]}
```

### Spawn Bullet
```json
{"eventType":"block","conditions":[{"id":"on-key-pressed","objectClass":"Keyboard","parameters":{"key":32}}],"actions":[{"id":"spawn-another-object","objectClass":"{Shooter}","parameters":{"object":"{Bullet}","layer":"0","image-point":"0"}}]}
```

---

## Events

### Collision Detection
```json
{"eventType":"block","conditions":[{"id":"on-collision-with-another-object","objectClass":"{Object1}","parameters":{"object":"{Object2}"}}],"actions":[{"id":"destroy","objectClass":"{Object2}","parameters":{}}]}
```

### Overlap Detection
```json
{"eventType":"block","conditions":[{"id":"is-overlapping-another-object","objectClass":"{Object1}","parameters":{"object":"{Object2}"}}],"actions":[...]}
```

### Every X Seconds
```json
{"eventType":"block","conditions":[{"id":"every-x-seconds","objectClass":"System","parameters":{"interval-seconds":"{N}"}}],"actions":[...]}
```

### On Layout Start
```json
{"eventType":"block","conditions":[{"id":"on-start-of-layout","objectClass":"System","parameters":{}}],"actions":[...]}
```

### On Created
```json
{"eventType":"block","conditions":[{"id":"on-created","objectClass":"{Object}","parameters":{}}],"actions":[...]}
```

### On Destroyed
```json
{"eventType":"block","conditions":[{"id":"on-destroyed","objectClass":"{Object}","parameters":{}}],"actions":[...]}
```

---

## Variables

### Define Variable
**comment field is required.**
```json
{"eventType":"variable","name":"{VarName}","type":"number","initialValue":"0","comment":""}
```

### Boolean Variable
```json
{"eventType":"variable","name":"{VarName}","type":"boolean","initialValue":"false","comment":""}
```

### String Variable
```json
{"eventType":"variable","name":"{VarName}","type":"string","initialValue":"\"\"","comment":""}
```

### Set Variable
```json
{"id":"set-eventvar-value","objectClass":"System","parameters":{"variable":"{VarName}","value":"{Value}"}}
```

### Add to Variable
```json
{"id":"add-to-eventvar","objectClass":"System","parameters":{"variable":"{VarName}","value":"{Value}"}}
```

### Set Boolean Variable
```json
{"id":"set-boolean-eventvar","objectClass":"System","parameters":{"variable":"{VarName}","value":"true"}}
```

### Set Instance Variable
```json
{"id":"set-instvar-value","objectClass":"{Object}","parameters":{"instance-variable":"{VarName}","value":"{Value}"}}
```

---

## Flow Control

### If/Else
comparison: 0=Equal, 1=NotEqual, 2=Less, 3=LessOrEqual, 4=Greater, 5=GreaterOrEqual
```json
{"eventType":"block","conditions":[{"id":"compare-eventvar","objectClass":"System","parameters":{"variable":"{VarName}","comparison":4,"value":"0"}}],"actions":[...]},
{"eventType":"block","conditions":[{"id":"else","objectClass":"System","parameters":{}}],"actions":[...]}
```

### Evaluate Expression
```json
{"eventType":"block","conditions":[{"id":"evaluate-expression","objectClass":"System","parameters":{"value":"{Expression}"}}],"actions":[...]}
```

### For Loop
```json
{"eventType":"block","conditions":[{"id":"for","objectClass":"System","parameters":{"name":"\"i\"","start-index":"0","end-index":"10"}}],"actions":[...]}
```

### For Each
```json
{"eventType":"block","conditions":[{"id":"for-each","objectClass":"System","parameters":{"object":"{ObjectType}"}}],"actions":[...]}
```

### Repeat
```json
{"eventType":"block","conditions":[{"id":"repeat","objectClass":"System","parameters":{"count":"10"}}],"actions":[...]}
```

### Function Call (no return)
```json
{"callFunction":"{FunctionName}","parameters":["{param1}","{param2}"]}
```

### Function Call (with return)
Use in expression:
```
"value": "Functions.{FunctionName}({params})"
```

### Function Definition
```json
{"eventType":"function-block","functionName":"{FuncName}","functionReturnType":"none","functionParameters":[],"conditions":[],"actions":[...]}
```

### Wait
```json
{"id":"wait","objectClass":"System","parameters":{"seconds":"{N}"}}
```

### Wait for Previous Actions
```json
{"id":"wait-for-previous-actions","objectClass":"System","parameters":{}}
```

---

## Animation

### Tween Property
property: x, y, width, height, angle, opacity, z-elevation
ease: linear, in-sine, out-sine, in-out-sine, in-back, out-back, in-elastic, out-elastic, in-bounce, out-bounce
```json
{"id":"tween-one-property","objectClass":"{Object}","behaviorType":"Tween","parameters":{"tags":"\"{tag}\"","property":"{property}","end-value":"{value}","time":"{seconds}","ease":"in-out-sine","destroy-on-complete":"no","loop":"no","ping-pong":"no","repeat-count":"1"}}
```

### Tween Position
```json
{"id":"tween-two-properties","objectClass":"{Object}","behaviorType":"Tween","parameters":{"tags":"\"{tag}\"","first-property":"x","first-end-value":"{x}","second-property":"y","second-end-value":"{y}","time":"{seconds}","ease":"in-out-sine","destroy-on-complete":"no","loop":"no","ping-pong":"no","repeat-count":"1"}}
```

### Flash
```json
{"id":"flash","objectClass":"{Object}","behaviorType":"Flash","parameters":{"on-time":"0.1","off-time":"0.1","duration":"1"}}
```

### Set Animation
**animation parameter requires nested quotes.**
```json
{"id":"set-animation","objectClass":"{Object}","parameters":{"animation":"\"{AnimationName}\"","from":"beginning"}}
```

### Set Mirrored
```json
{"id":"set-mirrored","objectClass":"{Object}","parameters":{"state":"mirrored"}}
```

---

## Input

### Key Down (continuous)
```json
{"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":{KeyCode}}}],"actions":[...]}
```

### Key Pressed (once)
```json
{"eventType":"block","conditions":[{"id":"on-key-pressed","objectClass":"Keyboard","parameters":{"key":{KeyCode}}}],"actions":[...]}
```

### Mouse Click
```json
{"eventType":"block","conditions":[{"id":"on-click","objectClass":"Mouse","parameters":{"mouse-button":"left","click-type":"clicked"}}],"actions":[...]}
```

### Click Object
```json
{"eventType":"block","conditions":[{"id":"on-object-clicked","objectClass":"Mouse","parameters":{"mouse-button":"left","click-type":"clicked","object-clicked":"{Object}"}}],"actions":[...]}
```

### Touch Object
```json
{"eventType":"block","conditions":[{"id":"on-touched-object","objectClass":"Touch","parameters":{"object":"{Object}","type":"touch"}}],"actions":[...]}
```

---

## Audio

### Play Sound
```json
{"id":"play","objectClass":"Audio","parameters":{"audio-file":"{SoundName}","loop":"not-looping","volume":"0","tag-optional":"\"\""}}
```

### Play BGM (loop)
```json
{"id":"play","objectClass":"Audio","parameters":{"audio-file":"{MusicName}","loop":"looping","volume":"0","tag-optional":"\"bgm\""}}
```

### Stop Audio
```json
{"id":"stop","objectClass":"Audio","parameters":{"tag":"\"bgm\""}}
```

### Fade Out
```json
{"id":"fade-volume","objectClass":"Audio","parameters":{"tag":"\"bgm\"","db":"-60","duration":"1"}}
```

---

## Key Codes

| Key | Code | Key | Code |
|-----|------|-----|------|
| W | 87 | ↑ | 38 |
| A | 65 | ← | 37 |
| S | 83 | ↓ | 40 |
| D | 68 | → | 39 |
| Space | 32 | Enter | 13 |
| Shift | 16 | Ctrl | 17 |
| Esc | 27 | Tab | 9 |
