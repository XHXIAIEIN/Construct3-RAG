# Event Sheet Pitfalls: Storage and export

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- A web export looks for an update only when the page loads, so a tab left
  open never sees a deploy. On each navigation its service worker fetches
  `offline.json` and downloads a newer version in the background. It posts *On
  update found* and *On update ready* about 3 seconds later. *Reload*, like
  the player's own refresh, switches to the new files only while no other tab
  of the game is open. In *On update ready*, ask the player to reload. To test
  it, deploy the new version, then load the old version once. [manual:
  plugin-reference/browser.md "On update ready", "Reload"; runtime: exported
  sw.js, `UpdateCheck` runs from the `fetch` handler for `navigate` requests,
  `PostBroadcastMessage` delays 3000 ms, `GetCacheNameToUse` keeps the old
  cache while `clients.matchAll()` finds more than one; r503 export,
  2026-09-28]
- In a project with the Browser object, the browser's own install banner
  never shows. On every page load the Browser object calls
  `preventDefault()` on `beforeinstallprompt` and holds the event for
  *Request install*. Chrome then logs "Banner not shown:
  beforeinstallpromptevent.preventDefault() called", which is not an error.
  To offer installing, show the game's own button once *On install
  available* fires, and call *Request install* from it. [manual:
  plugin-reference/browser.md "On install available", "Request install";
  runtime: exported main.js r504, the Browser DOM handler's
  `beforeinstallprompt` listener; observed on a game project's web export in
  Chrome, 2026-10-02]
- File System writes only through a picker tag, never a free path. The known
  folder tags (`<documents>`, `<desktop>`, `<saved-games>`, ...) exist only
  in the Windows WebView2, macOS WKWebView and Linux CEF exports. In preview
  and in a browser, *Has picker tag* is false for all of them. Test the
  plugin's own *Desktop features supported*, *Has picker tag*, then *Is
  supported*, and give each branch its fallback. Do not test Platform Info's
  OS, because Chrome on Windows is on Windows and has no known folders.
  [manual: plugin-reference/filesystem.md "Accessing known folders";
  construct.net tutorial "Exporting to Windows with the WebView2 wrapper"]
- No tag names the Construct project folder. `<app>` and `<web-resource>`
  are the exported executable's folder and its `www`, and may be read-only
  (e.g. Program Files). Save to `<current-app-data>`, or `<saved-games>` on
  Windows only. macOS and Linux do not support `<saved-games>`,
  `<screenshots>` and `<roaming-app-data>`. If the macOS App Sandbox is on,
  the known folders are the app's container, not the user's Finder folders.
  [manual: plugin-reference/filesystem.md "Known folders table", "macOS App
  Sandbox"]
- In a browser the plugin needs desktop Chromium, not Firefox or Safari. A
  picker opens only in a user input trigger, and a second write to a file
  opened earlier prompts for permission. A save picker erases the chosen file,
  so write with folder path "" and do not read it. *Start in* sets only the
  folder the dialog opens at. The picker tag persists across sessions, so with
  *Has picker tag* true at start, a *Save* button can rewrite the same file
  without a dialog. [manual: plugin-reference/filesystem.md "Browser
  permissions model", "Show save file picker"; example:
  file-system-text-editor]
- Android and iOS (Cordova) exports are not in the plugin's support list,
  and the WKWebView extension covers macOS only. So treat File System as
  unavailable there. Save with Local Storage, and hand a file to the user
  with Share's *Add file*, because *Invoke download* does not work in a
  mobile app. Enable each route by its own condition, as taking-screenshots
  does with *Is sharing files supported* and *Is supported*. This is not
  verified on a device. [manual: plugin-reference/filesystem.md
  "Browser/platform support"; plugin-reference/browser.md "Invoke download";
  example: taking-screenshots]
- The JSON plugin has no action that merges one object into another. *Set
  JSON* sets one key from a JSON string, and `GetAsCompactString(path)`
  reads one key as that string. So to split a large data file into several
  and still read them through one JSON object, parse each file into a
  second JSON object, then run *For each* on its path `""` and *Set
  JSON* in the main object at `Part.CurrentKey` to
  `Part.GetAsCompactString(Part.CurrentKey)`. The paths the events read stay
  the same, provided no two files share a top-level key, since the later
  file overwrites it. Several AJAX requests can share one tag. Each request
  sets `LastData` to its own response and then fires *On completed* for that
  tag, once per request and in the order the responses arrive. So request
  all files in one block, count them in a variable, merge each in *On
  completed*, and start the game in a sub-event when the count reaches 0.
  [manual: plugin-reference/json.md "For each", "Set JSON", "CurrentKey",
  "GetAsCompactString"; schema: plugins/json.json, no merge action; runtime:
  exported c3runtime.js r504, AJAX `onreadystatechange` sets `_lastData`
  and then calls `_TriggerComplete` for each request, `OnComplete` compares
  the tag; observed in a game project, r504, 2026-10-06: four data files
  requested with one tag, merged this way before the first level]
