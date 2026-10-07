# Event Sheet Pitfalls: Random

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- Advanced Random has one number sequence. `Random`, `Weighted`,
  `WeightedByName` and *Create permutation table* all take numbers from it:
  a weighted draw takes one number, and a permutation table is shuffled
  from it when it is created. *Create probability table* (also from JSON)
  and *Add probability entry* take none. *Update seed* with a string starts the
  sequence again from the start of that seed, so the same string gives the
  same numbers, weighted draws and permutation every time. So two kinds of
  draws that share the sequence shift each other: one more card drawn
  changes every enemy after it. To make each kind reproducible on its own,
  set the seed before each draw to the run's seed, the use and a counter,
  `RunSeed & ":card:" & CardDraws`, and save the counter with the run.
  A permutation table of length n, 2 or more, takes n numbers, and *Shuffle
  permutation table* takes n again; *Remove probability entry* takes none.
  A script that sets the same seeds and makes the same draws in the same
  order gets the numbers the game got, so such a run is reproduced
  offline: `advanced_random.py` of the `construct3-agent-plugin` skill
  computes them as the plugin does, for a seed, a probability table or a
  permutation table. A Construct update could change the plugin's
  algorithm and with it every number after a seed. After an update, run
  `advanced_random.py --check` before trusting the offline numbers: it
  runs the plugin's code from the project's export, or with `--preview`
  from the editor's preview, with node and compares every value.
  [manual: plugin-reference/advanced-random.md, "Seed" and "Update seed";
  runtime code, `plugins/AdvancedRandom` in an r505 export's
  `c3runtime.js`: `_UpdateSeed` hashes the string and re-initialises the
  generator; observed in a game project, r505 editor, 2026-10-07: a re-set seed
  repeated `Random`, `WeightedByName` and the permutation, a draw from a
  probability table took one number, and two runs of one seed with
  different buying times dealt the same cards and enemies; c3runtime.js
  `plugins/AdvancedRandom` and `lib/misc/probability.js`, r504 Web export
  and r505 editor preview, 2026-10-07: `_CreatePermutationTable` and
  `_ShufflePermutationTable` shuffle with one draw per entry, and
  `advanced_random.py --check` found 1068 values over six seeds the same]
- With *Replace system random* off, `random()`, `choose()` and *Pick random
  instance* use the system random, which no seed controls. A draw that the
  seed must reproduce uses Advanced Random instead: an integer below `n` is
  `floor(AdvancedRandom.Random * n)`, and a random instance among the
  picked ones is *Pick nth instance* with
  `floor(AdvancedRandom.Random * Slot.PickedCount)`. *Pick nth instance*
  counts in the picked instances, in creation order, so a layout's
  instances come in the same order on every run. Leave *Replace system
  random* off when only some draws are part of the run, so that battle
  rolls and visual jitter do not consume the run's numbers.
  [manual: plugin-reference/advanced-random.md, "Replace system random";
  plugins/system.json, condition `pick-nth-instance`; observed in a game
  project, r505 editor, 2026-10-07]
