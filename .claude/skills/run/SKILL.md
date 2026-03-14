---
name: run
description: Use when user types /run to launch the Construct 3 RAG retrieval API server in a new terminal window.
---

# Run Construct 3 RAG

## Modes

| Command | Action |
|---------|--------|
| `/run` | Start the RAG retrieval API server (FastAPI) |
| `/run --port 8000` | Start on a custom port |

## Steps

1. **Kill old processes**:

```bash
for pid in $(wmic process where "name='python.exe' and commandline like '%serve.py%'" get processid 2>/dev/null | grep -E '^[0-9]+' | tr -d '\r'); do
  taskkill /PID "$pid" /F 2>/dev/null || true
done
```

2. **Start the API server**:

```bash
PYTHON="/c/Users/test/AppData/Local/Python/bin/python.exe"
PROJECT="D:\\Users\\Administrator\\Documents\\GitHub\\Construct3-RAG"

# Launch in a new terminal tab
MSYS_NO_PATHCONV=1 wt new-tab cmd /k "cd /d $PROJECT && $PYTHON scripts/serve.py" 2>/dev/null \
|| start "RAG-API" cmd /k "cd /d $PROJECT && $PYTHON scripts/serve.py"
```

3. **Inform the user**: API server starting at `http://localhost:8765`. Embedding model loads on first request (~10s). Endpoints: `GET /health`, `POST /search`.

## Notes

- RAG is now a pure retrieval service (no LLM, no chat)
- Port configurable via `RAG_SERVER_PORT` env var (default `8765`)
- Requires Qdrant running at `localhost:6333`
- Copilot (generation layer) is a separate project that consumes this API
