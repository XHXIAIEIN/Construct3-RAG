# Event Sheet Pitfalls: Expressions

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- `Self` is the object of the condition or action that holds the expression.
  A System condition or action, *For each ordered* included, has no such
  object, so the editor refuses to open the project with `Invalid use of
  'self'`. Write the object: order *For each Segment* by `Segment.IID`, not
  `Self.IID`. [editor message `Invalid use of 'self'`; observed in a game
  project, 2026-09-22]
- A local or global variable named like a system expression is read as the
  expression. A local number `mid` passed as `Functions.Measure(mid)` is read
  as the text function `mid()`, so the editor refuses the whole project with
  `Invalid expressions ... parameter 0 does not take 'string'`. Give each
  variable a name that no system expression has (`probe`, not `mid`; not
  `left`, `right`, `len`, `find`, `max`, `min`, `abs`, `round`). A function
  parameter is read the same way: a parameter `round` used as `"第 " & round &
  " 轮"` stops the editor with `'round' does not accept 0 parameters`, and
  `roundNo` opens. `check_project.py` refuses both kinds of name.
  [plugins/system.json, expression `mid`; observed in a game project, r495.2
  editor, 2026-09-23; the parameter case observed in a game project, r504
  editor, 2026-09-30; both in minimal projects, r504 editor, 2026-10-02]
- The editor matches variable names without regard to case and uses the
  nearest scope's variable. A local string `count` declared in an event hides
  the global constant `COUNT` in that event and its sub-events. So `COUNT -
  1` there uses the string, and the editor refuses the whole project with
  `Type mismatch: - does not work with 'string' and 'number'`, naming the
  sub-event. `check_project.py` refuses a local or parameter named like a
  variable of another type in scope. Give a local a name that differs from
  every variable in scope by more than its case (`countText` beside `COUNT`).
  [observed in a game project, r502 editor, 2026-09-24]
- `lerp(Self.X, Target.X, 0.1)` moves a different fraction per second at
  different framerates, and it ignores the time scale. If the third argument
  is a constant and the first is last tick's result, write `lerp(a, b, 1 -
  f^dt)` with `f` in (0, 1). The common approximation `f * dt` is not exact.
  The same holds for `anglelerp`. [manual:
  system-reference/system-expressions.md "dt", linking the delta-time
  tutorial, section "Lerp"; examples: magic-feather, surface-jump]
- If the factor comes from the engine, `lerp` needs no time of its own:
  `Self.Tween.Value("Attack")` in labyrinth, a timeline value, `unlerp` of a
  slider thumb, `Car.Speed / Car.MaxSpeed` in abductractor. These are
  mappings, not tweens, so leave them as they are. [examples: labyrinth,
  abductractor]
- `lerp` and `unlerp` do not clamp. `lerp(0, 100, 1.5)` is 150, and `unlerp`
  of a value outside its range goes past 0 or 1. Remap with `lerp(lo, hi,
  unlerp(a, b, v))`. If `v` can leave `[a, b]`, wrap it in `clamp`. [manual:
  system-reference/system-expressions.md "lerp", "unlerp", "clamp"; cheat
  sheet "Useful expressions and formulas", Remapping a range]
- `%` is the remainder and keeps the sign of the left operand, so `-1 % 5` is
  `-1`. To wrap an index that steps backwards, use `(n % max + max) % max`.
  [manual: project-primitives/events/expressions.md "%"; cheat sheet "Useful
  expressions and formulas", Wrapping around a number]
- There is no null or undefined. An expression is a number or a text, and a
  missing value reads as the number 0. `Array.At` outside the array,
  `Dictionary.Get` of a key that is not there, `Functions.ReturnValue` when
  nothing set it and a Timer's `CurrentTime` after a one-off timer fired
  all give 0. `Array.IndexOf` gives -1, `int("33xx")` is 33 and
  `int("xx33")` is 0. So `= 0` cannot tell an empty slot from a missing
  one. Test *Has key*, *Contains value* or `Array.Width` first, or use
  `Dictionary.GetDefault(key, fallback)`. [manual:
  plugin-reference/array.md "At", "IndexOf"; plugin-reference/dictionary.md
  "Get", "GetDefault", "Has key"; plugin-reference/function.md
  "ReturnValue"; behavior-reference/timer.md "CurrentTime";
  system-reference/system-expressions.md "int", "float"]
- JSON `Type(path)` reads `"undefined"` for a path that is not there, and
  `"array"`, `"object"`, `"number"`, `"string"`, `"boolean"` or `"null"`
  otherwise. So an expression can test presence, while *Has key* works only
  as a condition: `"layers." & name & (RunData.Type("layers." & name &
  ".alt") = "array" ? ".alt" : ".main")`. [runtime: exported c3runtime.js
  r504, JSON `_GetTypeOf` returns `_JSONTypeOf` of the value, `typeof` for
  anything but null and arrays]
- *For* runs from its start index to its end index inclusive, and counts down
  if the end is below the start. So `For 0 to count - 1` over an empty list
  runs for 0 and -1. `For first to last` with `first` past `last` runs
  backwards over unwanted indexes. Put `count > 0`, or `first <= last`, among
  the same event's conditions before the loop. [runtime: exported
  c3runtime.js r504, `_For` takes the `--e` branch when the end is below the
  start]

- A local variable placed as a sub-event or in a group is visible to every
  event at its level, before or after it, and to their sub-events, but not to
  the parent's own actions. Set it in a sibling block with no conditions,
  then read it in the others. Unless it is static, it resets to its initial
  value every time the scope is entered. [manual:
  project-primitives/events/variables.md "Local variables", "Static and
  constant variables"; example: galactic-blocks, group Controls, `StoredY`]
- *Set mesh point* in *Relative* mode adds to the point's current position,
  not to its default, so a per-tick derivation accumulates. Derive with
  *Absolute* and normalised coordinates (0..1 across the object box, values
  may go past it). A texture value of -1 leaves the texture position
  unchanged. [manual: plugin-reference/common-features/common-actions.md "Set
  mesh point"]
