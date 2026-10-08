# Look Questions Measured Against the User's Labels

Date: 2026-10-08

## Problem

`scripts/review_look.py` ends with fixed yes/no questions about its
screenshots. Its brief gives them to a sub-agent that has not seen the
project, and the agent fixes each yes. Nothing showed that the answers agree
with the person whose games they judge.

## Evidence

The set has 35 screenshots of 14 of the user's own and generated games:

- 17 first screens, taken as `review_look.py` takes them
- 9 screens reached in play by a `preview_project.py` plan
- 9 copies broken on purpose in one way each: text over text, the HUD past
  the screen's edge, a text cut by its box, HUD text close to its
  background, stand-in boxes among finished art (twice), a bright patterned
  backdrop, a smooth gradient sign in a pixel-art scene, every kind of map
  node drawn alike

Layouts that only store object types are left out. On the page of
`evals/label_look.py`, the user answered every question for every
screenshot. The user also said whether the screen would ship, with a note.

Each judge was a Claude Code sub-agent whose whole task was the path of a
brief that `review_look.brief` wrote: one brief per run of `review_look.py`,
the screenshots copied under neutral names. Each brief had one run per
model, Opus and Haiku. `evals/judge_look.py --score` counts the agreement
per question. Most answers are no, so the baseline is a judge that answers
no to everything. The question about decoration repeated on every
screenshot had one brief to answer it, so it is not measured.

Agreement with the user, out of 35 screenshots:

| Question, round 1 wording | User yes | Haiku yes | Opus yes | Haiku agrees | Opus agrees | All no agrees |
|---------------------------|----------|-----------|----------|--------------|-------------|---------------|
| 1. Text cut, wrapped or over another object | 10 | 14 | 18 | 23 | 21 | 25 |
| 2. An object covers another | 6 | 17 | 21 | 22 | 20 | 29 |
| 3. An object cut by the screen's edge | 4 | 13 | 13 | 26 | 26 | 31 |
| 4. Two outline weights, shadows, fills or edge kinds together | 2 | 15 | 22 | 20 | 13 | 33 |
| 5. A background larger or brighter than what the player acts on | 6 | 8 | 15 | 25 | 20 | 29 |
| 6. Two kinds look identical | 2 | 6 | 6 | 29 | 29 | 33 |

- Every question agreed with the user less often than the baseline. The
  judges missed little, 0 to 4 faults a question, and said yes far more
  often than the user: 73 times (Haiku) and 95 times (Opus) against the
  user's 30. The stronger model said yes more often.
- The extra yeses were facts the questions asked for literally, which the
  user does not count as faults: two outline weights, scenery running past
  the screen's edge, a character standing on a tile, a sign in front of
  scenery, a glow brighter than the player.
- The user would ship 17 of the screens. Opus answered yes on 15 of them and
  Haiku on 10, so an agent that fixes every yes changes screens that are
  done.
- The user's own answers predicted "would not ship" on 30 of 35 screens.
  Four screens that would not ship had no yes. Three notes name stand-in
  art among finished art, a sign drawn in another style, and the layout of
  text inside cards; the fourth screen has no note. No question asked about
  stand-ins or faint text.

In round 2, each question asks what a player sees as a mistake and names
what it is about. The brief adds that art layered on purpose is no mistake.
Question 4 asks about stand-ins and objects drawn in a style of their own,
and question 1 adds text too small or too faint to read. The same set and
the same judges were scored against the same labels. The user labelled
once, so these labels answer the round-1 wording:

| Question, round 2 wording | User yes | Haiku yes | Opus yes | Haiku agrees | Opus agrees | All no agrees |
|---------------------------|----------|-----------|----------|--------------|-------------|---------------|
| 1. Text cut, wrapped, too small or faint, or partly hidden | 10 | 14 | 13 | 25 | 22 | 25 |
| 2. An object hides a text, a number, a button or a card's face | 6 | 1 | 6 | 30 | 33 | 29 |
| 3. A button, a text or the HUD cut by the screen's edge | 4 | 8 | 7 | 31 | 32 | 31 |
| 4. A stand-in or an object drawn in a style of its own | 2 | 10 | 11 | 25 | 24 | 33 |
| 5. A background or glow catches the eye first | 6 | 3 | 3 | 28 | 28 | 29 |
| 6. Two kinds look identical with nothing to tell them apart | 2 | 1 | 0 | 32 | 33 | 33 |

- The judges said yes 37 times (Haiku) and 40 times (Opus). Of the 17
  screens the user would ship, Opus answered yes on 8 and Haiku on 9.
