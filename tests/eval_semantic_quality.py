#!/usr/bin/env python
"""Real stage-two full-semantic quality evaluator.
Example (after the frozen manifest opens the requested split):

    python tests/eval_semantic_quality.py --strategy all --split dev \
      --manifest .cache/query-quality/stage-two/protocol-locked.json
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.semantic_eval.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
