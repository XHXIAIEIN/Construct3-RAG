# Troubleshooting Guide

Common issues and solutions for C3 event sheet JSON generation.

## Contents

- [Paste Not Working](#paste-not-working)
- [Action/Condition Error](#actioncondition-error)
- [String Parameter Failed](#string-parameter-failed)
- [Behavior Not Working](#behavior-not-working)
- [Validation Errors](#validation-errors)

---

## Paste Not Working

| Symptom | Cause | Solution |
|---------|-------|----------|
| Nothing happens on paste | Used `writeText()` | Use `ClipboardItem + Blob` |
| Nothing happens on paste | Focus not on target | Click event sheet margin first |
| Nothing happens on paste | Invalid JSON | Validate JSON syntax |
| Paste shows error | Wrong `type` value | Check type matches paste location |

### Correct Clipboard Write

```javascript
// Wrong - C3 cannot recognize
navigator.clipboard.writeText(json);

// Correct - Must use ClipboardItem + Blob
const blob = new Blob([json], {type: 'text/plain'});
await navigator.clipboard.write([new ClipboardItem({'text/plain': blob})])
```

### Paste Location Requirements

| type | Must paste at |
|------|---------------|
| `events` | Event sheet blank margin area |
| `conditions` | After selecting existing condition |
| `actions` | After selecting existing action |
| `object-types` | Project Bar → Object types |
| `world-instances` | Layout view (click to place after paste) |

---

## Action/Condition Error

| Symptom | Cause | Solution |
|---------|-------|----------|
| ACE not found | Wrong ID format | Use `kebab-case`: `set-animation` |
| ACE not found | Wrong ID | Check [system-reference.md](system-reference.md) |
| Parameter error | Wrong parameter name | Check Schema definition |
| Behavior action fails | Missing `behaviorType` | Add behavior name field |

### ID Format Rules

```json
// Wrong - used camelCase
"id": "setAnimation"

// Correct - use kebab-case
"id": "set-animation"
```

### Behavior ACE Requires behaviorType

```json
// Wrong - missing behaviorType
{"id": "simulate-control", "objectClass": "Player", "parameters": {"control": "up"}}

// Correct - include behaviorType
{"id": "simulate-control", "objectClass": "Player", "behaviorType": "8Direction", "parameters": {"control": "up"}}
```

---

## String Parameter Failed

| Symptom | Cause | Solution |
|---------|-------|----------|
| Parameter ignored | Missing nested quotes | Use `"\"value\""` format |
| Parse error | Unescaped quotes | Escape properly |
| Wrong value | Confused with expression | Strings need quotes, expressions don't |

### String vs Expression

```json
// String literal - needs nested quotes
"animation": "\"Walk\""
"text": "\"Hello World\""
"tag": "\"player\""

// Expression - no nested quotes
"x": "Player.X + 100"
"value": "Score * 2"

// String concatenation - mixed
"text": "\"Score: \" & Score"
```

---

## Behavior Not Working

| Symptom | Cause | Solution |
|---------|-------|----------|
| Behavior not found | Wrong behaviorType | Use display name: `"8Direction"` not `"EightDir"` |
| Property not set | Wrong property name | Check [behavior-config.md](behavior-config.md) |

### Common Behavior Name Errors

| Wrong (behaviorId) | Correct (behaviorType) |
|--------------------|------------------------|
| `EightDir` | `8Direction` |
| `DragnDrop` | `Drag & Drop` |
| `LOS` | `Line of sight` |
| `Sin` | `Sine` |

---

## Validation Errors

Use the validation script before pasting:

```bash
python scripts/validate_output.py '{"is-c3-clipboard-data":true,...}'
```

### Common Validation Errors

| Error | Solution |
|-------|----------|
| Missing `is-c3-clipboard-data` | Add `"is-c3-clipboard-data": true` |
| Missing `type` | Add `"type": "events"` (or other valid type) |
| Missing `items` | Add `"items": [...]` array |
| Variable missing `comment` | Add `"comment": ""` (can be empty) |
| Comparison is string | Use number: `"comparison": 0` not `"comparison": "="` |
