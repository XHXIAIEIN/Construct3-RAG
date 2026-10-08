# Look Questions Measured Against Agent Labels

Date: 2026-10-08

## Problem

`scripts/review_look.py` ends with fixed yes/no questions about its
screenshots. Its brief gives them to a sub-agent that has not seen the
project, and the agent fixes each yes. Nothing showed how often a judge's
answers are right, or which questions it answers wrongly.

## Evidence

The set has 35 screenshots of 14 games and generated projects:

- 17 first screens, taken as `review_look.py` takes them
- 9 screens reached in play by a `preview_project.py` plan
- 9 copies broken on purpose in one way each: text over text, the HUD past
  the screen's edge, a text cut by its box, HUD text close to its
  background, stand-in boxes among finished art (twice), a bright patterned
  backdrop, a smooth gradient sign in a pixel-art scene, every kind of map
  node drawn alike

Most of these games are throwaway projects that small models built with
early versions of the skill. Their faults are many and plain, and few of
their screens are finished. Layouts that only store object types are left
out.

Agents play every role, each a Claude Code sub-agent that gets one brief
and nothing else:

- Labellers: two Opus agents label each screenshot apart, through the
  brief of `evals/label_look.py`. They answer each question with a reason,
  a no included, and say whether the screen would ship.
- Adjudicator: an Opus agent settles each question the two labellers
  answered differently. It sees their answers and reasons only, never a
  judge's. The labellers differed on 6 of the 35 screenshots.
- Judges: a Haiku agent and an Opus agent answer the brief that
  `review_look.brief` writes, one run per brief, the screenshots under
  neutral names.

`evals/judge_look.py --score` counts how often a judge agrees with the
labels. Most answers are no, so the baseline is a judge that answers no to
everything. The labels find a fault on 22 screenshots and none on 13.
Every broken copy got a yes on the question its break was made for.

The first wording asked about facts in the picture: two outline weights,
an object over another, anything the edge of the screen cuts. The second
asks what a player sees as a mistake, and names what each question is
about. Its brief adds that art layered on purpose is no mistake. Its
question 4 asks about stand-ins and objects drawn in a style of their own,
and its question 1 adds text too small or too faint to read. The labels
answer the second wording, so the first is compared by what a judge says
about the screens without a fault and about the faults put in on purpose:

| Wording | Judge | Yes answers on the 13 screens without a fault | Of those screens, with a yes | Screens with a fault that get a yes, of 22 | Faults put in on purpose found, of 9 |
|---------|-------|----|----|----|----|
| Facts | Haiku | 19 | 8 | 20 | 5 |
| Facts | Opus | 25 | 11 | 22 | 8 |
| Mistakes | Haiku | 5 | 5 | 21 | 7 |
| Mistakes | Opus | 2 | 2 | 22 | 8 |

The second wording cuts the yeses on screens without a fault from 25 to 2
(Opus) and from 19 to 5 (Haiku), and it finds as many faults. An agent that
fixes every yes no longer changes screens that are done.

Agreement with the labels under the second wording, out of 35 screenshots:

| Question | Labels yes | Haiku agrees | Opus agrees | All no agrees |
|----------|------------|--------------|-------------|---------------|
| 1. Text cut, wrapped, too small or faint, or partly hidden | 11 | 28 | 33 | 24 |
| 2. An object hides a text, a number, a button or a card's face | 5 | 31 | 34 | 30 |
| 3. A button, a text or the HUD cut by the screen's edge | 7 | 34 | 35 | 28 |
| 4. A stand-in or an object drawn in a style of its own | 11 | 34 | 35 | 24 |
| 5. A background or glow catches the eye first | 3 | 31 | 35 | 32 |
| 6. Two kinds look identical with nothing to tell them apart | 1 | 33 | 34 | 34 |

- Opus agrees with the labels on 33 to 35 screenshots a question, but the
  labellers are Opus too, so this is close to a model agreeing with itself.
  Haiku measures a judge that differs from the labellers.
- Haiku beats the baseline on questions 1 to 4. On question 2 it says yes
  on 1 screenshot to the labels' 5, so for the small model the question is
  too narrow.
- Haiku stays below the baseline on question 5, with 2 missed and 2 extra,
  and on question 6. The one screenshot with two kinds alike is the copy
  whose map nodes all look the same. Both labellers found it, and neither
  judge did: a judge that gives no reason per question looks less closely.
  The `frame` finding of `review_look.py` measures that case from the
  instances.
- The question about decoration repeated on every screenshot had one brief
  to answer it and is not measured.

The sample is 35 screenshots with one run per brief, and the labels come
from the model family of one judge. The second wording was written after
the first was read on the same set. The numbers show a direction for these
games, not a rate to expect elsewhere. The set, every reply, the labels and
the scores are in `.local/docs/evidence/look-judge/`. `judge_look.py
--model` runs `claude -p` as the judge when the client is signed in. The
runs here used sub-agents.

## Options

1. Keep the questions about facts. The judges flag most screens that are
   done.
2. Score each screen with a rubric or a free critic. That is another model
   to calibrate, and the first wording shows that a loose question makes a
   model report more, not more correctly.
3. Ask what a player sees as a mistake, each question naming the things it
   is about.
4. Keep only the measured finding lines. They miss stand-ins and faint text,
   which the labels find.

## Decision

Option 3. `review_look.py` asks the second wording, and its brief says that
art layered on purpose is no mistake. The set in
`.local/docs/evidence/look-judge/` is the regression set, labelled by agents
with `label_look.py`. A change to the questions or the brief has both
judges answer the set with `judge_look.py`. The change keeps Haiku's
agreement at or above these numbers, and the yeses on screens without a
fault at or below them. A new screenshot gets its labels the same way: two
labellers apart, and the adjudicator where they differ.

## Re-evaluate when

- Labels from another model family or from a person differ from the Opus
  labels on more than a few answers. The labels lean toward how Opus sees,
  so the agreement of an Opus judge then means little.
- Haiku stays below the baseline on question 5 or 6 over a larger set.
  Reword the question, or replace it with a measurement.
- A small-model judge keeps missing question 2. It then needs examples of
  what counts as hidden.
