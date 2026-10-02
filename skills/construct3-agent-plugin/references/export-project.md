# Exporting a project

Read this before the first export of a project, when `scripts/export_project.py`
stops, or before passing it `--attach`. A lesson from an export goes under
"What the editor does", one bullet each: fact, consequence, source.

## Run it

```bash
python scripts/export_project.py --to export/web --bump
```

The script opens the project in the editor of the release that saved it,
exports it to Web (HTML5) as a zip with Offline support, Deduplicate images
and Optimize images on, and unpacks the zip into `--to`, replacing what was
there.

The version: `--bump` takes the export already in `--to` and adds one to its
last number, or takes the project's Version when that is greater;
`--version 1.2.0.0` names it; without either the export carries the
project's Version. The script writes the version into `project.c3proj` too,
so the project and its export agree. `--dry-run` prints the version, the
editor and the folder, and opens nothing.

A project over the Free edition's limits exports only from an account with a
subscription. The script drives a window of its own, and when the editor
shows Guest or Free edition it waits up to 5 minutes: tell the user to log
in in that window. Afterwards the script closes the project and minimizes
the window, and the next run goes on in it with the login. If the user
closes the window, they log in again next time.

## Use a browser the user has open

Only when the user asks for the browser they have open, or the
chrome-devtools MCP's browser: pass `--attach 127.0.0.1:9222`, or just the
port. The user turns remote debugging on at
`chrome://inspect/#remote-debugging` (`edge://` for Edge), which shows the
address, and allows the connection when the browser asks; the script waits
60 seconds for that.

The script never touches a tab with a project open, since it may hold
unsaved work. It uses an editor tab on the start page, or opens one and
closes it after the export.

## When it stops

- Exit 1, `not exported:` and the reason: the window or tab stays as it is.
  Do what it names (log in, allow the connection, close the dialog) and run
  the same command again.
- `trying again with longer pauses`: a menu item or dialog did not come
  within 30 seconds, as on a slow machine or network. The script closes
  what is open and runs the export once more with pauses three times as
  long. When that run stops too, or on a machine already known to be slow,
  pass `--slow`, which uses the longer pauses from the start.
- Exit 2: a bad flag, project or editor page.
- Exit 3: no Edge, Chrome or Chromium. Export by hand in the editor, or
  attach to a browser.

After an export by hand, set `project.c3proj` back to the exported version,
or export again with the script (last bullet below).

## What the editor does

- The login lives in the open page only, in no cookie or storage; a reload
  or browser restart shows Guest. So the script never reloads the page and
  closes the project instead of the browser. [r504 editor in Edge,
  2026-10-01]
- `editor.construct.net/` may serve an older release from cache, which
  refuses a project a newer release saved. The script opens
  `editor.construct.net/r<release>/` from `savedWithRelease`. [Edge,
  2026-10-01]
- The export report's download link, clicked in a driven browser, saves no
  file; the script reads the zip out of the page instead. [r504 editor in
  Edge, 2026-10-01]
- With *Auto-increment version* on, the editor raises the project's last
  number after an export, so a project saved after a hand export is one
  ahead of its export. [one hand export, 0.1.0.4 exported and 0.1.0.5 saved,
  2026-10-01]
