# Source-Driven Indexing: Official CDN as Single Source of Truth

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all intermediate/derived data artifacts with a live fetch pipeline from Construct 3's official CDN (`editor.construct.net`), so that updating to a new C3 release is a single version-number change + rebuild.

**Architecture:** A new `C3Fetcher` class downloads JSON from the official CDN, caches locally, and feeds into existing parsers. Schema parser and examples parser are rewritten to consume CDN data instead of local intermediates. Version detection is automatic via `versions.json`.

**Tech Stack:** Python 3.14, `urllib`/`requests`, Qdrant, existing parser infrastructure

---

## Official CDN Endpoint Map

Base URL: `https://editor.construct.net/r{version}/`

| Endpoint | Content | Replaces |
|----------|---------|----------|
| `versions.json` | All release versions + launch URLs | Manual version tracking |
| `plugins/pluginList.json` | 84 plugin IDs → paths | — |
| `behaviors/behaviorList.json` | 31 behavior IDs → paths | — |
| `plugins/allAces.json` | All plugin ACE definitions (2424 entries) | `data/schemas/plugins/*.json` |
| `behaviors/allAces.json` | All behavior ACE definitions (503 entries) | `data/schemas/behaviors/*.json` |
| `effects/allEffects.json` | 89 effects + shader code + parameters | `data/schemas/effects/*.json` |
| `loader/lang/precompiled-en-US.json` | English names, descriptions, params for all plugins/behaviors | Local `lang/en-US.json` files |
| `loader/lang/precompiled-zh-CN.json` | Chinese names, descriptions, params for all plugins/behaviors | `data/source/zh_r475.csv` |
| `media/example-project-data.json` | 481 example projects with tags, used-addons | `examples_browser_{en,cn}_r475.json` |

**Key constraint:** CDN returns 403 without a browser User-Agent header.

## Data Join Logic

ACE indexing requires joining 3 sources:

```
allAces.json          → ACE IDs, scriptNames, params (structure)
precompiled-en-US.json → English names, descriptions, param names
precompiled-zh-CN.json → Chinese names, descriptions, param names

Join key: plugin_id + ace_category + ace_type + ace_id
```

Example join for Sprite's "Is playing" condition:
```
allAces["Sprite"]["animations"]["conditions"][0]
  → id: "is-animation-playing", scriptName: "IsAnimPlaying"

en-US["text"]["plugins"]["sprite"]["conditions"]["is-animation-playing"]
  → list-name: "Is playing", description: "Test which animation is playing"

zh-CN["text"]["plugins"]["sprite"]["conditions"]["is-animation-playing"]
  → list-name: "正在播放", description: "检测当前正在播放的动画"
```

**Note:** Plugin IDs in allAces use PascalCase (`Sprite`, `AJAX`), while lang files use lowercase (`sprite`, `ajax`). Need case-insensitive matching or ID normalization.

## Files to Create / Modify

| Action | File | Responsibility |
|--------|------|----------------|
| **Create** | `src/ingest/c3_fetcher.py` | Fetch + cache CDN JSON, version detection |
| **Rewrite** | `src/ingest/schema_parser.py` | Parse ACE from CDN data (allAces + lang), not data/schemas/ |
| **Rewrite** | `src/ingest/examples_parser.py` | Parse examples from CDN + c3proj, not browser JSON |
| **Modify** | `src/ingest/indexer.py` | Wire new parsers, remove generate-schema dependency |
| **Modify** | `src/config.py` | Add C3_VERSION, C3_CDN_BASE, C3_CACHE_DIR configs |
| **Create** | `tests/test_c3_fetcher.py` | Fetcher tests (with mocked HTTP) |
| **Create** | `tests/test_schema_parser_cdn.py` | Schema parser tests with CDN data |
| **Create** | `tests/test_examples_parser_cdn.py` | Examples parser tests with CDN data |

## Files to Delete (after migration stable)

| File | Reason |
|------|--------|
| `data/examples_browser_en_r475.json` | Replaced by CDN example-project-data.json |
| `data/examples_browser_cn_r475.json` | Replaced by CDN precompiled-zh-CN.json |
| `data/examples_index.json` | Derived from browser JSON |
| `scripts/generate-schema.js` | Replaced by Python CDN parser |
| `scripts/patch-schema-zh.js` | Replaced by CDN zh-CN lang |

## Files to Keep (still needed)

