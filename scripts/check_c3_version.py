#!/usr/bin/env python3
"""Compare the release data/ holds with the latest stable release on the CDN.

Usage:
    python scripts/check_c3_version.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.settings import load_settings
from src.ingest.c3_fetcher import latest_stable_version


def main():
    settings = load_settings()
    current = settings.schema.version
    try:
        latest = latest_stable_version(settings.schema.cdn_base)
    except (OSError, ValueError, LookupError) as e:
        print(f"Failed to check versions: {e}")
        sys.exit(1)

    print(f"data/: {current or 'missing'}")
    print(f"Latest stable: {latest}")

    if latest == current:
        print("Up to date.")
    else:
        print("\nRefresh with `python scripts/init.py`, then review `git diff --stat data/`.")


if __name__ == "__main__":
    main()
