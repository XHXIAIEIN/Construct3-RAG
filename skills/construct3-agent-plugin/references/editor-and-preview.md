# What the editor and the preview do

Read this before previewing a project that starts on a layout other than the
one open in the editor, or before driving a preview with input from a script.
`scripts/preview_project.py` sends taps, holds, drags and keys as the bullets
below describe; a script of the agent's own needs them for what it does not
cover, such as two fingers at once. A lesson from the editor, the preview or a script driving them goes here with
its source, one bullet each: fact, consequence, source. A runtime behaviour
that changes which events are written goes to
`Construct3-RAG/prompts/event-sheet-pitfalls.md` instead, and a lesson about
which cases to play and how to reach and read them to
[verifying-a-change.md](verifying-a-change.md).

- *Preview* (F5, the toolbar button) starts from the layout open in the
  editor, not from the project's first layout; only *Preview project* uses
  that. A loader layout that reads Local Storage and then goes to the game
  layout is skipped whenever the game layout is previewed, and the save
  appears not to work. Read the save in the sheet of the layout that needs
  it, gated by a global such as `loaded`, and build from the trigger.
  [manual: overview/testing-projects.md "Preview project"; observed in a
  game project, 2026-09-18]
- A drag dispatched from a script into a preview page moves nothing with
  `pointermove` alone: the runtime reads `pointerrawupdate` where the browser
  has it, so send one before each `pointermove`; `pointerdown` and
  `pointerup` work as they are. Coordinates are the page's CSS pixels, not
  the pixels of a screenshot taken at a device scale factor. [observed in a
  game project, r503 preview in Chrome, 2026-09-29]
- Mouse input sent through the DevTools protocol, `Input.dispatchMouseEvent`
  with `mousePressed`, a run of `mouseMoved` carrying `buttons: 1` and
  `mouseReleased`, drags a Drag & Drop instance and fires its *On drop*
  without any pointer event of the page's own; the browser raises the
  pointer events itself. Aim it with the layer's `layerToCssPx(x, y)`,
  which turns a layer position into those CSS pixels; `ILayer` has no
  `layoutToCssPx`. [preview: ILayer.d.ts `layerToCssPx`; observed in a game
  project, r504 preview in Edge, 2026-09-30: a weapon dragged onto a piece
  and a piece onto a battle slot landed where the events put them]
- Two fingers at once go through `Input.dispatchTouchEvent` after
  `Emulation.setTouchEmulationEnabled`, which Touch and Drag & Drop both
  read. Every event lists all the fingers still down, each with its `id`: a
  `touchStart` that puts a second finger down repeats the first, and a
  `touchMove` gives each finger's place. One finger can then hold a button
  while another drags an instance. [observed in a game project, r504 preview
  in Edge, 2026-10-01: a finger held the buy button and bought six cards,
  then a second finger, added in a `touchStart` listing both, dragged a
  piece]
- `Emulation.setDeviceMetricsOverride` answers before the page has resized:
  `innerWidth` and `innerHeight` read right after it can still be the
  window's own size, for up to 0.4 seconds, while the runtime already places
  its layers in the new viewport. A target checked against that size is
  refused although `layerToCssPx` aimed it right; wait until the page reports
  the override's size before reading anything sized by it.
  `scripts/preview_project.py` waits, and stops the run when the size does
  not come. [observed in a popup opened with `window.open` and an r504 preview of a
  game project, Edge headless, 2026-10-02: a plan with a 430x932 viewport
  reported the window 778x511 and refused a piece at (215, 554); one probe
  in four read 778x511 at once, and 430x932 0.38 s later]
- An emulated size belongs to the page, not to the DevTools connection that
  set it, and closing any connection that set one clears it: the window goes
  back to its own size in the middle of a run, while the screenshots of the
  connection that set it still come out at the emulated size. A second
  connection that takes screenshots sets the override all the same, since
  without one a headed window captures at the display's scale, and stays open
  until the window closes; `scripts/preview_project.py` keeps its recorder's
  open that way. [observed in an r504 preview of a game project and a popup
  opened with `window.open`, Edge headless and headed, 2026-10-02: once a
  recording's connection closed, the page reported 778x511, a piece aimed at
  (448, 304) lay outside the 430x932 the run had set, and the screenshots
  were still 430x932; without the override, the second connection's headed
  screenshot was 645x1398 at 150 %]
- A `--headed` window behind other windows makes its page hidden, and a
  hidden editor lays out no menu and can stall at "Opening...". Focus
  emulation and the active lifecycle state keep a page visible for as long
  as the connection that set them stays open: `open_in_editor.py` sets both
  on the editor and the preview window it opens (`keep_active`), and a
  script of the agent's own that drives a headed window does the same. A
  minimized window then reports visible, but a click misses what the page
  draws next and a screenshot never comes: leave a `--headed` window
  restored while it runs. A headless window is never covered. [observed in
  exports through `export_project.py`, r504 editor in Edge, 2026-10-03; see
  [export-project.md](export-project.md), "What the editor does"]
