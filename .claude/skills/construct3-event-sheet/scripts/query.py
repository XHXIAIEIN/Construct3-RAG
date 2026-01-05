#!/usr/bin/env python3
"""
C3 Unified Query Tool

Query schemas, examples, and documentation for Construct 3.

Commands:
    c3query schema <type> <name> [ace-id]     Query ACE schema definitions
    c3query example <type> <query>            Query usage examples from 490 projects
    c3query search <query>                    Search across all data
    c3query top <type> [count]                Show top N by usage

Examples:
    c3query schema plugin sprite                    # List Sprite ACEs
    c3query schema plugin sprite set-animation      # Get set-animation details
    c3query schema behavior platform                # List Platform ACEs

    c3query example action create-object            # Find create-object usage
    c3query example condition collision             # Find collision examples
    c3query example behavior tween                  # Find Tween patterns

    c3query search simulate-control                 # Search everywhere
    c3query top actions 20                          # Top 20 actions
"""

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SCHEMAS_DIR = DATA_DIR / "schemas"
ANALYSIS_DIR = DATA_DIR / "project_analysis"

def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

# ============ Schema Queries ============

def query_schema(schema_type: str, name: str, ace_id: str = None):
    """Query plugin or behavior schema."""
    path = SCHEMAS_DIR / f"{schema_type}s" / f"{name.lower()}.json"

    if not path.exists():
        # Try fuzzy match
        for f in (SCHEMAS_DIR / f"{schema_type}s").glob("*.json"):
            if name.lower() in f.stem.lower():
                path = f
                break

    if not path.exists():
        available = [f.stem for f in (SCHEMAS_DIR / f"{schema_type}s").glob("*.json")]
        print(f"❌ Not found: {schema_type}/{name}")
        print(f"   Available: {', '.join(available[:10])}")
        return

    schema = load_json(path)
    print(f"\n📦 {schema.get('name', name)} ({schema_type})\n")

    if ace_id:
        # Find specific ACE
        for ace_type in ['conditions', 'actions', 'expressions']:
            for ace in schema.get(ace_type, []):
                if ace_id.lower() in ace.get('id', '').lower():
                    print(f"### {ace_type[:-1]}: `{ace['id']}`\n")

                    params = ace.get('params', [])
                    if params:
                        print("| Parameter | Type |")
                        print("|-----------|------|")
                        for p in params:
                            pid = p.get('id', '?')
                            ptype = p.get('type', 'any')
                            print(f"| `{pid}` | {ptype} |")

                            # Show combo values
                            if 'items' in p:
                                values = [i.get('id', str(i)) if isinstance(i, dict) else str(i) for i in p['items']]
                                print(f"    ↳ values: {', '.join(values)}")
                    else:
                        print("(no parameters)")
                    return
        print(f"❌ ACE not found: {ace_id}")
    else:
        # List all ACEs
        for ace_type in ['conditions', 'actions', 'expressions']:
            aces = schema.get(ace_type, [])
            if aces:
                print(f"## {ace_type.title()} ({len(aces)})\n")
                for ace in aces[:15]:  # Limit display
                    params = ', '.join(p.get('id', '?') for p in ace.get('params', []))
                    print(f"  `{ace['id']}` ({params or '-'})")
                if len(aces) > 15:
                    print(f"  ... and {len(aces) - 15} more")
                print()

# ============ Example Queries ============

def query_example(example_type: str, query: str):
    """Query usage examples."""
    file_map = {
        'action': 'actions_knowledge.json',
        'condition': 'conditions_knowledge.json',
        'behavior': 'behaviors_knowledge.json',
        'plugin': 'plugins_knowledge.json',
    }

    if example_type not in file_map:
        print(f"❌ Unknown type: {example_type}")
        print(f"   Valid: {', '.join(file_map.keys())}")
        return

    data = load_json(ANALYSIS_DIR / file_map[example_type])
    if not data:
        print(f"❌ No data found")
        return

    # Find matches
    matches = [(k, v) for k, v in data.items() if query.lower() in k.lower()]

    if not matches:
        print(f"❌ No matches for: {query}")
        print(f"   Try: {', '.join(list(data.keys())[:5])}")
        return

    print(f"\n🔍 Found {len(matches)} matches for `{query}`\n")

    for key, info in matches[:5]:
        print(f"### `{key}` (used {info.get('count', 0)} times)\n")

        # Show examples if available
        examples = info.get('examples', [])
        if examples:
            print("```json")
            for ex in examples[:2]:
                print(json.dumps(ex, ensure_ascii=False, indent=2))
            print("```")

        # Show common params
        params = info.get('common_params', {})
        if params:
            print("\nCommon values:")
            for param, values in list(params.items())[:3]:
                if isinstance(values, list):
                    print(f"  `{param}`: {values[:3]}")
                else:
                    print(f"  `{param}`: {values}")
        print()

# ============ Search All ============

def search_all(query: str):
    """Search across all data sources."""
    print(f"\n🔍 Searching: `{query}`\n")

    # Search schemas
    print("## Schemas\n")
    for schema_type in ['plugins', 'behaviors']:
        schema_dir = SCHEMAS_DIR / schema_type
        if not schema_dir.exists():
            continue
        for f in schema_dir.glob("*.json"):
            schema = load_json(f)
            for ace_type in ['conditions', 'actions']:
                for ace in schema.get(ace_type, []):
                    if query.lower() in ace.get('id', '').lower():
                        print(f"  [{schema_type[:-1]}:{f.stem}] {ace_type[:-1]}: `{ace['id']}`")

    # Search examples
    print("\n## Examples\n")
    for filename in ['actions_knowledge.json', 'conditions_knowledge.json']:
        data = load_json(ANALYSIS_DIR / filename)
        for key, info in data.items():
            if query.lower() in key.lower():
                print(f"  [{filename.split('_')[0]}] `{key}` (count: {info.get('count', 0)})")

# ============ Top N ============

def show_top(ace_type: str, count: int = 10):
    """Show top N by usage."""
    data = load_json(ANALYSIS_DIR / "sorted_indexes.json")
    key = f"top_50_{ace_type}"

    if key not in data:
        print(f"❌ Unknown: {ace_type}")
        print(f"   Valid: actions, conditions, behaviors, plugins")
        return

    print(f"\n📊 Top {count} {ace_type}\n")
    print("| # | ID | Count |")
    print("|---|-----|-------|")

    for i, item in enumerate(data[key][:count], 1):
        name = item.get('id', item.get('name', '?'))
        cnt = item.get('count', 0)
        print(f"| {i} | `{name}` | {cnt} |")

# ============ Main ============

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == 'schema' and len(sys.argv) >= 4:
        query_schema(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    elif cmd == 'example' and len(sys.argv) >= 4:
        query_example(sys.argv[2], sys.argv[3])
    elif cmd == 'search' and len(sys.argv) >= 3:
        search_all(sys.argv[2])
    elif cmd == 'top' and len(sys.argv) >= 3:
        count = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        show_top(sys.argv[2], count)
    else:
        print(__doc__)
        sys.exit(1)

if __name__ == "__main__":
    main()
