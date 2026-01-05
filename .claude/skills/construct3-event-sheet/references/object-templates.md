# Object Type Templates

Ready-to-paste JSON for creating objects. Paste to **Project Bar → Object types**.

## Single-Global Plugins (no imageData)

**Keyboard**
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Keyboard","plugin-id":"Keyboard","singleglobal-inst":{"type":"Keyboard","properties":{},"tags":""}}],"folders":[]}
```

**Mouse**
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Mouse","plugin-id":"Mouse","singleglobal-inst":{"type":"Mouse","properties":{},"tags":""}}],"folders":[]}
```

**Touch**
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Touch","plugin-id":"Touch","singleglobal-inst":{"type":"Touch","properties":{},"tags":""}}],"folders":[]}
```

**Audio**
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Audio","plugin-id":"Audio","singleglobal-inst":{"type":"Audio","properties":{"timescale-audio":false,"playback-rate-clamp-lo":0.5,"playback-rate-clamp-hi":4,"panning-model":"HRTF","distance-model":"inverse","ref-distance":600,"max-distance":10000,"rolloff-factor":1,"speed-of-sound":5000},"tags":""}}],"folders":[]}
```

---

## Non-World Objects (no imageData)

**Array**
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Array","plugin-id":"Arr","isGlobal":true,"nonworld-inst":{"type":"Array","properties":{"width":10,"height":1,"depth":1},"tags":""}}],"folders":[]}
```

**Dictionary**
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Dictionary","plugin-id":"Dictionary","isGlobal":true,"nonworld-inst":{"type":"Dictionary","properties":{},"tags":""}}],"folders":[]}
```

**Text**
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Text","plugin-id":"Text","isGlobal":false,"instanceVariables":[],"behaviorTypes":[],"effectTypes":[]}],"folders":[]}
```

---

## Sprite Objects (with imageData)

### Player (Blue character with face, 32x32)

**Platform behavior**
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Player","plugin-id":"Sprite","isGlobal":false,"editorNewInstanceIsReplica":true,"instanceVariables":[],"behaviorTypes":[{"behaviorId":"Platform","name":"Platform"}],"effectTypes":[],"animations":{"items":[{"frames":[{"width":32,"height":32,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":0,"useCollisionPoly":true,"duration":1,"tag":""}],"name":"Animation 1","isLooping":false,"isPingPong":false,"repeatCount":1,"repeatTo":0,"speed":5}],"subfolders":[],"name":"Animations"}}],"folders":[],"imageData":["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAjUlEQVR42u2XSw7AIAhEPVvv1ht338+iXTQCxYGCCZO4msR5GhVsrVQqgVrWbf89UBphwW4gI+FmEEg4DGERPgxBTXSJC+J8CKAnja8CoFZ2Ws/oAXC+CoJa/TvgDpF8GCB8B6zOwCcA6Toht8AMwv09KIBwAC+IsEJkXpCmK8lzd0QpesIUXXGaf4G1DmG5xdHvCASZAAAAAElFTkSuQmCC"]}
```

**8Direction behavior**
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Player","plugin-id":"Sprite","isGlobal":false,"editorNewInstanceIsReplica":true,"instanceVariables":[],"behaviorTypes":[{"behaviorId":"EightDir","name":"8Direction"}],"effectTypes":[],"animations":{"items":[{"frames":[{"width":32,"height":32,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":0,"useCollisionPoly":true,"duration":1,"tag":""}],"name":"Animation 1","isLooping":false,"isPingPong":false,"repeatCount":1,"repeatTo":0,"speed":5}],"subfolders":[],"name":"Animations"}}],"folders":[],"imageData":["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAjUlEQVR42u2XSw7AIAhEPVvv1ht338+iXTQCxYGCCZO4msR5GhVsrVQqgVrWbf89UBphwW4gI+FmEEg4DGERPgxBTXSJC+J8CKAnja8CoFZ2Ws/oAXC+CoJa/TvgDpF8GCB8B6zOwCcA6Toht8AMwv09KIBwAC+IsEJkXpCmK8lzd0QpesIUXXGaf4G1DmG5xdHvCASZAAAAAElFTkSuQmCC"]}
```

### Enemy (Red angry face, 32x32)
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Enemy","plugin-id":"Sprite","isGlobal":false,"editorNewInstanceIsReplica":true,"instanceVariables":[],"behaviorTypes":[],"effectTypes":[],"animations":{"items":[{"frames":[{"width":32,"height":32,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":0,"useCollisionPoly":true,"duration":1,"tag":""}],"name":"Animation 1","isLooping":false,"isPingPong":false,"repeatCount":1,"repeatTo":0,"speed":5}],"subfolders":[],"name":"Animations"}}],"folders":[],"imageData":["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAgklEQVR42mNgGAVDHbxyNv1PV8uIxQNqOVUdQY7FVHMINSwn2xHUtJwsRwyoA7BpxgWIlSfaEfh8QMhwQvJEOYJQMBIynJA8xQ6geVoY2Q6gh+WDwhGjaWBoOwCohCQ2WXUCLotJxVSvkEZOdTwoWkSDok04KFrFg6ZfMCh6RsMSAAAvcvm0Xp9LcwAAAABJRU5ErkJggg=="]}
```

