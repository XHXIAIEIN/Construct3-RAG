# src/ Directory

Project source code. 2 top-level modules and 2 subpackages.

## Top-Level Modules

| File | Purpose |
|------|---------|
| `config.py` | Global configuration (env vars + defaults, includes `load_dotenv`) |
| `collections.py` | Qdrant collection definitions (10 collections with names and parameters) |

## Subpackages

### `ingest/` — Data Parsing & Indexing

| File | Purpose |
|------|---------|
| `indexer.py` | Main indexing pipeline (`--rebuild` for full rebuild) |
| `markdown_parser.py` | Markdown document parser and chunker |
| `project_parser.py` | C3 project file parser |
| `schema_parser.py` | ACE Schema JSON parser |
| `sdk_parser.py` | Addon SDK code sample parser (addon.json, aces.json, lang, JS/TS) |

### `rag/` — RAG Core

| File | Purpose |
|------|---------|
| `chain.py` | RAGChain main class (`answer_smart`/`answer_high_confidence`/`answer_stream`) |
| `retriever.py` | HybridRetriever (cross-collection retrieval + RRF fusion) |
| `prompts.py` | Prompt re-exports from active locale |
| `lookup.py` | Query routing + direct lookup (SchemaIndex, TermIndex, LookupEngine) |
| `eventsheet_generator.py` | C3 event sheet JSON generator (SchemaLoader + ClipboardValidator + EventGenerator)，由 `chain.answer_code()` 调用 |

## Entry Points

- **Production**: `chain.answer_smart(query)` — auto complexity detection + graceful degradation
- **High accuracy**: `chain.answer_high_confidence(query)` — multi-query + Self-Reflection
- **Streaming**: `chain.answer_stream(query)` — generator, real-time output
- **Indexing**: `python -m src.ingest.indexer --rebuild`
