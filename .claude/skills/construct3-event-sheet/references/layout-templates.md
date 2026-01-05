# Layout Templates

Complete layout clipboard templates. Paste to **Project Bar → Layouts**.

---

## Structure Overview

```json
{
  "is-c3-clipboard-data": true,
  "type": "layouts",
  "families": [],
  "object-types": [...],    // Object definitions with imageData indices
  "items": [{
    "name": "Layout 1",
    "layers": [...],
    "width": 1280,
    "height": 720,
    "eventSheet": "Event sheet 1"
  }],
  "imageData": [...]        // Base64 PNG images
}
```

---

## Platform Game Layout

Player with Platform behavior, Ground with Solid, Enemy, ScoreText.

```json
{"is-c3-clipboard-data":true,"type":"layouts","families":[],"object-types":[{"name":"Player","plugin-id":"Sprite","isGlobal":false,"instanceVariables":[],"behaviorTypes":[{"behaviorId":"Platform","name":"Platform"}],"effectTypes":[],"animations":{"items":[{"frames":[{"width":32,"height":32,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":0,"useCollisionPoly":true,"duration":1,"tag":""}],"name":"Default","isLooping":false,"isPingPong":false,"repeatCount":1,"repeatTo":0,"speed":5}],"subfolders":[],"name":"Animations"}},{"name":"Ground","plugin-id":"TiledBg","isGlobal":false,"instanceVariables":[],"behaviorTypes":[{"behaviorId":"solid","name":"Solid"}],"effectTypes":[],"image":{"width":32,"height":32,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":1,"useCollisionPoly":true,"tag":""}},{"name":"Enemy","plugin-id":"Sprite","isGlobal":false,"instanceVariables":[],"behaviorTypes":[],"effectTypes":[],"animations":{"items":[{"frames":[{"width":32,"height":32,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":2,"useCollisionPoly":true,"duration":1,"tag":""}],"name":"Default","isLooping":false,"isPingPong":false,"repeatCount":1,"repeatTo":0,"speed":5}],"subfolders":[],"name":"Animations"}},{"name":"ScoreText","plugin-id":"Text","isGlobal":false,"instanceVariables":[],"behaviorTypes":[],"effectTypes":[]}],"items":[{"name":"Layout 1","layers":[{"name":"Game","instances":[{"type":"Ground","properties":{"initially-visible":true,"origin":"top-left","wrap-horizontal":"repeat","wrap-vertical":"repeat","image-offset-x":0,"image-offset-y":0,"image-scale-x":1,"image-scale-y":1,"image-angle":0,"enable-tile-randomization":false},"tags":"","instanceVariables":{},"behaviors":{"Solid":{"properties":{"enabled":true}}},"showing":true,"locked":false,"world":{"x":0,"y":688,"width":1280,"height":32,"originX":0,"originY":0,"color":[1,1,1,1],"angle":0,"zElevation":0}},{"type":"Player","properties":{"initially-visible":true,"initial-animation":"Default","initial-frame":0,"enable-collisions":true,"live-preview":false},"tags":"","instanceVariables":{},"behaviors":{"Platform":{"properties":{"max-speed":330,"acceleration":1500,"deceleration":1500,"jump-strength":650,"gravity":1500,"max-fall-speed":1000,"double-jump":false,"jump-sustain":0,"default-controls":false,"enabled":true}}},"showing":true,"locked":false,"world":{"x":100,"y":640,"width":32,"height":32,"originX":0.5,"originY":0.5,"color":[1,1,1,1],"angle":0,"zElevation":0}},{"type":"Enemy","properties":{"initially-visible":true,"initial-animation":"Default","initial-frame":0,"enable-collisions":true,"live-preview":false},"tags":"","instanceVariables":{},"behaviors":{},"showing":true,"locked":false,"world":{"x":400,"y":640,"width":32,"height":32,"originX":0.5,"originY":0.5,"color":[1,1,1,1],"angle":0,"zElevation":0}},{"type":"Enemy","properties":{"initially-visible":true,"initial-animation":"Default","initial-frame":0,"enable-collisions":true,"live-preview":false},"tags":"","instanceVariables":{},"behaviors":{},"showing":true,"locked":false,"world":{"x":600,"y":640,"width":32,"height":32,"originX":0.5,"originY":0.5,"color":[1,1,1,1],"angle":0,"zElevation":0}},{"type":"Enemy","properties":{"initially-visible":true,"initial-animation":"Default","initial-frame":0,"enable-collisions":true,"live-preview":false},"tags":"","instanceVariables":{},"behaviors":{},"showing":true,"locked":false,"world":{"x":900,"y":640,"width":32,"height":32,"originX":0.5,"originY":0.5,"color":[1,1,1,1],"angle":0,"zElevation":0}}],"effectTypes":[],"isInitiallyVisible":true,"isInitiallyInteractive":true,"isHTMLElementsLayer":false,"color":[1,1,1,1],"backgroundColor":[1,1,1,1],"isTransparent":false,"parallaxX":1,"parallaxY":1,"blendMode":"normal","zElevation":0},{"name":"UI","instances":[{"type":"ScoreText","properties":{"text":"Score: 0","enable-bbcode":false,"font":"Arial","size":24,"line-height":0,"bold":false,"italic":false,"color":[0,0,0,1],"horizontal-alignment":"left","vertical-alignment":"top","wrapping":"word","initially-visible":true,"origin":"top-left"},"tags":"","instanceVariables":{},"behaviors":{},"showing":true,"locked":false,"world":{"x":20,"y":20,"width":200,"height":40,"originX":0,"originY":0,"color":[1,1,1,1],"angle":0,"zElevation":0}}],"effectTypes":[],"isInitiallyVisible":true,"isInitiallyInteractive":true,"isHTMLElementsLayer":false,"color":[1,1,1,1],"backgroundColor":[1,1,1,1],"isTransparent":true,"parallaxX":0,"parallaxY":0,"blendMode":"normal","zElevation":0}],"width":1280,"height":720,"eventSheet":"Event sheet 1"}],"folders":[],"imageData":["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAbklEQVR4Ae2WsQ3AIAwEfRkig2QTNskgLJJNvAkFDUVEgUTyV1h+68flB9tKhRAREZF/IYDTuhxYxtc63AFcuL0B9wX3fngHZG/AQfnOZAemN+Cg3Bs8hszOAH7rMtVf0gPVG3BQXlP/ExERkX91ArMiSx2LhgJeAAAAAElFTkSuQmCC","data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAXUlEQVR4Ae2VsQ0AIAgFWcP9N3QTFmET1nACCwsbY6FBvgS4hOMV/wIAAACAb0lz4F3SHHiX3AfuJfeBe0lzYC9pDuwlzYG9pDmwl3QH7iXdgXtJd+BeAgAA8K0LqpYmIdMsvV0AAAAASUVORK5CYII=","data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAASklEQVR4Ae3UsQ0AIAhFUdbA/Td0ExZhE9ZwAgtLC2NhRL7NP0nTVw4AAAAAAN+q9pLvVe0lP8p8K9pLvle1l/wo862gvQQAAOC3LuWbJCGHPJefAAAAAElFTkSuQmCC"]}
```

