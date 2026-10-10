# Review the changed sheets

`review_design.py --check` runs the full checker and prints design questions.
Read the changed sheets with `print_sheet.py`, then follow their calls and
shared state to judge every question. The complete checker log is saved in
`.tmp/design-review/check.json`.

Use optional `--prepare` for complete evidence batches and saved judgements.
It reads the listed project files directly.

```bash
python scripts/review_design.py --check --prepare .tmp/design-review --resume --sheets Game --limit 0
```

Use the sheets changed by the task. Shared variables and calls can bring
other sheets into their questions. Without `--sheets`, every sheet is reviewed.
`--check` runs the full checker first and stops on failure.
`check.json` keeps its complete stdout, stderr, command and exit code.
Pass `--style` for a project the agent wrote.

Read the findings in `current.json`, then the batches it lists.
Each batch contains its own evidence, scopes, relations and rule versions.
The `review` object supplies constraints shared by every question in the batch.
Batch JSON uses compact whitespace; every question and evidence text stays whole.
A question's `evidence` key selects a list in `evidence_groups`; those ids
select the actual text in `evidence`. Its other keys select the named tables.
`--limit` groups complete questions by character size; a large question stays
whole. `--limit 0` keeps all pending questions in one file.

Answer each pending question using `answer-format.json`.
Use `pass`, `needs_change` or `insufficient_evidence`.
`pass` means the existing design can stay, with a reason from the evidence.
An intentional exception needs its reason and evidence in that answer.
Copy each question's `id` and `input_version`.
Cite an evidence `id` and a short exact `quote` from its text.
For `needs_change`, suggest a change within the question's scope.
If intent, picking or timing needs runtime evidence, say `insufficient_evidence`.

```bash
python scripts/review_design.py --prepare .tmp/design-review --resume --sheets Game --answers answers.json --limit 0
```

`--batch N` validates only pending batch N. After accepting a batch, prepare
with `--resume` and read the current list before answering another batch.
Validation rejects unknown or duplicate questions, missing answers, stale
inputs, citations absent from the batch, and suggestions outside its scope.
It saves judgements in `accepted.json`; it does not apply suggestions.
These checks validate structure and provenance, not semantic correctness.

Use `edit_sheet.py` for an explicit edit plan.
Copy the event's printed line as well as its number into the plan.
The review version checks the judgement's inputs; the printed line checks
which event an edit addresses. Run its `--dry-run` before applying it.
Then repeat the checked preparation on the changed sheets.

`--resume` reuses static judgements only when their inputs still match.
It recomputes relations from the current files on every invocation.
Local context includes parents, children and adjacent events.
Coverage questions start with all events in the selected sheet. Included
sheets and shared symbols extend that scope; unrelated sheets stay outside it.
Shared state and calls extend that context to definitions and other uses.
Object, family, layout, schema and rule changes invalidate dependent answers.
Container members carry their object definitions and explicit membership.
Relevant layouts retain complete initial values, hierarchy and instance data.
Lexical closure can include extra events; it is a conservative dependency scope.
Relations marked `project_format` come from explicit event or project fields.
Their evidence keys identify the actual source in the batch.
Unresolved mapped calls and scripts require evidence and widen the scope.
The absence of a relation does not prove the absence of an effect.

An interrupted preparation keeps complete earlier batches.
`current.json` lists invalidated answers and their reasons.
Current findings, accepted `needs_change` answers, pending questions and
pending runtime checks remain distinct there.
An `insufficient_evidence` answer remains pending on the next resume.
Runtime state and visual judgements are checked on each run.
Use `open_in_editor.py`, the target input plan of `preview_project.py` and
`review_look.py` for that evidence.

Exit 0 means preparation or answer validation finished.
It does not mean every judgement passed or the game was played.
Exit 2 identifies an invalid answer, sheet, batch or output folder.
With `--check`, a failed checker returns its own exit code.