| File | Reason |
|------|--------|
| `data/schemas/` | Fallback when CDN unreachable; remove after stable |
| `data/source/zh_r475.csv` | Used by csv_parser for c3_terms collection (separate from ACE) |
| `src/ingest/markdown_parser.py` | Already reads Manual directly |
| `src/ingest/event_parser.py` | Already reads Example-Projects directly |
| `src/ingest/csv_parser.py` | Still needed for c3_terms (translation vocabulary) |

---

## Chunk 1: C3 Fetcher — CDN Access Layer

### Task 1: Write C3Fetcher with caching

**Files:**
- Create: `src/ingest/c3_fetcher.py`
- Create: `tests/test_c3_fetcher.py`
- Modify: `src/config.py`

- [ ] **Step 1: Add config variables**

In `src/config.py`, add:
```python
# Construct 3 CDN
C3_VERSION = os.getenv("C3_VERSION", "r476")
C3_CDN_BASE = os.getenv("C3_CDN_BASE", "https://editor.construct.net")
C3_CACHE_DIR = Path(os.getenv("C3_CACHE_DIR", str(BASE_DIR / ".cache" / "c3-cdn")))
```

- [ ] **Step 2: Write failing test for fetcher**

```python
# tests/test_c3_fetcher.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.ingest.c3_fetcher import C3Fetcher


@pytest.fixture
def fetcher(tmp_path):
    return C3Fetcher(version="r476", cache_dir=tmp_path)


def test_fetch_caches_locally(fetcher):
    """Fetched data is cached to disk."""
    mock_data = {"pluginList": {"Sprite": {"path": "general/sprite"}}}
    with patch.object(fetcher, "_http_get", return_value=json.dumps(mock_data).encode()):
        result = fetcher.fetch("plugins/pluginList.json")
        assert result == mock_data
        # Second call should use cache, not HTTP
        fetcher._http_get = MagicMock(side_effect=Exception("should not be called"))
        result2 = fetcher.fetch("plugins/pluginList.json")
        assert result2 == mock_data


def test_get_latest_version(fetcher):
    """Detect latest stable version from versions.json."""
    mock_versions = [
        {"branchName": "Stable", "releaseName": "r476", "launchURL": "https://editor.construct.net"},
        {"branchName": "Beta", "releaseName": "r477", "launchURL": "https://editor.construct.net/r477/"},
    ]
    with patch.object(fetcher, "_http_get", return_value=json.dumps(mock_versions).encode()):
        assert fetcher.get_latest_stable_version() == "r476"


def test_fetch_all_aces(fetcher):
    """Convenience method returns joined plugin + behavior ACEs."""
    mock_plugin_aces = {"Sprite": {"": {"conditions": [{"id": "c1"}]}}}
    mock_behavior_aces = {"Platform": {"": {"actions": [{"id": "a1"}]}}}
    with patch.object(fetcher, "fetch", side_effect=[mock_plugin_aces, mock_behavior_aces]):
        result = fetcher.fetch_all_aces()
        assert "Sprite" in result["plugins"]
        assert "Platform" in result["behaviors"]
```

- [ ] **Step 3: Implement C3Fetcher**

```python
# src/ingest/c3_fetcher.py
"""Fetch Construct 3 data from official CDN with local caching."""
import json
import logging
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145.0.0.0"


class C3Fetcher:
    """Fetch and cache Construct 3 CDN data."""

    def __init__(self, version: str = "r476", base_url: str = "https://editor.construct.net",
                 cache_dir: Path | None = None):
        self.version = version
        self.base_url = base_url.rstrip("/")
        if cache_dir is None:
            from src.config import C3_CACHE_DIR
            cache_dir = C3_CACHE_DIR
        self.cache_dir = Path(cache_dir) / version
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _http_get(self, url: str) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()

    def fetch(self, path: str, force: bool = False) -> dict | list:
        cache_path = self.cache_dir / path.replace("/", "_")
        if not force and cache_path.exists():
            raw = cache_path.read_bytes()
        else:
            url = f"{self.base_url}/{self.version}/{path}"
            logger.info(f"[CDN] Fetching {url}")
            raw = self._http_get(url)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(raw)
        # Handle BOM
        if raw[:3] == b"\xef\xbb\xbf":
            raw = raw[3:]
        return json.loads(raw)

    def get_latest_stable_version(self) -> str:
        url = f"{self.base_url}/versions.json"
        raw = self._http_get(url)
        if raw[:3] == b"\xef\xbb\xbf":
            raw = raw[3:]
        versions = json.loads(raw)
        for v in versions:
            if v.get("branchName") == "Stable":
                return v["releaseName"]
        return self.version

    def fetch_all_aces(self) -> dict:
        return {
            "plugins": self.fetch("plugins/allAces.json"),
            "behaviors": self.fetch("behaviors/allAces.json"),
        }

    def fetch_lang(self, locale: str = "en-US") -> dict:
        return self.fetch(f"loader/lang/precompiled-{locale}.json")

    def fetch_effects(self) -> list:
        data = self.fetch("effects/allEffects.json")
        return data.get("all", data) if isinstance(data, dict) else data

    def fetch_examples(self) -> list:
        data = self.fetch("media/example-project-data.json")
        return data.get("projects", data) if isinstance(data, dict) else data

    def fetch_plugin_list(self) -> dict:
        data = self.fetch("plugins/pluginList.json")
        return data.get("pluginList", data) if isinstance(data, dict) else data

    def fetch_behavior_list(self) -> dict:
        data = self.fetch("behaviors/behaviorList.json")
        return data.get("behaviorList", data) if isinstance(data, dict) else data
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_c3_fetcher.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/ingest/c3_fetcher.py tests/test_c3_fetcher.py src/config.py
git commit -m "feat: add C3Fetcher — CDN access layer with caching"
```