---

## Top-Down Shooter Layout

Player with 8Direction, Bullet with Bullet behavior, Enemy, TiledBackground.

```json
{"is-c3-clipboard-data":true,"type":"layouts","families":[],"object-types":[{"name":"Player","plugin-id":"Sprite","isGlobal":false,"instanceVariables":[],"behaviorTypes":[{"behaviorId":"EightDir","name":"8Direction"},{"behaviorId":"bound","name":"BoundToLayout"}],"effectTypes":[],"animations":{"items":[{"frames":[{"width":32,"height":32,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":0,"useCollisionPoly":true,"imagePoints":[{"name":"ShootPoint","x":1,"y":0.5}],"duration":1,"tag":""}],"name":"Default","isLooping":false,"isPingPong":false,"repeatCount":1,"repeatTo":0,"speed":5}],"subfolders":[],"name":"Animations"}},{"name":"Bullet","plugin-id":"Sprite","isGlobal":false,"instanceVariables":[],"behaviorTypes":[{"behaviorId":"Bullet","name":"Bullet"},{"behaviorId":"destroy","name":"DestroyOutsideLayout"}],"effectTypes":[],"animations":{"items":[{"frames":[{"width":16,"height":8,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":1,"useCollisionPoly":true,"duration":1,"tag":""}],"name":"Default","isLooping":false,"isPingPong":false,"repeatCount":1,"repeatTo":0,"speed":5}],"subfolders":[],"name":"Animations"}},{"name":"Enemy","plugin-id":"Sprite","isGlobal":false,"instanceVariables":[{"name":"Health","type":"number","desc":"","show":true}],"behaviorTypes":[],"effectTypes":[],"animations":{"items":[{"frames":[{"width":32,"height":32,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":2,"useCollisionPoly":true,"duration":1,"tag":""}],"name":"Default","isLooping":false,"isPingPong":false,"repeatCount":1,"repeatTo":0,"speed":5}],"subfolders":[],"name":"Animations"}},{"name":"Background","plugin-id":"TiledBg","isGlobal":false,"instanceVariables":[],"behaviorTypes":[],"effectTypes":[],"image":{"width":32,"height":32,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":3,"useCollisionPoly":true,"tag":""}}],"items":[{"name":"Layout 1","layers":[{"name":"Background","instances":[{"type":"Background","properties":{"initially-visible":true,"origin":"top-left","wrap-horizontal":"repeat","wrap-vertical":"repeat","image-offset-x":0,"image-offset-y":0,"image-scale-x":1,"image-scale-y":1,"image-angle":0,"enable-tile-randomization":false},"tags":"","instanceVariables":{},"behaviors":{},"showing":true,"locked":false,"world":{"x":0,"y":0,"width":1280,"height":720,"originX":0,"originY":0,"color":[1,1,1,1],"angle":0,"zElevation":0}}],"effectTypes":[],"isInitiallyVisible":true,"isInitiallyInteractive":true,"isHTMLElementsLayer":false,"color":[1,1,1,1],"backgroundColor":[1,1,1,1],"isTransparent":false,"parallaxX":1,"parallaxY":1,"blendMode":"normal","zElevation":0},{"name":"Game","instances":[{"type":"Player","properties":{"initially-visible":true,"initial-animation":"Default","initial-frame":0,"enable-collisions":true,"live-preview":false},"tags":"","instanceVariables":{},"behaviors":{"8Direction":{"properties":{"max-speed":200,"acceleration":600,"deceleration":500,"directions":"dir-8","set-angle":"no","allow-sliding":false,"default-controls":true,"enabled":true}},"BoundToLayout":{"properties":{"bound-by":"edge"}}},"showing":true,"locked":false,"world":{"x":640,"y":360,"width":32,"height":32,"originX":0.5,"originY":0.5,"color":[1,1,1,1],"angle":0,"zElevation":0}},{"type":"Enemy","properties":{"initially-visible":true,"initial-animation":"Default","initial-frame":0,"enable-collisions":true,"live-preview":false},"tags":"","instanceVariables":{"Health":100},"behaviors":{},"showing":true,"locked":false,"world":{"x":200,"y":150,"width":32,"height":32,"originX":0.5,"originY":0.5,"color":[1,1,1,1],"angle":0,"zElevation":0}},{"type":"Enemy","properties":{"initially-visible":true,"initial-animation":"Default","initial-frame":0,"enable-collisions":true,"live-preview":false},"tags":"","instanceVariables":{"Health":100},"behaviors":{},"showing":true,"locked":false,"world":{"x":1000,"y":200,"width":32,"height":32,"originX":0.5,"originY":0.5,"color":[1,1,1,1],"angle":0,"zElevation":0}},{"type":"Enemy","properties":{"initially-visible":true,"initial-animation":"Default","initial-frame":0,"enable-collisions":true,"live-preview":false},"tags":"","instanceVariables":{"Health":100},"behaviors":{},"showing":true,"locked":false,"world":{"x":300,"y":550,"width":32,"height":32,"originX":0.5,"originY":0.5,"color":[1,1,1,1],"angle":0,"zElevation":0}},{"type":"Enemy","properties":{"initially-visible":true,"initial-animation":"Default","initial-frame":0,"enable-collisions":true,"live-preview":false},"tags":"","instanceVariables":{"Health":100},"behaviors":{},"showing":true,"locked":false,"world":{"x":900,"y":500,"width":32,"height":32,"originX":0.5,"originY":0.5,"color":[1,1,1,1],"angle":0,"zElevation":0}}],"effectTypes":[],"isInitiallyVisible":true,"isInitiallyInteractive":true,"isHTMLElementsLayer":false,"color":[1,1,1,1],"backgroundColor":[1,1,1,1],"isTransparent":true,"parallaxX":1,"parallaxY":1,"blendMode":"normal","zElevation":0}],"width":1280,"height":720,"eventSheet":"Event sheet 1"}],"folders":[],"imageData":["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAbklEQVR4Ae2WsQ3AIAwEfRkig2QTNskgLJJNvAkFDUVEgUTyV1h+68flB9tKhRAREZF/IYDTuhxYxtc63AFcuL0B9wX3fngHZG/AQfnOZAemN+Cg3Bs8hszOAH7rMtVf0gPVG3BQXlP/ExERkX91ArMiSx2LhgJeAAAAAElFTkSuQmCC","data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAICAYAAADwdn+XAAAAK0lEQVR4AWMY/OA/w38QJgYzUNUAkCLCYNQAqrrgarEBXM5BtwFdDYNnMAIAq5AoCejLG5QAAAAASUVORK5CYII=","data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAASklEQVR4Ae3UsQ0AIAhFUdbA/Td0ExZhE9ZwAgtLC2NhRL7NP0nTVw4AAAAAAN+q9pLvVe0lP8p8K9pLvle1l/wo862gvQQAAOC3LuWbJCGHPJefAAAAAElFTkSuQmCC","data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAPUlEQVR4Ae3VsQ0AMAjAQP7/aVZgBRZhkSwSuu4dAAAAAPCt9hLe1V7Co8y32kt4V3sJjzLfCu0lAADAty4FLCQhMxv1vQAAAABJRU5ErkJggg=="]}
```

