# Event Sheet Pitfalls: Functions

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- A function's locals, declared as children of its block, are in scope for
  its sub-events but not for the block's own top-level actions. If such an
  action sets a local with `Set value`, the editor rejects the whole project
  at load with "cannot find event variable". So compute them in a child
  block after the declarations. [observed in a game project, r502 editor,
  2026-09-17]
- Without *Copy picked*, a function runs with all instances of every object
  picked, so "modify this sprite" modifies every instance. [manual:
  interface/dialogs/function.md "Copy picked"]
- With *Copy picked*, type and family picks are copied separately. So a
  function that writes `Bases.*` acts on whatever `Bases` holds, even if the
  caller narrowed `base`. If shared logic acts only on the caller's picked
  instances of one object and returns nothing, make it a *custom action* on
  that object or family, not a function. A custom action runs on exactly the
  instances of its object that the caller picked. A family custom action
  called through a member type runs the family block on that member's picked
  instances. Inside a family block, write the family name (`Bases.X`),
  because the block does not get the member type: `base.X` reads the first
  of all instances. [manual: project-primitives/events/functions.md
  "functions with no return type are essentially custom actions";
  project-primitives/events/custom-actions.md "Picking", "Family custom
  actions"; example: custom-action-overrides; observed in a game project,
  2026-09-17]
- A custom action runs once with every instance of its object that the
  caller picked, not once per instance. Its own actions apply to each of
  them. But a System condition or an expression that names the object
  (`System: Sword.kind ≠ ""`, `Sword.UID` in a tag) reads the first picked
  one, so a call over three instances decides for all three by the first.
  If the block decides per instance, put *For each* first among its
  conditions. [manual: project-primitives/events/custom-actions.md
  "Picking"; observed in a game project, r504 preview, 2026-10-01: a custom
  action called from a function that picked three swords, the first of
  them hidden and without a kind, did nothing for any; with *For each*
  first in the block, each sword with a kind played its move]
- Parameters are bare identifiers in expressions: `Self.X + OffsetX`, not
  `Functions.OffsetX` or `Self.OffsetX`. [example: 3d-castle-maze, function
  OffsetHand]
- In an expression, call a function without parameters without parentheses:
  `Functions.settling`, not `Functions.settling()`. With the empty pair, the
  editor refuses the whole project with `Syntax error: ')' can't go here`
  and names each condition with the pair. `check_project.py` refuses it.
  [observed in a game project, r504 editor, 2026-10-01; in a minimal
  project, r504 editor, 2026-10-02]
