# A Pack Carries a Passing Check

Date: 2026-10-16

## Problem

`SKILL.md` names `check_project.py` as the last complete file check before
a hand-over, and `pack_project.py` as what packs a project handed over as a
file. No check ties the pack to the check: a pack that takes the folder as
it is can carry an edit made after the last check, or files that the last
check refused. A hand-over can then name a check that the file did not
pass.

Evidence: another skill's pipeline refuses to package files whose SHA-256
differs from its check report's, and tests that refusal. Here, a copy of an
official example packs after a passing check, refuses after an edit to one
event sheet, and packs with `--unchecked`
(`tests/test_skill_pack_project.py` pins the five cases).

## Options

- Say it in `SKILL.md` alone: a sentence binds only an agent that follows
  it, and nothing checks it.
- Run the checker inside the pack: a second run of the whole checker in
  every pack, and two places that decide what passes.
- Read the checker's own record: `check_project.py` writes
  `.tmp/check-project.json` for the fix loop, with a digest of
  `project.c3proj` and the editor's JSON files. The pack compares that
  digest with the files at present and reads the number of problems.

## Decision

The third. The checker writes its record on every run that keeps one, a
passing first run included: `project`, the digest; `problems`, the number
of errors; `findings`. `c3project.py` owns the digest, so the checker and
the pack compute it in one place. The pack of a folder project goes ahead
only when:

1. the record exists;
2. its digest equals the digest of the files at present;
3. `problems` is 0.

Otherwise the script writes nothing, names the condition that failed,
prints the check command and exits with 3. `--unchecked` packs anyway and
says so on stdout. An archive repacked or unpacked needs no record.
`--review` and `CONSTRUCT3_RAG_NO_RECORD=1` keep none.

The digest covers `project.c3proj` and the JSON files of the listed
folders. It does not cover the bytes of images, sounds or scripts, or
whether a listed file exists, so a deletion or a rename after the check
passes the digest. `export_project.py` and `open_in_editor.py` build their
copies from the same file list without the record, because each hands the
result to the editor, whose load reads every file.

## Re-evaluate when

A hand-over's `.c3p` carries a problem that the checker reports on the
folder: a file the check reads lies outside the digest, such as a listed
image deleted after the run. Or the export becomes the deliverable and
needs the same gate.