---

## Event Sheet Template

Complete event sheet. Paste to **Project Bar → Event sheets**.

```json
{
  "is-c3-clipboard-data": true,
  "type": "event-sheets",
  "items": [{
    "name": "Event sheet 1",
    "events": [...]
  }],
  "folders": []
}
```

### Platform Game Events
```json
{"is-c3-clipboard-data":true,"type":"event-sheets","items":[{"name":"Event sheet 1","events":[{"eventType":"variable","name":"Score","type":"number","initialValue":"0","comment":""},{"eventType":"comment","text":"Player Movement"},{"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":37}}],"actions":[{"id":"simulate-control","objectClass":"Player","behaviorType":"Platform","parameters":{"control":"left"}}]},{"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":39}}],"actions":[{"id":"simulate-control","objectClass":"Player","behaviorType":"Platform","parameters":{"control":"right"}}]},{"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":32}}],"actions":[{"id":"simulate-control","objectClass":"Player","behaviorType":"Platform","parameters":{"control":"jump"}}]},{"eventType":"comment","text":"Collision"},{"eventType":"block","conditions":[{"id":"on-collision-with-another-object","objectClass":"Player","parameters":{"object":"Enemy"}}],"actions":[{"id":"destroy","objectClass":"Enemy"},{"id":"add-to-eventvar","objectClass":"System","parameters":{"variable":"Score","value":"10"}},{"id":"set-text","objectClass":"ScoreText","parameters":{"text":"\"Score: \" & Score"}}]}]}],"folders":[]}
```

