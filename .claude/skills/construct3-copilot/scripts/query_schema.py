#!/usr/bin/env python3
"""
Query ACE schema definitions.

Usage:
    python query_schema.py plugin sprite              # List Sprite ACEs
    python query_schema.py plugin sprite set-animation # Get specific ACE
    python query_schema.py behavior platform          # List Platform ACEs
    python query_schema.py search create-object       # Search all schemas
"""

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent
SCHEMAS_DIR = PROJECT_ROOT / "data" / "schemas"

def load_schema(schema_type: str, name: str) -> dict:
    path = SCHEMAS_DIR / f"{schema_type}s" / f"{name.lower()}.json"
    if not path.exists():
        for f in (SCHEMAS_DIR / f"{schema_type}s").glob("*.json"):
            if name.lower() in f.stem.lower():
                path = f
                break
    if not path.exists():
        available = [f.stem for f in (SCHEMAS_DIR / f"{schema_type}s").glob("*.json")]
        print(f"❌ Not found: {name}\n   Available: {', '.join(available[:10])}")
        sys.exit(1)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def list_aces(schema: dict):
    name = schema.get('name_en', schema.get('name', schema.get('id', '?')))
    print(f"\n📦 {name}\n")
    for ace_type in ['conditions', 'actions', 'expressions']:
        aces = schema.get(ace_type, [])
        if aces:
            print(f"## {ace_type.title()} ({len(aces)})\n")
            for ace in aces:
                params = ', '.join(p.get('id', '?') for p in ace.get('params', []))
                print(f"  `{ace['id']}` ({params or '-'})")
            print()

def get_ace(schema: dict, ace_id: str):
    for ace_type in ['conditions', 'actions', 'expressions']:
        for ace in schema.get(ace_type, []):
            if ace_id.lower() in ace.get('id', '').lower():
                print(f"\n### {ace_type[:-1]}: `{ace['id']}`\n")
                params = ace.get('params', [])
                if params:
                    print("| Parameter | Type | Values |")
                    print("|-----------|------|--------|")
                    for p in params:
                        pid = p.get('id', '?')
                        ptype = p.get('type', 'any')
                        items = p.get('items', [])
                        if items:
                            vals = ', '.join(i.get('id', str(i)) if isinstance(i, dict) else str(i) for i in items)
                        else:
                            vals = '-'
                        print(f"| `{pid}` | {ptype} | {vals} |")
                else:
                    print("(no parameters)")
                return True
    print(f"❌ ACE not found: {ace_id}")
    return False

def search_all(query: str):
    print(f"\n🔍 Searching: `{query}`\n")
    for schema_type in ['plugins', 'behaviors']:
        schema_dir = SCHEMAS_DIR / schema_type
        if not schema_dir.exists():
            continue
        for f in schema_dir.glob("*.json"):
            with open(f, 'r', encoding='utf-8') as file:
                schema = json.load(file)
            for ace_type in ['conditions', 'actions']:
                for ace in schema.get(ace_type, []):
                    if query.lower() in ace.get('id', '').lower():
                        params = ', '.join(p.get('id', '?') for p in ace.get('params', []))
                        print(f"  [{schema_type[:-1]}:{f.stem}] `{ace['id']}` ({params or '-'})")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == 'search':
        search_all(sys.argv[2])
    elif cmd in ['plugin', 'behavior']:
        schema = load_schema(cmd, sys.argv[2])
        if len(sys.argv) > 3:
            get_ace(schema, sys.argv[3])
        else:
            list_aces(schema)
    else:
        print(__doc__)
