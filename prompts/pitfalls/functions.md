# Event Sheet Pitfalls: Functions

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- Function local variables declared as children of the function block are
  in scope for its sub-events, but NOT for the function block's own
  top-level actions: a `Set value` on the local there makes the editor
  reject the whole project at load with "cannot find event variable".
  Compute the locals in a child block placed after the declarations
  instead. [observed in a game project, r502 editor, 2026-09-17]
- Without *Copy picked* a function runs with every object reset to all picked:
  "modify this sprite" modifies every instance. [manual:
  interface/dialogs/function.md "Copy picked"]
- With *Copy picked*, type and family picks are copied separately. A function
  that writes `Bases.*` acts on whatever `Bases` happened to hold, even if the
  caller narrowed `base`. Shared logic that only acts on the caller's picked
  instances of one object and returns nothing is a *custom action* on that
  object or family, not a function: it runs on exactly the instances of its
  object the caller picked, and a family custom action called through a member
  type runs the family block on that member's picked instances. Inside a family
  block write the family name (`Bases.X`); the member type is not carried in
  and `base.X` reads the first of all instances. [manual:
  project-primitives/events/functions.md "functions with no return type are
  essentially custom actions"; project-primitives/events/custom-actions.md
  "Picking", "Family custom actions"; example: custom-action-overrides;
  observed in a game project, 2026-09-17]
- A custom action runs once, with every instance of its object that the
  caller picked, not once per instance. Its own actions apply to each of
  them, but a System condition or an expression that names the object
  (`System: Sword.kind ≠ ""`, `Sword.UID` in a tag) reads the first picked
  one, so a call over three instances decides for all three by the first.
  When the block decides per instance, put *For each* first among its
  conditions. [manual: project-primitives/events/custom-actions.md
  "Picking"; observed in a game project, r504 preview, 2026-10-01: a custom
  action called from a function that picked three swords, the first of
  them hidden and without a kind, did nothing for any; with *For each*
  first in the block, each sword with a kind played its move]
- Parameters are bare identifiers in expressions: `Self.X + OffsetX`, not
  `Functions.OffsetX` or `Self.OffsetX`. [example: 3d-castle-maze, function
  OffsetHand]
- A function without parameters is called in an expression without
  parentheses: `Functions.settling`, not `Functions.settling()`. The empty
  pair makes the editor refuse the whole project with `Syntax error: ')'
  can't go here`, naming each condition that holds it, and
  `check_project.py` lets it through. [observed in a game project, r504
  editor, 2026-10-01]
