#!/usr/bin/env python3
"""Build eval dataset from real LoRA training data (not AI-generated).

Sources:
  - Construct3-LoRA/data/pairs/lookup_chain.jsonl  (ACE query→doc pairs)
  - Construct3-LoRA/data/pairs/manual_chunks.jsonl  (doc section chunks)

Output:
  - data/ragas_dataset.json
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

random.seed(42)

LORA_DIR = Path(__file__).parent.parent.parent / "Construct3-LoRA" / "data" / "pairs"
OUTPUT = Path(__file__).parent.parent / "data" / "ragas_dataset.json"


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build_ace_cases(lookup_data, n=30):
    """Sample ACE lookup cases — real Chinese queries mapped to plugin docs."""
    by_plugin = {}
    for entry in lookup_data:
        p = entry.get("plugin", "unknown")
        by_plugin.setdefault(p, []).append(entry)

    sampled = random.sample(list(by_plugin.keys()), min(n, len(by_plugin)))
    cases = []
    for plugin in sorted(sampled):
        entries = by_plugin[plugin]
        pick = random.choice(entries)
        cases.append({
            "id": f"L{len(cases)+1:03d}",
            "query": pick["query"],
            "ground_truth": pick["positive"][:500],
            "expected_keywords": [pick["query"]],
            "category": "ace_lookup",
            "forbidden_phrases": [],
            "has_answer": True,
            "note": f"lookup_chain, plugin={plugin}",
            "expected_sources": ["construct3-schema"],
            "expected_collections": ["ace"],
            "retrieval_difficulty": "easy",
        })
    return cases


def _detect_collection(source_path):
    """Map source path to collection key."""
    s = source_path.lower()
    if s.startswith("plugin-reference"):
        return "plugins"
    if s.startswith("behavior-reference") or s.startswith("system-reference"):
        return "behaviors"
    if s.startswith("project-primitives"):
        return "project"
    if s.startswith("interface"):
        return "interface"
    if s.startswith("scripting"):
        return "scripting"
    return "guide"


def build_doc_cases(chunks_data, n=30):
    """Sample doc section cases — doc title + H2 as query, source as ground truth."""
    by_source = {}
    for c in chunks_data:
        s = c.get("source", "")
        if s:
            by_source.setdefault(s, []).append(c)

    sampled = random.sample(list(by_source.keys()), min(n, len(by_source)))
    cases = []
    for src in sorted(sampled):
        entries = by_source[src]
        pick = random.choice(entries)
        title = pick.get("doc_title", "")
        h2 = pick.get("h2_title", "")
        query = f"{title} {h2}".strip()
        if not query:
            continue

        src_path = pick["source"]
        bs = src_path.replace("/", "\\")
        coll = _detect_collection(src_path)

        cases.append({
            "id": f"D{len(cases)+1:03d}",
            "query": query,
            "ground_truth": pick["text"][:500],
            "expected_keywords": [w for w in query.split() if len(w) > 2][:5],
            "category": "doc_section",
            "forbidden_phrases": [],
            "has_answer": True,
            "note": f"manual_chunks, source={src_path}",
            "expected_sources": [bs],
            "expected_collections": [coll],
            "retrieval_difficulty": "medium",
        })
    return cases


def main():
    lookup = load_jsonl(LORA_DIR / "lookup_chain.jsonl")
    chunks = load_jsonl(LORA_DIR / "manual_chunks.jsonl")
    print(f"Loaded: {len(lookup)} lookup pairs, {len(chunks)} doc chunks")

    ace_cases = build_ace_cases(lookup, n=30)
    doc_cases = build_doc_cases(chunks, n=30)
    all_cases = ace_cases + doc_cases

    print(f"Built {len(all_cases)} eval cases:")
    print(f"  ACE lookup: {len(ace_cases)}")
    print(f"  Doc section: {len(doc_cases)}")

    # Category/collection distribution
    from collections import Counter
    cats = Counter(c["category"] for c in all_cases)
    colls = Counter(c["expected_collections"][0] for c in all_cases if c["expected_collections"])
    print(f"  Categories: {dict(cats)}")
    print(f"  Collections: {dict(colls)}")

    OUTPUT.write_text(json.dumps(all_cases, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()
