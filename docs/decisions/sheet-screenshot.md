# A picture of an event sheet comes from the editor, fitted and cropped

Date: 2026-10-14

## Problem

An answer on a forum, a bug report or a page of documentation shows events
as a picture of the editor. Taken by hand, that picture carries what the
reader does not need: the editor's panes and tab bar around the sheet, the
user's interface language, a conditions column of the default 300 px that
breaks a long condition over three lines, an actions column that fills the
window and leaves an empty band, and on Windows the coloured fringes of
subpixel text, which turn into halos once a forum scales the picture down.
Getting one readable picture for a forum answer took a dozen rounds of
cropping and re-rendering by hand.

## Evidence

Measured on generated sheets of up to 379 events in the r505 editor,
headless Edge, 2026-10-14:

- `Page.captureScreenshot` draws at most 16384 device px of a window's
  height; the test machine's WebGL `MAX_TEXTURE_SIZE` was also 16384. A
  taller window still answers and raises no error, but past that height the
  picture starts over with the top of the window, or stays blank.
- The guest editor shows a notice over the top of the sheet. The notice is
  a fixed element inside the element that also holds the sheet's pane.
- Fitting the columns takes about 2 s at 2300 sids. A capture of a picture
  under 16384 device px takes under 1 s.

## Options

- Draw the sheet from its JSON: no browser, but every icon, colour and
  layout rule of the editor redrawn, and a picture that differs from what a
  reader sees when they open the project.
- Undock the sheet to a popup window and take that window: only the sheet
  shows, but a second window to attach to, and the column widths and the
  text rendering stay as they are.
- Open the project as `open_in_editor.py` does, open the sheet from the
  Project Bar, set the columns and the text, and crop to the sheet's own
  element.

For a sheet taller than one capture:

- Capture it in strips, scrolling the view, and join the strips into one
  PNG. Joining them with the standard library inflates and deflates every
  row again, so its cost grows with the picture's area.
- Refuse the picture, and name the groups to take one at a time.

## Decision

The third option, as `scripts/screenshot_sheet.py`, and for a sheet taller
than one capture, the second. It opens the project with `Browser` and
`open_one()` of `open_in_editor.py`, and passes its own browser flags
through the `extra` argument of `Browser`.

- The sheet is the visible `ui-pane.eventSheetViewPane`; its
  `ui-body.eventSheetView` scrolls and holds `div.eventSheetRootView`, the
  grid of rows. The picture is that grid's box, or one group's box from its
  header to its "Add event to" row, never past the view's edges, so no
  pane, tab bar or scrollbar shows.
- The conditions column is `--conditions-column-size`, the variable the
  divider between the columns sets, and the actions column the grid's last
  track, fixed instead of the rest of the window. Each is bisected to the
  narrowest width at which none of its lines wraps, up to a cap (600 and
  900 px), and the actions column widens further until no comment wraps.
  A group's picture fits the columns to that group alone.
- Text is drawn with `--disable-lcd-text` and CSS that turns hinting off and
  thickens stems slightly, close to how macOS draws it; `--lang=en-US` keeps
  the editor in English.
- For each picture the view scrolls the box to its top. The window then
  grows to the box's height with `Browser.setWindowBounds`, up to the
  smaller of 16384 device px and the GPU's largest texture and render
  buffer. Without WebGL the limit is 8192, an unmeasured cautious value. A
  second emulated size reads to the editor as a zoom change and opens a
  modal that blocks the Project Bar; changing the device scale opens it
  once too, and the script presses its OK.
- A box taller than that is not captured. The error line gives the box's
  height and what one picture holds at the scale. It names `--scale 1` when
  the box fits at that scale, and the box's groups, from the sheet's JSON,
  as `--group` flags.
- `--group` takes the named groups instead of the whole sheet, so a group
  of a long sheet needs no capture of the sheet. A title the sheet's JSON
  lacks stops the run before the browser starts, with the closest title.
- Before the capture, each fixed, absolute or sticky element whose box
  overlaps the picture's box is hidden, except the sheet's pane and the
  elements that hold it. These elements are found by walking the page, not
  by hit-testing a grid of points, because hit-testing grows with the
  picture's area and passes the 10 s a call waits on a long sheet.
- A call into the editor waits 10 s plus 0.01 s per sid of the sheet. The
  column fit waits three times that. A capture waits 10 s plus 1 s per
  million pixels. A call that runs out names the step it stopped at.
- The pictures are made to be handed to people, so they go to
  `.build/sheets/` with the other products, not to `.tmp/`.

## Re-evaluate when

- The editor renames the pane, body or root classes or the
  `--conditions-column-size` variable: the script then stops with the sheet
  not showing.
- The browser captures a window taller than its largest texture.
- Construct gains its own export of a sheet as an image.
