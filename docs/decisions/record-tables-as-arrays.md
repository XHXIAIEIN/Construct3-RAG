# A Table of Records Is an Array File, Copied into a Dictionary at Start

Date: 2026-10-04

## Problem

The generator template kept a table of records, such as cards or enemies, as a
Dictionary file with one flat key per field, `"strike.cost"`. A generated card
game followed it and wrote one such file of more than 600 keys, most of them 0.
Nobody can read or change that file as a table: the editor shows a Dictionary
as one long list of keys, and adding a field means a new key for every record.

## Evidence

- 33 files of the official examples are Arrays and 20 are Dictionaries. The
  Arrays that hold records keep one record per row and one field per column:
  grukkle-onslaught `Enemies.json` (7 fields, 33 rows) and `Towers.json`,
  eventide `Waves.json`, meowgix `Projectiles.json`. The editor opens such a
  file in its Array editor as a grid.
- Those examples read a field by its column number, `Enemies.At(3, id)`,
  where a reader has to know which column 3 is.
- Copying the Array into a Dictionary at start keeps the field names in the
  events: a preview of the template's test project loaded a two-record table
  and read `Cards.Get("guard.block")` as the number 5.

## Options

1. A Dictionary file with flat keys. Reads by name, but the file is not a
   table.
2. An Array file read by column number, as the examples read it. The file is a
   table, but the events read numbers.
3. An Array file with field names in row 0 and ids in column 0, copied into a
   Dictionary by a loop at start. The file is a table and the events read names.

## Decision

Option 3. `record_table()` in `assets/build_project.py` writes the Array from a
dict of records, `load_data_file()` loads it, and `table_to_dictionary()` adds
the event that copies each cell to the key `<id>.<field>`. `dictionary_file()`
stays for a few named values, such as settings. The `data` finding of
`review_design.py` names the same form.

## Re-evaluate when

The runtime gains a way to read an Array cell by a header name, or a project
needs a table too large to copy at start.
