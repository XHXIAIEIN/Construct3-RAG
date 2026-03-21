---
name: run
description: Use when user types /run to start the API server.
---

# Run

## Steps

1. **Kill old processes**:

```bash
MSYS_NO_PATHCONV=1 taskkill /F /IM python.exe 2>/dev/null || true
sleep 2
```

2. **Clear cache and start**:

```bash
find "D:/Users/Administrator/Documents/GitHub/Construct3-RAG" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
cd "D:/Users/Administrator/Documents/GitHub/Construct3-RAG"
/c/Users/test/AppData/Local/Python/bin/python.exe -m uvicorn src.api:app --host 0.0.0.0 --port 8765 --reload
```

3. **Inform the user**: Server at `http://localhost:8765/playground`.
