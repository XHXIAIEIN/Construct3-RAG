# Construct 3 Event Sheet — Runtime Facts and Pitfalls

> Load this with [event-sheet-thinking.md](event-sheet-thinking.md) and
> [event-sheet-assistant.md](event-sheet-assistant.md). The design guide says
> how to shape events; this file lists runtime facts that a model gets wrong
> when it reasons from general programming intuition. Every entry carries a
> source. If you cannot cite one for a new entry, do not add it.

Sources are the official manual (paths relative to the `Construct3-Manual`
repository cloned alongside this one), the schema files under
`data/c3-schemas/`, official example projects by id, or an observation in a
named project on a given date and editor release. "Observed" means it ran,
not that the manual says so.

## Picking

**An instance with collisions disabled fails every overlap and collision test,
in both directions.** Other objects testing against it also get `false`. This
is the tool for taking an instance out of the world while it is dragged or
tweened; an `isMoving` flag is the wrong tool. Source:
`plugin-reference/sprite.md` *Set collisions enabled*;
`scripting/scripting-reference/object-interfaces/iworldinstance.md`
`isCollisionEnabled` ("will always fail all overlap or collision checks") and
`testOverlap` ("If either instance has collisions disabled, this will always
return false").

**A family and its member types are picked separately.** Narrowing `Piece`
never narrows `Pieces`, and the reverse. Two consequences: the same object
type can be picked as two independent lists in one event, and a function or
sub-event must refer to the same name the caller narrowed (see Functions).
Source: `project-primitives/objects/families.md`, section *Picking families in
events*.

**Container members are created, destroyed, and picked together. Hierarchy
children are not picked with their parent.** Setting text on a child `Text`
after picking its parent works when both are in a container; with hierarchy
alone it needs *Pick children*. Source: `project-primitives/objects/containers.md`
points 1–3; `plugin-reference/common-features/common-conditions.md`, section
*Hierarchy*.

**Sub-events run after the parent's actions.** A state change made by the
parent's actions is visible to the sub-event's conditions. Re-enabling
collisions in the parent and testing overlap in the sub-event is therefore
correct. Source: `project-primitives/events/sub-events.md` ("They run after
the parent event's actions have finished").

## Triggers and Else

**A trigger can fire with several instances picked.** Timer *On timer* fires
once with every instance whose timer elapsed in the same tick. Actions written
for "the one instance" (a *Pick nearest* to its position, a function call that
creates one object) then run once instead of once per instance. Add *For each*
after the trigger. Do not assume one picked instance for any trigger unless
its manual page says so; write `Self`-relative actions, and add *For each* when
the block calls a function or picks by one instance's position. Source:
`behavior-reference/timer.md`, note under *On timer*.

**Else is decided per block, not per instance.** It runs only if the previous
sibling ran for no instance at all. With three instances picked and one
passing the sibling's condition, Else does not run for the other two.
Per-instance branching is a second event with the inverted condition, or the
default-then-override pattern from the design guide. Source:
`system-reference/system-conditions.md` *Else* ("Run if the previous event did
not run").

**Else does not narrow.** The sibling's picks are discarded; Else starts from
what the parent event left picked, like any other sub-event. Else cannot
directly follow a trigger block; it can follow a normal sub-event inside one.
Source: same entry ("does not pick any objects"; "can only follow normal
(non-triggered) events"); `project-primitives/events/sub-events.md` for what
siblings start from.

## Functions

**Without *Copy picked*, a function runs with every object reset to all
picked.** "Modify the current sprite" modifies every instance. Source:
`interface/dialogs/function.md` *Copy picked*;
`project-primitives/events/functions.md`.

**With *Copy picked*, type and family picks are copied separately.** If the
caller narrowed through the family, the body must act on the family name. When
one function is called from a context that narrowed the type and from another
that narrowed the family, either pick the name that is narrowed in both, or
write the action so that running it on extra instances is harmless, for example
`Set attack to 10 * 2 ^ (Self.level - 1)`. Source: families.md as above.
Observed: `applyStats` in mergeGame, 2026-09-15, called after *Create object*
(type picked) and after a merge (family picked).

**Function parameters are referenced by bare name in expressions.** Official
example `3d-castle-maze` defines `OffsetHand(OffsetX, OffsetY)` and uses
`Self.X + OffsetX`. Prefer names that cannot be read as an object expression
(`posX`, not `x`); whether `x` is rejected is unverified, the point is
legibility.

## Timers

**The Timer behavior keeps time per instance and is the manual's recommended
replacement for subtracting `dt` from an instance variable.** Source:
`behavior-reference/timer.md`, introduction.

**Timer facts** from the same page: *Start timer* on a tag that already exists
restarts it with the new options. After *Stop timer*, or after a *Once* timer
fires, the timer no longer exists and its expressions return 0.
`CurrentTime(tag)` is seconds since *On timer* last fired; `Duration(tag)` is
the interval; remaining time is `Duration(tag) - CurrentTime(tag)`.

**A timer is state you start and stop, so list every transition before
choosing it.** For an attacker that must only run while settled on a battle
slot the transitions were: tween finished (start if overlapping the slot, else
stop), picked up (stop), displaced by a swap (stop). A `dt` countdown gated by
an overlap condition has no transitions to maintain but needs *compare + For
each* to dispatch. Both are valid; pick knowingly. Observed: mergeGame,
2026-09-15, both versions.

## Creating objects

**Create object picks only the new instance. With *Create hierarchy* the
created children are picked too. Container siblings are created as well.**
Source: `system-reference/system-actions.md` *Create object* and its tip;
`project-primitives/objects/containers.md` point 1.

**Whether the new instance is also picked in its families is not documented.**
Do not depend on it either way; see the idempotent-action pattern under
Functions.

**A runtime-created instance takes its properties from an existing instance,
or from the named template.** Keep one template instance of every
runtime-created object in a layout that never runs (an "ObjectRepository"
layout). Source: system-actions.md *Create object* ("based on the template
rather than an arbitrary instance"). Whether creation works when the object
has no instance in any layout is unverified; keep the template.

**Create object with a family creates a random member type.** Source:
system-actions.md *Create object*.

## Writing event JSON directly

The condition and action entry shape is documented for clipboard payloads in
`Construct3-Clipboard/docs/clipboard-format.md`; folder-project
`eventSheets/*.json` files use the same entries. Facts observed in
editor-written files (mergeGame, editor release recorded as
`savedWithRelease: 50000`, 2026-09-14):

- Comparison parameters are integers: 0 `=`, 1 `≠`, 2 `<`, 3 `≤`, 4 `>`,
  5 `≥`. Order confirmed in `data/c3-lang/en-US.json` under
  `ui/dialogs/parameters/controls/comparison`.
- String parameters carry their quotes: `"tag": "\"attack\""`. The layer
  parameter is either an index string `"2"` or a quoted name `"\"Graphics\""`.
  `create-hierarchy` is a JSON boolean. Inverted conditions carry
  `"isInverted": true`.
- A function call is `{"callFunction": "name", "sid": ..., "parameters":
  ["expr", ...]}`; the function block carries `functionCopyPicked` as a boolean
  and `functionParameters` entries with `name`, `type`, `initialValue`,
  `comment`, `sid`.
- Parameters added to an ACE in a later release may be omitted; the editor
  fills defaults on load. Every official example that uses
  `pick-nearestfurthest` (saved between r184 and r437) writes only `which`,
  `x`, `y`; the r495.2 schema also lists `z` and `pick-all-tied`.
- `sid` values are 15-digit integers unique across the whole project, `uid`
  values are unique across all layouts. Files are UTF-8 with raw non-ASCII,
  tab-indented, LF, no trailing newline.

Verify every `id` and parameter key against `data/c3-schemas/` before writing;
`plugins/_common.json` holds the ACEs shared by all world objects.

## Checking a project without a license

Observed on editor.construct.net, r495.2, 2026-09-15: a guest session is
limited to 25 events, a verified free account to 50; families are a paid
feature (`families.md` is marked `[Paid plans only]`). A project that uses
families cannot be previewed there without a licensed account.
`#open=<example-id>` opens an official example; opening a project from an
arbitrary URL through `#open=` did not work in that test and is unverified.
Structural checks that need no editor: JSON parses, every `objectClass` and
instance variable exists, `sid`/`uid` unique, every ACE `id` and parameter key
present in the schema, every called function defined with the right
parameter count.

## Adding an entry

One fact in bold, the consequence or the pattern that follows from it, then the
source. Allowed sources: a manual page path, a schema file, an official example
id, or "Observed: project, date, release". Manual wording wins over an
observation; an observation wins over intuition; intuition is not an entry.
