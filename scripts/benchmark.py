#!/usr/bin/env python3
"""
DEPRECATED: Use scripts/evaluate.py instead.

    python scripts/evaluate.py --heuristic --mode smart
    python scripts/evaluate.py --heuristic --mode smart --output report.md

This file is kept for backwards compatibility only.
"""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
warnings.warn(
    "benchmark.py is deprecated. Use: python scripts/evaluate.py --heuristic",
    DeprecationWarning, stacklevel=1,
)

# Translate legacy flags into new CLI; pass through --help and unknown flags
args = sys.argv[1:]
new_args = ["--heuristic"]
i = 0
while i < len(args):
    if args[i] in ("--mode", "--output", "--cases") and i + 1 < len(args):
        new_args += [args[i], args[i + 1]]
        i += 2
    elif args[i] in ("-h", "--help"):
        new_args.append(args[i])
        i += 1
    else:
        i += 1

sys.argv = [sys.argv[0]] + new_args

import runpy
runpy.run_module("src.evaluation.evaluate_ragas", run_name="__main__", alter_sys=True)