### Ground (Brick pattern, 32x32)
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Ground","plugin-id":"Sprite","isGlobal":false,"editorNewInstanceIsReplica":true,"instanceVariables":[],"behaviorTypes":[{"behaviorId":"solid","name":"Solid"}],"effectTypes":[],"animations":{"items":[{"frames":[{"width":32,"height":32,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":0,"useCollisionPoly":true,"duration":1,"tag":""}],"name":"Animation 1","isLooping":false,"isPingPong":false,"repeatCount":1,"repeatTo":0,"speed":5}],"subfolders":[],"name":"Animations"}}],"folders":[],"imageData":["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAARklEQVR42mMIMBL5P5CYAUR0R2mTjSnVP+qAUQeMOoBhwMsBWvuQkP5RB4w6YNQBDKPtgVEHjDpg1AGj7YFRB4w6YMQ7AACYFeS6KUxcgQAAAABJRU5ErkJggg=="]}
```

### Bullet (Yellow arrow, 16x16)
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Bullet","plugin-id":"Sprite","isGlobal":false,"editorNewInstanceIsReplica":true,"instanceVariables":[],"behaviorTypes":[{"behaviorId":"Bullet","name":"Bullet"},{"behaviorId":"destroy","name":"DestroyOutsideLayout"}],"effectTypes":[],"animations":{"items":[{"frames":[{"width":16,"height":16,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":0,"useCollisionPoly":true,"duration":1,"tag":""}],"name":"Animation 1","isLooping":false,"isPingPong":false,"repeatCount":1,"repeatTo":0,"speed":5}],"subfolders":[],"name":"Animations"}}],"folders":[],"imageData":["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAMElEQVR42mNgGAVw8P8g+39CmGID/s9g+E+xATgNIcUArIaQagCGIXR1AW1iYQQDAIFS8RHMpZr1AAAAAElFTkSuQmCC"]}
```

