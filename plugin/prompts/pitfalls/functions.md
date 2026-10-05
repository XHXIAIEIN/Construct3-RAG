# Event Sheet Pitfalls: Functions

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- A function's locals, declared as children of its block, are in scope for
  its sub-events but not for the block's own top-level actions. If such an
  action sets a local with *Set value*, the editor refuses to open the
  project with "cannot find event variable". So compute them in a child
  block after the declarations. [observed in a game project, r502 editor,
  2026-09-17]
- A function with a return type is an expression of the Functions object,
  under whatever name the project gave that object. Without parameters it is
  written `Functions.MyFunction`, with no parentheses; parameters go in
  parentheses, `Functions.MyFunction(1, 2)`. So `Functions.MyFunction`
  without `()` already calls it and returns the value. [manual:
  project-primitives/events/functions.md, "It can then be called using it as
  an expression"]
- Without *Copy picked*, a function resets every object to all its instances
  picked, so "modify this sprite" modifies every instance. [manual:
  interface/dialogs/function.md "Copy picked"]
- With *Copy picked*, type and family picks are copied separately. So a
  function that writes `Pieces.*` acts on whatever `Pieces` holds, even if the
  caller narrowed `Piece`. If shared logic acts only on the caller's picked
  instances of one object and returns nothing, make it a *custom action* on
  that object or family, not a function. A custom action runs on exactly the
  instances of its object that the caller picked. A family custom action
  called through a member type runs the family block on that member's picked
  instances. Inside a family block, write the family name (`Pieces.X`),
  because the block does not get the member type: `Piece.X` reads the first
  of all instances. [manual: project-primitives/events/functions.md
  "functions with no return type are essentially custom actions";
  project-primitives/events/custom-actions.md "Picking", "Family custom
  actions"; example: custom-action-overrides; observed in a game project,
  2026-09-17]
- A custom action runs once with every instance of its object that the caller
  picked, not once per instance. Its own actions apply to each of them. But a
  System condition or an expression that names the object (`System: Sword.kind
  ≠ ""`, `Sword.UID` in a tag) reads the first picked one. So a call over
  three instances decides for all three by the first. If the block decides per
  instance, put *For each* first among its conditions. [manual:
  project-primitives/events/custom-actions.md "Picking"; observed in a game
  project, r504 preview, 2026-10-01: a custom action called from a function
  that picked three swords, the first of them hidden and without a kind, did
  nothing for any; with *For each* first in the block, each sword with a kind
  played its move]
- Parameters are bare identifiers in expressions: `Self.X + OffsetX`, not
  `Functions.OffsetX` or `Self.OffsetX`. [example: 3d-castle-maze, function
  OffsetHand]
- A parameter and a variable of the function's group, or of a group around
  it, whose names match once case is ignored, do not both keep their names.
  As the editor opens the project, it renames the one that comes later in
  the sheet. A parameter `speed` after the group's constant `SPEED` becomes
  `speed2`. Every `speed` in the function then refers to `SPEED`, and the
  value a call passes is lost. If the function comes first, the editor
  renames the group's variable instead. An expression elsewhere in the group
  that names it then stops the open with `Unknown expression`. Of a
  function's parameters whose names match, the editor renames every one but
  the last, and every use refers to the last. A global of a parameter's name
  keeps its name and is hidden inside the function. Give each parameter a
  name that differs from the variables around it by more than case
  (`launchSpeed` beside `SPEED`). `check_project.py` refuses each of these,
  and warns about a global of the parameter's own type. [observed in a game
  project, r504 editor, 2026-10-05: two parameters named like variables of
  their group, once case is ignored, read the group's values; minimal
  projects, r495.2 and r504 editors, 2026-10-05]
- Two functions, or two custom actions of one object, whose names match once
  case is ignored, do not both keep their names. As the editor opens the
  project, it renames the second, `Beep` to `Beep2`. A call by either name
  then runs the first, so the second never runs. Give each function and
  custom action a name that differs from the others by more than case.
  `check_project.py` refuses both. [minimal projects, r495.2 and r504
  editors, 2026-10-05]
- If a function has no parameters, call it in an expression without
  parentheses: `Functions.settling`, not `Functions.settling()`. With the
  empty pair, the editor refuses the whole project with `Syntax error: ')'
  can't go here` and names each condition with the pair. `check_project.py`
  refuses it. [observed in a game project, r504 editor, 2026-10-01; in a
  minimal project, r504 editor, 2026-10-02]
