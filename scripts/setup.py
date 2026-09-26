#!/usr/bin/env python3
"""One-command setup for Construct3-RAG.

Usage:
    python scripts/setup.py                 # install deps, start the lookup server
    python scripts/setup.py --refresh-data  # explicitly refresh Construct data
    python scripts/setup.py --version <release>  # refresh data/ from a specific release
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.lookup.schema_layout import schema_counts, schema_version
from src.settings import load_settings
from scripts.init import refresh

SETTINGS = load_settings()


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


def install_deps():
    req_file = ROOT / "src" / "requirements.txt"
    print(f"[deps] Installing from {req_file.name}...")
    run([sys.executable, "-m", "pip", "install", "-r", str(req_file), "-q"])
    print("  OK")


def report_local_schema():
    """Report the already available deterministic lookup dataset."""
    schema_dir = SETTINGS.schema.directory
    counts = schema_counts(schema_dir)
    actual_version = schema_version(schema_dir) or "unknown version"
    print("[data] Using existing local Construct schema (no CDN request)")
    print(
        f"  {actual_version}: {counts['plugins']} plugins, "
        f"{counts['behaviors']} behaviors, {counts['effects']} effects"
    )
    print(f"  {schema_dir}")
    print("  Use --refresh-data to refresh it explicitly.")


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
    parser.add_argument(
        "--refresh-data",
        action="store_true",
        help="Explicitly refresh the versioned Construct CDN dataset",
    )
    parser.add_argument("--version", type=str, help="Refresh data/ from this release")
    parser.add_argument("--skip-deps", action="store_true", help="Skip pip install")
    parser.add_argument("--port", type=int, default=SETTINGS.runtime.server_port, help="Server port")
    args = parser.parse_args()

    print("=" * 50)
    print("  Construct 3 RAG — Setup")
    print("=" * 50)
    print()

    check_python()
    if not args.skip_deps:
        install_deps()
    if args.refresh_data or args.version:
        refresh(args.version)
    else:
        report_local_schema()

    start_server(args.port)


if __name__ == "__main__":
    main()