- Opus beat the baseline on questions 2 and 3 and matched it on 6. Haiku
  beat it on 2 and matched it on 1 and 3.
- The user's labels for question 4 answer the old question. Both models
  answered the new one yes on every screen whose note names a stand-in or
  an odd style, four screens. Their other yeses were the other stand-in
  copy, stand-in boxes in a component demo the user ships, and blurred or
  hard-cut edges.
- Questions 4 and 5 stay below the baseline for both models, question 1
  for Opus and question 6 for Haiku. On question 5 the judges now say yes
  on 3 screens to the user's 6. Both find the bright backdrop, and both miss
  decorations brighter than the board and several bright elements that
  compete for the eye.

A label can be wrong, and a label for the old wording can be right for it
and wrong for the new one. So every screenshot and question on which the
user and the two round-2 judges did not all agree, 48 of 210, went to a
third Opus sub-agent. It saw the screenshot, the current question and each
answer with its reason or the user's note, under letters in a shuffled
order. It was told that any reviewer, a majority too, may be wrong, and it
gave a verdict from the picture. Its verdicts kept the user's answer on 15
of the 48 and turned it on 33:

- 29 times the user stood against both judges, and the verdict kept the
  user's answer 3 times.
- Some turns are faults the picture shows that the user did not mark: a
  text cut by its box, a price cut to its last digit by the screen's edge,
  a shop tray running off the screen.
- 7 turns are question 4, which the user answered in its old wording.
- 5 turns are question 5, where the user saw clutter and competing colours
  and the verdict saw no backdrop or glow pulling the eye. That is taste,
  and on taste the user's answer is the one to match.

Scored against the labels with the verdicts in:

| Question, round 2 wording | Labels yes | Haiku agrees | Opus agrees | All no agrees |
|---------------------------|------------|--------------|-------------|---------------|
| 1. Text | 12 | 29 | 32 | 23 |
| 2. An object hides what the player reads or uses | 5 | 31 | 34 | 30 |
| 3. HUD cut by the screen's edge | 8 | 35 | 34 | 27 |
| 4. A stand-in or an odd style | 8 | 33 | 32 | 27 |
| 5. A background or glow catches the eye first | 2 | 32 | 34 | 33 |
| 6. Two kinds look identical | 0 | 34 | 35 | 35 |

Opus beats the baseline on questions 1 to 5 and Haiku on 1 to 4. These
numbers are an upper bound. The third judge is the model of one judge and
read both judges' reasons. It sided with the two judges against the user
26 times of 29, so the labels moved toward the judges. The labels without
the verdicts, in the table before, are the lower bound. Question 5 is
measured by the user's own labels, and against them the judges miss 5 of
the user's 6.

Question 6 is not measured: no label says yes after the verdicts. Under the
round-2 wording neither judge, nor the user, answered yes on the copy whose
map nodes all look alike. A judge that has not seen the project cannot
tell from a picture that two alike objects stand for different things. The
`frame` finding of `review_look.py` measures that case from the instances.

The sample is 35 screenshots labelled by one person, with one run per brief.
Round 2 was tuned and scored on the same set, against labels for the old
wording and against those labels with a model's verdicts in. The numbers show a direction for these games, not a rate to expect
elsewhere. The set, the labels, every reply and the scores are in
`.local/docs/evidence/look-judge/`. `judge_look.py --model` runs
`claude -p` as the judge when the client is signed in. The runs here used
sub-agents.

## Options

1. Keep the literal questions. The judges flag most screens that are done.
2. Score each screen with a rubric or a free critic. That is a second model
   to calibrate, and round 1 shows that a loose question makes a model
   report more, not agree more with the user.
3. Ask what a player sees as a mistake, each question naming the things it
   is about.
4. Keep only the measured finding lines. They miss stand-ins and faint text,
   which the user's notes name.

## Decision

Option 3. `review_look.py` asks the round-2 questions and its brief says
that art layered on purpose is no mistake. The set in
`.local/docs/evidence/look-judge/` is the regression set. A change to the
questions or the brief runs both judges over it with `judge_look.py` and
scores them against both label files, `labels.json` and
`labels-adjudicated.json`. The change keeps both scores at or above these
numbers.

## Re-evaluate when

- The user labels the round-2 wording (`label_look.py --ask 1 2 3 4 5 6`
  into a new labels file). That score replaces both round-2 scores.
- A question stays below the baseline on those labels. Reword it again, or
  replace it with a measurement. Question 5 is the first to look at.
- A screen shows two kinds alike that the `frame` finding misses: question 6
  needs to know the kinds, from the design or the instances.
- A screen the user would not ship gets every answer no. Its note names the
  question that is missing.
