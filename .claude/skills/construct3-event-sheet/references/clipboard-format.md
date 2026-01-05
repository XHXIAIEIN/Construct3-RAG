# Construct 3 Clipboard Format

Paste content into C3 editor via JSON.

## Contents

- [Basic Structure](#basic-structure)
- [Type Values](#type-values)
- [Getting Correct Format](#getting-correct-format)
- [Key Notes](#key-notes)
- [Event Structure](#event-structure)
- [Object Types Structure](#object-types-structure)
- [World Instances](#world-instances)
- [Debugging](#debugging)
- [Unsupported Elements](#unsupported-elements)

---

## Basic Structure

```json
{"is-c3-clipboard-data": true, "type": "TYPE", "items": [...]}
```

## Type Values

| type | Purpose | Paste Location |
|------|---------|----------------|
| `"events"` | Complete event blocks | Event sheet margin |
| `"conditions"` | Conditions only | After selecting condition |
| `"actions"` | Actions only | After selecting action |
| `"object-types"` | Object type definitions | Object types folder |
| `"world-instances"` | Scene instances | Layout view |
| `"layouts"` | Layouts/Scenes | Layouts folder |
| `"event-sheets"` | Event sheets | Event sheets folder |

---

## Getting Correct Format

### Method 1: Copy from Editor (Recommended)
Copy existing events/objects in C3 editor, then read clipboard via JS:
```javascript
// Run in C3 editor console
navigator.clipboard.readText().then(t => console.log(t))
```

### Method 2: Query Schema Files
Schema files are the authoritative source:
- Plugins: `data/schemas/plugins/*.json`
- Behaviors: `data/schemas/behaviors/*.json`

```bash
# Find condition/action IDs
grep -n "every-x-seconds\|create-object" data/schemas/plugins/system.json

# Find behavior actions
grep -n "simulate-control" data/schemas/behaviors/eightdir.json
```

---

## Key Notes

### 1. Programmatic Clipboard Write
```javascript
// Wrong - C3 cannot recognize
navigator.clipboard.writeText(json);

// Correct - Must use ClipboardItem + Blob
const blob = new Blob([json], {type: 'text/plain'});
await navigator.clipboard.write([new ClipboardItem({'text/plain': blob})]);
```

### 2. String Parameters Need Nested Quotes
```json
"animation": "\"Walk\""           // animation name
"layer": "\"HUD\""                // layer name (string)
"layer": "0"                      // layer index (number)
"text": "\"Score: \" & Score"     // string concatenation
```

### 3. Variable Requires comment Field
```json
{"eventType": "variable", "name": "Score", "comment": ""}
```

### 4. Comparison Operators
See [parameter-types.md](parameter-types.md#comparison)

### 5. simulate-control Uses Strings
See [parameter-types.md](parameter-types.md#simulate-control)

### 6. Function Calls
- No return value: use `callFunction` action
- With return value: use expression `Functions.FuncName(params)`

---

## Event Structure

### eventType Values
```json
// Variable
{"eventType": "variable", "name": "Score", "type": "number", "initialValue": "0", "comment": "", "isStatic": false, "isConstant": false}

// Comment
{"eventType": "comment", "text": "Comment text"}

// Group
{"eventType": "group", "disabled": false, "title": "Title", "description": "", "isActiveOnStart": true, "children": []}

// Event block
{"eventType": "block", "conditions": [...], "actions": [...]}

// With sub-events
{"eventType": "block", "conditions": [...], "actions": [...], "children": [...]}

// OR block
{"eventType": "block", "conditions": [...], "actions": [...], "isOrBlock": true}

// Function
{"eventType": "function-block", "functionName": "MyFunc", "functionReturnType": "none", "functionParameters": [], "conditions": [], "actions": []}
```

### Condition/Action Structure
```json
// Condition
{"id": "condition-id", "objectClass": "ObjectName", "parameters": {...}}

// Condition with behavior
{"id": "condition-id", "objectClass": "ObjectName", "behaviorType": "BehaviorName", "parameters": {...}}

// Action
{"id": "action-id", "objectClass": "ObjectName", "parameters": {...}}

// Function call action
{"callFunction": "FunctionName", "parameters": ["param1", "param2"]}
```

---

## Object Types Structure

### Singleton Plugins (Keyboard, Mouse, Audio, etc.)
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[
  {"name":"Keyboard","plugin-id":"Keyboard","singleglobal-inst":{"type":"Keyboard","properties":{},"tags":""}}
],"folders":[]}
```

### World Objects (Sprite, Text)
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[
  {"name":"Text","plugin-id":"Text","isGlobal":false,"instanceVariables":[],"behaviorTypes":[],"effectTypes":[]}
],"folders":[]}
```

### Data Objects (Array, Dictionary)
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[
  {"name":"Array","plugin-id":"Arr","isGlobal":true,"nonworld-inst":{"type":"Array","properties":{"width":10,"height":1,"depth":1},"tags":""}}
],"folders":[]}
```

---

## World Instances

Paste instances in Layout view. **After pasting, click on scene to place instance.**

### Full Format (must include object-types and imageData)
```json
{"is-c3-clipboard-data":true,"type":"world-instances",
  "items":[{
    "type":"Player",
    "properties":{"initially-visible":true,"initial-animation":"Animation 1","initial-frame":0,"enable-collisions":true,"live-preview":false},
    "tags":"",
    "instanceVariables":{},
    "behaviors":{"8Direction":{"properties":{"max-speed":200,"acceleration":600,"deceleration":500,"directions":"dir-8","set-angle":"smooth","allow-sliding":false,"default-controls":false,"enabled":true}}},
    "instanceFolderItem":{"sid":936354517293677,"expanded":true},
    "showing":true,
    "locked":false,
    "world":{"x":600,"y":400,"width":32,"height":32,"originX":0.5,"originY":0.5,"color":[1,1,1,1],"angle":0,"zElevation":0}
  }],
  "object-types":[{
    "name":"Player",
    "plugin-id":"Sprite",
    "isGlobal":false,
    "editorNewInstanceIsReplica":true,
    "instanceVariables":[],
    "behaviorTypes":[{"behaviorId":"EightDir","name":"8Direction"}],
    "effectTypes":[],
    "animations":{"items":[{"frames":[{"width":32,"height":32,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":0,"useCollisionPoly":true,"duration":1,"tag":""}],"name":"Animation 1","isLooping":false,"isPingPong":false,"repeatCount":1,"repeatTo":0,"speed":5}],"subfolders":[],"name":"Animations"}
  }],
  "imageData":["data:image/png;base64,iVBORw0KGgo..."]
}
```

**Key Points**:
- **Must include `object-types`** - even if object exists, need full definition
- **Must include `imageData`** - base64 encoded PNG image array
- `behaviors` is object format: `{"BehaviorName": {"properties": {...}}}`
- `instanceFolderItem.sid` can be any number
- After pasting, cursor becomes placement mode, click scene to confirm position

---

## Debugging

### Validate Clipboard Content
```javascript
// Read and format output
navigator.clipboard.readText().then(t => console.log(JSON.stringify(JSON.parse(t), null, 2)))
```

### Common Errors

| Symptom | Cause | Solution |
|---------|-------|----------|
| Paste no response | Used `writeText()` | Use `ClipboardItem + Blob` |
| Paste no response | Focus not on target area | Click target area first |
| world-instances no preview | Missing `object-types` or `imageData` | Must include full definition and image data |
| Action/condition error | Wrong ID | Find correct ID from Schema |
| String parameter fails | Missing nested quotes | Use `"\"value\""` format |
| Behavior action fails | Missing `behaviorType` | Add behavior name field |

### Paste Location Requirements

| type | Must paste at |
|------|---------------|
| `events` | Event sheet blank margin area |
| `conditions` | After selecting existing condition |
| `actions` | After selecting existing action |
| `object-types` | Project Bar → Object types |
| `world-instances` | Layout view (click to place after paste) |

---

## Unsupported Elements

- **Layers** - No Copy option available
