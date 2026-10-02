# Reading the game's state in a preview

`assets/runtime-probe.js` lets a script of the agent's read what a running
preview holds: positions, instance variables, global variables, animations
and behavior state. Use it to check that an event did what it was written
for, after sending input as [editor-and-preview.md](editor-and-preview.md)
describes, instead of writing probe actions into the event sheet. For the
state at the end of a preview without input,
`scripts/open_in_editor.py --preview 10 --state Player Enemy` prints the same
snapshot and needs no script.

## Attach

1. Start the preview with F5, as `scripts/open_in_editor.py` does. With
   Shift+F5, the debug preview, the game runs in an iframe of the debugger
   page and the debugger slows it; its Inspect tab shows nothing the probe
   does not return.
2. Connect to the preview window, call `Target.setAutoAttach` with
   `flatten: true`, and evaluate the text of `assets/runtime-probe.js` with
   `Runtime.evaluate` and `awaitPromise: true` in the page and in each
   worker session. It resolves `true` where the game runs, `null`
   elsewhere, and `false` when the runtime did not tick for 3 seconds. The
   game runs in the page or in a worker, depending on the project's
   `useWorker` and the browser, so try every session.
3. Evaluate later reads in the session that answered `true`, for as long as
   the preview runs. Evaluating the file there again returns `true` at
   once. A restarted preview needs the file again.

## Declarations

```ts
declare const c3probe: {
  /** The scripting API, the `runtime` of a project's scripts:
   *  Construct3-RAG/data/c3-ts-defs/preview/interfaces/IRuntime.d.ts */
  runtime: IRuntime;
  /** `names`: object types as the project spells them; every type with
   *  instances when left out. At most `max` instances per type (default 20). */
  snapshot(names?: string[], max?: number): Snapshot;
};

interface Snapshot {
  layout: string;
  tickCount: number;
  gameTime: number;
  wallTime: number;
  framesPerSecond: number;
  globalVars: Record<string, number | string | boolean>;
  /** null for a name the project has no object type of. */
  objects: Record<string, { count: number; instances: InstanceState[] } | null>;
}

interface InstanceState {
  uid: number;
  /** World instances only. */
  x?: number; y?: number; width?: number; height?: number; angle?: number;
  layer?: string; zIndex?: number; isVisible?: boolean; opacity?: number;
  /** Where the plugin has them: Sprite, Text. */
  animationName?: string; animationFrame?: number; text?: string;
  instVars?: Record<string, number | string | boolean>;
  /** What the debugger's Inspect tab shows for the plugin and for each
   *  behavior by its name on the object; see "Inspector values". */
  inspector?: {
    plugin: { title: string; values: Record<string, unknown> }[];
    behaviors: Record<string, Record<string, unknown>>;
  };
}
```

`count` is the number of instances, also when `instances` stops at `max`. A
snapshot without names covers every type, so name the types you need when a
game has many instances.

## Reading one value

`c3probe.runtime` is the same object a project's script gets, so any
expression of the scripting API works:

| To read | Write | Declared in `Construct3-RAG/data/c3-ts-defs/` |
|---------|-------|-------------------------------------------|
| A global variable | `runtime.globalVars.Score` | `preview/interfaces/IRuntime.d.ts` |
| The instances of a type | `runtime.objects.Enemy.getAllInstances()` | `preview/interfaces/objects/IObjectClass.d.ts` |
| An instance by UID | `runtime.getInstanceByUid(12)` | `preview/interfaces/IRuntime.d.ts` |
| Position, size, layer | `inst.x`, `inst.width`, `inst.layer.name` | `preview/interfaces/objects/IWorldInstance.d.ts` |
| An instance variable | `inst.instVars.health` | none: generated for each project; the manual's IInstance page |
| A behavior's state | `inst.behaviors.Platform.isOnFloor` | `behaviors/movements/platform/c3runtime/IPlatformBehaviorInstance.d.ts` |
| A Sprite's animation | `inst.animationName`, `inst.animationFrame` | `plugins/general/sprite/c3runtime/ISpriteInstance.d.ts` |
| Time | `runtime.tickCount`, `runtime.gameTime` | `preview/interfaces/IRuntime.d.ts` |

`inst.behaviors` is keyed by the behavior's name on the object, which the
project may have changed from the default. The interface of another plugin
or behavior is found by its name in `data/c3-ts-defs/autocomplete-data.json`,
then in the `.d.ts` under the directory of the same name.

To wait for an event, evaluate the same read every few hundred milliseconds
until it changes, with a limit on the wait; the preview keeps running
between evaluations.

## Inspector values

`inspector` holds the values the engine gives the debugger, under the keys
of the editor's language files: `behaviors.platform.debugger.vector-x` is
"Vector X" in `Construct3-RAG/data/c3-lang/en-US.json`, under `text`, then
`behaviors`, `platform`, `debugger`, and `zh-CN.json` has the Chinese. A
value can be a list of such keys, as the Platform behavior's animation
mode is. These come from the engine's internals, not the scripting API,
so a release may change them, and `inspector` is then left out while the
rest of the snapshot stays. Prefer the scripting API for a value it has;
read `inspector` for one it lacks, or to see everything an object holds
without knowing its interface.
