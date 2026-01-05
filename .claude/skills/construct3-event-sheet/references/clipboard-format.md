# Construct 3 Clipboard Format & Templates

## Clipboard Structure

```json
{"is-c3-clipboard-data": true, "type": "TYPE", "items": [...]}
```

### Valid Types
| type | Purpose | Paste Location |
|------|---------|----------------|
| `"events"` | Event blocks | Event sheet margin |
| `"conditions"` | Conditions only | After selecting condition |
| `"actions"` | Actions only | After selecting action |

### Write to Clipboard (MUST use Blob)
```javascript
// ❌ Wrong
navigator.clipboard.writeText(json);

// ✅ Correct
const blob = new Blob([json], {type: 'text/plain'});
await navigator.clipboard.write([new ClipboardItem({'text/plain': blob})]);
```

---

## Event Types

```json
// Variable (comment required!)
{"eventType": "variable", "name": "Score", "type": "number", "initialValue": "0", "comment": ""}

// Comment
{"eventType": "comment", "text": "Comment text"}

// Group
{"eventType": "group", "disabled": false, "title": "Title", "children": []}

// Event Block
{"eventType": "block", "conditions": [...], "actions": [...]}

// With sub-events
{"eventType": "block", "conditions": [...], "actions": [...], "children": [...]}

// Function
{"eventType": "function-block", "functionName": "MyFunc", "functionReturnType": "none", "functionParameters": [], "conditions": [], "actions": [...]}
```

---

## Parameter Rules

### String Parameters (MUST have nested quotes)
```json
"animation": "\"Walk\""           // Animation name
"layer": "\"HUD\""                // Layer name
"text": "\"Score: \" & Score"     // String concatenation
```

### Comparison Operators (use numbers)
| Value | Operator |
|-------|----------|
| 0 | = |
| 1 | ≠ |
| 2 | < |
| 3 | ≤ |
| 4 | > |
| 5 | ≥ |

### Key Codes
| Key | Code | Key | Code |
|-----|------|-----|------|
| W | 87 | ↑ | 38 |
| A | 65 | ← | 37 |
| S | 83 | ↓ | 40 |
| D | 68 | → | 39 |
| Space | 32 | Enter | 13 |
| Shift | 16 | Esc | 27 |

---

## Templates

Replace `{placeholder}` with actual values.

### Movement

**WASD 8Direction**
```json
{"is-c3-clipboard-data":true,"type":"events","items":[
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":87}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"8Direction","parameters":{"control":"up"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":65}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"8Direction","parameters":{"control":"left"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":83}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"8Direction","parameters":{"control":"down"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":68}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"8Direction","parameters":{"control":"right"}}]}
]}
```

**Platform Movement + Jump**
```json
{"is-c3-clipboard-data":true,"type":"events","items":[
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":37}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"Platform","parameters":{"control":"left"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":39}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"Platform","parameters":{"control":"right"}}]},
  {"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":32}}],"actions":[{"id":"simulate-control","objectClass":"{Object}","behaviorType":"Platform","parameters":{"control":"jump"}}]}
]}
```

**Spawn Bullet**
```json
{"eventType":"block","conditions":[{"id":"on-key-pressed","objectClass":"Keyboard","parameters":{"key":32}}],"actions":[{"id":"spawn-another-object","objectClass":"{Shooter}","parameters":{"object":"{Bullet}","layer":"0","image-point":"0"}}]}
```

### Events

**Collision**
```json
{"eventType":"block","conditions":[{"id":"on-collision-with-another-object","objectClass":"{Object1}","parameters":{"object":"{Object2}"}}],"actions":[{"id":"destroy","objectClass":"{Object2}","parameters":{}}]}
```

**Every X Seconds**
```json
{"eventType":"block","conditions":[{"id":"every-x-seconds","objectClass":"System","parameters":{"interval-seconds":"{N}"}}],"actions":[...]}
```

**On Layout Start**
```json
{"eventType":"block","conditions":[{"id":"on-start-of-layout","objectClass":"System","parameters":{}}],"actions":[...]}
```

**On Created / Destroyed**
```json
{"eventType":"block","conditions":[{"id":"on-created","objectClass":"{Object}","parameters":{}}],"actions":[...]}
{"eventType":"block","conditions":[{"id":"on-destroyed","objectClass":"{Object}","parameters":{}}],"actions":[...]}
```

### Variables

**Define (comment required!)**
```json
{"eventType":"variable","name":"{VarName}","type":"number","initialValue":"0","comment":""}
{"eventType":"variable","name":"{VarName}","type":"boolean","initialValue":"false","comment":""}
{"eventType":"variable","name":"{VarName}","type":"string","initialValue":"\"\"","comment":""}
```

