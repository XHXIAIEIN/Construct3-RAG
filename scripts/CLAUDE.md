# scripts/ Directory

## Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `setup.py` | Default setup (CDN + lookup server) | `python scripts/setup.py` |
| `setup.py --full` | Full setup (+ Qdrant + embedding + index) | `python scripts/setup.py --full` |
| `init.py` | Fetch CDN data and export schemas | `python scripts/init.py` |
| `check_c3_version.py` | Check latest C3 version on CDN | `python scripts/check_c3_version.py` |
| `start-services.sh` | Start Qdrant + Ollama | `./scripts/start-services.sh` |
| `stop-services.sh` | Stop Qdrant + Ollama | `./scripts/stop-services.sh` |
| `status.sh` | Check service status | `./scripts/status.sh` |
| `clear-all.sh` | Clear all Qdrant collections | `./scripts/clear-all.sh` |
