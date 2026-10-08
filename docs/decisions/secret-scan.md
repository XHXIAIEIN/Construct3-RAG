# A key a web export would ship is a warning, and stops the export

Date: 2026-10-08

## Problem

A web export ships every string of the events, the scripts and the project
files, and every player can read them in the browser's tools. A game that
calls a service, a language model or a leaderboard, needs a key, and an agent
asked to make the call writes the key where the call is: into an AJAX header
in an event or into a script. Once the game is published, every player can
read the key, and the user pays for its use until it is revoked.

## Evidence

A scan of whole lines over the official examples and the game projects
flags only lines of a minified decoder that one example bundles in its
files: long identifiers, a base64 alphabet and an embedded binary. A key
sits in a text literal, so in code the scan reads the literals; with the
rules below it finds nothing in those projects.

## Options

- A sentence in the export reference: it reaches the agent that reads the
  reference before exporting, and not the one that writes the key.
- A checker error: the editor opens such a project, and a key meant to be
  public, as some services issue for web pages, would fail every check.
- A checker warning at the place, which reaches the agent after each edit,
  and an export that stops on the same finding until the key moves out or is
  marked public.

## Decision

The third. `c3project.py` reads the strings a web export ships: the
parameters of conditions and actions, the values of variables and the lines
of script blocks in every sheet, and the lines of the script files and the
text files `project.c3proj` lists. Comments, group descriptions and names stay
in the editor and are not read. `check_project.py` warns of a string shaped
like a key with its place, `sheet Game event 7 action 2`, and so does
`edit_sheet.py` for a plan that writes one. `export_project.py` stops before
the browser starts and names the places, 20 at most. It also names the hosts
of the addresses the game holds, for the user to confirm.

A string is shaped like a key when it holds:

- the key of a common service, by its documented prefix: OpenAI, Anthropic,
  Google, AWS, GitHub, Slack, a Stripe secret key, a private key block or a
  signed token (JWT);
- or a random-looking token in a text literal: 32 to 512 letters, digits and
  `-_+/=`, with letters and digits among them and a character that repeats,
  and at least 3 bits of entropy per character when it is hexadecimal, or
  mixed case and at least 4.3 when it is not.

In code, an expression or a script, only the text literals are read for a
random token, because identifiers are long words, not keys. An address up to
its query and a picture in a `data:` URI are left out, and so is a token over
512 characters, which is data. A token whose every character differs is an
alphabet written out, and one made of words and short numbers joined by `_`
or `-`, such as `Draco_Float32Array_GetValue_1`, is a name. The finding shows the first characters and never the
key, so the transcript does not carry it.

A key meant to be public stays when `allow-secret` is in the comment above
the event, in the variable's comment, or on the line of a script or a text
file. The mark sits beside the key so that a reader of the event or the line
sees the decision.

## Re-evaluate when

- A key of a service the agents call is missed: add its prefix to
  `KEY_SHAPES`.
- A game the user publishes is flagged for a string that is no key: read its
  shape before loosening a threshold, and measure the change over the
  official examples again.
