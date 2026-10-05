# Exporting a project

Read this before the first export of a project, when `scripts/export_project.py`
stops, or before passing it `--attach`. A lesson from an export goes under
"What the editor does", one bullet each: fact, consequence, source.

## Run it

```bash
python scripts/export_project.py --bump
```

The script opens the project in the editor of the release that saved it,
with only the files the editor reads, as `scripts/pack_project.py` packs them,
exports it to Web (HTML5) as a zip with Offline support, Deduplicate images
and Optimize images on, and unpacks the zip into `--to`, replacing what was
there. Without `--to` the export goes to `.build/web`, where the products
go and Git ignores them; the browser profile stays in `.tmp/`.

The copy handed to the editor sets *Use worker* to Auto, so the engine
decides: a worker, unless the project has a script or an addon without worker
support. `project.c3proj` keeps its own setting, so a project set to No for a
test previews in the page and still exports with Auto. The last line says
where the export's runtime starts, read from the main.js it holds.

The version: `--bump` takes the export already in `--to` and adds one to its
last number, or takes the project's Version when that is greater;
`--version 1.2.0.0` names it; without either the export carries the
project's Version. The script writes the version into `project.c3proj` too,
so the project and its export agree. `--dry-run` prints the version, the
editor and the folder, and opens nothing.

A project over the Free edition's limits exports only from an account with a
subscription. The script drives a window of its own, and when the editor
shows Guest or Free edition it waits up to 5 minutes: tell the user to log
in in that window. The script restores the window for the export, which
then runs with other windows over it; afterwards it closes the project and
minimizes the window, and the next run goes on in it with the login. If the
user closes the window, they log in again next time.

## Use a browser the user has open

Only when the user asks for the browser they have open, or the
chrome-devtools MCP's browser: pass `--attach 127.0.0.1:9222`, or just the
port. The user turns remote debugging on at
`chrome://inspect/#remote-debugging` (`edge://` for Edge), which shows the
address, and allows the connection when the browser asks; the script waits
60 seconds for that.

The script never touches a tab with a project open, since it may hold
unsaved work. It uses an editor tab on the start page, or opens one and
closes it after the export or when the run stops.

## When it stops

- Exit 1, `not exported:` and the reason. The run closes the copy it
  handed to the editor, without saving, and the dialogs over it: a tab it
  opened is closed, and the user's own tab or the script's window is left
  on the start page. Do what the reason names (log in, allow the
  connection) and run the same command again.
- `the editor showed its crash report over the copy; pressing its
  Restart`: the editor crashed on the project, and Restart is the report's
  one way out. The reloaded editor may ask for the login again. Run
  `scripts/check_project.py` before exporting again: a collision polygon
  of fewer than three points crashed an export this way.
- A run that was killed leaves its copy open in the script's window, and
  the next run closes it before it reads the login.
- `trying again with longer pauses`: a menu item or dialog did not come
  within 30 seconds, as on a slow machine or network. The script closes
  what is open and runs the export once more with pauses three times as
  long. When that run stops too, or on a machine already known to be slow,
  pass `--slow`, which uses the longer pauses from the start.
- Exit 2: a bad flag, project or editor page.
- Exit 3: no Edge, Chrome or Chromium. Export by hand in the editor, or
  attach to a browser.

After an export by hand, set `project.c3proj` back to the exported version,
or export again with the script (the *Auto-increment version* bullet below).

## What the editor does

- An editor that crashed shows its crash report, "Oops! Something went
  wrong", with Save open projects, Copy information and Restart and no way
  to close it, and shows it again as soon as the menu opens, so its project
  cannot be closed. Restart reloads the page after the page's question about
  leaving, which the DevTools protocol sees only after `Page.enable` and
  answers with `Page.handleJavaScriptDialog`; a mouse click on Restart waits
  on that question. So the script presses Restart from the page and answers
  the question. [observed in r495.2, 2026-10-04: an export of a project whose
  collision polygon had two points crashed as its Export dialog opened, in
  the user's Chrome over `--attach`; the run pressed Restart, and the tab came
  back to the start page with the account and its subscription still shown.
  In a tab the run opened, an r504 export of it finished and the report came
  as the copy closed; the run restarted that tab and closed it. A run that
  stopped in `open_project` closed the tab it had opened. In a headless
  editor, Restart pressed this way reloaded in about 3 seconds]

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
- An editor window covered by other windows makes its page hidden
  (`document.visibilityState` `hidden`), and `Page.bringToFront` does not
  undo it. The editor then shows no menu item to click and stalls at
  "Opening...", so a run stops with "no 'Project' in the editor" or a call
  that gets no answer. `Emulation.setFocusEmulationEnabled` and
  `Page.setWebLifecycleState` `active`, on a session held for the whole run,
  keep the page visible, and the script sets both on the page it drives
  before the first click. A minimized window needs restoring as well: with
  both set it reports `visible`, but the click on Export opens no dialog and
  a screenshot never comes. [r504 editor in Edge, exports of a game project,
  2026-10-03: three runs stopped and the fourth exported once a second
  session had set both; then, with both set, a window under another one
  opened the export dialog and a minimized one did not]
