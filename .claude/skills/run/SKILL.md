---
name: run
description: Use when user types /run to start the API server.
---

# Run

## Steps

1. **Stop old server processes** listening on port 8765, if any.

2. **Clear cache and start** from the repository root:

```bash
find . -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null
python -m uvicorn src.api:app --host 0.0.0.0 --port 8765 --reload
```

3. **Inform the user**: Server at `http://localhost:8765/playground`.
