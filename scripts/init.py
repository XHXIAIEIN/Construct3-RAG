#!/usr/bin/env python3
"""Refresh the committed Construct 3 data from the CDN, and Scirra's guides.

Fetches the latest stable release (or --version), exports schemas,
example metadata, language packs and TypeScript definitions into the cache,
then replaces the matching directories under data/. It then fetches the
guides of src/ingest/guides.py into data/c3-guides/, writing a guide only
when its text changed; a guide that cannot be fetched keeps its committed
copy. The runtime reads data/, so the refresh shows in `git diff` before it
is committed. The update workflow runs this same command, and
--guides-only every week.

Usage:
    python scripts/init.py
    python scripts/init.py --version <release>
    python scripts/init.py --guides-only
    python scripts/init.py --guides-only --guide-html <page saved from a browser>
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.lookup.schema_layout import SCHEMA_ACE_TYPES, SCHEMA_LOCALES, schema_counts


def _ace_count(addons: dict) -> int:
    """The ACEs of an allAces.json section, every category of every addon."""
    return sum(
        len(category.get(ace_type, []))
        for categories in addons.values()
        for category in categories.values()
        for ace_type in SCHEMA_ACE_TYPES
    )


def refresh_guides(data_dir: Path, saved: list[Path]) -> None:
    """Write each guide whose text changed; report what happened to each."""
    from src.ingest.guides import GUIDES_DIR, refresh_guides as refresh

    for name, outcome in refresh(data_dir, saved).items():
        print(f"  {GUIDES_DIR}/{name}.md: {outcome}")


def refresh(version: str | None = None, saved: list[Path] = ()) -> None:
    """Fetch one release, the latest stable by default, replace data/, then refresh the guides."""
    from src.settings import load_settings
    from src.ingest.c3_fetcher import C3Fetcher, latest_stable_version

    settings = load_settings()
    version = version or latest_stable_version(settings.schema.cdn_base)
    print(f"Refreshing Construct3-RAG data from Construct 3 {version}")
    print(f"CDN: {settings.schema.cdn_base}")
    print()

    fetcher = C3Fetcher(
        version=version,
        base_url=settings.schema.cdn_base,
        cache_dir=settings.schema.cache_dir,
    )

    # 1. Fetch core data
    print("[1/6] Fetching ACE definitions...")
    aces = fetcher.fetch_all_aces()
    p_count, b_count = _ace_count(aces["plugins"]), _ace_count(aces["behaviors"])
    print(f"  {len(aces['plugins'])} plugins ({p_count} ACEs)")
    print(f"  {len(aces['behaviors'])} behaviors ({b_count} ACEs)")

    print("[2/6] Fetching language data...")
    packs = {locale: fetcher.fetch_lang(locale) for locale in SCHEMA_LOCALES}
    for locale, pack in packs.items():
        print(f"  {locale}: {len(pack.get('text', {}).get('plugins', {}))} plugins")

    print("[3/6] Fetching effects...")
    effects = fetcher.fetch_effects()
    print(f"  {len(effects)} effects")

    print("[4/6] Fetching example project data...")
    examples = fetcher.fetch_examples()
    print(f"  {len(examples)} example projects")

    # 2. Export, then replace the committed copies
    print("[5/6] Exporting schemas, language packs, and TypeScript definitions...")
    targets = fetcher.export_to_data(settings.paths.data_dir)
    counts = schema_counts(targets["c3-schemas"])
    print(f"  {counts['plugins']} plugin schemas")
    print(f"  {counts['behaviors']} behavior schemas")
    print(f"  {counts['effects']} effect schemas")
    print(f"  language packs: {', '.join(sorted(p.stem for p in targets['c3-lang'].glob('*.json')))}")
    print(f"  ts-defs: {len(list(targets['c3-ts-defs'].rglob('*.d.ts')))} files")

    # 3. Scirra's guides: pages, not release data
    print("[6/6] Fetching Scirra's guides...")
    refresh_guides(settings.paths.data_dir, saved)

    # 4. Summary
    print(f"\n{'='*50}")
    print(f"  Construct 3 {version} — data refreshed")
    print(f"  Cache: {fetcher.cache_dir}")
    print(f"  Data:  {settings.paths.data_dir}")
    print(f"{'='*50}")
    print("\nReview with `git diff --stat data/`, then commit.")


def main():
    parser = argparse.ArgumentParser(description="Refresh data/ from the Construct 3 CDN, and Scirra's guides")
    parser.add_argument("--version", type=str, help="Release to fetch (default: latest stable on the CDN)")
    parser.add_argument("--guides-only", action="store_true",
                        help="Refresh only data/c3-guides/, the guides of src/ingest/guides.py")
    parser.add_argument("--guide-html", type=Path, action="append", default=[], metavar="FILE",
                        help="A guide's page saved from a browser, read instead of fetching that guide, "
                             "for when construct.net answers the script with a browser check")
    args = parser.parse_args()
    if args.guides_only:
        from src.settings import load_settings
        print("Fetching Scirra's guides...")
        refresh_guides(load_settings().paths.data_dir, args.guide_html)
    else:
        refresh(args.version, args.guide_html)


if __name__ == "__main__":
    main()