**Modify**
```json
{"id":"set-eventvar-value","objectClass":"System","parameters":{"variable":"{VarName}","value":"{Value}"}}
{"id":"add-to-eventvar","objectClass":"System","parameters":{"variable":"{VarName}","value":"{Value}"}}
{"id":"set-instvar-value","objectClass":"{Object}","parameters":{"instance-variable":"{VarName}","value":"{Value}"}}
```

**Compare**
```json
{"eventType":"block","conditions":[{"id":"compare-eventvar","objectClass":"System","parameters":{"variable":"{VarName}","comparison":4,"value":"0"}}],"actions":[...]}
```

### Flow Control

**If/Else**
```json
{"eventType":"block","conditions":[{"id":"compare-eventvar","objectClass":"System","parameters":{"variable":"{VarName}","comparison":4,"value":"0"}}],"actions":[...]},
{"eventType":"block","conditions":[{"id":"else","objectClass":"System","parameters":{}}],"actions":[...]}
```

**Loops**
```json
{"eventType":"block","conditions":[{"id":"for","objectClass":"System","parameters":{"name":"\"i\"","start-index":"0","end-index":"10"}}],"actions":[...]}
{"eventType":"block","conditions":[{"id":"for-each","objectClass":"System","parameters":{"object":"{ObjectType}"}}],"actions":[...]}
{"eventType":"block","conditions":[{"id":"repeat","objectClass":"System","parameters":{"count":"10"}}],"actions":[...]}
```

**Function Call**
```json
{"callFunction":"{FunctionName}","parameters":["{param1}","{param2}"]}
```
With return value: `"value": "Functions.{FunctionName}({params})"`

**Wait**
```json
{"id":"wait","objectClass":"System","parameters":{"seconds":"{N}"}}
```

### Animation

**Tween Property**
property: x, y, width, height, angle, opacity, z-elevation
ease: linear, in-sine, out-sine, in-out-sine, in-back, out-back, in-elastic, out-elastic, in-bounce, out-bounce
```json
{"id":"tween-one-property","objectClass":"{Object}","behaviorType":"Tween","parameters":{"tags":"\"{tag}\"","property":"{property}","end-value":"{value}","time":"{seconds}","ease":"in-out-sine","destroy-on-complete":"no","loop":"no","ping-pong":"no","repeat-count":"1"}}
```

**Flash**
```json
{"id":"flash","objectClass":"{Object}","behaviorType":"Flash","parameters":{"on-time":"0.1","off-time":"0.1","duration":"1"}}
```

**Set Animation**
```json
{"id":"set-animation","objectClass":"{Object}","parameters":{"animation":"\"{AnimationName}\"","from":"beginning"}}
```

### Input

**Keyboard**
```json
{"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":{KeyCode}}}],"actions":[...]}
{"eventType":"block","conditions":[{"id":"on-key-pressed","objectClass":"Keyboard","parameters":{"key":{KeyCode}}}],"actions":[...]}
```

**Mouse**
```json
{"eventType":"block","conditions":[{"id":"on-click","objectClass":"Mouse","parameters":{"mouse-button":"left","click-type":"clicked"}}],"actions":[...]}
{"eventType":"block","conditions":[{"id":"on-object-clicked","objectClass":"Mouse","parameters":{"mouse-button":"left","click-type":"clicked","object-clicked":"{Object}"}}],"actions":[...]}
```

**Touch**
```json
{"eventType":"block","conditions":[{"id":"on-touched-object","objectClass":"Touch","parameters":{"object":"{Object}","type":"touch"}}],"actions":[...]}
```

### Audio

```json
{"id":"play","objectClass":"Audio","parameters":{"audio-file":"{SoundName}","loop":"not-looping","volume":"0","tag-optional":"\"\""}}
{"id":"play","objectClass":"Audio","parameters":{"audio-file":"{MusicName}","loop":"looping","volume":"0","tag-optional":"\"bgm\""}}
{"id":"stop","objectClass":"Audio","parameters":{"tag":"\"bgm\""}}
{"id":"fade-volume","objectClass":"Audio","parameters":{"tag":"\"bgm\"","db":"-60","duration":"1"}}
```

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Paste not working | Used `writeText()` | Use `ClipboardItem + Blob` |
| Paste not working | Focus not on target | Click target area first |
| Action/condition error | Wrong ID | Check schema files |
| String param failed | Missing nested quotes | Use `"\"value\""` format |
| Behavior action failed | Missing behaviorType | Add behavior name field |

### Get Correct Format
```javascript
// Read clipboard in C3 console
navigator.clipboard.readText().then(t => console.log(JSON.stringify(JSON.parse(t), null, 2)))
```

### Query Schema
```bash
grep -n "set-animation" data/schemas/plugins/sprite.json
grep -n "simulate-control" data/schemas/behaviors/eightdir.json
```
