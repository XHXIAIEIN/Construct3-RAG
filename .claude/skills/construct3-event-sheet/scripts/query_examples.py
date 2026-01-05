#!/usr/bin/env python3
"""
Query usage examples from 490 official projects.

Usage:
    python query_examples.py action create-object     # Find action usage
    python query_examples.py condition collision      # Find condition usage
    python query_examples.py behavior tween           # Find behavior patterns
    python query_examples.py plugin audio             # Find plugin patterns
    python query_examples.py top actions 20           # Top 20 actions
"""

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent
ANALYSIS_DIR = PROJECT_ROOT / "data" / "project_analysis"

def load_json(filename: str) -> dict:
    path = ANALYSIS_DIR / filename
    if not path.exists():
        print(f"❌ File not found: {filename}")
        sys.exit(1)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

FILE_MAP = {
    'action': 'actions_knowledge.json',
    'condition': 'conditions_knowledge.json',
    'behavior': 'behaviors_knowledge.json',
    'plugin': 'plugins_knowledge.json',
}

def query(data_type: str, search: str):
    if data_type not in FILE_MAP:
        print(f"❌ Unknown type: {data_type}\n   Valid: {', '.join(FILE_MAP.keys())}")
        sys.exit(1)

    data = load_json(FILE_MAP[data_type])
    matches = [(k, v) for k, v in data.items() if search.lower() in k.lower()]

    if not matches:
        print(f"❌ No matches for: {search}")
        return

    print(f"\n🔍 Found {len(matches)} matches\n")
    for key, info in matches[:5]:
        print(f"### `{key}` (used {info.get('count', 0)} times)\n")

        examples = info.get('examples', [])
        if examples:
            print("```json")
            for ex in examples[:2]:
                print(json.dumps(ex, ensure_ascii=False))
            print("```\n")

        params = info.get('common_params', {})
        if params:
            print("Common values:")
            for param, values in list(params.items())[:3]:
                if isinstance(values, list):
                    print(f"  `{param}`: {values[:3]}")

def show_top(ace_type: str, count: int = 10):
    data = load_json("sorted_indexes.json")
    key = f"top_50_{ace_type}"

    if key not in data:
        print(f"❌ Unknown: {ace_type}\n   Valid: actions, conditions, behaviors, plugins")
        return

    print(f"\n📊 Top {count} {ace_type}\n")
    print("| # | ID | Count |")
    print("|---|-----|-------|")
    for i, item in enumerate(data[key][:count], 1):
        name = item.get('id', item.get('name', '?'))
        cnt = item.get('count', 0)
        print(f"| {i} | `{name}` | {cnt} |")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == 'top':
        count = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        show_top(sys.argv[2], count)
    elif cmd in FILE_MAP:
        query(cmd, sys.argv[2])
    else:
        print(__doc__)