---

## Chunk 2: Schema Parser — Read from CDN

### Task 2: Rewrite SchemaParser to consume CDN data

**Files:**
- Modify: `src/ingest/schema_parser.py`
- Create: `tests/test_schema_parser_cdn.py`

The new SchemaParser takes a `C3Fetcher` and joins 3 data sources:
1. `allAces.json` → ACE structure (id, scriptName, params, isTriggered)
2. `precompiled-en-US.json` → English names, descriptions
3. `precompiled-zh-CN.json` → Chinese names, descriptions

- [ ] **Step 6: Write failing test**

```python
# tests/test_schema_parser_cdn.py
import pytest
from unittest.mock import MagicMock

from src.ingest.schema_parser import SchemaParser, ACEEntry


@pytest.fixture
def mock_fetcher():
    f = MagicMock()
    f.fetch_all_aces.return_value = {
        "plugins": {
            "Sprite": {
                "animations": {
                    "conditions": [{"id": "is-animation-playing", "scriptName": "IsAnimPlaying",
                                    "params": [{"id": "animation", "type": "animation"}]}],
                    "actions": [],
                    "expressions": [],
                }
            }
        },
        "behaviors": {},
    }
    f.fetch_lang.side_effect = lambda locale: {
        "text": {
            "plugins": {
                "sprite": {
                    "name": "Sprite" if "en" in locale else "精灵",
                    "conditions": {
                        "is-animation-playing": {
                            "list-name": "Is playing" if "en" in locale else "正在播放",
                            "description": "Test animation" if "en" in locale else "检测动画",
                            "params": {"animation": {"name": "Animation" if "en" in locale else "动画"}}
                        }
                    },
                    "actions": {}, "expressions": {},
                }
            },
            "behaviors": {},
        }
    }
    return f


def test_parse_from_cdn(mock_fetcher):
    parser = SchemaParser(fetcher=mock_fetcher)
    entries = parser.parse_ace_entries()
    assert len(entries) == 1
    e = entries[0]
    assert e.ace_id == "is-animation-playing"
    assert e.name_en == "Is playing"
    assert e.name_zh == "正在播放"
    assert e.plugin_name == "Sprite"
    assert e.plugin_name_zh == "精灵"
    assert e.script_name == "IsAnimPlaying"
```

- [ ] **Step 7: Implement CDN-driven SchemaParser**

Key changes to `SchemaParser.__init__`:
- Accept `fetcher: C3Fetcher` parameter
- If fetcher provided: use CDN data
- If not: fall back to `schema_dir` (existing behavior, backward compat)

Key logic in `parse_ace_entries()`:
```python
aces_data = self.fetcher.fetch_all_aces()
en_lang = self.fetcher.fetch_lang("en-US").get("text", {})
zh_lang = self.fetcher.fetch_lang("zh-CN").get("text", {})

for addon_type in ["plugins", "behaviors"]:
    lang_key = addon_type  # same key in lang files
    for plugin_id, categories in aces_data[addon_type].items():
        plugin_id_lower = plugin_id.lower()
        en_plugin = en_lang.get(lang_key, {}).get(plugin_id_lower, {})
        zh_plugin = zh_lang.get(lang_key, {}).get(plugin_id_lower, {})
        plugin_name_en = en_plugin.get("name", plugin_id)
        plugin_name_zh = zh_plugin.get("name", plugin_name_en)

        for category, ace_types in categories.items():
            for ace_type in ["conditions", "actions", "expressions"]:
                for ace in ace_types.get(ace_type, []):
                    ace_id = ace["id"]
                    en_ace = en_plugin.get(ace_type, {}).get(ace_id, {})
                    zh_ace = zh_plugin.get(ace_type, {}).get(ace_id, {})
                    # Build ACEEntry with joined data...
```

