# Exporting a project

Read this before the first export of a project, when `scripts/export_project.py`
stops, before passing it `--attach`, or before changing how it drives the
editor. A lesson from an export goes here with its source, one bullet each:
fact, consequence, source.

## Run it

```bash
python scripts/export_project.py --to export/web --bump
```

The script opens the project in the editor of the release that saved it,
exports it to Web (HTML5) as a zip with Offline support, and unpacks the zip
into `--to`, replacing what was there. `--bump` gives the export the version
of the export already in `--to` plus one in its last number, or the
project's Version when that is greater, as after a hand edit that starts a
new line; `--version 1.2.0.0` names it; without either the export carries
the project's Version. The version goes into `project.c3proj` too, so the
project and its export agree. `--dry-run` prints the version, the editor and
the folder and opens nothing.

The editor exports a project over the Free edition's limits only for an
account with a subscription, and it keeps the login in the open page only.
So the script drives a headed window of its own, on the profile
`.tmp/export-<browser>` of the main clone, and when the editor shows Guest or
Free edition it prints a line and waits up to 5 minutes for the user to log
in there: tell the user to log in in that window. After the export it closes
the project and minimizes the window; the next run restores that window and
goes on with its login. A user who closes the window logs in again next
time; a GitHub or Google login stays in the profile, so that is a click or
two.

## Use a browser the user has open

When the user says to use the browser they have open, or the browser of the
chrome-devtools MCP, pass `--attach` with that browser's debugging address;
otherwise use the script's own window. The user turns remote debugging on at
`chrome://inspect/#remote-debugging` (`edge://inspect/#remote-debugging`),
which shows the address, `127.0.0.1:9222`, and allows the connection when the
browser asks; the script waits 60 seconds for that. A port alone is enough:
the script finds the browser's `DevToolsActivePort` in the user data folders
of Chrome, Chromium and Edge. The file itself, or an `http://` or `ws://`
address, works too. A browser started with a pipe instead of a port cannot
be attached.

In that browser the script uses an editor tab on the start page whose
release opens the project, and never a tab with a project open, which may
hold the user's unsaved work. Without such a tab it opens one and closes it
after the export; the user's own tab is left on the start page.

## When it stops

Exit 1 prints `not exported:` and why, and leaves the window or tab as it
is: log in, allow the connection or close the dialog it names, and run the
same command again, which goes on in that window. Exit 2 is a flag, the
project or the editor's page; exit 3, no Edge, Chrome or Chromium on the
machine: export by hand in the editor, or attach to a browser.

After an export made by hand the saved project is one ahead of its export
(see the last bullet below): set `project.c3proj` back to the exported
version, or export again with the script.

## What the editor does

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
- A browser whose remote debugging is turned on at
  `chrome://inspect/#remote-debugging` answers 404 to `/json/version` and 403
  to a connection to a tab; its address is in the user data folder's
  `DevToolsActivePort`, and a tab is driven through `Target.attachToTarget`
  with `flatten` on the browser's connection. The browser may hold the
  handshake until the user allows the connection. [observed in Chrome and
  Chrome Beta, 2026-10-01]
- An export carries the project's Version. With *Auto-increment version* on,
  the editor raises the project's last number after the export, so a project
  saved after a hand export is one ahead of its export; a copy with the
  option off exports the version it holds. [inferred from one hand export,
  0.1.0.4 exported and 0.1.0.5 saved; observed through the script, 2026-10-01]
