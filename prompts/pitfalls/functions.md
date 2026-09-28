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
- Parameters are bare identifiers in expressions: `Self.X + OffsetX`, not
  `Functions.OffsetX` or `Self.OffsetX`. [example: 3d-castle-maze, function
  OffsetHand]
