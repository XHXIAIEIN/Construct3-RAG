# Reading the game's state in a preview

`assets/runtime-probe.js` lets a script of the agent's read what a running
preview holds: positions, instance variables, global variables, animations
and behavior state. Use it to check that an event did what it was written
for, after sending input as [editor-and-preview.md](editor-and-preview.md)
describes, instead of writing probe actions into the event sheet. For the
state at the end of a preview without input,
`scripts/open_in_editor.py --preview 10 --state Player Enemy` prints the same
snapshot and needs no script, and `scripts/preview_project.py` plays a plan
of taps, drags and keys with the same reads between the steps.

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
   *  python scripts/lookup_script_api.py IRuntime */
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

| To read | Write | `scripts/lookup_script_api.py` prints it for |
|---------|-------|----------------------------------------------|
| A global variable | `runtime.globalVars.Score` | `IRuntime.globalVars` |
| The instances of a type | `runtime.objects.Enemy.getAllInstances()` | `IObjectClass.getAllInstances` |
| An instance by UID | `runtime.getInstanceByUid(12)` | `IRuntime.getInstanceByUid` |
| Position, size, layer | `inst.x`, `inst.width`, `inst.layer.name` | `IWorldInstance` |
| An instance variable | `inst.instVars.health` | none: generated for each project; the manual's IInstance page |
| A behavior's state | `inst.behaviors.Platform.isOnFloor` | `IPlatformBehaviorInstance.isOnFloor` |
| A Sprite's animation | `inst.animationName`, `inst.animationFrame` | `ISpriteInstance` |
| Time | `runtime.tickCount`, `runtime.gameTime` | `IRuntime.gameTime` |

`inst.behaviors` is keyed by the behavior's name on the object, which the
project may have changed from the default. The interface of another plugin
or behavior is printed for its name: `python scripts/lookup_script_api.py
Platform`.

To wait for an event, evaluate the same read every few hundred milliseconds
until it changes, with a limit on the wait; the preview keeps running
between evaluations.

`runtime.globalVars` holds the global variables only. A local variable of an
event sheet, static or not, is not on it, and a read of its name returns
`undefined` with no error. Read a local through a function of the sheet that
returns it, `runtime.callFunction("getLevel")`, or copy it to a global in an
event for the test. [observed in a minimal project, r504 preview,
2026-10-05: a static local counted every tick, `runtime.globalVars` had no
key for it or for a plain local, and a global set from it each tick read
the count]

To see which audio files a preview holds decoded while debugging, read the
Audio object's state on the page: each entry of
`self.C3Audio_DOMInterface._audioBuffers` has `GetOriginalUrl()`, and its
`_audioBuffer` the `length`, `numberOfChannels` and `sampleRate` of the
decoded data. Evaluate this in the page session, not in a worker session,
because Web Audio runs on the page. These are internals of the runtime, not
the scripting API, so a release can change them. Use them to debug, not in
a project's scripts.
[r504 main.js, the Audio DOM handler sets `self["C3Audio_DOMInterface"]`;
observed in a minimal project, r504 preview, 2026-10-05: a preloaded mono
file listed with 1 channel at 48 kHz, and the list emptied at *Unload audio
(by name)*]

## Inspector values

`inspector` holds the inspector values, the values the engine gives the
debugger's Inspect tab, under the keys of the editor's language files:
`behaviors.platform.debugger.vector-x` is "Vector X" in
`Construct3-RAG/data/c3-lang/en-US.json`, under `text`, then `behaviors`,
`platform`, `debugger`, and `zh-CN.json` has the Chinese. A value can be a
list of such keys, as the Platform behavior's animation mode is. The
inspector values come from the engine's internals, not the scripting API,
so a release may change them, and `inspector` is then left out while the
rest of the snapshot stays. Prefer the scripting API for a value it has;
read `inspector` for one it lacks, or to see everything an object holds
without knowing its interface. `open_in_editor.py --state` and a `state`
step of `preview_project.py` print each inspector value under its text
from the language pack, in the language of `--locale`.
