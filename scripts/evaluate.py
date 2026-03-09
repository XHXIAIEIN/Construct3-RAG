#!/usr/bin/env python3
"""Thin wrapper — delegates to src.evaluation.evaluate_ragas.

Usage:
    python scripts/evaluate.py --heuristic
    python scripts/evaluate.py --ragas
    python scripts/evaluate.py --all
    python scripts/evaluate.py --generate-ground-truth
    python scripts/evaluate.py --all --output report.md
"""
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
runpy.run_module("src.evaluation.evaluate_ragas", run_name="__main__", alter_sys=True)
