# What the editor and the preview do

Read this before previewing a project that starts on a layout other than the
one open in the editor, or before driving a preview with input from a script.
A lesson from the editor, the preview or a script driving them goes here with
its source, one bullet each: fact, consequence, source. A runtime behaviour
that changes which events are written goes to
`Construct3-RAG/prompts/event-sheet-pitfalls.md` instead.

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
- A browser started with `--user-data-dir=\\?\<path>`, the prefix that lifts
  MAX_PATH, writes no cookie file, so a third-party login (GitHub) is gone at
  the next start; `open_in_editor.py` adds the prefix only to a long path.
  [observed in Edge 155, 2026-10-01: a cookie set through the DevTools
  protocol was on disk without the prefix and not with it]
