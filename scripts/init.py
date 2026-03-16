#!/usr/bin/env python3
"""Initialize Construct3-RAG: fetch CDN data, export schemas, verify setup.

Run this once after cloning, or after updating C3_VERSION.

Usage:
    python scripts/init.py
    python scripts/init.py --version r477   # use specific version
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    parser = argparse.ArgumentParser(description="Initialize Construct3-RAG")
    parser.add_argument("--version", type=str, help="C3 version override (e.g. r477)")
    args = parser.parse_args()

    from src.config import C3_VERSION, C3_CDN_BASE, C3_CACHE_DIR
    from src.ingest.c3_fetcher import C3Fetcher

    version = args.version or C3_VERSION
    print(f"Initializing Construct3-RAG with Construct 3 {version}")
    print(f"CDN: {C3_CDN_BASE}")
    print()

    fetcher = C3Fetcher(version=version, base_url=C3_CDN_BASE, cache_dir=C3_CACHE_DIR)

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

    # 2. Export schemas for lookup.py
    print("[5/5] Exporting schemas...")
    schemas_dir = fetcher.export_schemas()
    plugins = list((schemas_dir / "plugins").glob("*.json"))
    behaviors = list((schemas_dir / "behaviors").glob("*.json"))
    print(f"  {len(plugins)} plugin schemas")
    print(f"  {len(behaviors)} behavior schemas")

    # 3. Discover locales
    locales = fetcher.fetch_available_locales()
    print(f"\nAvailable locales: {len(locales)}")

    # 4. Terms
    terms = fetcher.export_terms()
    print(f"Translation terms: {len(terms)}")

    # 5. Summary
    print(f"\n{'='*50}")
    print(f"  Construct 3 {version} — initialized")
    print(f"  Cache: {fetcher.cache_dir}")
    print(f"  Schemas: {schemas_dir}")
    print(f"{'='*50}")
    print(f"\nNext steps:")
    print(f"  1. Start Qdrant:  docker start qdrant")
    print(f"  2. Build index:   python -m src.ingest.indexer --rebuild")
    print(f"  3. Start server:  python -m uvicorn src.api:app --port 8765")


if __name__ == "__main__":
    main()
