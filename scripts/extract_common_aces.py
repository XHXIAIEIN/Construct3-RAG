#!/usr/bin/env python3
"""Regenerate src/ingest/common_aces.json from the editor bundle.

The ACEs shared by every world object are not in allAces.json; the editor
registers them in main.js. This script fetches the bundle, cuts out that block
and stores it in the allAces shape the exporter merges with the language pack.
Run it when scripts/init.py stops with "language pack names shared ACEs that
common_aces.json does not define", then review the diff and commit the file.

The CDN serves main.js only at its root (the current stable release), so the
extracted block matches the version reported in versions.json, not
necessarily C3_VERSION. The file records the version it was taken from.

Usage:
    python scripts/extract_common_aces.py
    python scripts/extract_common_aces.py --main-js path/to/main.js   # local copy
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / "src" / ".env")
except ImportError:
    pass

from src.settings import load_settings
from src.ingest.c3_fetcher import C3Fetcher
from src.ingest.common_aces import (
    ACE_TYPES,
    COMMON_ACES_PATH,
    COMMON_ADDON_ID,
    check_common_coverage,
    extract_common_aces,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract shared ACE definitions from main.js")
    parser.add_argument("--main-js", type=Path, help="Use a local main.js instead of fetching it")
    parser.add_argument("--output", type=Path, default=COMMON_ACES_PATH)
    args = parser.parse_args()

    settings = load_settings()
    fetcher = C3Fetcher(
        version=settings.schema.version,
        base_url=settings.schema.cdn_base,
        cache_dir=settings.schema.cache_dir,
    )
    lang_common = fetcher.fetch_lang("en-US").get("text", {}).get("plugins", {}).get(COMMON_ADDON_ID, {})
    if not lang_common:
        sys.exit("en-US language pack has no plugins._common section")

    if args.main_js:
        main_js = args.main_js.read_text(encoding="utf-8", errors="replace")
        source_version = "local file " + args.main_js.name
    else:
        main_js = fetcher.fetch_raw("main.js").decode("utf-8", errors="replace")
        source_version = fetcher.get_latest_stable_version()

    categories = extract_common_aces(main_js, lang_common)
    check_common_coverage(categories, lang_common)

    counts = {t: sum(len(c.get(t, [])) for c in categories.values()) for t in ACE_TYPES}
    payload = {
        "_source": {
            "file": "main.js",
            "url": f"{settings.schema.cdn_base}/main.js",
            "block": "the function that registers plugins._common in the editor bundle",
            "release": source_version,
            "extracted": date.today().isoformat(),
            "script": "scripts/extract_common_aces.py",
        },
        "categories": categories,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{args.output}: {len(categories)} categories, "
          + ", ".join(f"{n} {t}" for t, n in counts.items())
          + f" (from {source_version})")


if __name__ == "__main__":
    main()
