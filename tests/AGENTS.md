# `tests/` Directory

The pytest suite is offline: it needs no service, no model and no network.

## Rules

- Name unit-test files `test_<module_name>.py`; a script of the
  `construct3-project` skill is tested in `test_skill_<script>.py`.
- Assert public contracts, not private implementation fields.
- `SearchStage` has exactly three stable values: `initialize`, `lookup`,
  `respond`. Request validation happens inside `initialize`; do not add a
  validation stage.

## Gold set

`fixtures/query_gold.jsonl` holds one Direct Lookup query per line, and
`test_query_gold.py` runs each as a test. A case says whether the service
answers (`hit`) or declines (`miss`); for an answer, the intent, the entity,
the ACE types, and the results it must and must not give, each by its stable
key (collection, plugin id, ACE type, ACE id) within a rank, five unless
`within_top_k` says otherwise. A `complete_list` case must return the whole
list, and the test counts it from the entity's schema file, so a case never
states how long a list is in one release. `source_path` names the data that
settles the case and `rationale` says why. A declined query that still names
an addon keeps it as `expected_entity`.

A new keyword, alias or routing rule starts from a failing case here.

The evals of the `construct3-project` skill are not here. They run agents,
not the service, and live with the skill: `skills/AGENTS.md`, "Evals".
The `test_skill_*.py` files cover the skill's scripts, and
`test_skill_spec.py` the skill's format and, against a stand-in client, the
trigger runner. They share `skill_helpers.py` and, in `conftest.py`, the
stand-in game, generated once a run.

## Commands

```bash
python -m pytest tests/ -q
python -m pytest tests/test_query_gold.py -q
python -m pytest tests -q -k test_skill_
python -m pytest tests/test_module_boundaries.py tests/test_lookup_boundaries.py -q
```
