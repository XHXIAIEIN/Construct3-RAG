# Generating a Construct project from a script

`assets/build_project.py` is a generator for a project an agent writes end to
end: object types, families, layouts, event sheets, images and the index in
`project.c3proj`, produced from one Python file. It came out of the Water
Sort project (r502, September 2026), where the event sheet grew past what
hand-editing JSON can keep consistent: every rerun produces the whole
project, and `scripts/check_project.py` catches the mistakes the editor would
otherwise report one at a time.

Generate when the agent owns the project and the user reviews it in the
editor: a prototype, a game built from a design conversation, a rewrite. Edit
JSON by hand (`Construct3-RAG/prompts/references/hand-editing-project-files.md`)
when the change is small and the project is the user's, made in the editor.
Do not generate over a project the user edits in parallel: the generator
overwrites the files it produces.

## Set up

1. In Construct, create the project (**Menu** > **Project** > **New**) and
   save it as a folder (**Menu** > **Project** > **Save As** > **Save as
   project folder**). `project.c3proj` now has the `uniqueId`, icons and
   scripts the generator keeps. A folder the editor never saved holds none of
   the properties it reads before it opens a file; the generator fills those
   with the editor's defaults, and the game's own values are set in the
   Properties Bar with the project selected in the Project Bar. The editor's
   `Layout 1` and `Event sheet 1` are left in place but no longer listed once
   the generator has run; delete the two files or give the generated ones
   those names.
2. Copy `assets/build_project.py` to `tools/build_project.py` in the project.
   The generator belongs to the game and is committed with it; the checker
   stays in the skill.
3. Ignore what the editor and the scripts leave behind:

   ```gitignore
   *.uistate.json
   .trash/
   .tmp/
   __pycache__/
   ```

## Build, check, open

Design first, as `Construct3-RAG/prompts/event-sheet-thinking.md` says:
relations, an official example with the same behaviors, the Native first and
Feel tables, the layout of the sheet. Then:

1. Write the design into the generator: the constants at the top, the
   objects and their variables and behaviors, the layouts, then the event
   sheet one group at a time, a `module_*()` function per group in the order
   the guide gives (Setup, Input, ..., Restart). Write one module, run the
   generator, read the sheet it printed, then write the next; a game of ten
   groups is ten short runs, not one long one.
2. Run the generator until its last line starts with `ok:`. It ends by
   running the checker with `--style` on what it wrote and exits with the
   checker's code:

   ```bash
   python tools/build_project.py
   ```

   Warnings do not fail the run; read them anyway, a generated project should
   have none. Then read the sheet once as events, `python
   scripts/print_sheet.py`, before anyone opens the editor.
3. Open and preview it, `python scripts/open_in_editor.py --preview`, until
   it prints `opened` and `preview: ... no errors`. A `failed` or a
   `runtime:` line names the sheet and event at fault: fix the generator,
   not the JSON, and run both again.
4. Hand over: ask the user to open the folder (**Menu** > **Project** >
   **Open**, the local project folder option) and to preview, and say what
   to look at. When no tool of the session could open it, ask for the text
   of any dialog the editor shows on opening as well.
5. What the preview shows that the checker cannot (an instance picked twice,
   a tween and a timer ending a tick apart, a mask that leaves a corner
   uncovered) is a runtime fact. Fix the generator, and when the fact would
   trip the next agent, add it to
   `Construct3-RAG/prompts/event-sheet-pitfalls.md` with its source.
6. Commit the generator with the files it produced; the diff of the
   generated JSON is the review of the change.

The project's README explains the objects, the groups, the constants and how
to regenerate. It is the second copy of the design, for the user, and it says
that running the generator discards edits made in the editor.

## Writing the generator

The stand-in game in `assets/build_project.py` shows the shape. Keep these
habits; they are what makes rerunning safe.

- Constants once, at the top, and a global constant in the sheet for every
  number an event reads; a tunable value has one place to change. What a
  behavior owns (a Sine period, a particle rate) is an instance property set
  in `build_layouts()`, not an event. The template holds the properties
  block of the common behaviors (`SINE`, `BULLET`, `PLATFORM` ...) with the
  editor's keys; one it lacks is copied from an instance of an official
  example, under the behavior's name on that object (`"Sine"`, not `"Sin"`).
- `random.seed(...)` before the first `sid()`: a rerun then produces the same
  ids and the diff shows only what changed.
- One helper per ACE, named for what it does, its parameters in the
  schema's order, with a docstring only where the schema does not say enough
  (which pick it leaves, what a tick later looks like). A helper is added
  when the design needs the ACE; print its entry with
  `scripts/lookup_ace.py` first and copy the `write:` line.
