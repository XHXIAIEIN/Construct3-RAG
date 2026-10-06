# Scripted sequences

This page says how an attack pattern, a cutscene or a line of dialogue runs
from a data file, so that a designer edits the file and the events stay the
same. Read it before writing a boss fight with scripted attacks, a cutscene
of several cues, or dialogue with pauses, colours and a voice. Design first
with [event-sheet-thinking.md](../event-sheet-thinking.md); this page expands
its rows "a sequence scripted in data" and the smell "a cue list or dialogue
markup read with `mid`". Its mechanisms come from the official examples
named in each section and from a studied project read on 2026-10-06, marked
`studied`.

## A cue list

A sequence is a project file with one row per cue: the delay since the cue
before it, the cue's name, then its parameters. Write the delay as seconds
since the previous row, so a row can be moved or inserted without
renumbering the rest.

```
0,BoxResize,132,250,507,390
0.3,SpawnWall,bottom,15,180
0,SpawnWall,top,15,0
1.5,Gravity,down
3,Gravity,up
```

- **Load once.** When the sequence starts: AJAX *Request project file*,
  *Wait for previous actions*, then CSV *Parse CSV* from `AJAX.LastData` into
  an Array, in that one block ([event-sheet-thinking.md](../event-sheet-thinking.md),
  "Level data, loot tables"). The Array then holds one row per cue, and
  `Array.At(0, row)` is the delay, the row on the Y axis. A row that only names a label, such as
  `:loop`, goes into a Dictionary as its row index when the file loads, so a
  jump finds it without a search. [manual: plugin-reference/csv.md "Parse
  CSV"; studied]
- **Step with an accumulated clock.** One number `clock` gains `dt` each
  tick while the sequence runs. A *While* with the conditions `running`,
  `row < Array.Height` and `clock ≥ float(Array.At(0, row))` drains every
  cue that is due: it subtracts the row's delay from the clock, dispatches
  the cue, and adds 1 to the row. Several cues with delay 0 fire in one
  tick, in file order, and a cue is never late by more than a tick, because
  the clock keeps what the tick overshot. A Timer per cue loses that
  remainder at each restart. [studied]
- **Cap the steps.** Count the steps taken in one tick and stop the sequence
  with a message when the count passes a bound, such as 1000. A jump back to
  a label with no delay on the way never advances the clock, and without the
  cap it hangs the tick with no error shown. [studied]
- **Keep the file a cue list.** Variables, arithmetic, random choices and
  jumps in the file turn the sheet into an interpreter, and every new opcode
  is an event that no tool checks. Write a pattern that needs a loop or a
  random choice as a function with parameters, and call it from one row with
  its numbers. The file then holds only what a designer changes: when, which
  cue, with which numbers. [studied: a file of fifteen opcodes with `$`
  variables, read by seventy events]
- **Music in step.** If the attack pattern must stay on the music through a
  pause, one clock leads. Each tick, if `abs(Audio.PlaybackTime(tag) -
  clock)` passes a frame, *Seek to* the clock. The sequence's pause then holds the
  music's place too. [studied; the audio clock's own rules are in
  [pitfalls: Audio](../pitfalls/audio.md)]

## Dispatching a cue by its name

The cue's name is a string from the file, and a function map calls a
function by a string. At the start, *Map function to string* once per cue
name, and *Map default function* to a function that reports an unknown cue
with its row. Then the step calls *Call mapped function* with the row's
name. The parameters go through an intermediate function: call
`Cue(name, a, b, c, d)` with the row's fields as typed parameters, and
inside it *Call mapped function* forwards the parameters from index 1, so
each cue function declares only the parameters it uses, in the order the
file gives them. `Functions.CallMapped(map, name, ...)` returns a value
when the cue is a query. A project with cue names in the hundreds can
dispatch from a script block instead, with `runtime.callFunction(name,
...params)`. The deprecated Function plugin's *Call function* by name is
the same shape, and a migration replaces it with a map ([pitfalls:
Functions](../pitfalls/functions.md)). [manual:
project-primitives/events/functions.md "Function maps"; example:
function-maps, events 7 to 10; data/c3-ts-defs/preview/interfaces/IRuntime.d.ts
`callFunction`]

