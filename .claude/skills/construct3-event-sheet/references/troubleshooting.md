# Error Prevention

Common mistakes and how to avoid them.

## Paste Not Working

| Cause | Fix |
|-------|-----|
| Used `writeText()` | Use `ClipboardItem + Blob` |
| Wrong focus | Click event sheet margin first |
| Bad JSON | Validate with `scripts/validate_output.py` |

## ACE Errors

| Error | Fix |
|-------|-----|
| ACE not found | Use kebab-case ID: `set-animation` |
| Wrong behavior | Use display name: `8Direction` not `EightDir` |
| Missing behaviorType | Add `"behaviorType": "BehaviorName"` |

## Parameter Errors

| Error | Fix |
|-------|-----|
| String ignored | Add nested quotes: `"\"Walk\""` |
| Comparison fails | Use number: `4` not `">"` |
| Key code fails | Use number: `87` not `"87"` |

## Variable Errors

| Error | Fix |
|-------|-----|
| Variable not created | Add `"comment": ""` field |

## Quick Validation

```bash
python scripts/validate_output.py '{"is-c3-clipboard-data":true,...}'
```
