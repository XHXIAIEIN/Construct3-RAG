"""Run the published-game study from one command."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .catalog import DOWNLOADS, REPO, STATS, load_catalog


def downloaded(names: list[str] | None = None) -> list[Path]:
    wanted = names or [entry["folder"] for entry in load_catalog()]
    return [DOWNLOADS / name for name in wanted if (DOWNLOADS / name / "manifest.json").exists()]


def run_module(name: str, args: list[str], output: Path | None = None) -> None:
    command = [sys.executable, "-m", f"scripts.reference_games.{name}", *args]
    if output is None:
        subprocess.run(command, cwd=REPO, check=True)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        subprocess.run(command, cwd=REPO, check=True, stdout=stream)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect published Construct exports.")
    parser.add_argument("stage", choices=("fetch", "decode", "atlas", "report", "all"))
    parser.add_argument("items", nargs="*", help="Sources for fetch, or downloaded folder names for decode and atlas.")
    args = parser.parse_args()

    if args.stage == "all" and args.items:
        parser.error("The all stage uses the complete catalog and does not accept item filters.")

    if args.stage in ("fetch", "all"):
        sources = args.items or [entry["source"] for entry in load_catalog()]
        run_module("fetch", sources)

    if args.stage in ("decode", "atlas", "all"):
        paths = [str(path) for path in downloaded(args.items or None)]
        if not paths:
            raise SystemExit("No downloaded exports matched the requested games.")
        if args.stage in ("decode", "all"):
            run_module("decode", paths)
        if args.stage in ("atlas", "all"):
            run_module("atlas", paths)

    if args.stage in ("report", "all"):
        run_module("stats", [])
        run_module("compare", [], STATS / "compare_authors.txt")


if __name__ == "__main__":
    main()
