"""
Start the Construct 3 RAG retrieval API server.

Usage:
    python scripts/serve.py
    python scripts/serve.py --port 8000
    python scripts/serve.py --reload    # dev mode with auto-reload
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    from src.config import RAG_SERVER_PORT

    parser = argparse.ArgumentParser(description="Start RAG retrieval API server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=RAG_SERVER_PORT, help="Port")
    parser.add_argument("--reload", action="store_true", help="Auto-reload on code changes")
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "src.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
