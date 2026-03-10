"""Parse Playwright browser_evaluate result file and save examples to JSON."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

SRC = Path(r"C:\Users\test\.claude\projects\D--Users-Administrator-Documents-GitHub-Construct3-RAG\8b9a2e90-6fd5-4d38-b2e1-db755f979609\tool-results\mcp-plugin_playwright_playwright-browser_evaluate-1772946314818.txt")
OUT = Path(r"D:\Users\Administrator\Documents\GitHub\Construct3-RAG\data\examples_browser.json")


def main():
    raw = SRC.read_text(encoding="utf-8")
    arr = json.loads(raw)
    text = arr[0]["text"]

    # Extract JSON between "### Result\n" and "\n### Ran Playwright"
    start = text.index("### Result\n") + len("### Result\n")
    end = text.index("\n### Ran Playwright")
    json_str = text[start:end].strip()

    data = json.loads(json_str)
    examples = data["examples"]
    print(f"Total examples: {len(examples)}")

    OUT.write_text(json.dumps(examples, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved to {OUT}")

    # Stats
    all_plugins = [p for ex in examples for p in ex.get("plugins", [])]
    all_behaviors = [b for ex in examples for b in ex.get("behaviors", [])]
    print("Top 10 plugins:", Counter(all_plugins).most_common(10))
    print("Top 10 behaviors:", Counter(all_behaviors).most_common(10))

    # Find wall-creature entry
    for ex in examples:
        if "wall" in ex["title"].lower() or "wall" in ex.get("description", "").lower():
            print("\nWall example:", json.dumps(ex, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
