# A Preview Is Played from a Plan of Steps

Date: 2026-10-02
Schema: Construct 3 r495.2 (stable), r504 (beta)

## Problem

A five-second preview without input shows that a layout starts. It says
nothing about a drop, a merge, a jump or a purchase, which is what an agent
changes most often. Agents that tested those wrote a script of their own per
check: in one game project about twenty of them, a few hundred lines each,
every one repeating the same skeleton. Each opened the project through the
editor opener's functions, pressed F5, found the preview window, made it
phone-sized with touch, took the runtime from its Tick, turned layer
positions into page positions with `ILayer.layerToCssPx`, pressed, moved and
released through the DevTools protocol, waited, read state, took
screenshots, and collected the runtime's errors. Only the scenario in the
middle differed.

Task: the agent says what a player does and what should follow, and gets
back, step by step, what happened, with the game's errors placed at the step
that caused them.

## Options

1. Keep it to the agent: the reference pages say how, the agent writes the
   script. That is the twenty scripts above, and a small model does not get
   that far.
2. A Python library the agent's script imports. Shorter scripts, still code
   to write, run and debug per check.
3. A plan: a JSON list of steps, checked before the editor opens, run by one
   script that owns the browser, the preview and the input.
4. Flags on `open_in_editor.py`. Its job is to say whether a project opens;
   a sequence of inputs is not a flag.

## Decision

Option 3, `scripts/preview_project.py PLAN.json`.

- Steps: `tap`, `hold`, `drag`, `key`, `wait`, `until`, `js`, `state`,
  `shot`, one per object, with `note` for a label. A plan sets the
  `viewport` and whether presses are `touch`. The first failing step stops
  the run, since later steps assume it.
- A `key` step holds one key or a list of keys, such as
  `["ShiftLeft", "ArrowRight"]`. The keys go down in order and come up in
  reverse. Each key event carries the modifier bits of the Shift, Control
  and Alt keys that are down at that moment, as a browser's events do.
- A target is an instance named the way the project names it (`"Piece 2"`,
  `"uid 12"`), a position on a layer, or JavaScript returning either. The
  script presses the middle of the instance's bounding box, converted by the
  layer, so a plan does not depend on the window's size or the camera.
- `js` and `until` run in the session that runs the game, page or worker,
  with the scripting `runtime`, a `vars` object kept between steps and
  `wait`. They are the way out for what the step kinds do not cover, such as
  calling a function of the project to set a scene up.
- The output is one line per step, then the runtime errors logged during it;
  `--out` keeps every value read. A failed step leaves a screenshot.
- `record` keeps screenshots of the window, taken one after another on a
  connection of its own, and joins them into an .mp4 with ffmpeg or a .gif
  with Pillow where one is installed; the frames stay for the agent to read.
  The browser's screencast cannot do it: with the window's size emulated it
  sends no frame, or a strip. Construct's Video Recorder plugin records the
  canvas with its sound, but only in a project that has the object.
- A recording is for reviewing what happened. Its `watch` expressions are
  read with every frame, and `timeline.json` puts the frames, the steps that
  ran and the errors on one clock; the agent gets the watched values' changes
  printed, the user a page beside the frames that plays them, steps through
  them and jumps to a step.
- The agent judges a motion from a contact sheet, `NN-NAME-sheet.png`: up to
  12 frames in one image, each numbered with its time. It holds the first
  and last frames, the frames around the largest change between two frames,
  the start and end of each step, and the cells left over spread over the
  change, so a motion that runs between two steps is on it. The run asks for
  the three worst defects, each with its time, what the frame shows and the
  event to change, then a fix of only those and a new recording of that
  part. Before it, the agent read the watched values and left the eye to the
  user. The pattern is the contact sheet of code-rendered video production;
  on a HealthBar recording of 70 frames, a sheet of the hit and the heal at
  their step boundaries left out the lost-HP bar closing between them, and
  spreading the spare cells over the change put it on the sheet.
- What the user sees go wrong reaches the agent as a part of the recording.
  The user selects it on the page and copies it as a task for an agent that
  starts cold: what to find out, in their words or a default question, the
  project, the frames by absolute path (the agent opens a frame as a file),
  the steps and watched values of that part, how to investigate and what to
  report. The timeline holds the project's and the frames' paths, so a page
  opened without its recording, from a folder the user chooses, writes the
  same task. A page cannot start the browser's folder chooser at a path,
  only at a folder the user chose before, so the script writes `index.html`
  beside the recordings, the same page listing every one with a link to its
  review page, and the page without a recording takes the game project or
  its `.tmp/preview/` and lists the recordings it finds there.
- A bug is played before it is fixed. The agent writes the report as given,
  doing, produces and instead of, and plays the plan on the unchanged
  project until it fails at the step that reads the produces, for the
  reported reason. A plan that never failed passes whether the fix works
  or not, and one that fails elsewhere tests another fault.
- A word of feel becomes a number. Floaty or slow names no value, so the
  agent names the variable behind it, reads its current value, and
  measures what the player feels with `record` and `watch`, against a
  target in the same measure from `prompts/references/feel.md` or the user.
  The change ends when the measure meets the target; a motion judged only
  by eye is changed again on every review.
- A plan that passed is kept as a check of its change. `--keep NAME` copies
  it into the project as `tools/plans/NAME.json`, where the generator and the
  design live and the editor reads nothing it is not told to, and the plan is
  committed with the change. `--all` replays every kept plan in one editor
  session, each from a first launch, and names each one that fails, since a
  later change broke what it checks. Each run overwrites `.tmp/preview/` and
  its result, so a plan that is not kept is played once. A passing run says
  how to keep it and how many plans are kept, and a refused kept plan fails
  the replay like a failed step.
- The run's output tells the agent what the page does for the user, so the
  agent points the user to it: a part that looks wrong comes back as a task.
- The review page follows a technical drawing: compact ruled panels,
  collapsible recording details, blue for what the page marks and red
  for what failed, the selected part dimensioned on the timeline and the
  marks for its ends over the playhead, line icons whose tooltips name their
  keys. Repeated instructions live in tooltips; one selection hint stays
  visible until a part is selected. This keeps the preview and watched values
  in view without shrinking their type. A path shows by its last part, the
  whole path in its tooltip and copied by a click; the task for the agent keeps paths whole, since the
  agent opens the files by them. It loads no font or script from the
  network, so it opens offline as the recording does.
- A run starts from a first launch: the browser profile is kept between runs
  for its cache, and with it the preview's Local Storage and IndexedDB, where
  a game keeps its save, so one run's save changed the next run's start.
  `keep_saves` keeps them for a returning player.
- The runtime is reached through `assets/runtime-probe.js`, the same file
  `open_in_editor.py --state` and an agent's own script use, documented in
  `references/reading-the-runtime.md`.
- `open_in_editor.py` keeps opening the project, `--preview` and `--state`,
  and the browser and editor functions both scripts share; the preview
  player imports them, as `export_project.py` does.

Not covered: two fingers at once, a gamepad, and what a sound sounds like.
`references/editor-and-preview.md` says how a script of one's own does the
first and the last.

## Re-evaluate when

- Plans keep falling back to long `js` steps for the same kind of action:
  that action becomes a step.
- A Construct release changes how the preview window opens or where the
  runtime runs, and the probe answers in neither the page nor a worker.
