# Event Sheet Pitfalls: Wait and time scale

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- *Wait* does not stop a loop: the remaining iterations run on in the same
  tick, and the actions after the *Wait* run later, once per iteration, with
  that iteration's picked instances. A staggered effect is `Wait 0.1 *
  loopindex`; a loop that must pause between iterations is a Timer or a
  function called from *On timer*. [manual:
  system-reference/system-actions.md "Wait"; examples: arcade-shooter,
  layout-transition]
- *Wait for previous actions* (the manual's "Wait for previous actions to
  complete") waits only for asynchronous actions, marked with an icon in the
  editor: Tween actions, AJAX requests, Local Storage, *Snapshot canvas*.
  Anything else before it is already done.
  A function call counts only when the function is marked *Asynchronous* and
  itself ends with *Wait for previous actions*. [manual:
  system-reference/system-actions.md "Wait for previous actions to complete",
  project-primitives/events/functions.md "Asynchronous functions"; example:
  avalanche, sheets Stalagmite and Credits]
- A *Wait* holds back only the actions after it in its own block and that
  block's sub-events. A sibling event, or the next sub-event of the same
  parent, runs at once: a *Wait for previous actions* alone in sub-event 1,
  with *Destroy* in sub-event 2, destroys before the tween ends. Put the
  async action, the wait and what follows in one action list. [manual:
  system-reference/system-actions.md "Wait", "Wait for previous actions to
  complete": "before continuing on to the next action or sub-events. Other
  events continue to run in the meantime."]
- A *Wait* with *Use time scale* on never ends while the time scale is 0.
  The wait that resumes the game, and the UI tweens shown while paused, run
  on their own clock: *Use time scale* off, *Set object time scale* 1 on the
  fader, the buttons and the manager object. [manual:
  system-reference/system-actions.md "Wait", "Set object time scale";
  example: airborne-explorer, In-Game Menu]
- *Wait 0* resumes at the start of the next tick, not at the end of the
  event or the sheet: before behaviors and every event of that tick, after
  the current tick has run all its events and been drawn. The rest of the
  event, in an included sheet or a function alike, runs one frame late, with
  the picks saved at the *Wait* minus destroyed instances, and with function
  parameters and function locals restored. It runs at time scale 0 too, and
  a layout change drops it. *Wait for previous actions* with nothing to wait
  for resumes at the same point. Leave *Wait 0* out: a created instance is
  pickable from the next top-level event and a destroyed one gone by then
  (see [Creating objects](creating-objects.md)); initialise in *On created* or the creating event,
  pass `UID`, put the dependent step in a later top-level event or trigger.
  Ashley's tutorial still says "until the end of the event sheet", which is
  Construct 2 wording. [runtime: exported c3runtime.js r503, `Wait` calls
  `AddScheduledWait`, `RunScheduledWaits` is called only from
  `Step_BeforePreTick`, ahead of `Step_RunEventsEtc` and `Render`;
  `ScheduledWait._Init` saves SOL, parameters and locals;
  `ClearAllScheduledWaits` on layout end; read from source, not observed.
  Ashley: "rarely any need to use Wait 0 seconds", forum
  construct-2/general-discussion-17/wait-59374; *Wait for previous actions*
  "always runs at the end of the tick", Scirra/Construct-bugs#3948;
  construct.net tutorial system-wait-action-63, updated 2019]
- Deactivating a group stops its events, including its triggers, and
  nothing else: behaviors, timers and tweens started by it keep running. It
  turns a phase off; it does not pause. [manual:
  system-reference/system-actions.md "Set group active"; examples: every
  pause is *Set time scale* 0]
- A hit stop is *Set time scale* 0.1, *Wait*, *Set time scale* 1 in one
  block; a smooth ramp is a *Tween (value)* on any object read into *Set
  time scale* while *Is playing*. [examples: segmented-boss-fight BossHeath;
  samuroof Credits `Camera.Tween.Value("TimeScaleChange")`; eventide
  `1 - PauseUI.Tween.Progress("ShowPause")`]
