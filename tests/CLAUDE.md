# tests/ Directory

Unit tests. No Qdrant, LLM, or other external services required.

## Test Files

| File | Content | Cases | Data |
|------|---------|-------|------|
| `test_chain.py` | RAGChain core logic (includes Self-Reflect parsing) | 22 | Fully mocked |
| `test_lookup.py` | Query routing + direct lookup system | 55 | Real schema/CSV files |
| `test_event_generator.py` | Event sheet JSON generator | 49 | Real schema files |

**Note:** `test_lookup.py` and `test_event_generator.py` use real data files from `data/schemas/` and `data/source/`. They require no external services but do depend on the data directory being present.

## Commands

```bash
# Run all tests
python -m pytest tests/ -v

# Run a single file
python -m pytest tests/test_chain.py -v

# Run a single test class
python -m pytest tests/test_chain.py::TestSelfReflect -v
```

## Conventions

- File naming: `test_<module_name>.py`
- `test_chain.py` uses `unittest.mock` — fully isolated from real services
- `test_lookup.py` / `test_event_generator.py` read real JSON schemas (no mocks needed)
- Tests run without Docker or GPU
- When adding a new `src/` module, add a corresponding test file
