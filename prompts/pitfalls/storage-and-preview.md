# Event Sheet Pitfalls: Storage and preview

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- *Preview* (F5, the toolbar button) starts from the layout open in the
  editor, not from the project's first layout; only *Preview project* uses
  that. A loader layout that reads Local Storage and then goes to the game
  layout is skipped whenever the game layout is previewed, and the save
  appears not to work. Read the save in the sheet of the layout that needs
  it, gated by a global such as `loaded`, and build from the trigger.
  [manual: overview/testing-projects.md "Preview project"; observed in a
  game project, 2026-09-18]
- Local Storage is an IndexedDB database named `c3-localstorage-` plus the
  project's `uniqueId`, so it survives closing the preview and is separate
  per project. A tool that rewrites `project.c3proj` must keep `uniqueId`
  or the saved data is orphaned. [runtime: exported c3runtime.js
  `_GetProjectStorage`; manual:
  scripting/scripting-reference/interfaces/istorage.md "unique to the
  specific project"]
- A web export looks for an update only when the page loads: on each
  navigation its service worker fetches `offline.json`, downloads a newer
  version in the background and posts *On update found* and *On update
  ready* about 3 seconds later. A tab left open never learns of a deploy,
  and *Reload*, like the player's own refresh, switches to the new files
  only while no other tab of the game is open. Prompt from *On update
  ready* and let the player reload; testing it takes loading the old
  version once after the new one is deployed. [manual:
  plugin-reference/browser.md "On update ready", "Reload"; runtime:
  exported sw.js, `UpdateCheck` runs from the `fetch` handler for
  `navigate` requests, `PostBroadcastMessage` delays 3000 ms,
  `GetCacheNameToUse` keeps the old cache while `clients.matchAll()` finds
  more than one; r503 export, 2026-09-28]
- File System writes only through a picker tag, never a free path. The known
  folder tags (`<documents>`, `<desktop>`, `<saved-games>`, ...) exist only in
  the Windows WebView2, macOS WKWebView and Linux CEF exports; in preview and
  in a browser *Has picker tag* is false for all of them. Gate on the plugin's
  own *Desktop features supported*, *Has picker tag*, then *Is supported*,
  not on Platform Info's OS (Chrome on Windows is on Windows and has no known
  folders), and give each branch its fallback. [manual:
  plugin-reference/filesystem.md "Accessing known folders"; construct.net
  tutorial "Exporting to Windows with the WebView2 wrapper"]
- No tag names the Construct project folder. `<app>` and `<web-resource>` are
  the exported executable's folder and its `www`, and may be read-only (e.g.
  Program Files). Saves go to `<current-app-data>`, or `<saved-games>` on
  Windows only; `<saved-games>`, `<screenshots>` and `<roaming-app-data>` are
  unsupported on macOS and Linux. With the macOS App Sandbox on, the known
  folders are the app's container, not the user's Finder folders. [manual:
  plugin-reference/filesystem.md "Known folders table", "macOS App Sandbox"]
- In a browser the plugin needs desktop Chromium (not Firefox or Safari), a
  picker only opens in a user input trigger, and writing again to a file
  opened earlier prompts for permission. A save picker erases the chosen file,
  so write with folder path "" and do not read it; *Start in* sets only the
  folder the dialog opens at. The picker tag is remembered across sessions:
  *Has picker tag* at start lets a *Save* button rewrite the same file without
  a dialog. [manual: plugin-reference/filesystem.md "Browser permissions
  model", "Show save file picker"; example: file-system-text-editor]
- Android and iOS (Cordova) exports are not in the plugin's support list; the
  WKWebView extension covers macOS only. Treat File System as unavailable
  there: save with Local Storage, hand a file to the user with Share's *Add
  file*, since *Invoke download* does not work in a mobile app. Enable each
  route by its own condition, as taking-screenshots does with *Is sharing
  files supported* and *Is supported*. Not verified on a device. [manual:
  plugin-reference/filesystem.md "Browser/platform support";
  plugin-reference/browser.md "Invoke download"; example: taking-screenshots]