## A cue that waits for a motion

A cue such as "resize the box, then go on" starts a tween and must hold the
sequence until the tween ends.

1. The cue function starts the tween and stores the name of the cue to
   resume with, then sets `running` to 0.
2. The tween's *On finished* is a top-level event of its own ([pitfalls:
   Triggers and Else](../pitfalls/triggers-and-else.md)). It reads the stored
   name, clears it, and calls that cue through the map, which sets `running`
   back to 1.
3. A motion of several tweens, one per edge of a box, keeps a progress latch
   per tween, set to 1 in its *On finished*, and resumes when every latch is
   1. Clearing the stored name makes the resume run once, whichever tween
   ends last ([feel.md](feel.md), "A battle box").

[studied]

## Dialogue

The baseline is the Text or Sprite Font object's own *Typewriter text*: the
line appears over a duration, *Is running typewriter text* says that it
still types, *On typewriter text finished* ends it, and *Finish typewriter*
is the skip. Use it when the line needs no pause and no voice.
[plugins/text.json and plugins/spritefont2.json `typewriter-text`]

- **Pauses, a voice, a speed that changes.** One Text or Sprite Font object
  and a count of shown characters. A regular Timer at the interval per
  character runs *On timer*: add 1 to the count, *Set text* to `left(line,
  count)`, and play the voice ([sound.md](sound.md), "A dialogue voice"). A
  pause mark at the count restarts the Timer with the pause's length, which
  *Start timer* on the same tag does. A skip sets the count to `len(line)`
  and stops the Timer. [manual: behavior-reference/timer.md "Start timer";
  studied: a per-instance `Timer` variable minus `dt`, with the same shape]
- **Parse the markup once per line.** A line such as `<color red>Hi<pause
  3> there` is split when the line starts, into the plain text and a second
  Array as long as the text, holding at each index the tag that applies
  there. The typing event then reads one index per character: if the tag
  Array holds a tag at the count, one *Compare* per tag kind applies it,
  with the tag's parts from `tokenat(tag, i, " ")`. Reading the raw line
  with `mid` one character at a time, every tick, inside a *While*, is the
  smell row of the design guide. Write a colour in a tag as three numbers,
  `<color 255 0 0>`, or as a name that a Dictionary maps to `rgbEx`, so no
  event decodes hex by hand. [studied: tags, a localisation key and a pause
  mark parsed per character in a *While* of ninety events]
- **Glyphs that move.** Only when a glyph shakes or waves on its own does
  each one become an instance: one Sprite Font instance per character,
  made a child of the line's object with *Add child*, so it follows the
  line and is destroyed with it, with its own Sine or Tween. Its X is the
  sum of `CharacterWidth` of the characters before it. The parent is a
  hierarchy relation, not a UID written into the instance's coordinates.
  [event-sheet-thinking.md rule 1; studied: the parent's UID passed as the
  X of *Create object*]
- **Arguments in a line.** `StringSub("{0} takes {1} damage", name, n)`
  ([event-sheet-style.md](../event-sheet-style.md), "UI text"), so a
  translator reorders the arguments by moving `{0}` and `{1}`. [manual:
  system-reference/system-expressions.md "StringSub"; studied: `%` filled
  in order]

## Localisation

The Internationalization plugin holds the strings: one JSON file per
language with a `locale` key and a `strings` object, loaded with *Load from
JSON* from AJAX, *Set locale*, then `Lookup(path)` where a dot steps into a
nested object. It also formats numbers and plurals for the locale. The
examples' simpler form is an Array project file with one row per language
and one column per string, read as `Strings.At(language, index)` when the
language changes. A hand-written JSON with one root per language and a
lookup function that returns the key when *Has key* fails works too, and
then a missing translation shows its key on screen, where a tester sees it.
In that JSON, a key with a dot in it must be escaped in the path
([pitfalls: Expressions](../pitfalls/expressions.md)); keys without dots
avoid it. A font per language is a Sprite Font per language, its widths in
*Spacing data* ([pitfalls: Rendering](../pitfalls/rendering.md)). [manual:
plugin-reference/internationalization.md "The translation file", "Looking up
localized strings"; examples: internationalization, languages-from-json
events 2 to 5; studied]
