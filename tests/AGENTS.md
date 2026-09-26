# `tests/` Directory

The pytest suite is offline: it needs no service, no model and no network.

## Rules

- Name unit-test files `test_<module_name>.py`.
- Assert public contracts, not private implementation fields.
- `SearchStage` has exactly three stable values: `initialize`, `lookup`,
  `respond`. Request validation happens inside `initialize`; do not add a
  validation stage.
- `eval_lookup.py` and `eval_query_quality.py` are scripts, not pytest files.

## Evaluation

| File | Purpose |
|------|---------|
| `fixtures/query_gold.jsonl` | Product gold set for Direct Lookup: stable IDs, required and forbidden results, evidence |
| `eval_query_quality.py` | The product quality runner. Its JSON output gives route, intent, entity, ordering, expansion source, ranking and latency per query |
| `eval_lookup.py` | Quick smoke run of bare plugin names, keyword and script API queries. Not a substitute for the quality runner |

The evals of the `construct3-project` skill are not here. They run agents,
not the service, and live with the skill: `skills/AGENTS.md`, "Evals".
`test_project_tools.py` covers the skill's scripts and, against a stand-in
client, the trigger runner.

## Commands

```bash
python -m pytest tests/ -q
python -m pytest tests/test_module_boundaries.py tests/test_lookup_boundaries.py -q
python tests/eval_query_quality.py --strategy all --split all --output query-quality.json
python tests/eval_lookup.py -v
```
