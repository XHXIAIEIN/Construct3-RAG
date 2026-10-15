# Event Sheet Pitfalls: Expressions

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- `Self` is the object of the condition or action that holds the expression.
  A System condition or action, *For Each (ordered)* included, has no such
  object, so the editor refuses to open the project with `Invalid use of
  'self'`. Write the object: order *For each Segment* by `Segment.IID`, not
  `Self.IID`. [editor message `Invalid use of 'self'`; observed in a game
  project, 2026-09-22]
- A local or global variable or a function parameter named like a system
  expression is read as the expression. A local number `mid` passed as
  `Functions.Measure(mid)` is read as the text function `mid()`, so the
  editor refuses the whole project with
  `Invalid expressions ... parameter 0 does not take 'string'`. A parameter
  `round` used as `"Round " & round` stops the editor with
  `'round' does not accept 0 parameters`, and `roundNo` opens. Give each
  variable and parameter a name that no system expression has (`probe`, not
  `mid`; not `left`, `right`, `len`, `find`, `max`, `min`, `abs`, `round`).
  `check_project.py` refuses both kinds of name.
  [plugins/system.json, expression `mid`; observed in a game project, r495.2
  editor, 2026-09-23; the parameter case observed in a game project, r504
  editor, 2026-09-30; both in minimal projects, r504 editor, 2026-10-02]
- The editor matches variable names without regard to case. A local named
  like a global hides the global in the local's scope. A local string
  `count` declared in an event hides the global constant `COUNT` in that
  event's sub-events. So `COUNT - 1` there uses the string, and the editor
  refuses the whole project with `Type mismatch: - does not work with
  'string' and 'number'`, naming the sub-event. Two locals such as `step`
  and `STEP`, one in the other's list or in a list below it, do not both
  keep their names. As the editor opens the project, it renames the one
  that comes later in the sheet, `STEP` to `STEP2`. Every use of either
  name then refers to `step`. Two globals both keep their names, and every
  event refers to the one declared first. Give each variable a name that
  differs from every variable in its scope by more than its case
  (`countText` beside `COUNT`). `check_project.py` refuses each of these,
  and warns about a local of the global's own type, which hides the global
  too. [observed in a game project, r502 editor, 2026-09-24; the renaming in
  minimal projects, r495.2 and r504 editors, 2026-10-05]
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
- `%` is applied before `*`, so `a * b % c` is `a * (b % c)`. The test
  `loopindex("i") * 100 % 1000 = 0` reads `loopindex("i") * 100 = 0` and
  holds for no tick of a loop from 1. Put the product in parentheses:
  `(loopindex("i") * 100) % 1000 = 0`. [observed in a minimal project,
  stable editor preview, 2026-10-07: a loop drew a line 4 px wide where the
  test held and 2 px wide otherwise; with the parentheses the wide lines
  stood at 1000, 2000 and 3000, and without them every line was 2 px wide]
- There is no null or undefined. An expression is a number or a text, and a
  missing value reads as the number 0. `Array.At` outside the array,
  `Dictionary.Get` of a key that is not there, the deprecated Function
  plugin's `Function.ReturnValue` when nothing set it and a Timer's
  `CurrentTime` after a one-off timer fired all give 0. `Array.IndexOf`
  gives -1, `int("33xx")` is 33 and `int("xx33")` is 0. So `= 0` cannot
  tell an empty slot from a missing one. Test *Has key*, *Contains value*
  or `Array.Width` first, or use
  `Dictionary.GetDefault(key, fallback)`. [manual:
  plugin-reference/array.md "At", "IndexOf"; plugin-reference/dictionary.md
  "Get", "GetDefault", "Has key"; plugin-reference/function.md
  "ReturnValue"; behavior-reference/timer.md "CurrentTime";
  system-reference/system-expressions.md "int", "float"]
- Dictionary *Set key* changes only an existing key and silently ignores
  a missing one. *Add key* creates or overwrites, so write gates and
  counters with *Add key*. [manual: plugin-reference/dictionary.md
  "Add key", "Set key"; runtime: `scripts/c3runtime.js` of an exported
  r503/r504 web build, `SetKey(t,e){this._data.has(t)&&...}`, `AddKey`]
