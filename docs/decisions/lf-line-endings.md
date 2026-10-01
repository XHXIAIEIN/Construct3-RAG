# Every Text File Is LF, in the Repository and in Every Checkout

Date: 2026-10-02

## Problem

Several agents work on this repository at once, each in its own worktree,
some through the Windows git, some through a git inside a sandbox or WSL,
and the update workflow runs on Linux. The repository had no
`.gitattributes`, so each git decided line endings from its own
`core.autocrlf`, and edits that changed no content showed up as whole-file
changes that then conflicted with other branches.

## Evidence

- The Windows git on this machine has `core.autocrlf=true` in its system
  configuration and checks text files out with CRLF. A git with
  `core.autocrlf=false` reading such a checkout reported 1498 files modified
  with no edit made.
- 150 files under `data/c3-ts-defs/` were stored with CRLF, the bytes the
  CDN ships, written unchanged by `C3Fetcher`. A tool that rewrites one of
  them with LF, as most agent edit tools do, changed every line: 241 of 241
  for `preview/interfaces/IRuntime.d.ts`.
- The r476.2 sync commit flipped the line endings of about a hundred of those
  definitions, and of `src/config.py`, with no content change.

## Decision

`.gitattributes` holds `* text=auto eol=lf`, and the 150 CRLF files were
renormalized to LF in the same commit. The attribute takes precedence over
`core.autocrlf`, so every checkout has LF whatever the machine's settings,
and a file written with CRLF, by an editor, a Python script on Windows or
the CDN, is stored as LF without a diff. `text=auto` leaves files git
detects as binary, the PNG icons, untouched.

With the attribute in place, the same checkout read with
`core.autocrlf=false` reports no change, and the LF rewrite of
`IRuntime.d.ts` produces no diff.

The CDN bytes of the TypeScript definitions are not kept: nothing reads
them in a way that depends on the line ending, and keeping them would keep
the whole-file diffs.

## Consequence

A checkout made before this change keeps its CRLF files until git rewrites
them; `git status` stays clean meanwhile. No file in the repository needs
CRLF; one that does, a `.bat` for example, gets its own `eol=crlf` line.