### Coin (4-frame spin animation, Gold, 24x24)
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Coin","plugin-id":"Sprite","isGlobal":false,"editorNewInstanceIsReplica":true,"instanceVariables":[],"behaviorTypes":[],"effectTypes":[],"animations":{"items":[{"frames":[{"width":24,"height":24,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":0,"useCollisionPoly":true,"duration":1,"tag":""},{"width":24,"height":24,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":1,"useCollisionPoly":true,"duration":1,"tag":""},{"width":24,"height":24,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":2,"useCollisionPoly":true,"duration":1,"tag":""},{"width":24,"height":24,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":3,"useCollisionPoly":true,"duration":1,"tag":""}],"name":"Animation 1","isLooping":true,"isPingPong":false,"repeatCount":1,"repeatTo":0,"speed":8}],"subfolders":[],"name":"Animations"}}],"folders":[],"imageData":["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAAoklEQVR42uWVLQ+EMBBE518jTyKRSCQSiUSCQyJPIpHIIZOVhAClbDiupl+776VN2gX+rnEAo8GGCvzW4NiAUwvOPSiBes21rn3FnQK3BdiXlnhUoHjl7cKb3AJDBcrfhNeZBVwViLOCV6ltxBKId0pAduGC8mMLWwLBQ04g7iFB6BX5CIrEBr97gncIHvHQLgtu/4tcflOXeuBS0dxqcoy2AHr1quJg/4LzAAAAAElFTkSuQmCC","data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAAiklEQVR42mNgGHHg/3WG/1Q39Pl+hv/vjzP8/36e4T/IAhAN4oPEKTb8/naIQbgsAMmTbfj19RADCFkAUkey4eeXQzQSawFI/eCx4Ph8iAZkC/7/P0HQApA+siwAGU6MD8i2gNggGhwW7J8OUUiuBSD9wzyIhocFQ7+ooEtpSpf6gC41Gl3qZEoAAJg1hWh46hhwAAAAAElFTkSuQmCC","data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAAU0lEQVR42mNgGHHg/3WG/zQz/Pt5hv8gC0A01Q1/fxxiMMwCEH/oWPB8P8RAdAtA4qMWjFpAGNzfDjEIlwUg+dE4GLVgEFgw9ItrutRodKmTyQEA06VKvTGBRyUAAAAASUVORK5CYII=","data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAAiklEQVR42mNgGHHg/3WG/1Q39Pl+hv/vjzP8/36e4T/IAhAN4oPEKTb8/naIQbgsAMmTbfj19RADCFkAUkey4eeXQzQSawFI/eCx4Ph8iAZkC/7/P0HQApA+siwAGU6MD8i2gNggGhwW7J8OUUiuBSD9wzyIhocFQ7+ooEtpSpf6gC41Gl3qZEoAAJg1hWh46hhwAAAAAElFTkSuQmCC"]}
```

### Spike (Gray triangle, 32x32)
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Spike","plugin-id":"Sprite","isGlobal":false,"editorNewInstanceIsReplica":true,"instanceVariables":[],"behaviorTypes":[],"effectTypes":[],"animations":{"items":[{"frames":[{"width":32,"height":32,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":0,"useCollisionPoly":true,"duration":1,"tag":""}],"name":"Animation 1","isLooping":false,"isPingPong":false,"repeatCount":1,"repeatTo":0,"speed":5}],"subfolders":[],"name":"Animations"}}],"folders":[],"imageData":["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAzklEQVR42u3OrRZFQBiF4X3pgiAIgiAIgiAIgiAI7myftU8SLMvPzOziLRZmvu9BlmXM85xFUbAsS1ZVxbqu2TQN27Zl13Xs+57DMHAcR07TxHmeuSwL13Xltm3/p971Xf91Tud1T/c1R/M0V/O1R/u0F+oDKAcA++wAlRKAo+wAlQKAs+wAFROAK9kBKgYAd7IDVEgAnmQHqBAAvMkOUG8ACJEdoJ4AEDI7QN0BIEZ2gLoCQMzsAHUGQIrsAHUEQMrsALUHwJEdoAR4c/8H2NVXfBM856wAAAAASUVORK5CYII="]}
```

### Platform (Green, 64x16)
```json
{"is-c3-clipboard-data":true,"type":"object-types","families":[],"items":[{"name":"Platform","plugin-id":"Sprite","isGlobal":false,"editorNewInstanceIsReplica":true,"instanceVariables":[],"behaviorTypes":[{"behaviorId":"solid","name":"Solid"},{"behaviorId":"jumpthru","name":"Jump-thru"}],"effectTypes":[],"animations":{"items":[{"frames":[{"width":64,"height":16,"originX":0.5,"originY":0.5,"originalSource":"","exportFormat":"lossless","exportQuality":0.8,"fileType":"image/png","imageDataIndex":0,"useCollisionPoly":true,"duration":1,"tag":""}],"name":"Animation 1","isLooping":false,"isPingPong":false,"repeatCount":1,"repeatTo":0,"speed":5}],"subfolders":[],"name":"Animations"}}],"folders":[],"imageData":["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAAAQCAYAAACm53kpAAAAL0lEQVR42u3QMQEAAAgDIAN62NSIGmQcFKB655KVAAECBAgQIECAAAECBAgQkOcBKyYoiNpLxzIAAAAASUVORK5CYII="]}
```

---

## Image Reference

| Object | Size | Description |
|--------|------|-------------|
| Player | 32x32 | Blue circle with eyes |
| Enemy | 32x32 | Red circle with angry face |
| Ground | 32x32 | Brown brick pattern |
| Bullet | 16x16 | Yellow arrow |
| Coin | 24x24 | Gold spinning (4 frames) |
| Spike | 32x32 | Gray triangle |
| Platform | 64x16 | Green bar |