- JSON `Type(path)` reads `"undefined"` for a path that is not there, and
  `"array"`, `"object"`, `"number"`, `"string"`, `"boolean"` or `"null"`
  otherwise. So an expression can test presence, while *Has key* works only
  as a condition: `"layers." & name & (JSON.Type("layers." & name &
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
  constant variables"; example: galactic-blocks, group Controls, `StoredY`;
  observed in a minimal project, r506.2 editor, 2026-10-16: an event whose
  own action set a local declared among its sub-events stopped the open
  with `cannot find event variable`, and `check_project.py` refuses it as
  not in scope]
- *Set mesh point* in *Relative* mode adds to the point's current position,
  not to its default, so a per-tick derivation accumulates. Derive with
  *Absolute* and normalised coordinates (0..1 across the object box, values
  may go past it). A texture value of -1 leaves the texture position
  unchanged. [manual: plugin-reference/common-features/common-actions.md "Set
  mesh point"]
- The JSON plugin reads a path as keys separated by dots, so a key with a
  dot in it, `"menu.title"`, is looked for as `menu` and then `title`
  inside it, and *Has key* fails. Escape the dot in the path with a
  backslash, `my\.key`, and a backslash in a key with two, `my\\key`. An
  expression string has no escape character of its own, only the doubled
  quote, so `"my\.key"` is written as it is. Keys without dots need none
  of this, and a Dictionary reads every key whole. [manual:
  plugin-reference/json.md "Escaping",
  project-primitives/events/expressions.md on double quotes; observation in
  a studied project, 2026-10-06]
- A variable at the root of a sheet, outside every group and event, is a
  global: every sheet of every layout reads it, included or not, and it
  keeps its value between layouts. Only a variable inside a group or under
  an event is local. So a variable meant for one sheet goes into a group at
  the top of that sheet, *static* if it must keep its value from tick to
  tick. [manual: project-primitives/events/variables.md "Variables at the
  root level of the event sheet ... become global variables", "Global
  variables"; observed in a minimal project, r506.2 preview, 2026-10-16: a
  root variable of a sheet no layout uses read its value from the layout's
  sheet]
- `tokencount("", ",")` is 1, not 0, and `tokencount("a,", ",")` is 2: the
  count is the separators plus one, whatever the text. So *Repeat
  tokencount(list, ",")* over an empty list runs once, with `tokenat`
  reading `""`. Test `list ≠ ""` among the event's conditions before the
  loop, or skip an empty token inside it. [manual:
  system-reference/system-expressions.md "tokencount", which gives only a
  non-empty example; observed in a minimal project, r506.2 preview,
  2026-10-16: `tokencount("", ",")` read 1, `tokencount("a", ",")` 1,
  `tokencount("a,b", ",")` 2 and `tokencount("a,", ",")` 2]
- A local that is not static resets to its initial value whenever its scope
  is entered, and a group's scope is entered every tick. So a value set in
  one trigger is gone when a trigger of a later tick reads it: Timer *On
  timer*, AJAX *On completed*, JSON *On parse success*, a tween's *On
  finished*. The later trigger reads the initial value, and nothing warns;
  in the setting trigger's own tick the value is still there. Make the
  local static, or keep the value in a global or an instance variable.
  [manual: project-primitives/events/variables.md "Static and constant
  variables", "reset to their initial value whenever entering their scope
  (usually every tick)"; observed in a minimal project, r506.2 preview,
  2026-10-16: a group's local set to 5 in *On start of layout* read 5 in
  the same event and 0 in *On timer* 0.3 s later, while a static local
  beside it read 5]
- *Set value* on a number variable, global, local or instance, with a text
  parses it: a text that starts with a number stores that number, `"12"`
  and `"12px"` 12, `"1.5"` 1.5, and a text that starts with none, such as
  `"abc"`, stores NaN, not 0. NaN prints as `NaN`, fails every comparison,
  `= 0` and `< 1` included, and `NaN + 1` is NaN, so a `= 0` guard never
  catches it and it spreads through every sum. Convert the text first with
  `int(text)` or `float(text)`, which give 0 for a text without a number,
  or declare the variable as text. [observed in a minimal project, r506.2
  preview, 2026-10-16: a number global and a number instance variable set
  to `"abc"` held NaN, `numStr & ""` read `"NaN"`, `numStr = 0` and
  `numStr < 1` both read 0, `numStr + 1` NaN; `"12"` and `"12px"` stored
  12, `"1.5"` 1.5]
- A local is visible to every event at its level, before or after its
  declaration, but the declaration is an event of its own: when the tick
  reaches it, a local that is not static is set back to its initial value.
  So a value written by an event above the declaration is gone for the
  events below it, in a group and among sub-events alike, and nothing
  warns. A static local keeps its value through its declaration. Declare a
  local above the first event that writes it. [manual:
  project-primitives/events/variables.md "Local variables", which says only
  that events at the same level can access it; observed in a minimal
  project, r506.2 preview, 2026-10-16: an event above the declaration set a
  group's local to 5 and read 5, the event below the declaration read 0
  every tick, the same among the sub-events of one event; a static local
  counted up above its declaration read the same count below it]
