# Behavior Name Mapping

**CRITICAL**: In event JSON, use Display Name (behaviorType), NOT behaviorId.

| behaviorId | behaviorType (use this) |
|------------|------------------------|
| EightDir | 8Direction |
| Platform | Platform |
| Bullet | Bullet |
| Tween | Tween |
| Timer | Timer |
| solid | Solid |
| Sin | Sine |
| Physics | Physics |
| LOS | Line of sight |
| DragnDrop | Drag & Drop |
| destroy | DestroyOutsideLayout |
| Anchor | Anchor |
| Fade | Fade |
| Flash | Flash |
| MoveTo | MoveTo |
| Orbit | Orbit |
| Pathfinding | Pathfinding |
| Pin | Pin |
| TileMovement | TileMovement |
| Turret | Turret |

## Example

```json
// Wrong - used behaviorId
{"behaviorType": "EightDir"}

// Correct - use display name
{"behaviorType": "8Direction"}
```