- A preview run for five seconds without input shows that the layout
  starts; it says nothing about an event that waits for a drop, a merge or
  a deployment. Such an event is verified by playing it, a plan of
  `scripts/preview_project.py` that drags and then waits `until` the flow
  has run through, before it is handed over. [observed in a game
  project, r504 preview, 2026-09-30: a *Pick parent* with *Own* that could
  not reach a grandparent passed the five-second preview and left a piece
  idle on its battle slot at the first drag by hand]
- A preview ticks at the display's rate, headless or headed, but the window
  loads for part of the preview's seconds: `--preview 5` runs the game
  about 4 seconds, and once, headed, ran it under one. The `preview:` line gives
  the runtime's own ticks and wall time; an event that waits for a time
  longer than that has not run. Pass more seconds for it. [observed in
  official examples and a game project, r504 preview in Edge and Chrome,
  headless and headed, 2026-10-02]
- `open_in_editor.py` starts the browser with `--mute-audio`, so a
  preview's sound stays off the user's speakers; a script of the agent's
  own that starts a browser does the same. The audio graph and
  `Audio.CurrentTime` run as before; only the output device is silent. A
  sound is heard or measured by recording it in the page: connect a
  `MediaStreamAudioDestinationNode` beside the context's destination,
  record its stream with `MediaRecorder`, and analyse the file, or read an
  `AnalyserNode` on the same point. [source: `open_in_editor.py`, the
  comment at `--mute-audio`; the user's rule, 2026-09-30, that a test must
  not play sound through their speakers]
- A browser started with `--user-data-dir=\\?\<path>`, the prefix that lifts
  MAX_PATH, writes no cookie file, so a third-party login (GitHub) is gone at
  the next start; `open_in_editor.py` adds the prefix only to a long path.
  [observed in Edge 155, 2026-10-01: a cookie set through the DevTools
  protocol was on disk without the prefix and not with it]
- The browser opens no IndexedDB whose folder path reaches MAX_PATH, counted
  as a string with the `\\?\` prefix, so the prefix does not lift this one.
  The preview's is `Default\IndexedDB\https_preview.construct.net_0.indexeddb.leveldb`
  below the profile, which leaves 193 characters for the profile as passed,
  the prefix included; past that the preview page stops answering.
  `open_in_editor.py` passes a long profile by its 8.3 short name where the
  volume keeps one, and refuses the preview of one still too deep, naming
  `--profile`. [observed in Edge, 2026-10-01: a profile of 189 characters
  plus the prefix previewed, one of 190 hung at `Target.setAutoAttach`; the
  same project at a short path ran]
- A `.c3p` or a `.zip` opens only with `project.c3proj` at the root of the
  archive; one that holds the project folder fails with "Check it is a
  valid Construct 3 single-file (.c3p) project". `scripts/pack_project.py`
  writes the root layout, by default to `.build/<folder>.c3p`. [observed in r504, 2026-10-02: the same project
  opened packed at the root and failed packed inside its folder]
- A file put on a page's file input through the DevTools protocol from a
  path past MAX_PATH reaches the page empty, with its name and no error: the
  upload "succeeds" with 0 bytes. Hand the browser a copy under a short
  folder and read `files[0].size` in the page before using it;
  `pack_project.py` warns when it writes such a path. [observed in Chrome
  154, 2026-10-02: a 73 KB zip at a 273-character path arrived as 0 bytes,
  the same file under `%TEMP%` whole]
- A project saved with Bundle addons asks, while it opens, to install each
  bundled addon the browser profile lacks, and waits at
  `#addonConfirmInstallDialog` with the progress dialog still open.
  `open_in_editor.py` clicks Install and names the addon in a `warning:`
  line; the preview then runs with it. A project that uses a custom addon
  without bundling it fails with "Missing addons" in any profile that has
  not installed it, the headless one included: bundle the addon in an
  example or a repro. [observed in r504, 2026-10-03: an effect addon
  bundled in a demo installed from the dialog and previewed in a fresh
  profile]
- The editor refuses a `.c3addon` whose `addon.json` leaves `name`, `id`,
  `version`, `author`, `website`, `documentation` or `description` empty,
  with "Failed to install the addon" and the console line `invalid addon
  json`. In an effect addon, `supported-renderers` names `webgl2` only
  beside a WebGL 2 shader; the built-ins list `["webgl", "webgpu"]`, with
  `effect.fx` and `effect.wgsl`. The lang file keys a parameter by its `id`
  exactly, case included, else the Properties Bar shows `[???]`; the
  built-ins write ids in kebab case. The editor's own effects, their
  `addon.json`, GLSL and WGSL, are in `.cache/c3-cdn/<release>/effects_allEffects.json`
  of the Construct3-RAG clone. [r504 `main.js`, the addon installer;
  observed installing an effect addon, 2026-10-03]
- An effect that counts its pixels by `pixelSize` changes with the editor's
  zoom and the window size, since a texel of the drawn rect is a screen
  pixel. Count them in the object's layout units instead, as the built-in
  Randomize tiling does: the position in the object is
  `(vTex - srcOriginStart) / (srcOriginEnd - srcOriginStart)`
  (`c3_srcOriginToNorm` in WGSL), its size `abs(layoutEnd - layoutStart)`.
  [r495.2 effect sources; observed in r504 previews at 640x400 and
  1400x860, 2026-10-03: the same cells, scaled]
