# --attach Names the Browser; the Script Reads No Browser Folder of the User's

Date: 2026-10-16

## Problem

`export_project.py --attach PORT` connects to a browser the user has open.
A browser debugged from `chrome://inspect/#remote-debugging` does not answer
`/json/version` on its port, so the script looked for a `DevToolsActivePort`
file naming that port in the user data folders of Chrome, Chromium and Edge
under the user's home folder, on Windows, macOS and Linux.

Those folders hold the user's cookies, saved logins and history. The script
read one small file in them, but a review of the plugin cannot tell that
from the paths alone: the plugin directory's check held the plugin for
"uses a credential from the user's machine", naming that lookup. The
lookup also guessed: a browser installed elsewhere, or a profile folder
moved with `--user-data-dir`, was not found, and the error then told the
user to pass the file anyway.

## Options

- Keep the lookup and explain it in the listing: the reviewer still sees a
  script that walks browser profile folders.
- Ask for the file through a `user_config` option: the value changes with
  each browser and each run, so an option does not fit.
- Drop the lookup. A port that does not answer `/json/version` stops the run
  with the path form to pass instead, the `DevToolsActivePort` file, which
  the user names.

## Decision

The lookup is removed. `--attach` takes a port or an http:// address, which
the script asks for `/json/version`; a ws:// address; or the
`DevToolsActivePort` file the user names. The script reads no folder of the
user's browsers on its own, and the error for a port that does not answer
says which file to pass.

## Consequences

- A browser debugged from `chrome://inspect` needs the file's path on the
  command line, once per run.
- The skill holds no path under the user's home folder but its own font
  cache and the skills folders it is installed in.
