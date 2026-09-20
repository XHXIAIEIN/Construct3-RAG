# `tests/` Directory

The pytest suite is offline: it needs neither Qdrant, a GPU nor network,
and every Qdrant or model call in it is mocked. Live semantic evaluation is
a separate workflow that must name the exact endpoint, collection, model and
frozen gold set it ran against; an infrastructure failure invalidates such a
run, it is not a quality score.

## Rules

- Name unit-test files `test_<module_name>.py`.
- Assert public contracts and facade identity, not private implementation
  fields.
- `SearchStage` has exactly five stable values: `initialize`, `lookup`,
  `semantic`, `deduplicate`, `respond`. Request validation happens inside
  `initialize`; do not add a validation stage.
- Ingestion preparation and validation stay side-effect free; publication is
  the first stage allowed to mutate Qdrant.
- `eval_lookup.py`, `eval_query_quality.py` and `eval_semantic_quality.py`
  are scripts, not pytest files.

## Evaluation

| File | Purpose |
|------|---------|
| `fixtures/query_gold.jsonl` | Product gold set for Direct Lookup: stable IDs, required and forbidden results, evidence |
| `eval_query_quality.py` | The product quality runner. Its JSON output gives route, intent, entity, ordering, expansion source, ranking and latency per query |
| `fixtures/semantic_gold.jsonl` | Frozen development and held-out cases for semantic evaluation |
| `eval_semantic_quality.py` | Optional live semantic evaluation; it needs a frozen manifest, see its docstring |
| `semantic_eval/` | Models, metrics, CLI and live adapter behind it |
| `eval_lookup.py` | Historical bare-ID diagnostic. Not a substitute for the quality runner |

## Commands

```bash
python -m pytest tests/ -q
python -m pytest tests/test_module_boundaries.py tests/test_lookup_boundaries.py -q
python tests/eval_query_quality.py --strategy all --split all --output query-quality.json
python tests/eval_lookup.py -v
```