- Behaviors are referred to by the name given on the object, not the
  behavior id: `beh_def("Sin", "Shake")` and `beh_def("Sin", "Rock")` are
  two behaviors, and a helper takes `beh="Shake"`. The id is the editor's
  spelling from `data/c3-schemas/_index.json` (`originalId`): `Sin`, not
  `Sine`; `EightDir`, `TiledBg`, `Arr`, `Json`, `solid`.
- A `block()` has one trigger, as its first condition, and `func()` and
  `custom_action()` hold none. A function that starts a tween and must react
  to its end ends there; the reaction is a top-level `on_tween_finished`
  block that calls the next function.
- Names are plain words: no spaces or hyphens, an instance variable starts
  with a letter, an object is not named like a system expression (`Floor`,
  `Time`, `Random`), an instance variable not like an expression of its
  object (`Angle`, `Width`, `Count`).
- Every runtime-created type has a template instance in a layout that never
  runs (`Objects` in the stand-in).
- Positions and sizes are whole units of the placement grid, never numbers
  picked one by one: `units(n)` for a size, `snap(v)` for a coordinate,
  `anchor("top-left", w, h, ox, oy)` for a HUD element held against an
  edge or corner, `MARGIN` inside the viewport, with the instance's origin
  passed so the point returned is the one the file stores. A HUD label is
  `hud_text(type, text, where, longest=...)`: its box fits its longest text
  and reads towards the side it hangs on. Repeated items, hearts or stars,
  are `row(where, n, w, h)`, spaced so they never touch. A second row on
  the same edge is `dy` in units on the same call, `dy=3` under a 2-unit
  label. The UI layer's instances go through `no_overlap()`, which stops
  the run naming two boxes that meet, with the `dy` that clears them, or
  one past the viewport. A value shown as a bar, health, fuel, progress, a
  row of hearts, is `hud_bar(frame, fill, where, length)`: a frame and,
  inside it, a fill whose origin is its left edge, both Tiled Backgrounds
  from `bar_types()` and `bar_images()` (9-patches with `caps=True`); the
  sheet sets the fill in the one place the value changes,
  `set_width(fill, bar_width(value, maximum, LENGTH))`, or slides it with
  `tween_width()`. `UNIT` follows the viewport
  (8 px for pixel art, 32 px otherwise) and `TOUCH` is the smallest object
  a finger taps at that viewport; a tapped sprite is at least `TOUCH` wide.
  The middle of the screen is the game's; the HUD lives on the edges. The
  counts behind the grid are in `Construct3-RAG/prompts/event-sheet-style.md`,
  *Project*.
- Colours are roles of `PALETTE`, named once at the top with the game's own
  colours. The images `write_png()` draws, the labels and the layers take
  them by role through `rgb()`, and a pixel of any other colour stops the
  run with the nearest role: a new object reuses the game's colours or adds
  one under the role it plays. A painting, a gradient or a photograph,
  passes `painted=True`. The template draws stand-ins, one colour or a plain
  shape each, and leaves the art to the user or to real assets. A stand-in
  is `shape(file, kind, w, h, role)` in `build_images()`: a rectangle,
  circle or triangle with the outline and cast shadow of `SHAPE_STYLE`
  drawn into the image, since Construct's effects have neither. The type
  takes `drawn(file)` as its frame and an instance is that frame's size,
  the shadow included; a sprite that rotates is drawn with `shadow=False`.
  A shape is whole units wide and high, and `shape_inst(type, file, col,
  row)` places it by the grid cell of its top-left corner; `on_grid()`
  stops the run on a world instance off the grid, and an object created at
  runtime goes to `grid_random(lo, hi)`, never a raw `random()`. A drawn
  image holds three alpha values, clear, opaque and the shadow's, and a
  clear pixel is written with no colour under it. A hit shows as a colour:
  `hit_frame(file)` draws the shape's second frame in the `flash` role,
  tagged `hit`, and `hit_flash(obj)` gives the actions that show it for
  `HIT_FLASH["seconds"]` and return to frame 0. `squash(obj, kind)` sets
  the share of the image's size that `SQUASH` gives for `"hit"`, `"land"` or
  `"jump"`, holds it and tweens back, and `hit(obj)` gives the hit's squash
  with the flash, last in their block, as the coin's `Collect` does; the
  object needs the Tween behavior. The Flash behavior stops the run. A
  squash acts on the art, never on an object that collides: a player is an
  invisible mask with Platform and its art, drawn with `shape(..., oy=1)`,
  pinned to it, and the run stops on a squash of the mask. A label is
  `TEXT_SIZE["body"]`, a banner `TEXT_SIZE["title"]`, in `FONT`;
  `hud_text()` stops the run on a colour that reads below 4.5:1 on what is
  behind it, 3:1 for a title, and names the roles that would read there. A
  viewport 360 px high or less is pixel art: `PIXEL_ART` has the project
  sample *Nearest* at a whole-number scale.
