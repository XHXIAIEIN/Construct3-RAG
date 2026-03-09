# Examples Index & Vector Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add example project awareness to the RAG system via inverted index, vector collection, and ACE query auto-attachment.

**Architecture:** Three layers — (1) `ExamplesIndex` inverted index for fast tag→examples lookup in `LookupEngine`, (2) `c3_examples` Qdrant collection for semantic search, (3) auto-attach examples to ACE query results and new `example_find` intent. Chinese titles merged into embed text for cross-lingual matching.

**Tech Stack:** Python, Qdrant, bge-m3, existing `src/rag/lookup.py` + `src/ingest/indexer.py` patterns.

---

### Task 1: Build Inverted Index Script

**Files:**
- Create: `scripts/build_examples_index.py`
- Create: `data/examples_index.json` (output artifact)

**Background:** We have `data/examples_browser_en_r475.json` (529 items) and `data/examples_browser.json` (Chinese titles). Each item has a `tags` list with prefixed values like `plugin-Sprite`, `behavior-Tween`, `platformer`, `beginner`, `event-sheets-only`, etc.

The inverted index maps each tag to a list of example records containing fields needed for formatting.

**Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Build inverted index: tag -> [example records] from examples_browser_en_r475.json"""
import json
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).parent.parent / "data"
EN_FILE = DATA_DIR / "examples_browser_en_r475.json"
ZH_FILE = DATA_DIR / "examples_browser.json"
OUT_FILE = DATA_DIR / "examples_index.json"


def _parse_tags(tags: list[str]) -> dict:
    """Split data-tags into categorized lists."""
    plugins, behaviors, effects, genres, levels, categories, coding, misc = [], [], [], [], [], [], [], []
    for t in tags:
        if t.startswith("plugin-"):
            plugins.append(t[7:])
        elif t.startswith("behavior-"):
            behaviors.append(t[9:])
        elif t.startswith("effect-"):
            effects.append(t[7:])
        elif t in ("beginner", "intermediate", "advanced"):
            levels.append(t)
        elif t in ("event-sheets-only", "javascript", "typescript"):
            coding.append(t)
        elif t in ("action", "adventure", "animation", "arcade", "fighting",
                   "multiplayer", "platformer", "puzzle", "rpg", "racing", "shooter", "strategy"):
            genres.append(t)
        elif t in ("demo-game", "game-template", "barebones-template",
                   "gameplay-mechanic", "feature-example", "tech-demo", "guided-tour", "recommended"):
            categories.append(t)
        else:
            misc.append(t)
    return dict(plugins=plugins, behaviors=behaviors, effects=effects,
                genres=genres, levels=levels, categories=categories,
                coding=coding, misc=misc)


def build_index():
    en_items = json.loads(EN_FILE.read_text(encoding="utf-8"))
    zh_items = json.loads(ZH_FILE.read_text(encoding="utf-8"))

    # Build zh title lookup by English title
    zh_by_title = {item["title"]: item.get("title", "") for item in zh_items}
    # zh_items may use different field names - check first item
    if zh_items and "title" in zh_items[0]:
        zh_by_title = {item["title"]: item["title"] for item in zh_items}

    index = defaultdict(list)

    for item in en_items:
        slug = item.get("slug", "")
        title_en = item.get("title", "")
        parsed = _parse_tags(item.get("tags", []))

        record = {
            "title": title_en,
            "slug": slug,
            "genres": parsed["genres"],
            "behaviors": parsed["behaviors"],
            "plugins": parsed["plugins"],
            "level": parsed["levels"][0] if parsed["levels"] else "",
        }

        for tag in item.get("tags", []):
            index[tag].append(record)

    # Deduplicate (same example may appear multiple times for same tag if duplicated in source)
    deduped = {}
    for tag, records in index.items():
        seen = set()
        unique = []
        for r in records:
            key = r["slug"]
            if key not in seen:
                seen.add(key)
                unique.append(r)
        deduped[tag] = unique

    OUT_FILE.write_text(json.dumps(deduped, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Built index: {len(deduped)} tags, saved to {OUT_FILE}")
    # Print stats
    top = sorted(deduped.items(), key=lambda x: len(x[1]), reverse=True)[:5]
    for tag, recs in top:
        print(f"  {tag}: {len(recs)} examples")


if __name__ == "__main__":
    build_index()
```

**Step 2: Run the script**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe scripts/build_examples_index.py
```

Expected output:
```
Built index: ~200 tags, saved to data/examples_index.json
  plugin-Sprite: ~200 examples
  plugin-Keyboard: ~150 examples
  ...
```

**Step 3: Verify output**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -c "
import json
data = json.load(open('data/examples_index.json'))
print('tags:', len(data))
print('behavior-Tween:', len(data.get('behavior-Tween', [])))
print('first Tween example:', data.get('behavior-Tween', [{}])[0])
"
```

**Step 4: Commit**

```bash
git add scripts/build_examples_index.py data/examples_index.json
git commit -m "feat: build examples inverted index (tag → examples)"
```

---

### Task 2: ExamplesIndex Class + example_find Intent

**Files:**
- Modify: `src/rag/lookup.py` (add `ExamplesIndex` class, `example_find` intent, hook into `LookupEngine`)
- Modify: `tests/test_lookup.py` (add tests)

**Background:** `lookup.py` already has `SchemaIndex` and `TermIndex` classes following the same pattern. `LookupEngine.__init__` creates them. `IntentClassifier.classify()` returns a `LookupIntent` dataclass. `LookupEngine._execute()` dispatches by `intent_type`.

The `example_find` intent is triggered when the query contains example-seeking language ("有没有...示例", "example", "示例推荐") combined with a recognizable tag keyword.

**Step 1: Write failing tests**

Add to `tests/test_lookup.py`:

```python
class TestExamplesIndex:
    def setup_method(self):
        # Use real data/examples_index.json if present, else mock
        self.index = ExamplesIndex()

    def test_search_by_behavior_tag(self):
        results = self.index.search(["behavior-Tween"])
        assert isinstance(results, list)

    def test_search_returns_records_with_slug(self):
        results = self.index.search(["behavior-Tween"])
        if results:
            assert "slug" in results[0]
            assert "title" in results[0]

    def test_search_empty_tags(self):
        results = self.index.search([])
        assert results == []

    def test_search_unknown_tag(self):
        results = self.index.search(["behavior-Nonexistent99999"])
        assert results == []

    def test_format_for_ace_context(self):
        records = [
            {"title": "Cave Bridge", "slug": "cave-bridge", "genres": ["adventure"], "behaviors": ["Tween"]},
            {"title": "Kiwi Story", "slug": "kiwi-story", "genres": ["platformer"], "behaviors": ["Platform"]},
        ]
        result = ExamplesIndex.format_for_ace(records)
        assert "Cave Bridge" in result
        assert "cave-bridge" in result
        assert "Kiwi Story" in result

    def test_format_for_example_find(self):
        records = [
            {"title": "Cave Bridge", "slug": "cave-bridge", "genres": ["adventure"], "behaviors": ["Tween"]},
        ]
        result = ExamplesIndex.format_for_find(records)
        assert "Cave Bridge" in result
        assert "cave-bridge" in result
        assert "Adventure" in result or "adventure" in result
```

**Step 2: Run to confirm failure**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_lookup.py::TestExamplesIndex -v 2>&1 | head -30
```

Expected: `ImportError` or `AttributeError` (class not yet defined).

**Step 3: Implement ExamplesIndex**

Add after the `TermIndex` class in `src/rag/lookup.py`:

```python
class ExamplesIndex:
    """
    Inverted index: data-tag -> example records.
    Loaded from data/examples_index.json (built by scripts/build_examples_index.py).
    """

    _INDEX_PATH = Path(__file__).parent.parent.parent / "data" / "examples_index.json"

    def __init__(self, index_path: Optional[Path] = None):
        path = index_path or self._INDEX_PATH
        self._index: Dict[str, List[Dict]] = {}
        if path.exists():
            try:
                self._index = json.loads(path.read_text(encoding="utf-8"))
                logger.info(f"[ExamplesIndex] Loaded {len(self._index)} tags")
            except Exception as e:
                logger.warning(f"[ExamplesIndex] Failed to load: {e}")
        else:
            logger.warning(f"[ExamplesIndex] Index not found: {path}")

    def search(self, tags: List[str], max_results: int = 5) -> List[Dict]:
        """Find examples matching any of the given tags, ranked by overlap count."""
        if not tags:
            return []
        scores: Dict[str, Dict] = {}
        for tag in tags:
            for record in self._index.get(tag, []):
                slug = record.get("slug", "")
                if not slug:
                    continue
                if slug not in scores:
                    scores[slug] = {"record": record, "score": 0}
                scores[slug]["score"] += 1
        ranked = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
        return [r["record"] for r in ranked[:max_results]]

    @staticmethod
    def format_for_ace(records: List[Dict]) -> str:
        """Compact format for appending to ACE query results (no tags)."""
        if not records:
            return ""
        parts = [f"{r['title']} ({r['slug']})" for r in records if r.get("slug")]
        if not parts:
            return ""
        return "Related examples: " + ", ".join(parts)

    @staticmethod
    def format_for_find(records: List[Dict]) -> str:
        """Format for example_find intent results (with genre/behavior tags)."""
        if not records:
            return ""
        parts = []
        for r in records:
            if not r.get("slug"):
                continue
            tag_parts = r.get("genres", []) + r.get("behaviors", [])
            tag_str = f" [{', '.join(tag_parts[:3])}]" if tag_parts else ""
            parts.append(f"{r['title']} ({r['slug']}){tag_str}")
        if not parts:
            return ""
        return "Related examples: " + ", ".join(parts)
```

Also add `ExamplesIndex` import to the top of the file (it's defined in the same file, so just ensure it's accessible from tests by adding to `__all__` if needed, or just import in test with `from src.rag.lookup import ExamplesIndex`).

**Step 4: Run tests**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_lookup.py::TestExamplesIndex -v
```

Expected: All 6 tests pass.

**Step 5: Add example_find intent to IntentClassifier**

In `IntentClassifier.classify()`, before the final return, add detection for example queries. Find the section in `IntentClassifier` that handles intent classification and add:

```python
# example_find: "有没有Tween的示例", "platform game example"
EXAMPLE_KEYWORDS = {"示例", "example", "案例", "样例", "模板", "template"}

def _detect_example_find(self, query: str) -> Optional[LookupIntent]:
    """Detect example-seeking queries."""
    q_lower = query.lower()
    has_example_kw = any(kw in q_lower for kw in ("示例", "example", "案例", "样例", "模板", "template", "有没有"))
    if not has_example_kw:
        return None
    # Extract matching tags from query
    matched_tags = []
    for tag in self.schema_index._schemas:  # plugin IDs
        if tag.lower() in q_lower:
            matched_tags.append(f"plugin-{tag}")
    # Also check behavior names
    # (simple keyword match - expand as needed)
    return LookupIntent(
        intent_type="example_find",
        plugin_id="",
        filter_term=query,
        matched_tags=matched_tags,
    ) if matched_tags or has_example_kw else None
```

Note: `LookupIntent` dataclass needs a `matched_tags` field added:
```python
@dataclass
class LookupIntent:
    intent_type: str
    plugin_id: str
    ...
    matched_tags: List[str] = field(default_factory=list)  # ADD THIS
```

**Step 6: Wire into LookupEngine**

In `LookupEngine.__init__`, add:
```python
self.examples_index = ExamplesIndex()
```

In `LookupEngine._execute()`, add:
```python
elif intent.intent_type == "example_find":
    return self._format_example_find(intent)
```

Add method:
```python
def _format_example_find(self, intent: LookupIntent) -> str:
    tags = intent.matched_tags or []
    # Also try to extract tags from filter_term
    results = self.examples_index.search(tags, max_results=5)
    return ExamplesIndex.format_for_find(results)
```

**Step 7: Run all lookup tests**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_lookup.py -v 2>&1 | tail -20
```

Expected: All tests pass (including existing 50+).

**Step 8: Commit**

```bash
git add src/rag/lookup.py tests/test_lookup.py
git commit -m "feat: add ExamplesIndex + example_find intent to LookupEngine"
```

---

### Task 3: Auto-Attach Examples to ACE Results

**Files:**
- Modify: `src/rag/lookup.py` (`_format_ace_list`, `_format_ace_detail`)

**Background:** When the user asks about a specific plugin's ACE (e.g., "Tween 的动作有哪些"), after returning the ACE list, we append related examples using the plugin/behavior tag.

**Step 1: Write failing test**

Add to `tests/test_lookup.py`:

```python
class TestACEExampleAttach:
    def test_ace_list_appends_examples(self):
        """ACE list result should include Related examples section when examples exist."""
        engine = LookupEngine()
        # Query for Tween behavior ACE list
        intent = LookupIntent(
            intent_type="ace_list",
            plugin_id="tween",
            is_behavior=True,
            ace_type="actions",
            filter_term="",
            matched_tags=["behavior-Tween"],
        )
        result = engine._format_ace_list(intent)
        # Only check if examples index has data
        if engine.examples_index._index:
            assert "Related examples" in result
```

**Step 2: Run to confirm failure**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_lookup.py::TestACEExampleAttach -v
```

**Step 3: Implement auto-attach**

In `_format_ace_list`, at the end before `return`, add:

```python
# Append related examples
example_tags = [f"behavior-{intent.plugin_id}" if intent.is_behavior else f"plugin-{intent.plugin_id}"]
example_records = self.examples_index.search(example_tags, max_results=3)
example_line = ExamplesIndex.format_for_ace(example_records)
if example_line:
    lines.append("")
    lines.append(example_line)
```

Do the same in `_format_ace_detail`.

**Step 4: Run tests**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_lookup.py -v 2>&1 | tail -20
```

**Step 5: Commit**

```bash
git add src/rag/lookup.py tests/test_lookup.py
git commit -m "feat: auto-attach related examples to ACE query results"
```

---

### Task 4: Index c3_examples Collection

**Files:**
- Modify: `src/ingest/indexer.py` (update examples indexing section)
- Create: `src/ingest/examples_parser.py`

**Background:** `indexer.py` already has a stub for `c3_examples` that calls `process_example_projects()` (for event sheet projects). We replace/augment this with our browser data. The embed text merges zh+en title with all tag categories.

**Step 1: Create examples_parser.py**

```python
"""Parse examples_browser_en_r475.json + examples_browser.json for vector indexing."""
import json
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def _parse_tags(tags: list[str]) -> dict:
    """Categorize data-tags into typed lists."""
    plugins, behaviors, effects, genres, levels, categories, coding, misc = [], [], [], [], [], [], [], []
    for t in tags:
        if t.startswith("plugin-"):
            plugins.append(t[7:])
        elif t.startswith("behavior-"):
            behaviors.append(t[9:])
        elif t.startswith("effect-"):
            effects.append(t[7:])
        elif t in ("beginner", "intermediate", "advanced"):
            levels.append(t)
        elif t in ("event-sheets-only", "javascript", "typescript"):
            coding.append(t)
        elif t in ("action", "adventure", "animation", "arcade", "fighting",
                   "multiplayer", "platformer", "puzzle", "rpg", "racing", "shooter", "strategy"):
            genres.append(t)
        else:
            categories.append(t)
    return dict(plugins=plugins, behaviors=behaviors, effects=effects,
                genres=genres, level=levels[0] if levels else "",
                categories=categories, coding=coding)


def build_embed_text(title_zh: str, title_en: str, parsed: dict) -> str:
    """Build embed text for bge-m3 vector indexing."""
    parts = []
    if title_zh and title_zh != title_en:
        parts.append(f"{title_zh} | {title_en}")
    else:
        parts.append(title_en)
    if parsed["plugins"]:
        parts.append("plugins: " + ", ".join(parsed["plugins"]))
    if parsed["behaviors"]:
        parts.append("behaviors: " + ", ".join(parsed["behaviors"]))
    if parsed["genres"]:
        parts.append("genres: " + ", ".join(parsed["genres"]))
    if parsed["level"]:
        parts.append("level: " + parsed["level"])
    if parsed["coding"]:
        parts.append("coding: " + ", ".join(parsed["coding"]))
    if parsed["effects"]:
        parts.append("effects: " + ", ".join(parsed["effects"][:5]))  # cap effects
    return " | ".join(parts)


def load_examples_for_vectordb(
    en_path: Optional[Path] = None,
    zh_path: Optional[Path] = None,
) -> list[dict]:
    """Return list of {id, text, metadata} dicts for Qdrant indexing."""
    en_path = en_path or DATA_DIR / "examples_browser_en_r475.json"
    zh_path = zh_path or DATA_DIR / "examples_browser.json"

    en_items = json.loads(en_path.read_text(encoding="utf-8"))
    zh_items = json.loads(zh_path.read_text(encoding="utf-8")) if zh_path.exists() else []

    # Build zh title lookup
    zh_by_en_title = {}
    for item in zh_items:
        title_en = item.get("title", "")
        if title_en:
            zh_by_en_title[title_en] = item.get("title_zh") or item.get("title", "")

    docs = []
    for i, item in enumerate(en_items):
        title_en = item.get("title", "")
        title_zh = zh_by_en_title.get(title_en, title_en)
        slug = item.get("slug", "")
        parsed = _parse_tags(item.get("tags", []))

        embed_text = build_embed_text(title_zh, title_en, parsed)
        docs.append({
            "id": f"example_{i}",
            "text": embed_text,
            "metadata": {
                "title_en": title_en,
                "title_zh": title_zh,
                "slug": slug,
                "example_type": item.get("exampleType", ""),
                "plugins": parsed["plugins"],
                "behaviors": parsed["behaviors"],
                "genres": parsed["genres"],
                "level": parsed["level"],
                "coding": parsed["coding"],
                "slug_derived": item.get("slug_derived", False),
            }
        })
    return docs
```

**Step 2: Update indexer.py**

Find the `# Index example projects` section in `indexer.py` and update it:

```python
# Index example projects (browser data)
print("\n=== Indexing Example Projects ===")
indexer.create_collection(COLLECTIONS["examples"], recreate=rebuild)
from src.ingest.examples_parser import load_examples_for_vectordb
example_docs = load_examples_for_vectordb()
if example_docs:
    indexer.index_documents(COLLECTIONS["examples"], example_docs)
    print(f"  Indexed {len(example_docs)} examples")
```

**Step 3: Write test for examples_parser**

Create `tests/test_examples_parser.py`:

```python
"""Tests for examples_parser - no external services required."""
from src.ingest.examples_parser import build_embed_text, load_examples_for_vectordb, _parse_tags


class TestParseTagsAndEmbed:
    def test_parse_plugin_tags(self):
        parsed = _parse_tags(["plugin-Sprite", "plugin-Tween", "beginner"])
        assert "Sprite" in parsed["plugins"]
        assert "Tween" in parsed["plugins"]
        assert parsed["level"] == "beginner"

    def test_parse_behavior_tags(self):
        parsed = _parse_tags(["behavior-Platform", "behavior-Tween"])
        assert "Platform" in parsed["behaviors"]
        assert "Tween" in parsed["behaviors"]

    def test_parse_effect_tags(self):
        parsed = _parse_tags(["effect-blur", "effect-noise"])
        assert "blur" in parsed["effects"]

    def test_build_embed_text_basic(self):
        parsed = _parse_tags(["plugin-Sprite", "behavior-Platform", "platformer", "intermediate"])
        text = build_embed_text("平台游戏", "Platform Game", parsed)
        assert "平台游戏" in text
        assert "Platform Game" in text
        assert "Sprite" in text
        assert "Platform" in text
        assert "platformer" in text
        assert "intermediate" in text

    def test_build_embed_text_same_title(self):
        parsed = _parse_tags(["plugin-Sprite"])
        text = build_embed_text("Cave Bridge", "Cave Bridge", parsed)
        assert text.count("Cave Bridge") == 1  # not duplicated

    def test_load_returns_list(self):
        docs = load_examples_for_vectordb()
        assert isinstance(docs, list)
        if docs:
            assert "id" in docs[0]
            assert "text" in docs[0]
            assert "metadata" in docs[0]
            assert "slug" in docs[0]["metadata"]

    def test_load_embed_text_not_empty(self):
        docs = load_examples_for_vectordb()
        for doc in docs:
            assert doc["text"].strip(), f"Empty embed text for {doc['id']}"
```

**Step 4: Run tests**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_examples_parser.py -v
```

Expected: All 7 tests pass.

**Step 5: Commit**

```bash
git add src/ingest/examples_parser.py tests/test_examples_parser.py src/ingest/indexer.py
git commit -m "feat: add examples_parser + update indexer for c3_examples collection"
```

---

### Task 5: Add c3_examples to Retrieval Path

**Files:**
- Modify: `src/rag/retriever.py` (add `search_examples` method)
- Modify: `src/rag/chain.py` (include examples collection in smart retrieval)

**Background:** `retriever.py` already has methods like `search_guide`, `search_plugins` etc. that call `search_collection`. We add `search_examples` following the same pattern. In `chain.py`, `answer_smart` determines which collections to search — add `examples` when query has example-seeking intent.

**Step 1: Add search_examples to retriever.py**

Find the last `search_*` method and add after it:

```python
def search_examples(self, query: str, top_k: int = 3) -> List[SearchResult]:
    from src.collections import COLLECTIONS
    return self.search_collection(COLLECTIONS["examples"], query, top_k)
```

**Step 2: Update chain.py smart retrieval**

In `chain.py`, find where collections are selected for retrieval. Add examples collection when query contains example-seeking keywords:

```python
EXAMPLE_KEYWORDS = {"示例", "example", "案例", "样例", "模板", "template"}

def _wants_examples(self, query: str) -> bool:
    q = query.lower()
    return any(kw in q for kw in EXAMPLE_KEYWORDS)
```

In the retrieval section, add:
```python
if self._wants_examples(query):
    results += self.retriever.search_examples(query, top_k=3)
```

**Step 3: Run existing tests to verify no regression**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/ -v 2>&1 | tail -30
```

Expected: All existing tests still pass.

**Step 4: Commit**

```bash
git add src/rag/retriever.py src/rag/chain.py
git commit -m "feat: add c3_examples to retrieval path for example-seeking queries"
```

---

### Task 6: Re-index with Qdrant (Integration)

**Note:** Requires Qdrant running (`docker run -d -p 6333:6333 qdrant/qdrant`).

**Step 1: Run indexer for examples collection only**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m src.ingest.indexer --rebuild
```

Or add a `--collections examples` flag if supported, else run full rebuild.

**Step 2: Verify collection populated**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -c "
from qdrant_client import QdrantClient
client = QdrantClient(host='localhost', port=6333)
info = client.get_collection('c3_examples')
print('vectors:', info.points_count)
"
```

Expected: `vectors: 529`

**Step 3: Smoke test retrieval**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -c "
from src.rag.retriever import HybridRetriever
r = HybridRetriever()
results = r.search_examples('platform game with tween animation', top_k=3)
for res in results:
    print(res.payload.get('title_en'), res.score)
"
```

**Step 4: Commit**

```bash
git add .
git commit -m "feat: examples index complete - inverted index + vector collection + retrieval"
```

---

### Task 7: Run Full Test Suite + Verify

**Step 1: Run all tests**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/ -v
```

Expected: All tests pass.

**Step 2: Manual smoke test via chat**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe scripts/chat.py
```

Test queries:
- "有没有用Tween的示例？"
- "Tween行为有哪些动作？"  (should append related examples)
- "platform game example"

**Step 3: Final commit**

```bash
git add .
git commit -m "feat: examples awareness complete (inverted index + vector + ACE attach)"
```
