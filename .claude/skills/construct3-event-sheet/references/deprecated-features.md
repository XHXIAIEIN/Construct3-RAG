# Deprecated and Superseded Features

Deprecated and superseded feature warnings. Avoid using these in new projects.

---

## Deprecated

The following features are deprecated and should be avoided in new projects:

### Function Plugin

| Status | Deprecated |
|--------|------------|
| Replacement | Built-in `Functions` system |
| Note | Old Function plugin uses `callFunction` action, new built-in Functions system is more powerful |

**Old way (avoid)**:
```json
{"callFunction": "MyFunction", "parameters": ["param1"]}
```

**New way (recommended)**:
```json
// Define function in event sheet
{"eventType": "function-block", "functionName": "MyFunction", "functionReturnType": "number",
 "functionParameters": [{"name": "param1", "type": "number"}],
 "conditions": [], "actions": [...]}

// Call function (action)
{"callFunction": "MyFunction", "parameters": ["100"]}

// Call function (in expression)
"value": "Functions.MyFunction(100)"
```

---

## Superseded

The following features have been superseded by better alternatives. New projects should use the alternatives:

### Pin Behavior → Hierarchies

| Old Feature | Pin behavior |
|-------------|--------------|
| Replacement | Hierarchies (Add child) |
| Note | Hierarchy system is more reliable, supports object chains, use `add-child` action |

**Old way (Pin)**:
```json
{"id": "pin-to-object", "objectClass": "Weapon", "behaviorType": "Pin",
 "parameters": {"pin-to": "Player", "mode": "position-angle"}}
```

**New way (Hierarchies)**:
```json
{"id": "add-child", "objectClass": "Player",
 "parameters": {
   "child": "Weapon",
   "transform-x": "yes",
   "transform-y": "yes",
   "transform-a": "yes",
   "destroy-with-parent": "yes"
 }}
```

### Fade Behavior → Tween Behavior

| Old Feature | Fade behavior |
|-------------|---------------|
| Replacement | Tween behavior |
| Note | Tween is more versatile, can control any property, not just opacity |

**Old way (Fade)**:
```json
// Need to add Fade behavior to object, configure via properties
"behaviors": {
  "Fade": {
    "properties": {
      "fade-in-time": 0.5,
      "wait-time": 1,
      "fade-out-time": 0.5,
      "destroy": true
    }
  }
}
```

**New way (Tween)**:
```json
{"id": "tween-one-property", "objectClass": "Sprite", "behaviorType": "Tween",
 "parameters": {
   "tags": "\"fade\"",
   "property": "opacity",
   "end-value": "0",
   "time": "0.5",
   "ease": "in-out-sine",
   "destroy-on-complete": "yes"
 }}
```

### solid Behavior tags Property → Instance Tags

| Old Feature | solid behavior's `tags` property |
|-------------|----------------------------------|
| Replacement | Instance tags system |
| Note | Instance tags system is more flexible |

---

## Detection Patterns

Warn if the following patterns are detected in generated code:

```json
// Detect Function plugin (deprecated)
"objectClass": "Function"

// Detect Pin behavior (superseded)
"behaviorType": "Pin"
"id": "pin-to-object"

// Detect Fade behavior (superseded)
"behaviorType": "Fade"
```

---

## Migration Guide

### Function → Functions

1. Create new function definition block
2. Migrate function logic
3. Update all call sites

### Pin → Hierarchies

1. Remove Pin behavior
2. Use `add-child` action to establish parent-child relationship
3. Configure appropriate transform options

### Fade → Tween

1. Add Tween behavior
2. Use `tween-one-property` action to control `opacity`
3. Configure `destroy-on-complete` if destruction needed
