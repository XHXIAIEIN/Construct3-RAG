# scripts/ Directory

Operations and development scripts. All scripts are in the `scripts/` root (no subdirectories).

## Scripts

### System Setup & Check

| Script | Purpose | Usage |
|--------|---------|-------|
| `run-all.sh` | One-click full system setup (install → services → index) | `./scripts/run-all.sh` |
| `run.sh` | Check services & show usage info | `./scripts/run.sh` |
| `run-dev.sh` | Run tests | `./scripts/run-dev.sh` |

### Environment Setup

| Script | Purpose | Usage |
|--------|---------|-------|
| `install.sh` | Create venv + pip install | `./scripts/install.sh` |
| `start-services.sh` | Start Qdrant (Docker) + Ollama | `./scripts/start-services.sh` |
| `stop-services.sh` | Stop Qdrant container + Ollama process | `./scripts/stop-services.sh` |
| `status.sh` | Check Docker/Qdrant/Ollama/Python status | `./scripts/status.sh` |

### Data Indexing

| Script | Purpose | Usage |
|--------|---------|-------|
| `index-all.sh` | Index all data to Qdrant (calls `python -m src.ingest.indexer`) | `./scripts/index-all.sh` |
| `index-manual.sh` | Index manual docs only | `./scripts/index-manual.sh` |
| `index-examples.sh` | Index example projects only | `./scripts/index-examples.sh` |
| `index-terms.sh` | Index translation glossary only | `./scripts/index-terms.sh` |
| `clear-all.sh` | Clear all Qdrant collections | `./scripts/clear-all.sh` |

### Interactive Chat

| Script | Purpose | Usage |
|--------|---------|-------|
| `server.py` | Model server — load models once, serve multiple chat clients | `python scripts/server.py` |
| `chat.py` | Interactive CLI — auto-connects to server, falls back to local load | `python scripts/chat.py` |

Workflow: start `server.py` once, then open as many `chat.py` terminals as needed.
Server auto-shuts after 30s with no active clients. Port: `RAG_SERVER_PORT` (default `8765`).

### Evaluation & Analysis

| Script | Purpose | Usage |
|--------|---------|-------|
| `evaluate.py` | Unified evaluation (heuristic + RAGAS). Replaces benchmark.py | `python scripts/evaluate.py --all` |
| `benchmark.py` | **DEPRECATED** — thin wrapper calling `evaluate.py --heuristic` | `python scripts/benchmark.py --mode smart` |
| `download_model.py` | Download HuggingFace model to local cache | `python scripts/download_model.py Qwen/Qwen3.5-9B` |
| `analyze_eventsheets.py` | Deep analysis of C3 event sheet structures (incremental) | `python scripts/analyze_eventsheets.py` |
| `analyze_projects.py` | Full analysis of C3 project structures (incremental) | `python scripts/analyze_projects.py` |

## Shell Script Conventions

All `.sh` scripts follow the same pattern:

```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
```

- `SCRIPT_DIR` points to `scripts/` itself
- `PROJECT_ROOT` points to project root
- Commands run from `PROJECT_ROOT` (`cd "$PROJECT_ROOT"`)
- Activates `venv/` if present
- Scripts requiring Qdrant perform a connection check first

## Notes

- Indexing scripts use `from src.ingest.indexer import ...` (formerly `data_processing`)
- Cross-references between scripts (e.g., `run-all.sh` calls `install.sh`) use `$SCRIPT_DIR/xxx.sh`
- Indexing can also be run directly: `python -m src.ingest.indexer --rebuild`
- Benchmark requires both Qdrant and LLM services running
