# A picture of an event sheet comes from the editor, fitted and cropped

Date: 2026-10-04

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

## Decision

The third, as `scripts/screenshot_sheet.py`. It reuses `open_one()` of
`open_in_editor.py`, which gained `extra` browser flags for it.

- The sheet is the visible `ui-pane.eventSheetViewPane`; its
  `ui-body.eventSheetView` scrolls and holds `div.eventSheetRootView`, the
  grid of rows. The picture is that grid's box, never past the view's edge,
  so no pane, tab bar or scrollbar shows.
- The conditions column is `--conditions-column-size`, the variable the
  divider between the columns sets, and the actions column the grid's last
  track, fixed instead of the rest of the window. Each is bisected to the
  narrowest width at which none of its lines wraps, up to a cap (600 and
  900 px), and the actions column widens further until no comment wraps.
  A group's picture fits the columns to that group alone.
- Text is drawn with `--disable-lcd-text` and CSS that turns hinting off and
  thickens stems slightly, close to how macOS draws it; `--lang=en-US` keeps
  the editor in English.
- The window grows to the sheet's height with `Browser.setWindowBounds`. A
  second emulated size reads to the editor as a zoom change and opens a
  modal that blocks the Project Bar; changing the device scale opens it once
  too, and the script presses its OK.
- Anything drawn over the crop (a notice, a banner) is hidden before the
  capture.
- The pictures are made to be handed to people, so they go to
  `.build/sheets/` with the other products, not to `.tmp/`.

Measured on the stand-in demo and on airborne-explorer: an 18 000 px sheet
opens, grows and is captured in one picture in about 20 seconds; every edge
of every picture is the sheet's background colour.

## Re-evaluate when

The editor renames the pane, body or root classes or the
`--conditions-column-size` variable (the script then stops with the sheet
not showing), or Construct gains its own export of a sheet as an image.