- [ ] **Step 8: Run tests**

Run: `python -m pytest tests/test_schema_parser_cdn.py -v`

- [ ] **Step 9: Verify against current data**

```bash
python -c "
from src.ingest.c3_fetcher import C3Fetcher
from src.ingest.schema_parser import SchemaParser

# CDN way
fetcher = C3Fetcher(version='r476')
cdn_parser = SchemaParser(fetcher=fetcher)
cdn_entries = cdn_parser.parse_ace_entries()
cdn_docs = cdn_parser.export_ace_for_vectordb(cdn_entries)

# Old way
old_parser = SchemaParser()
old_entries = old_parser.parse_ace_entries()
old_docs = old_parser.export_ace_for_vectordb(old_entries)

print(f'CDN: {len(cdn_entries)} ACEs → {len(cdn_docs)} docs')
print(f'Old: {len(old_entries)} ACEs → {len(old_docs)} docs')
"
```

- [ ] **Step 10: Commit**

```bash
git add src/ingest/schema_parser.py tests/test_schema_parser_cdn.py
git commit -m "feat: schema_parser reads ACE from official CDN"
```

---

## Chunk 3: Examples Parser — Read from CDN + c3proj

### Task 3: Rewrite examples_parser

**Files:**
- Modify: `src/ingest/examples_parser.py`
- Create: `tests/test_examples_parser_cdn.py`

