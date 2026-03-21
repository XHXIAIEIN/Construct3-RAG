#!/usr/bin/env python3
"""One-command setup for Construct3-RAG.

Usage:
    python scripts/setup.py              # full setup (CDN + index + server)
    python scripts/setup.py --lite       # lite mode (CDN + lookup only, no embedding/Qdrant)
    python scripts/setup.py --skip-index # skip indexing (just start server)
    python scripts/setup.py --version r477  # use specific C3 version
"""
import argparse
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def run(cmd: list[str], check: bool = True, **kw) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, **kw)


def check_python():
    v = sys.version_info
    print(f"[check] Python {v.major}.{v.minor}.{v.micro}")
    if v < (3, 11):
        print("  ERROR: Python 3.11+ required")
        sys.exit(1)
    print("  OK")


def install_deps(lite: bool = False):
    req_file = ROOT / ("requirements-lite.txt" if lite else "requirements.txt")
    print(f"[deps] Installing from {req_file.name}...")
    run([sys.executable, "-m", "pip", "install", "-r", str(req_file), "-q"])
    print("  OK")


def check_qdrant(host: str = "localhost", port: int = 6333) -> bool:
    print(f"[qdrant] Checking Qdrant at {host}:{port}...")
    try:
        urllib.request.urlopen(f"http://{host}:{port}", timeout=3)
        print("  OK — Qdrant is running")
        return True
    except Exception:
        print("  NOT RUNNING")
        print()
        print("  Start Qdrant with one of:")
        print("    docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant")
        print("    docker start qdrant  (if container already exists)")
        print()
        return False


def fetch_cdn(version: str | None = None):
    print("[cdn] Fetching Construct 3 CDN data...")
    from src.config import C3_VERSION, C3_CDN_BASE, C3_CACHE_DIR
    from src.ingest.c3_fetcher import C3Fetcher

    ver = version or C3_VERSION
    fetcher = C3Fetcher(version=ver, base_url=C3_CDN_BASE, cache_dir=C3_CACHE_DIR)

    aces = fetcher.fetch_all_aces()
    fetcher.fetch_lang("en-US")
    fetcher.fetch_lang("zh-CN")
    fetcher.fetch_effects()
    fetcher.fetch_examples()
    schemas_dir = fetcher.export_schemas()

    total_aces = sum(
        len(cat.get(t, []))
        for section in aces.values()
        for cats in section.values()
        for cat in cats.values()
        for t in ("conditions", "actions", "expressions")
    )
    plugins = list((schemas_dir / "plugins").glob("*.json"))
    behaviors = list((schemas_dir / "behaviors").glob("*.json"))
    print(f"  {ver}: {total_aces} ACEs, {len(plugins)} plugins, {len(behaviors)} behaviors")
    print("  OK")


def build_index():
    print("[index] Building vector index (this takes a few minutes)...")
    run([sys.executable, "-m", "src.ingest.indexer", "--rebuild"], cwd=str(ROOT))
    print("  OK")


def start_server(port: int = 8765):
    print(f"[server] Starting API server on port {port}...")
    print(f"  Playground: http://localhost:{port}/playground")
    print(f"  Health:     http://localhost:{port}/health")
    print()
    run([sys.executable, "-m", "uvicorn", "src.api:app",
         "--host", "0.0.0.0", "--port", str(port), "--reload"],
        cwd=str(ROOT))


def main():
    parser = argparse.ArgumentParser(description="Construct3-RAG setup")
    parser.add_argument("--lite", action="store_true",
                        help="Lite mode: lookup only, no embedding model, no Qdrant needed")
    parser.add_argument("--version", type=str, help="C3 version (default: from .env)")
    parser.add_argument("--skip-index", action="store_true", help="Skip index rebuild")
    parser.add_argument("--skip-deps", action="store_true", help="Skip pip install")
    parser.add_argument("--port", type=int, default=8765, help="Server port")
    args = parser.parse_args()

    if args.lite:
        print("=" * 50)
        print("  Construct 3 RAG — Lite Setup")
        print("  (lookup only, no embedding/Qdrant)")
        print("=" * 50)
        print()
        check_python()
        if not args.skip_deps:
            install_deps(lite=True)
        fetch_cdn(args.version)
        import os
        os.environ["LITE_MODE"] = "true"
        start_server(args.port)
    else:
        print("=" * 50)
        print("  Construct 3 RAG — Full Setup")
        print("=" * 50)
        print()
        check_python()
        if not args.skip_deps:
            install_deps()
        qdrant_ok = check_qdrant()
        if not qdrant_ok:
            print("  Start Qdrant and re-run, or use --lite for lookup-only mode.")
            sys.exit(1)
        fetch_cdn(args.version)
        if not args.skip_index:
            build_index()
        else:
            print("[index] Skipping (--skip-index)")
        start_server(args.port)


if __name__ == "__main__":
    main()
