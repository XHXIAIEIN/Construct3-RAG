#!/usr/bin/env python3
"""Compare the release data/ holds with the latest stable release on the CDN.

Exits 1 when the CDN cannot be read or names no stable release, so a failed
check never reads as "no new release".

Usage:
    python scripts/check_c3_version.py
    python scripts/check_c3_version.py --github-output
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.settings import load_settings
from src.ingest.c3_fetcher import latest_stable_version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--github-output",
        action="store_true",
        help="append current=, latest= and changed=true|false to $GITHUB_OUTPUT; "
        "nothing is appended when the check fails",
    )
    args = parser.parse_args(argv)

    settings = load_settings()
    current = settings.schema.version
    try:
        latest = latest_stable_version(settings.schema.cdn_base)
    except (OSError, ValueError, LookupError) as e:
        print(f"Failed to check versions: {e}", file=sys.stderr)
        return 1

    print(f"data/: {current or 'missing'}")
    print(f"Latest stable: {latest}")

    if latest == current:
        print("Up to date.")
    else:
        print("\nRefresh with `python scripts/init.py`, then review `git diff --stat data/`.")
    if args.github_output:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
            print(f"current={current}", f"latest={latest}", f"changed={str(latest != current).lower()}",
                  sep="\n", file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
