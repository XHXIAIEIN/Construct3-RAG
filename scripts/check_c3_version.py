#!/usr/bin/env python3
"""Check if a newer Construct 3 version is available on the official CDN.

Usage:
    python scripts/check_c3_version.py
    python scripts/check_c3_version.py --update   # update .env automatically
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from src.settings import load_settings
from src.ingest.c3_fetcher import C3Fetcher


def main():
    parser = argparse.ArgumentParser(description="Check for Construct 3 updates")
    parser.add_argument("--update", action="store_true",
                        help="Update C3_VERSION in .env if newer version found")
    args = parser.parse_args()

    current_version = load_settings().schema.version
    fetcher = C3Fetcher(version=current_version)
    try:
        latest = fetcher.get_latest_stable_version()
    except Exception as e:
        print(f"Failed to check versions: {e}")
        sys.exit(1)

    print(f"Current: {current_version}")
    print(f"Latest stable: {latest}")

    if latest == current_version:
        print("Up to date.")
        return

    print(f"\nNew version available: {latest}")

    if args.update:
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            content = env_path.read_text(encoding="utf-8")
            if f"C3_VERSION={current_version}" in content:
                content = content.replace(f"C3_VERSION={current_version}", f"C3_VERSION={latest}")
                env_path.write_text(content, encoding="utf-8")
                print(f"Updated .env: C3_VERSION={latest}")
            else:
                content += f"\nC3_VERSION={latest}\n"
                env_path.write_text(content, encoding="utf-8")
                print(f"Added to .env: C3_VERSION={latest}")
        else:
            env_path.write_text(f"C3_VERSION={latest}\n", encoding="utf-8")
            print(f"Created .env: C3_VERSION={latest}")
        print("Run `python -m src.ingest.indexer --rebuild` to re-index with new data.")
    else:
        print(f"To update: set C3_VERSION={latest} in .env, then rebuild index.")


if __name__ == "__main__":
    main()
