# Clipboard Format Rules

JSON structure for pasting into C3 editor.

## Required Structure

```json
{"is-c3-clipboard-data": true, "type": "TYPE", "items": [...]}
```

## Type Values

| type | Paste Location |
|------|----------------|
| `"events"` | Event sheet margin |
| `"conditions"` | After selecting condition |
| `"actions"` | After selecting action |
| `"object-types"` | Project Bar → Object types |
| `"world-instances"` | Layout view |

## eventType Values

| eventType | Required Fields |
|-----------|-----------------|
| `"block"` | `conditions`, `actions` |
| `"variable"` | `name`, `type`, `initialValue`, **`comment`** |
| `"comment"` | `text` |
| `"group"` | `title`, `children`, `isActiveOnStart` |
| `"function-block"` | `functionName`, `functionReturnType`, `functionParameters` |

## Condition/Action Structure

```json
{"id": "ace-id", "objectClass": "ObjectName", "parameters": {...}}
```

With behavior:
```json
{"id": "ace-id", "objectClass": "ObjectName", "behaviorType": "BehaviorName", "parameters": {...}}
```

## Function Call

```json
{"callFunction": "FuncName", "parameters": ["param1", "param2"]}
```

In expression: `Functions.FuncName(param1, param2)`

## Write to Clipboard

```javascript
// MUST use this method, NOT writeText()
const blob = new Blob([json], {type: 'text/plain'});
await navigator.clipboard.write([new ClipboardItem({'text/plain': blob})])
```

## Variable Definition

**comment field is REQUIRED** (can be empty string):

```json
{"eventType": "variable", "name": "Score", "type": "number", "initialValue": "0", "comment": ""}
```

Types: `number`, `string`, `boolean`