Two data sources merged:
1. CDN `media/example-project-data.json` → tags, used-addons (English)
2. CDN `precompiled-zh-CN.json` → NOT for examples (it doesn't have example titles)
3. Local `Example-Projects/*/project.c3proj` → layouts, eventSheets, c3_version

For Chinese example titles: CDN example-project-data only has English. Chinese titles are NOT in the precompiled lang file. Options:
- Keep `examples_browser_cn_r475.json` just for title translations (lightweight)
- Or drop Chinese titles for examples (use English only)
- Or build a title translation map from the CN browser JSON as a one-time export

**Decision:** Use English titles from CDN. Chinese titles are nice-to-have but not critical for retrieval (ACE names and plugin IDs drive matching, not example titles).

- [ ] **Step 11: Write failing test**

```python
# tests/test_examples_parser_cdn.py
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.ingest.examples_parser import load_examples_for_vectordb


@pytest.fixture
def mock_fetcher():
    f = MagicMock()
    f.fetch_examples.return_value = [
        {
            "id": "platformer-basics",
            "tags": ["beginner", "game-template", "platformer"],
            "used-addons": {
                "plugins": ["Sprite", "Keyboard"],
                "behaviors": ["Platform", "Solid"],
                "effects": [],
            },
        },
    ]
    return f


@pytest.fixture
def fake_projects(tmp_path):
    proj = tmp_path / "platformer-basics"
    proj.mkdir()
    (proj / "project.c3proj").write_text(json.dumps({
        "name": "Platformer Basics",
        "savedWithRelease": 47600,
        "usedAddons": [
            {"type": "plugin", "id": "Sprite", "name": "Sprite"},
            {"type": "plugin", "id": "Keyboard", "name": "Keyboard"},
            {"type": "behavior", "id": "Platform", "name": "Platform"},
        ],
        "layouts": {"items": ["Game"]},
        "eventSheets": {"items": ["Events"]},
    }), encoding="utf-8")
    return tmp_path


def test_loads_from_cdn_plus_c3proj(mock_fetcher, fake_projects):
    docs = load_examples_for_vectordb(fetcher=mock_fetcher, projects_dir=fake_projects)
    assert len(docs) == 1
    d = docs[0]
    assert d["metadata"]["slug"] == "platformer-basics"
    assert "Sprite" in d["metadata"]["plugins"]
    assert "Platform" in d["metadata"]["behaviors"]
    assert "Platformer Basics" in d["text"]
```

- [ ] **Step 12: Implement CDN-driven examples_parser**

New `load_examples_for_vectordb` signature:
```python
def load_examples_for_vectordb(
    fetcher: C3Fetcher | None = None,
    projects_dir: Path | None = None,
) -> list[dict]:
```

Logic:
1. `fetcher.fetch_examples()` → get all example metadata (tags, used-addons)
2. For each example, `slug = example["id"]`
3. Try `projects_dir / slug / project.c3proj` for enrichment (layouts, eventSheets, version)
4. Title from c3proj `"name"` field (or slug as fallback)
5. `build_embed_text()` with CDN addons + c3proj enrichment

- [ ] **Step 13: Run tests + verify counts**

```bash
python -m pytest tests/test_examples_parser_cdn.py -v
python -c "
from src.ingest.c3_fetcher import C3Fetcher
from src.ingest.examples_parser import load_examples_for_vectordb
fetcher = C3Fetcher('r476')
docs = load_examples_for_vectordb(fetcher=fetcher)
print(f'{len(docs)} examples loaded from CDN')
"
```

- [ ] **Step 14: Commit**

```bash
git add src/ingest/examples_parser.py tests/test_examples_parser_cdn.py
git commit -m "feat: examples_parser reads from CDN + c3proj"
```

---

## Chunk 4: Wire Up Indexer + Cleanup

### Task 4: Update indexer to use C3Fetcher

**Files:**
- Modify: `src/ingest/indexer.py`

- [ ] **Step 15: Initialize C3Fetcher in index_all_data()**

At the top of `index_all_data()`:
```python
from src.ingest.c3_fetcher import C3Fetcher
from src.config import C3_VERSION, C3_CDN_BASE, C3_CACHE_DIR
fetcher = C3Fetcher(version=C3_VERSION, base_url=C3_CDN_BASE, cache_dir=C3_CACHE_DIR)
```

Pass `fetcher` to `SchemaParser(fetcher=fetcher)` and `load_examples_for_vectordb(fetcher=fetcher)`.

- [ ] **Step 16: Full rebuild + eval**

```bash
python -m src.ingest.indexer --rebuild
python scripts/evaluate_retrieval.py --output tmp/retrieval_eval_cdn.md
```

Expected: Recall >= 96%, Hit Rate >= 97% (same as before)

- [ ] **Step 17: Commit**

```bash
git add src/ingest/indexer.py
git commit -m "feat: indexer uses C3Fetcher for CDN-driven indexing"
```

### Task 5: Cleanup deprecated files

- [ ] **Step 18: Delete deprecated intermediate files**

```bash
git rm data/examples_browser_en_r475.json
git rm data/examples_browser_cn_r475.json
git rm data/examples_index.json
git rm scripts/generate-schema.js
git rm scripts/patch-schema-zh.js
```

- [ ] **Step 19: Final commit**

```bash
git commit -m "cleanup: remove intermediate artifacts replaced by CDN pipeline"
```

---

## Chunk 5: Version Auto-Update Script

### Task 6: Add version check script

**Files:**
- Create: `scripts/check_c3_version.py`

- [ ] **Step 20: Write version checker**

A simple script that:
1. Fetches `versions.json`
2. Compares latest stable to current `C3_VERSION`
3. If newer: prints the new version and instructions to update

```bash
python scripts/check_c3_version.py
# Output: "Current: r476, Latest stable: r477. Update C3_VERSION in .env"
```

- [ ] **Step 21: Commit**

```bash
git add scripts/check_c3_version.py
git commit -m "feat: add C3 version checker script"
```

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| CDN returns 403 (User-Agent blocked) | Index build fails | Fall back to cached data; configurable User-Agent |
| CDN endpoint structure changes | Parser breaks | Schema validation; keep data/schemas/ as fallback |
| Plugin ID case mismatch (Sprite vs sprite) | Missing translations | Case-insensitive lookup in lang join |
| Chinese example titles lost | Minor retrieval quality drop | Plugin/behavior names drive matching, not titles |
| CDN rate limiting | Slow index build | Local cache (7-day TTL matches CDN Cache-Control) |
| New C3 release adds new ACE categories | Unknown fields ignored | Defensive parsing with `.get()` defaults |

## Migration Checklist

After all chunks complete:
- [ ] `python -m src.ingest.indexer --rebuild` works without any files in `data/schemas/`
- [ ] `python scripts/evaluate_retrieval.py` shows no regression
- [ ] `python scripts/check_c3_version.py` detects current version
- [ ] `.cache/c3-cdn/r476/` contains all cached CDN responses
- [ ] No references to `examples_browser` in codebase (grep verify)
- [ ] No references to `generate-schema.js` in codebase
