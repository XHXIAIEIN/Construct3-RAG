#!/usr/bin/env python3
"""One-command setup for Construct3-RAG.

Usage:
    python scripts/setup.py              # default: lookup only (no Docker needed)
    python scripts/setup.py --full       # full: install all deps + Qdrant + index
    python scripts/setup.py --refresh-data  # explicitly refresh Construct data
    python scripts/setup.py --version <release>  # use a specific C3 version
"""
import argparse
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.schema_layout import schema_counts, schema_version
from src.config import C3_VERSION, RAG_SERVER_PORT, SCHEMA_DIR


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


def install_deps(full: bool = False):
    req_file = ROOT / ("requirements-full.txt" if full else "requirements.txt")
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
    counts = schema_counts(schemas_dir)
    print(
        f"  {ver}: {total_aces} ACEs, {counts['plugins']} plugins, "
        f"{counts['behaviors']} behaviors, {counts['effects']} effects"
    )
    print("  OK")


def report_local_schema():
    """Report the already available deterministic lookup dataset."""
    counts = schema_counts(SCHEMA_DIR)
    actual_version = schema_version(SCHEMA_DIR) or C3_VERSION
    print("[data] Using existing local Construct schema (no CDN request)")
    print(
        f"  {actual_version}: {counts['plugins']} plugins, "
        f"{counts['behaviors']} behaviors, {counts['effects']} effects"
    )
    print(f"  {SCHEMA_DIR}")
    print("  Use --refresh-data to refresh it explicitly.")


def build_index(version: str | None = None):
    print("[index] Building vector index (this takes a few minutes)...")
    index_env = os.environ.copy()
    if version:
        index_env["C3_VERSION"] = version
    run(
        [sys.executable, "-m", "src.ingest.indexer", "--rebuild"],
        cwd=str(ROOT),
        env=index_env,
    )
    print("  OK")


def start_server(
    port: int = 8765, full: bool = False, version: str | None = None
):
    print(f"[server] Starting API server on port {port}...")
    print(f"  Mode:       {'full semantic (explicit)' if full else 'lookup only (default)'}")
    print(f"  Playground: http://localhost:{port}/playground")
    print(f"  Health:     http://localhost:{port}/health")
    print()
    server_env = os.environ.copy()
    server_env["LITE_MODE"] = "false" if full else "true"
    if version:
        server_env["C3_VERSION"] = version
    run([sys.executable, "-m", "uvicorn", "src.api:app",
         "--host", "0.0.0.0", "--port", str(port), "--reload"],
        cwd=str(ROOT), env=server_env)


def main():
    parser = argparse.ArgumentParser(description="Construct3-RAG setup")
    parser.add_argument("--full", action="store_true",
                        help="Full mode: install all deps including embedding/Qdrant, build index")
    parser.add_argument(
        "--refresh-data",
        action="store_true",
        help="Explicitly refresh the versioned Construct CDN dataset",
    )
    parser.add_argument("--version", type=str, help="C3 version (default: from .env)")
    parser.add_argument("--skip-index", action="store_true", help="Skip index rebuild")
    parser.add_argument("--skip-deps", action="store_true", help="Skip pip install")
    parser.add_argument("--port", type=int, default=RAG_SERVER_PORT, help="Server port")
    args = parser.parse_args()

    print("=" * 50)
    print(f"  Construct 3 RAG — {'Full' if args.full else 'Lookup'} Setup")
    print("=" * 50)
    print()

    check_python()
    if not args.skip_deps:
        install_deps(full=args.full)
    if args.full or args.refresh_data or args.version:
        fetch_cdn(args.version)
    else:
        report_local_schema()

    if args.full:
        qdrant_ok = check_qdrant()
        if not qdrant_ok:
            print("  Start Qdrant and re-run.")
            sys.exit(1)
        if not args.skip_index:
            build_index(args.version)
        else:
            print("[index] Skipping (--skip-index)")

    start_server(args.port, full=args.full, version=args.version)


if __name__ == "__main__":
    main()
