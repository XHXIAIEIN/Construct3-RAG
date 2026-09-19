#!/usr/bin/env python3
"""Refresh the committed Construct 3 data from the CDN.

Fetches the release named by C3_VERSION (or --version), exports schemas,
example metadata, language packs and TypeScript definitions into the cache,
then replaces the matching directories under data/. The runtime reads data/,
so the refresh shows in `git diff` before it is committed. The update
workflow runs this same command.

Usage:
    python scripts/init.py
    python scripts/init.py --version <release>
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

from src.lookup.schema_layout import schema_counts


def main():
    parser = argparse.ArgumentParser(description="Refresh data/ from the Construct 3 CDN")
    parser.add_argument("--version", type=str, help="C3 version override (for example rNNN)")
    args = parser.parse_args()

    from src.settings import load_settings
    from src.ingest.c3_fetcher import C3Fetcher

    settings = load_settings()
    version = args.version or settings.schema.version
    print(f"Refreshing Construct3-RAG data from Construct 3 {version}")
    print(f"CDN: {settings.schema.cdn_base}")
    print()

    fetcher = C3Fetcher(
        version=version,
        base_url=settings.schema.cdn_base,
        cache_dir=settings.schema.cache_dir,
    )

    # 1. Fetch core data
    print("[1/5] Fetching ACE definitions...")
    aces = fetcher.fetch_all_aces()
    p_count = sum(
        len(cat.get("conditions", [])) + len(cat.get("actions", [])) + len(cat.get("expressions", []))
        for cats in aces["plugins"].values() for cat in cats.values()
    )
    b_count = sum(
        len(cat.get("conditions", [])) + len(cat.get("actions", [])) + len(cat.get("expressions", []))
        for cats in aces["behaviors"].values() for cat in cats.values()
    )
    print(f"  {len(aces['plugins'])} plugins ({p_count} ACEs)")
    print(f"  {len(aces['behaviors'])} behaviors ({b_count} ACEs)")

    print("[2/5] Fetching language data...")
    en = fetcher.fetch_lang("en-US")
    zh = fetcher.fetch_lang("zh-CN")
    print(f"  en-US: {len(en.get('text', {}).get('plugins', {}))} plugins")
    print(f"  zh-CN: {len(zh.get('text', {}).get('plugins', {}))} plugins")

    print("[3/5] Fetching effects...")
    effects = fetcher.fetch_effects()
    print(f"  {len(effects)} effects")

    print("[4/5] Fetching example project data...")
    examples = fetcher.fetch_examples()
    print(f"  {len(examples)} example projects")

    # 2. Export, then replace the committed copies
    print("[5/5] Exporting schemas, language packs, and TypeScript definitions...")
    targets = fetcher.export_to_data(settings.paths.data_dir)
    counts = schema_counts(targets["c3-schemas"])
    print(f"  {counts['plugins']} plugin schemas")
    print(f"  {counts['behaviors']} behavior schemas")
    print(f"  {counts['effects']} effect schemas")
    print(f"  language packs: {', '.join(sorted(p.stem for p in targets['c3-lang'].glob('*.json')))}")
    print(f"  ts-defs: {len(list(targets['c3-ts-defs'].rglob('*.d.ts')))} files")

    # 3. Summary
    print(f"\n{'='*50}")
    print(f"  Construct 3 {version} — data refreshed")
    print(f"  Cache: {fetcher.cache_dir}")
    print(f"  Data:  {settings.paths.data_dir}")
    print(f"{'='*50}")
    print("\nReview with `git diff --stat data/`, then commit.")
    print("Full mode: rebuild the index with `python -m src.ingest.indexer --rebuild`.")


if __name__ == "__main__":
    main()
