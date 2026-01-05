# Deprecated Features

Do NOT use these. Use the alternatives instead.

## Deprecated

| Feature | Use Instead |
|---------|-------------|
| Function plugin (`objectClass: "Function"`) | Built-in Functions system |
| Pin behavior | Hierarchies (`add-child` action) |
| Fade behavior | Tween behavior (`property: "opacity"`) |

## Function Plugin → Functions System

```json
// OLD (deprecated)
{"callFunction": "MyFunc", "parameters": [...]}

// NEW (use this)
{"eventType": "function-block", "functionName": "MyFunc", "functionReturnType": "number",
 "functionParameters": [{"name": "param1", "type": "number"}], "conditions": [], "actions": [...]}

// Call in expression
"value": "Functions.MyFunc(100)"
```

## Pin → Hierarchies

```json
// OLD (deprecated)
{"id": "pin-to-object", "objectClass": "Weapon", "behaviorType": "Pin", "parameters": {...}}

// NEW (use this)
{"id": "add-child", "objectClass": "Player", "parameters": {
  "child": "Weapon", "transform-x": "yes", "transform-y": "yes", "transform-a": "yes", "destroy-with-parent": "yes"}}
```

## Fade → Tween

```json
// OLD (deprecated)
Use Fade behavior properties

// NEW (use this)
{"id": "tween-one-property", "objectClass": "Sprite", "behaviorType": "Tween", "parameters": {
  "tags": "\"fade\"", "property": "opacity", "end-value": "0", "time": "0.5", "ease": "in-out-sine", "destroy-on-complete": "yes"}}
```
