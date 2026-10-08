# An Index Says Which Official Examples Use Each ACE

Date: 2026-10-08

## Problem

`lookup_ace.py` gives an ACE's id, parameters and the JSON to write. It does
not show the events around a real use: the trigger it sits under, what
follows a *Wait*, which sub-events read its result. The official examples
hold those shapes, and `print_sheet.py` reads them as events.
`search_guides.py` finds an example by the words of its topic. An agent that
holds an ACE therefore has no way to an event that uses it.

## Evidence

For the conditions and actions checked, the counts of the index equal a
plain text search of the sheets for the same id. No agent eval has measured
whether agents run the printed commands.

## Options

- Search the clone at lookup time. The `Construct-Example-Projects` clone
  holds every example's images and sounds, and it is often missing beside a
  plugin install. A lookup would also have to read every sheet.
- An index built from the clone once, committed with the other data, and
  read offline by the lookup.
- An index that lists every use. It is several times larger, and the lookup
  prints three.

## Decision

`scripts/example_usage.py` reads every event sheet of the clone and writes
`data/c3-example-usage/`: one file per plugin and behavior, keyed by its
schema id, and `_source.json` with the clone's commit. For each condition,
action and expression a file gives `examples`, the number of examples that
use it, and `read`, up to three uses as example folder, sheet, and the first
and last event as `print_sheet.py` numbers them. The same commit of the
clone gives the same files. The format is in `docs/guide/data-format.md`.

- The key is the addon id, not an object name. A lookup through an object
  of the project, the plugin's name or a behavior's name therefore reads
  the same entry. The ACEs every world object shares are under
  `plugins/_common.json`, as in the schemas.
- The uses are ordered by the size of their sheet in numbered events, then
  by folder, sheet and event, so the first command is a short read. A use is
  the first event in the example's smallest sheet that uses the ACE, with up
  to seven of its sub-events, the events that read its result.
- An expression is counted where a parameter of an expression type writes
  it: `Player.X`, `Player.Platform.VectorX`, `Self.X` as the object of its
  condition or action, and a System expression such as `random(1, 5)` by
  name. Text inside quotes is not read, and a name that the project declares
  as a variable or a function parameter is that variable.
- An example written in both languages is two folders, `<id>-js` and
  `<id>-ts`, with the same events. It counts once, read from the `-js`
  folder.
- `scripts/init.py` rebuilds the index after the CDN export, from the clone
  beside this repository. The update workflow has no clone, so it keeps the
  committed index. When the clone gets new commits,
  `python scripts/example_usage.py` rebuilds the index from them.

`lookup_ace.py` prints the count after each entry it prints in full, and the
`print_sheet.py` commands under it when the clone lies beside
Construct3-RAG. Without the clone, the count stays and one line gives the
command that clones it. An entry that no example uses prints no count. A
list of seven or more entries prints one line each and no counts, since the
agent narrows it first. An entry that fits `--limit` only without these
lines prints without them, because the limit protects the output a harness
reads. Without the index, the lookup prints the entries alone.

`plugin/` carries the index as one bundle (`plugin-folder.md`).

## Re-evaluate when

- An eval shows that agents do not run the printed commands, or run them and
  still write the ACE wrong.
- The update workflow gets a copy of the examples clone, which would let it
  rebuild the index with each release.
- The index outgrows one bundle by much, which would call for fewer uses per
  ACE.
