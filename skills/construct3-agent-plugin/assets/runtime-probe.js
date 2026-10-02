// Reads a running preview's state from outside it. Evaluate this whole file with
// the DevTools protocol (Runtime.evaluate, awaitPromise) in the preview page and
// in each of its workers: it resolves true in the one that runs the game, null in
// the others. There it leaves `globalThis.c3probe`; later evaluations in the same
// place call `c3probe.snapshot()` or read `c3probe.runtime`, the scripting API.
// What it returns and how to use it: references/reading-the-runtime.md.
//
// The runtime is not exposed, but it runs C3.Runtime.prototype.Tick every frame:
// wrapped once, the next tick hands over `this`, and the method is put back.
(async () => {
  if (globalThis.c3probe) return true;
  if (typeof C3 === "undefined" || !C3.Runtime || typeof C3.Runtime.prototype.Tick !== "function") return null;
  const proto = C3.Runtime.prototype, orig = proto.Tick;
  const internal = await new Promise(resolve => {
    const timer = setTimeout(() => { proto.Tick = orig; resolve(null); }, 3000);
    proto.Tick = function (...args) {
      proto.Tick = orig;
      clearTimeout(timer);
      resolve(this);
      return orig.apply(this, args);
    };
  });
  if (!internal) return false;
  const runtime = internal.GetIRuntime();

  // The values the debugger's Inspect tab shows for a plugin or a behavior. They come
  // from the engine's own methods, not the scripting API, so a release may rename
  // them: the snapshot then leaves `inspector` out and keeps the rest.
  const sections = sdk => {
    const read = sdk && (sdk._getDebuggerProperties || sdk.GetDebuggerProperties);
    if (!read) return [];
    return (read.call(sdk) || []).map(s => ({
      title: s.title,
      values: Object.fromEntries((s.properties || []).map(p => [p.name, typeof p.value === "function" ? null : p.value])),
    }));
  };
  const inspector = uid => {
    try {
      const inst = internal.GetInstanceByUID(uid);
      if (!inst) return undefined;
      const behaviors = {};
      for (const b of inst.GetBehaviorInstances?.() || [])
        for (const s of sections(b.GetSdkInstance())) behaviors[s.title.replace(/^\$/, "")] = s.values;
      return {plugin: sections(inst.GetSdkInstance()), behaviors};
    } catch (e) {
      return undefined;
    }
  };

  const copy = o => (o ? Object.fromEntries(Object.keys(o).map(k => [k, o[k]])) : undefined);
  const world = i => ("x" in i ? {
    x: i.x, y: i.y, width: i.width, height: i.height, angle: i.angle,
    layer: i.layer?.name, zIndex: i.zIndex, isVisible: i.isVisible, opacity: i.opacity,
  } : {});

  function snapshot(names, max = 20) {
    const objects = {};
    for (const name of names || Object.keys(runtime.objects)) {
      const type = runtime.objects[name];
      if (!type) { objects[name] = null; continue; }
      const all = type.getAllInstances();
      if (!names && !all.length) continue;
      objects[name] = {
        count: all.length,
        instances: all.slice(0, max).map(i => ({
          uid: i.uid, ...world(i),
          animationName: i.animationName, animationFrame: i.animationFrame, text: i.text,
          instVars: copy(i.instVars), inspector: inspector(i.uid),
        })),
      };
    }
    return {
      layout: runtime.layout.name, tickCount: runtime.tickCount, gameTime: runtime.gameTime,
      wallTime: runtime.wallTime, framesPerSecond: runtime.framesPerSecond,
      globalVars: copy(runtime.globalVars), objects,
    };
  }

  globalThis.c3probe = {runtime, snapshot};
  return true;
})()
