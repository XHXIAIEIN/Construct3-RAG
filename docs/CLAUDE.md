# docs/ Directory

Project documentation, divided into system docs and domain knowledge.

## Documents

### System Documentation

| File | Content | Status |
|------|---------|--------|
| `architecture.md` | System architecture (layer diagram, collections, retrieval strategy, tech choices) | Maintained |
| `data-processing.md` | Data processing pipeline (parsing and indexing for 4 data sources) | Maintained |
| `quick-start.md` | Quick start guide (requirements, one-click setup, step-by-step install) | Maintained |
| `rag-introduction.md` | RAG concepts (beginner-friendly: vectorization, chunking, etc.) | Educational |
| `query-pipeline-trace.md` | Full query pipeline trace (6-stage analysis with real query example) | Maintained |

### Domain Knowledge

| File | Content |
|------|---------|
| `knowledge/clipboard-format.md` | Construct 3 clipboard JSON format spec (used by event sheet generator) |
| `knowledge/manual.md` | External manual repos reference (Construct3-Manual, Addon-SDK) |

## Notes

- Tech choices should match `src/config.py` (LLM_PROVIDER, EMBEDDING_MODEL, etc.)
- Collection definitions should match `src/collections.py` (10 collections)
- `knowledge/` files are domain knowledge for the event sheet generator and dev reference
- `rag-introduction.md` is educational; not required to stay in sync with code
- `query-pipeline-trace.md` traces a real query end-to-end; update after pipeline code changes
