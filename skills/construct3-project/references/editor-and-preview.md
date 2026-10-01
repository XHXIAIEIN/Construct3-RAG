# What the editor and the preview do

Read this before previewing a project that starts on a layout other than the
one open in the editor, before driving a preview with input from a script, or
before changing how `scripts/export_project.py` drives the editor.
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

## Exporting

- The editor exports a project over the Free edition's limits only for an
  account with a subscription; the Free edition stops at the platform's
  *Next* with "This project exceeds the Free Edition limit for events". The
  account shows at the top right, `#userAccountWrap`: the name, or Guest,
  and before it `#userLicenseType`, "Free edition", which a subscription
  hides with `display: none` while its text stays. An editor that has just
  loaded shows the last name with the badge hidden for a second or two, then
  Guest, so a check waits for a state that holds. [observed in a game
  project, r504 editor in Edge, 2026-10-01]
- The login lives in the open page only. With an account logged in, no
  cookie of construct.net, no Local Storage, Session Storage or IndexedDB
  entry of the editor or of account.construct.net holds it, and the editor
  shows Guest after a reload or a restart of the browser. A script keeps the
  page: it never reloads it, closes the project instead of the browser, and
  a run goes on in the page a run before left. [observed in a game project,
  r504 editor in Edge, 2026-10-01]
- A browser started with `--user-data-dir=\?\<path>`, the prefix that lifts
  MAX_PATH, writes no cookie file, so a third-party login (GitHub) is gone at
  the next start; `open_in_editor.py` adds the prefix only to a long path.
  [observed in Edge 155, 2026-10-01: a cookie set through the DevTools
  protocol was on disk without the prefix and not with it]
- `editor.construct.net/` can serve an older release from the service
  worker's cache, r495.2 where r504 was current, and it refuses a project a
  newer one saved ("saved in r504, and you are currently using r495.2"). Open
  `editor.construct.net/r<major>[-<minor>]/` from `savedWithRelease`.
  [observed in a game project, Edge, 2026-10-01]
- *Project > Export > Web (HTML5) > Next* opens `exportStandardOptionsDialog`:
  `#exportTo` (zip or folder), `#exportOfflineSupport`, the image and minify
  options. Its *Next* exports and opens `webExportReportDialog`, whose
  download link is a `blob:` URL; a click on it in a driven browser saved no
  file and closed the dialog. Fetch the blob in the page and read it out in
  base64 parts instead. [observed in a game project, r504 editor in Edge,
  2026-10-01]
- An export carries the project's Version. With *Auto-increment version* on,
  the editor raises the project's last number after the export, so a project
  saved after a hand export is one ahead of its export; a copy with the
  option off exports the version it holds. [inferred from one hand export,
  0.1.0.4 exported and 0.1.0.5 saved; observed through the script, 2026-10-01]
- A browser whose remote debugging is turned on at
  `chrome://inspect/#remote-debugging` answers 404 to `/json/version` and 403
  to a connection to a tab; its address is in the user data folder's
  `DevToolsActivePort`, and a tab is driven through `Target.attachToTarget`
  with `flatten` on the browser's connection. The browser may hold the
  handshake until the user allows the connection. [observed in Chrome and
  Chrome Beta, 2026-10-01]