### Top-Down Shooter Events
```json
{"is-c3-clipboard-data":true,"type":"event-sheets","items":[{"name":"Event sheet 1","events":[{"eventType":"comment","text":"Player looks at mouse"},{"eventType":"block","conditions":[{"id":"every-tick","objectClass":"System"}],"actions":[{"id":"set-angle-toward-position","objectClass":"Player","parameters":{"x":"Mouse.X","y":"Mouse.Y"}}]},{"eventType":"comment","text":"Shoot on click"},{"eventType":"block","conditions":[{"id":"on-click","objectClass":"Mouse","parameters":{"mouse-button":"left","click-type":"clicked"}}],"actions":[{"id":"spawn-another-object","objectClass":"Player","parameters":{"object":"Bullet","layer":"\"Game\"","image-point":"\"ShootPoint\""}}]},{"eventType":"comment","text":"Bullet hits enemy"},{"eventType":"block","conditions":[{"id":"on-collision-with-another-object","objectClass":"Bullet","parameters":{"object":"Enemy"}}],"actions":[{"id":"subtract-from-instvar","objectClass":"Enemy","parameters":{"instance-variable":"Health","value":"10"}},{"id":"destroy","objectClass":"Bullet"}]},{"eventType":"block","conditions":[{"id":"compare-instance-variable","objectClass":"Enemy","parameters":{"instance-variable":"Health","comparison":3,"value":"0"}}],"actions":[{"id":"destroy","objectClass":"Enemy"}]},{"eventType":"comment","text":"WASD Movement"},{"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":87}}],"actions":[{"id":"simulate-control","objectClass":"Player","behaviorType":"8Direction","parameters":{"control":"up"}}]},{"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":65}}],"actions":[{"id":"simulate-control","objectClass":"Player","behaviorType":"8Direction","parameters":{"control":"left"}}]},{"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":83}}],"actions":[{"id":"simulate-control","objectClass":"Player","behaviorType":"8Direction","parameters":{"control":"down"}}]},{"eventType":"block","conditions":[{"id":"key-is-down","objectClass":"Keyboard","parameters":{"key":68}}],"actions":[{"id":"simulate-control","objectClass":"Player","behaviorType":"8Direction","parameters":{"control":"right"}}]}]}],"folders":[]}
```

---

## Image Data Reference

| Index | Object | Color | Description |
|-------|--------|-------|-------------|
| 0 | Player | Blue | 32x32 player sprite |
| 1 | Ground/Bullet | Brown/Yellow | Platform or projectile |
| 2 | Enemy | Red | 32x32 enemy sprite |
| 3 | Background | Gray | Tiled background |

### Generate Custom Images

For custom colored sprites, create 32x32 PNG with solid color or pattern.