- The stand-in's look is a blockout. `PALETTE` holds two canvas greys,
  `solid`, `dim`, `ink`, the accents `reward` and `danger`, and `flash`;
  keep the roles and change values only. `check_palette()` stops the run
  when the backdrop's greys pass 1.2:1 or `solid` falls under 3:1 on them,
  and `shape()` stops on an accent drawn without its outline or a fill
  under 3:1 against the ink. The player is an ink rectangle, structure a
  solid one, a pickup a circle, a hazard a triangle. The backdrop is the
  checker, `backdrop("Backdrop")` on a layer at parallax 1, its cells two to
  a unit: it is the ruler, so draw no grid. An area or an edge is
  `area(type, col, row, cols, rows)` of a type whose tile `pattern(name,
  kind)` drew in `build_images()` and `pattern_type(name)` declares: `low`
  stripes for a harmless special surface, `caution` for what moves or
  triggers, `hazard` for what hurts, the last two on strips and small zones
  only. `tiledbg_inst()` offsets a pattern so neighbouring pieces meet
  without a seam.
- `BEATS` paces the game: one beat per camera zone of a level, or per
  round, wave or window of time in a one-screen game, as the stand-in's
  rounds are. A beat is `beat(type, intensity, mechanics, holds=...)` plus
  the game's own fields. `pace()` stops the run on a curve that breaks a
  rule and prints it, one line a beat, above `generated; checking`; read it
  before the checker's lines. In a platformer, measure each gap and step up
  with `jump(gap, rise)` in units: it says easy, medium or hard against the
  reach `jump_reach()` computes from `PLATFORM`, and stops past nine tenths
  of it. The reach is an approximation; confirm it in a preview.
- Family variables and behaviors are declared on the family and set on every
  member instance; the checker reports the instance that lacks one. A family
  is `family(name, plugin_id, members, ...)` in `build_object_types()` and
  gets `families/<name>.json`; a container, object types created, destroyed
  and picked together, is `container([...])` there and has no file of its
  own: it is a row of `project.c3proj`'s `containers`. Neither has a schema
  or an example folder to search; the helpers are their format.
- A custom action on the object or family for logic that runs on the caller's
  picked instances; a function only for a return value or for logic that
  picks its own instances. Inside a family's block, write the family's name.
- Locals declared as children of a function block are not in scope for the
  block's own actions; put the actions that read them in a child block.
- A group is a `module(title, events=[...], variables=[...],
  procedures=[...])`: it lays the group out as the official examples do,
  variables first, then functions and custom actions, then events. A
  top-level event is `event("What it does", conds, acts)`, a function or
  custom action `procedure("What it does", func(...))`, both with the
  comment the examples put above every event; the description of a
  procedure is the same sentence. A variable one group reads is declared in
  its module, not at the top of the sheet.
- A long block is `steps(("Reset the score", [...]), ("Clear the board",
  [...]))`: a comment action, then three to five actions, per batch. A
  decision is `cases(gate, [("Case one", conds, acts), ("Otherwise",
  None, acts)])`: one gate event, flat sibling cases with a comment each,
  `None` for Else. The checker's `--style` warns where a sheet departs from
  these three shapes; the names, folders, layers and `ObjectRepository`
  layout it cannot check are in
  `Construct3-RAG/prompts/event-sheet-style.md`.

  ```python
  def module_player() -> dict:
      return module("Player",
          variables=[var("P_SPEED", "number", 200, "Run speed", const=True)],
          procedures=[*procedure("Jump when on the floor", custom_action("Player", "Jump", [...]))],
          events=[
              *event("Jump", [on_key("Space")], [call_custom("Player", "Jump")]),
              cases([on_touch_end()], [
                  ("Swipe right: dash", [cmp2("Touch.X - touchStartX", GT, "SWIPE")], [call_custom("Player", "Dash")]),
                  ("Swipe left: slow", [cmp2("touchStartX - Touch.X", GT, "SWIPE")], [call_custom("Player", "Slow")]),
                  ("Otherwise a tap: jump", None, [call_custom("Player", "Jump")]),
              ]),
          ])
  ```

## Keeping the editor's changes

The generator overwrites what it produces, so a change made in the editor is
either moved into the generator or lost. Before regenerating over files the
editor has touched, copy them to `.trash/<date>/<relative path>` (untracked
projects) or commit (tracked projects). `json.dumps(obj, indent="\t",
ensure_ascii=False)` written with `newline="\n"` and no trailing newline is
the editor's own file layout, so what the editor saves over a generated
project differs only where it changed something (roundtrip checked with
the r502 editor).
