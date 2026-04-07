# Construct3-RAG

Construct 3 documentation retrieval service. Fetches ACE definitions from official CDN, indexes with Qdrant, provides structured search API.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Vector DB | Qdrant |
| Embedding | BAAI/bge-m3 |
| Data source | Construct 3 CDN (live) + Markdown manual + Addon SDK |
| Language | Python 3.11+ |

## Directory Structure

| Directory | Purpose |
|-----------|---------|
| `src/` | Source code (api, ingest, rag) |
| `src/ingest/` | CDN fetching, parsing, indexing |
| `src/rag/` | Lookup engine, vector retriever, query expander |
| `scripts/` | Setup, init, evaluation |
| `tests/` | Unit tests (no external services required) |
| `docs/` | Architecture, API reference, data pipeline |
| `.cache/c3-cdn/` | CDN cache + exported schemas (auto-generated) |

## Common Commands

```bash
# One-command setup (deps + CDN + index + server)
python scripts/setup.py

# Run tests
python -m pytest tests/ -v

# Rebuild index only
python -m src.ingest.indexer --rebuild

# Start server only
python -m uvicorn src.api:app --port 8765 --reload
```

## Configuration

Environment variables (`.env` file supported), defined in `src/config.py`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `C3_VERSION` | see `src/config.py` | Construct 3 editor version for CDN |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Embedding model |
| `QDRANT_HOST` | `localhost` | Qdrant host |
| `RAG_SERVER_PORT` | `8765` | API server port |

## Code Style

- Python PEP 8; `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants
- `_leading_underscore` for private methods
- Type hints for function signatures
- `pathlib.Path` for file operations
- Functions under 50 lines; return early for error cases
- Catch specific exceptions, not bare `except:`
- Comments only for non-obvious logic

### Imports

```python
# 1. Standard library
# 2. Third-party
# 3. Local (from src.xxx import ...)
```

## UI / Frontend

- Match existing page style exactly. Do not add borders, cards, or decorative elements unless requested.
- Minimal approach — if it works without styling, don't add styling.

## File Placement

- Private/sensitive files (API keys, prompts, local configs) → `.local/` (gitignored)
- Never write secrets or local paths to git-tracked files
- Pre-built data → `data/` (committed)
- CDN cache → `.cache/` (gitignored, auto-generated)

## Testing

- Run `python -m pytest tests/ -v` before committing
- All tests must pass with no external services (no Qdrant, no GPU)

## Documentation

- Write for end users, not developers
- No hardcoded versions, paths, or Chinese-only examples in English docs
- Keep README examples minimal and runnable

## Environment Constraints

- VRAM limited (24GB RTX 5090); check `nvidia-smi` before GPU tasks
- Ollama may consume VRAM; stop before training: `ollama stop`
- WSL memory constrained; avoid running Qdrant + training simultaneously
- Windows paths: use forward slashes in bash, `MSYS_NO_PATHCONV=1` for taskkill

## Construct 3 Knowledge

This repo contains pre-built Construct 3 API definitions. When answering questions about C3 plugins, behaviors, ACEs, or scripting, **always look up the data files below** instead of guessing from training data.

### Data files (always available, no setup needed)

Per-language files using CDN-native field names (`list-name`, `display-text`, `translated-name`).
Each language is a complete, independent copy — pick one directory and read it.

```
data/c3-schemas/
  _index.json                               — START HERE: plugin/behavior/effect index
  {lang}/plugins/{id}.json                  — ACE definitions (conditions, actions, expressions)
  {lang}/behaviors/{id}.json                — behavior ACE definitions
  {lang}/effects/{id}.json                  — effect definitions (parameters, categories)
  (lang = en-US, zh-CN, ...)

data/c3-examples/{lang}/{id}.json             — 481 example projects (name, description, tags, used-addons, open URL)

data/c3-ts-defs/
  autocomplete-data.json                    — scripting API: 109 classes → method/property lists
  plugins/.../*.d.ts                        — full TypeScript interface signatures
  behaviors/.../*.d.ts                      — behavior TypeScript interfaces
  preview/interfaces/...                    — runtime base classes (IInstance, IWorldInstance, etc.)
```

### How to answer C3 questions

**"What actions/conditions/expressions does [plugin] have?"**
→ Read `_index.json`, find the plugin id, then read `{lang}/plugins/{id}.json`

**"How do I use [ACE] in event sheets?"**
→ Read the plugin schema JSON, find the ACE entry. Look at `display-text` (editor format), `params`, `description`.

**"How do I use [plugin] in JavaScript/TypeScript?"**
→ Read `data/c3-ts-defs/autocomplete-data.json` to find the interface class name.
→ Then read the `.d.ts` file for full method signatures.
→ Example: Sprite → `ISpriteInstance` → `data/c3-ts-defs/plugins/general/sprite/c3runtime/ISpriteInstance.d.ts`

**"What effects are available?"**
→ Read `_index.json` effects section, then `{lang}/effects/{id}.json`

**"Are there example projects for [topic]?"**
→ Browse `data/c3-examples/{lang}/` — each file has `name`, `description`, `tags`, `used-addons`, and an `open` URL to launch in the editor.

**"What is [C3 concept]?" (layouts, event sheets, behaviors, etc.)**
→ General knowledge is fine. No lookup needed.

### API (optional, if server is running)

Full spec: `docs/api-reference.md`

```
POST /search  mode=list     — ACE name listing (grouped by type)
POST /search  mode=lookup   — keyword search with full ACE details
POST /search  mode=auto     — lookup + semantic vector search
```

## Related Files

- `CLAUDE.md` in each subdirectory — directory-level details
