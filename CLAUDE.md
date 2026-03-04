# Construct3-RAG

RAG assistant for Construct 3 game engine documentation. Local LLM + Qdrant vector store, providing Chinese Q&A and event sheet generation.

## Tech Stack

| Component | Technology |
|-----------|------------|
| LLM | HuggingFace / Ollama (default: Qwen3.5-9B) |
| Embedding | BAAI/bge-m3 |
| Vector DB | Qdrant |
| Language | Python 3.14 |

## Directory Structure

| Directory | Purpose |
|-----------|---------|
| `src/` | Source code (config, ingest, rag, locale) |
| `data/` | Data files (translation CSV, ACE schemas, analysis artifacts) |
| `docs/` | Documentation (architecture, quick start, domain knowledge) |
| `scripts/` | Operations scripts (startup, indexing, benchmarking) |
| `tests/` | Unit tests (all mocked, no external services required) |

## Common Commands

```bash
# Index data (requires Qdrant running)
python -m src.ingest.indexer --rebuild

# Run tests (no external services needed)
python -m pytest tests/ -v

# Run benchmark (requires Qdrant + LLM)
python scripts/benchmark.py --mode smart
```

## Setup

```bash
pip install -r requirements.txt

# Start Qdrant
docker run -d -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
```

## Configuration

All config is managed via environment variables, defined in `src/config.py`, with `.env` file support.
Key variables: `LLM_PROVIDER`, `LLM_MODEL`, `QDRANT_HOST`, `EMBEDDING_MODEL`.

## Code Style

- Python PEP 8; `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants
- `_leading_underscore` for private methods
- Use type hints for function signatures
- Use `pathlib.Path` for file operations
- Keep functions under 50 lines; return early for error cases
- Catch specific exceptions, not bare `except:`
- Comments only for non-obvious logic

### Imports

```python
# 1. Standard library
# 2. Third-party
# 3. Local (from src.xxx import ...)
```

### Locale Convention

- `src/locale/zh/` and `src/locale/en/` contain language-specific `prompts.py` and `messages.py`
- `src/locale/__init__.py` routes exports based on `UI_LANGUAGE` config (default: `zh`)
- `src/locale/keywords.py` stays top-level (Chinese NLP keywords, not i18n-dependent)
- `src/rag/prompts.py` is a thin re-export layer (imports from active locale)
- Developer-facing text (logs, comments, docstrings) should be in English
- `src/locale/keywords.py` comments should be in Chinese (describing Chinese keyword semantics)
- New user-facing strings must be added to **both** `zh/` and `en/` with the same constant name

## Related Files

- `CLAUDE.md` in each subdirectory — directory-level details
