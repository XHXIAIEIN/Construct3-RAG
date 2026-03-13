# Construct3-LoRA Embedding Fine-tuning Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new standalone repo `Construct3-LoRA` that fine-tunes `Qwen3-Embedding-4B` on Construct 3-specific data, producing a drop-in replacement for the RAG system's embedding model.

**Architecture:** Data pipeline (lookup chain miner → `pairs/lookup_chain.jsonl`; manual chunker → `pairs/manual_chunks.jsonl`; synthetic gen → `pairs/manual_queries.jsonl`) feeds a LoRA fine-tuning workflow (LoRATransformer subclass + SentenceTransformerTrainer + MNR loss). Three sequential curriculum stages from checkpoint. Merged model exports to `output/` for drop-in use in RAG.

**Tech Stack:** Python 3.14, sentence-transformers≥5.0, peft≥0.9, transformers≥4.40, datasets, PyTorch nightly cu128 (RTX 5090 / sm_120), anthropic SDK (Claude API), PyYAML

---

## Context for implementer

**Existing repos (read-only references):**
- RAG project: `D:/Users/Administrator/Documents/GitHub/Construct3-RAG/`
  - ACE schemas: `data/schemas/{behaviors,plugins}/*.json`
  - Translation CSV: `data/source/zh_r475.csv`
- C3 Manual: `D:/Users/Administrator/Documents/GitHub/Construct3-Manual/Construct3-Manual/`
  - 335 `.md` files with YAML frontmatter, H2-level sections

**New repo location:** `D:/Users/Administrator/Documents/GitHub/Construct3-LoRA/`

**Python path:** `/c/Users/test/AppData/Local/Python/bin/python.exe`
**HF model cache:** `D:/Agent/models/hub/` (set via `HF_HOME`)

**Schema structure** (confirmed from `data/schemas/behaviors/anchor.json`):
```json
{
  "id": "anchor",
  "name_zh": "锚点",
  "name_en": "Anchor",
  "path": "general/anchor",
  "conditions": [
    {
      "id": "is-enabled",
      "name_zh": "已启用",
      "name_en": "Is enabled",
      "description_zh": "检测当前行为是否已启用。",
      "description_en": "Test if the behavior is enabled.",
      "display_zh": "{my} 已启用",
      "display_en": "{my} is enabled"
    }
  ],
  "actions": [...],
  "expressions": [...]
}
```
Note: `isTrigger: true` is present on trigger conditions but absent (falsy) on non-trigger ones. No `isLooping` field exists — looping conditions must be identified by name heuristic.

**Manual frontmatter format** (from `behavior-reference/anchor.md` line 1-4):
```
---
title: "Anchor behavior"
source: "https://www.construct.net/..."
---
```
Then `# H1 title` then `## H2 sections`.

**Query instruction (must match RAG project exactly):**
```
"Instruct: Retrieve relevant Construct 3 documentation for the following query\nQuery: "
```
Defined in `src/ingest/indexer.py:_QWEN3_QUERY_INSTRUCTION`. Training queries must be prefixed with this string; document chunks must NOT.

---

## File Structure

```
Construct3-LoRA/
  src/
    collect/
      __init__.py
      lookup_chain_miner.py   # schema zh/en names → manual section → JSONL pairs
      manual_chunker.py       # manual H2 chunking → pairs/manual_chunks.jsonl
      synthetic_gen.py        # Claude API: chunks → query variants → pairs/manual_queries.jsonl
    embedding/
      __init__.py
      dataset.py              # load JSONL pairs → HF Dataset with correct column order
      trainer.py              # LoRATransformer + SentenceTransformerTrainer
      evaluate.py             # Recall@5, MRR@10 vs baseline
    sft/
      .gitkeep
  tests/
    conftest.py               # shared fixtures (tmp_path, sample schema, sample chunks)
    test_lookup_chain_miner.py
    test_manual_chunker.py
    test_synthetic_gen.py
    test_dataset.py
    test_evaluate.py
  scripts/
    generate_synthetic.py     # CLI: run synthetic_gen on manual_chunks.jsonl
    train_embedding.py        # CLI: run curriculum training
    evaluate_embedding.py     # CLI: run evaluation vs baseline
  data/
    pairs/                    # .gitignore — generated JSONL files
  output/                     # .gitignore — trained model
  config.yaml
  requirements.txt
  .gitignore
```

---

## Chunk 1: Repo Scaffold + Lookup Chain Miner

### Task 1: Scaffold new repo

**Files:**
- Create: `Construct3-LoRA/` (entire repo)
- Create: `requirements.txt`
- Create: `config.yaml`
- Create: `.gitignore`
- Create: `src/__init__.py`, `src/collect/__init__.py`, `src/embedding/__init__.py`, `src/sft/.gitkeep`

- [ ] **Step 1: Verify source data paths exist**

```bash
# Verify schemas
ls D:/Users/Administrator/Documents/GitHub/Construct3-RAG/data/schemas/behaviors/ | head -3
ls D:/Users/Administrator/Documents/GitHub/Construct3-RAG/data/schemas/plugins/ | head -3

# Verify manual (should show 300+ files)
find D:/Users/Administrator/Documents/GitHub/Construct3-Manual/Construct3-Manual -name "*.md" | wc -l

# Verify query instruction string in RAG project (must match config.yaml exactly)
grep "_QWEN3_QUERY_INSTRUCTION" D:/Users/Administrator/Documents/GitHub/Construct3-RAG/src/ingest/indexer.py
```
Expected: schemas dirs non-empty, 300+ .md files, instruction = `"Instruct: Retrieve relevant Construct 3 documentation for the following query\nQuery: "`

- [ ] **Step 2: Create directory structure**

```bash
mkdir -p D:/Users/Administrator/Documents/GitHub/Construct3-LoRA
cd D:/Users/Administrator/Documents/GitHub/Construct3-LoRA
git init
mkdir -p src/collect src/embedding src/sft tests scripts data/pairs output
touch src/__init__.py src/collect/__init__.py src/embedding/__init__.py src/sft/.gitkeep
```

- [ ] **Step 2: Create `requirements.txt`**

```
sentence-transformers>=5.0.0
peft>=0.9.0
transformers>=4.40.0
datasets>=2.19.0
accelerate>=0.30.0
anthropic>=0.25.0
pandas>=2.0.0
numpy>=1.24.0
tqdm>=4.66.0
pyyaml>=6.0
python-dotenv>=1.0.0
pytest>=8.0.0
pytest-mock>=3.14.0
jsonlines>=4.0.0
```

Note: PyTorch must be installed separately (nightly cu128):
```bash
pip install --pre torch --index-url https://download.pytorch.org/whl/nightly/cu128
```

- [ ] **Step 3: Create `config.yaml`**

```yaml
paths:
  rag_schemas_dir: "D:/Users/Administrator/Documents/GitHub/Construct3-RAG/data/schemas"
  manual_dir: "D:/Users/Administrator/Documents/GitHub/Construct3-Manual/Construct3-Manual"
  output_dir: "./output/qwen3-embedding-4b-c3"
  pairs_dir: "./data/pairs"

model:
  base_model: "Qwen/Qwen3-Embedding-4B"
  hf_cache_dir: "D:/Agent/models/hub"
  # Must match src/ingest/indexer.py:_QWEN3_QUERY_INSTRUCTION exactly
  query_instruction: "Instruct: Retrieve relevant Construct 3 documentation for the following query\nQuery: "

api:
  claude_api_key_env: "ANTHROPIC_API_KEY"
  claude_model: "claude-3-5-haiku-20241022"
  queries_per_chunk: 6

training:
  batch_size: 16
  learning_rate: 2.0e-4
  warmup_ratio: 0.1
  max_seq_length: 512
  gradient_checkpointing: true
  bf16: true

lora:
  r: 8
  lora_alpha: 16
  target_modules: ["q_proj", "k_proj", "v_proj", "o_proj"]
  lora_dropout: 0.05
  bias: "none"

evaluation:
  recall_k: 5
  mrr_k: 10
  eval_split: 0.1
  success_threshold: 0.05

curriculum:
  stage1_epochs: 2   # easy negatives (lookup chain non-trigger pairs + manual chunks)
  stage2_epochs: 2   # hard negatives (same-plugin same-type ACE pairs)
  stage3_epochs: 1   # full mix with hard negatives
```

- [ ] **Step 4: Create `.gitignore`**

```
data/pairs/
output/
__pycache__/
*.pyc
.env
*.egg-info/
.pytest_cache/
```

- [ ] **Step 5: Create `pytest.ini`**

Without this, `import src.*` fails when running pytest from repo root.

```ini
[pytest]
testpaths = tests
```

Also create `src/__init__.py` (should already exist from Step 2, but confirm):
```bash
touch src/__init__.py src/collect/__init__.py src/embedding/__init__.py
```

- [ ] **Step 6: Create `tests/conftest.py`**

```python
import json
import pytest
from pathlib import Path


@pytest.fixture
def sample_schema(tmp_path):
    """Minimal schema JSON for testing."""
    schema = {
        "id": "testplugin",
        "name_zh": "测试插件",
        "name_en": "Test Plugin",
        "path": "plugin-reference/testplugin",
        "conditions": [
            {
                "id": "is-active",
                "name_zh": "是否激活",
                "name_en": "Is active",
                "description_zh": "检测是否激活。",
                "description_en": "Test if active.",
                "display_zh": "{my} 已激活",
                "display_en": "{my} is active",
            },
            {
                "id": "on-trigger",
                "name_zh": "触发时",
                "name_en": "On trigger",
                "description_zh": "触发时执行。",
                "description_en": "Triggered when fired.",
                "display_zh": "触发时",
                "display_en": "On trigger",
                "isTrigger": True,
            },
        ],
        "actions": [
            {
                "id": "set-active",
                "name_zh": "设置激活",
                "name_en": "Set active",
                "description_zh": "设置激活状态。",
                "description_en": "Set active state.",
                "display_zh": "设置 {my} 激活={0}",
                "display_en": "Set {my} active to {0}",
            }
        ],
        "expressions": [],
    }
    schemas_dir = tmp_path / "schemas" / "plugins"
    schemas_dir.mkdir(parents=True)
    schema_file = schemas_dir / "testplugin.json"
    schema_file.write_text(json.dumps(schema), encoding="utf-8")
    return tmp_path / "schemas"


@pytest.fixture
def sample_manual(tmp_path):
    """Minimal manual markdown for testing."""
    manual_dir = tmp_path / "manual" / "plugin-reference"
    manual_dir.mkdir(parents=True)
    md = manual_dir / "testplugin.md"
    md.write_text(
        '---\ntitle: "Test Plugin"\n---\n\n# Test Plugin\n\n'
        "## Overview\nThe test plugin does things.\n\n"
        "## Is active condition\nTrue when the plugin is active.\n\n"
        "## Set active action\nSets the active state.\n",
        encoding="utf-8",
    )
    return tmp_path / "manual"


@pytest.fixture
def sample_chunk():
    return {
        "chunk_id": "testplugin:0",
        "source": "plugin-reference/testplugin.md",
        "doc_title": "Test Plugin",
        "h2_title": "Overview",
        "text": "## Overview\nThe test plugin does things.",
    }
```

- [ ] **Step 7: Initial commit**

```bash
cd D:/Users/Administrator/Documents/GitHub/Construct3-LoRA
git add .
git commit -m "chore: scaffold Construct3-LoRA repo"
```

---

### Task 2: Lookup Chain Miner

**Files:**
- Create: `src/collect/lookup_chain_miner.py`
- Create: `tests/test_lookup_chain_miner.py`

The miner reads all schema JSONs. Each ACE has `name_zh` (query) and `name_en` + description + manual section (positive). Hard negatives come from other ACEs of the same type and plugin.

**Manual file resolution:** Schema `path` field (e.g. `"general/anchor"`) → strip category prefix → normalize → fuzzy match against manual filenames. Override table handles edge cases.

- [ ] **Step 1: Write failing tests**

Create `tests/test_lookup_chain_miner.py`:

```python
import json
import pytest
from pathlib import Path
from src.collect.lookup_chain_miner import (
    load_schemas,
    resolve_manual_path,
    extract_h2_section,
    build_ace_pairs,
    _normalize_name,
)


def test_load_schemas_reads_all_json(sample_schema):
    schemas = load_schemas(sample_schema)
    assert "testplugin" in schemas
    assert len(schemas["testplugin"]["conditions"]) == 2


def test_normalize_name_strips_punctuation():
    assert _normalize_name("8-direction") == "8direction"
    assert _normalize_name("Jump Thru") == "jumpthru"


def test_resolve_manual_path_finds_by_stem(sample_manual):
    path = resolve_manual_path(sample_manual, "testplugin", "plugin-reference/testplugin")
    assert path is not None
    assert path.exists()


def test_resolve_manual_path_returns_none_for_unknown(sample_manual):
    path = resolve_manual_path(sample_manual, "nonexistent", None)
    assert path is None


def test_extract_h2_section_finds_matching_section(sample_manual):
    md_path = sample_manual / "plugin-reference" / "testplugin.md"
    text = extract_h2_section(md_path, "Is active")
    assert text is not None
    assert "active" in text.lower()


def test_extract_h2_section_falls_back_to_first_h2(sample_manual):
    md_path = sample_manual / "plugin-reference" / "testplugin.md"
    text = extract_h2_section(md_path, "nonexistent ace name")
    assert text is not None
    assert text.startswith("## ")


def test_build_ace_pairs_outputs_correct_fields(sample_schema, sample_manual, tmp_path):
    output_path = tmp_path / "pairs.jsonl"
    count = build_ace_pairs(sample_schema, sample_manual, output_path)
    assert count > 0
    lines = [json.loads(l) for l in output_path.read_text().splitlines()]
    for line in lines:
        assert "query" in line
        assert "positive" in line
        assert "ace_type" in line     # "triggered" or "non_triggered"
        assert "plugin" in line
        assert "negatives" in line    # list (may be empty)
        assert line["query"]          # non-empty
        assert line["positive"]       # non-empty


def test_build_ace_pairs_trigger_classification(sample_schema, sample_manual, tmp_path):
    output_path = tmp_path / "pairs.jsonl"
    build_ace_pairs(sample_schema, sample_manual, output_path)
    lines = [json.loads(l) for l in output_path.read_text().splitlines()]
    types = {l["ace_type"] for l in lines}
    # Should have both triggered and non_triggered
    assert "triggered" in types
    assert "non_triggered" in types


def test_build_ace_pairs_schema_fallback_when_no_manual(sample_schema, tmp_path):
    """When manual file not found, falls back to description text."""
    empty_manual = tmp_path / "empty_manual"
    empty_manual.mkdir()
    output_path = tmp_path / "pairs.jsonl"
    count = build_ace_pairs(sample_schema, empty_manual, output_path)
    assert count > 0
    lines = [json.loads(l) for l in output_path.read_text().splitlines()]
    # Positive should be description text (fallback)
    for line in lines:
        assert line["positive"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd D:/Users/Administrator/Documents/GitHub/Construct3-LoRA
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_lookup_chain_miner.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'src'`

- [ ] **Step 3: Implement `src/collect/lookup_chain_miner.py`**

```python
"""Primary training data source: ACE Schema → Construct3-Manual pairs.

For each ACE in every schema file:
  query   = name_zh (Chinese display name)
  positive = manual H2 section text (fallback: description_en + params)
  negatives = other ACEs of same plugin + same type tier (triggered vs non_triggered)
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Manual filename overrides for non-obvious plugin→filename mappings
_MANUAL_OVERRIDES: dict[str, str] = {
    "eightdir": "behavior-reference/8-direction.md",
    "jumpthru": "behavior-reference/jump-thru.md",
    "platformer": "behavior-reference/platform.md",
    "lineofsight": "behavior-reference/line-of-sight.md",
    "nodewebkit": "plugin-reference/nwjs.md",
}


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_\s]", "", name.lower())


def load_schemas(schemas_dir: Path) -> dict[str, dict]:
    """Load all schema JSONs from {schemas_dir}/{behaviors,plugins}/*.json.

    Returns {plugin_id: schema_dict}.
    """
    schemas: dict[str, dict] = {}
    for json_file in schemas_dir.rglob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.debug("Skip %s: %s", json_file, e)
            continue
        plugin_id = data.get("id") or json_file.stem
        schemas[plugin_id] = data
    return schemas


def resolve_manual_path(
    manual_dir: Path, plugin_id: str, schema_path: Optional[str]
) -> Optional[Path]:
    """Find the manual .md file for a plugin.

    Resolution order:
    1. Override table (_MANUAL_OVERRIDES)
    2. Stem from schema path field (e.g. "general/anchor" → "anchor")
    3. Fuzzy match plugin_id against all .md filenames
    """
    norm_id = _normalize_name(plugin_id)

    if norm_id in _MANUAL_OVERRIDES:
        p = manual_dir / _MANUAL_OVERRIDES[norm_id]
        return p if p.exists() else None

    candidates: list[str] = []
    if schema_path:
        candidates.append(Path(schema_path).stem)
    candidates.append(plugin_id)

    all_md = list(manual_dir.rglob("*.md"))
    for candidate in candidates:
        norm_candidate = _normalize_name(candidate)
        for md_file in all_md:
            if _normalize_name(md_file.stem) == norm_candidate:
                return md_file

    return None


def extract_h2_section(md_path: Path, ace_name_en: str) -> Optional[str]:
    """Extract most relevant H2 section from a manual file.

    Searches for section heading or body containing the ACE name.
    Falls back to first H2 section.
    """
    text = md_path.read_text(encoding="utf-8")
    # Remove YAML frontmatter
    if text.startswith("---"):
        text = re.sub(r"^---.*?---\n", "", text, flags=re.DOTALL)

    sections = re.split(r"\n(?=## )", text)
    h2_sections = [s for s in sections if s.startswith("## ")]
    if not h2_sections:
        return None

    norm_ace = _normalize_name(ace_name_en)

    # Match by heading
    for section in h2_sections:
        heading = section.split("\n")[0]
        if norm_ace in _normalize_name(heading):
            return section.strip()

    # Match by body content
    for section in h2_sections:
        if norm_ace in _normalize_name(section):
            return section.strip()

    # Fallback: first H2 section
    return h2_sections[0].strip()


def _ace_tier(ace: dict) -> str:
    return "triggered" if ace.get("isTrigger") else "non_triggered"


def build_ace_pairs(
    schemas_dir: Path,
    manual_dir: Path,
    output_path: Path,
) -> int:
    """Mine ACE-level training pairs from schemas + manual.

    Output JSONL format:
      {"query": str, "positive": str, "ace_type": str,
       "plugin": str, "negatives": list[str]}

    Returns count of pairs written.
    """
    schemas = load_schemas(schemas_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Pre-build hard-negative index: (plugin, ace_category, tier) → [name_zh list]
    neg_index: dict[tuple, list[str]] = {}
    for plugin_id, schema in schemas.items():
        for category in ("conditions", "actions", "expressions"):
            for ace in schema.get(category, []):
                tier = _ace_tier(ace)
                key = (plugin_id, category, tier)
                neg_index.setdefault(key, []).append(ace.get("name_zh", ""))

    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for plugin_id, schema in schemas.items():
            manual_path = resolve_manual_path(
                manual_dir, plugin_id, schema.get("path")
            )
            for category in ("conditions", "actions", "expressions"):
                for ace in schema.get(category, []):
                    query = ace.get("name_zh", "").strip()
                    if not query:
                        continue

                    name_en = ace.get("name_en", "")
                    tier = _ace_tier(ace)

                    # Build positive text
                    if manual_path:
                        positive = extract_h2_section(manual_path, name_en)
                    else:
                        positive = None

                    if not positive:
                        desc = ace.get("description_en", "")
                        positive = f"{name_en}: {desc}".strip() if desc else name_en

                    # Hard negatives: same plugin, same category, same tier
                    neg_key = (plugin_id, category, tier)
                    all_neg_names = neg_index.get(neg_key, [])
                    negatives = [n for n in all_neg_names if n != query][:4]

                    pair = {
                        "query": query,
                        "positive": positive,
                        "ace_type": tier,
                        "plugin": plugin_id,
                        "negatives": negatives,
                    }
                    f.write(json.dumps(pair, ensure_ascii=False) + "\n")
                    count += 1

    logger.info("Wrote %d ACE pairs to %s", count, output_path)
    return count
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_lookup_chain_miner.py -v
```
Expected: All 9 tests PASS

- [ ] **Step 5: Smoke test against real data**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -c "
from pathlib import Path
from src.collect.lookup_chain_miner import build_ace_pairs
count = build_ace_pairs(
    Path('D:/Users/Administrator/Documents/GitHub/Construct3-RAG/data/schemas'),
    Path('D:/Users/Administrator/Documents/GitHub/Construct3-Manual/Construct3-Manual'),
    Path('data/pairs/lookup_chain.jsonl'),
)
print(f'Wrote {count} pairs')
import json
lines = Path('data/pairs/lookup_chain.jsonl').read_text().splitlines()
print('Sample:', json.loads(lines[0]))
"
```
Expected: ~2900+ pairs written, sample shows non-empty query/positive

- [ ] **Step 6: Commit**

```bash
git add src/collect/lookup_chain_miner.py tests/test_lookup_chain_miner.py tests/conftest.py
git commit -m "feat: add lookup chain miner (ACE schema → manual pairs)"
```

---

## Chunk 2: Manual Chunker + Synthetic Gen

### Task 3: Manual Chunker

**Files:**
- Create: `src/collect/manual_chunker.py`
- Create: `tests/test_manual_chunker.py`

Chunks all `.md` files in the manual at H2 boundaries. Outputs `pairs/manual_chunks.jsonl` — one entry per H2 chunk. This file is human-reviewable before query generation.

- [ ] **Step 1: Write failing tests**

Create `tests/test_manual_chunker.py`:

```python
import json
import pytest
from pathlib import Path
from src.collect.manual_chunker import chunk_manual, _split_h2


def test_split_h2_returns_sections(sample_manual):
    md_path = sample_manual / "plugin-reference" / "testplugin.md"
    sections = _split_h2(md_path.read_text(encoding="utf-8"))
    assert len(sections) >= 2
    for s in sections:
        assert s["h2_title"]
        assert s["text"].startswith("## ")


def test_split_h2_skips_nav_sections(sample_manual):
    """'On this page' navigation sections should be skipped."""
    md = "# Doc\n\n## On this page\n- link\n\n## Real section\nContent here.\n"
    sections = _split_h2(md)
    titles = [s["h2_title"] for s in sections]
    assert "On this page" not in titles
    assert "Real section" in titles


def test_chunk_manual_writes_jsonl(sample_manual, tmp_path):
    output_path = tmp_path / "chunks.jsonl"
    count = chunk_manual(sample_manual, output_path)
    assert count > 0
    lines = output_path.read_text().splitlines()
    assert len(lines) == count
    for line in lines:
        chunk = json.loads(line)
        assert "chunk_id" in chunk
        assert "source" in chunk
        assert "doc_title" in chunk
        assert "h2_title" in chunk
        assert "text" in chunk
        assert chunk["text"].startswith("## ")


def test_chunk_manual_chunk_id_is_unique(sample_manual, tmp_path):
    output_path = tmp_path / "chunks.jsonl"
    chunk_manual(sample_manual, output_path)
    lines = [json.loads(l) for l in output_path.read_text().splitlines()]
    chunk_ids = [l["chunk_id"] for l in lines]
    assert len(chunk_ids) == len(set(chunk_ids))


def test_chunk_manual_source_is_relative_path(sample_manual, tmp_path):
    output_path = tmp_path / "chunks.jsonl"
    chunk_manual(sample_manual, output_path)
    lines = [json.loads(l) for l in output_path.read_text().splitlines()]
    for line in lines:
        # source should be relative (not absolute), uses forward slashes
        assert not Path(line["source"]).is_absolute()
        assert "\\" not in line["source"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_manual_chunker.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/collect/manual_chunker.py`**

```python
"""Manual H2 chunker.

Reads all .md files from Construct3-Manual, splits at H2 boundaries,
outputs one JSONL entry per chunk. Output is human-reviewable before
synthetic query generation.

Output format (pairs/manual_chunks.jsonl):
  {"chunk_id": str, "source": str, "doc_title": str, "h2_title": str, "text": str}
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# H2 sections to skip (navigation, not content)
_SKIP_H2_TITLES = frozenset({"on this page", "see also", "related topics"})


def _split_h2(content: str) -> list[dict]:
    """Split markdown content into H2 sections.

    Returns list of {"h2_title": str, "text": str}.
    Strips YAML frontmatter. Skips navigation sections.
    """
    # Remove YAML frontmatter
    if content.startswith("---"):
        content = re.sub(r"^---.*?---\s*\n", "", content, flags=re.DOTALL)

    sections = re.split(r"\n(?=## )", content)
    result = []
    for section in sections:
        if not section.startswith("## "):
            continue
        h2_title = section.split("\n")[0].lstrip("# ").strip()
        if h2_title.lower() in _SKIP_H2_TITLES:
            continue
        result.append({"h2_title": h2_title, "text": section.strip()})
    return result


def chunk_manual(manual_dir: Path, output_path: Path) -> int:
    """Chunk all manual .md files into H2 sections.

    Returns count of chunks written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0

    with open(output_path, "w", encoding="utf-8") as f:
        for md_file in sorted(manual_dir.rglob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
            except OSError as e:
                logger.debug("Skip %s: %s", md_file, e)
                continue

            # Extract title from frontmatter or H1
            title_match = re.search(r'^title:\s*"?([^"\n]+)"?', content, re.MULTILINE)
            h1_match = re.search(r"^# (.+)", content, re.MULTILINE)
            doc_title = (
                title_match.group(1).strip() if title_match
                else h1_match.group(1).strip() if h1_match
                else md_file.stem
            )

            sections = _split_h2(content)
            source = md_file.relative_to(manual_dir).as_posix()

            for i, section in enumerate(sections):
                chunk_id = f"{md_file.stem}:{i}"
                chunk = {
                    "chunk_id": chunk_id,
                    "source": source,
                    "doc_title": doc_title,
                    "h2_title": section["h2_title"],
                    "text": section["text"],
                }
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                count += 1

    logger.info("Wrote %d chunks to %s", count, output_path)
    return count
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_manual_chunker.py -v
```
Expected: All 5 tests PASS

- [ ] **Step 5: Smoke test against real manual**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -c "
from pathlib import Path
from src.collect.manual_chunker import chunk_manual
count = chunk_manual(
    Path('D:/Users/Administrator/Documents/GitHub/Construct3-Manual/Construct3-Manual'),
    Path('data/pairs/manual_chunks.jsonl'),
)
print(f'Wrote {count} chunks')
import json
lines = Path('data/pairs/manual_chunks.jsonl').read_text().splitlines()
print('Sample:', json.loads(lines[10]))
"
```
Expected: ~1200-1400 chunks written (335 files × ~4 H2 sections)

- [ ] **Step 6: Commit**

```bash
git add src/collect/manual_chunker.py tests/test_manual_chunker.py
git commit -m "feat: add manual H2 chunker"
```

---

### Task 4: Synthetic Query Generator

**Files:**
- Create: `src/collect/synthetic_gen.py`
- Create: `tests/test_synthetic_gen.py`

Reads `manual_chunks.jsonl`, sends each chunk to Claude API, generates 6 Chinese user queries per chunk. Outputs `manual_queries.jsonl` — one entry per (query, chunk) pair. Separated from chunking for independent review and re-running.

Supports resuming: skips chunks whose `chunk_id` already appears in output.

- [ ] **Step 1: Write failing tests**

Create `tests/test_synthetic_gen.py`:

```python
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.collect.synthetic_gen import (
    generate_queries_for_chunk,
    process_chunks,
    _parse_queries,
)


def test_parse_queries_extracts_numbered_list():
    raw = "1. 如何使用锚点？\n2. 锚点行为怎么设置？\n3. C3 里固定对象用什么？"
    result = _parse_queries(raw)
    assert len(result) == 3
    assert result[0] == "如何使用锚点？"


def test_parse_queries_extracts_bullet_list():
    raw = "- 如何固定对象\n- 锚点的作用\n- 对象跟随屏幕"
    result = _parse_queries(raw)
    assert len(result) == 3


def test_parse_queries_handles_empty():
    assert _parse_queries("") == []


def test_generate_queries_calls_claude(sample_chunk):
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [
        MagicMock(text="1. 问题一\n2. 问题二\n3. 问题三\n4. 问题四\n5. 问题五\n6. 问题六")
    ]
    queries = generate_queries_for_chunk(
        sample_chunk, mock_client, model="claude-3-5-haiku-20241022", count=6
    )
    assert len(queries) == 6
    assert mock_client.messages.create.called


def test_generate_queries_returns_empty_on_api_error(sample_chunk):
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API error")
    queries = generate_queries_for_chunk(sample_chunk, mock_client, model="x", count=6)
    assert queries == []


def test_process_chunks_outputs_correct_format(tmp_path, sample_chunk):
    chunks_path = tmp_path / "chunks.jsonl"
    chunks_path.write_text(json.dumps(sample_chunk) + "\n", encoding="utf-8")

    output_path = tmp_path / "queries.jsonl"

    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [
        MagicMock(text="1. 问题一\n2. 问题二\n3. 问题三\n4. 问题四\n5. 问题五\n6. 问题六")
    ]

    count = process_chunks(chunks_path, output_path, mock_client, model="x", count=6)
    assert count == 6

    lines = [json.loads(l) for l in output_path.read_text().splitlines()]
    for line in lines:
        assert "query" in line
        assert "positive" in line   # chunk text
        assert "chunk_id" in line
        assert "source" in line


def test_process_chunks_resumes_existing(tmp_path, sample_chunk):
    """Already-processed chunk_ids are skipped."""
    chunks_path = tmp_path / "chunks.jsonl"
    chunks_path.write_text(json.dumps(sample_chunk) + "\n", encoding="utf-8")

    # Pre-populate output with this chunk_id already processed
    output_path = tmp_path / "queries.jsonl"
    existing = {"query": "已有问题", "positive": "text", "chunk_id": sample_chunk["chunk_id"], "source": "x"}
    output_path.write_text(json.dumps(existing) + "\n", encoding="utf-8")

    mock_client = MagicMock()
    count = process_chunks(chunks_path, output_path, mock_client, model="x", count=6)
    # Should skip — no new API calls
    assert count == 0
    assert not mock_client.messages.create.called
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_synthetic_gen.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/collect/synthetic_gen.py`**

```python
"""Synthetic query generator for manual chunks.

Reads pairs/manual_chunks.jsonl (output of manual_chunker.py).
For each H2 chunk, calls Claude API to generate N Chinese user queries.
Outputs pairs/manual_queries.jsonl — one entry per (query, chunk).

Supports resuming: chunks already present in output are skipped.
This separation allows human review of chunks before query generation,
and independent re-running if query quality needs adjustment.

Output format:
  {"query": str, "positive": str, "chunk_id": str, "source": str}
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
You are helping build training data for an embedding model for Construct 3, a game engine.

Below is a section from the Construct 3 manual:

Title: {h2_title}
Source document: {doc_title}

Content:
{text}

Generate exactly {count} natural Chinese questions that a Construct 3 user might ask, \
where this section would be the relevant answer. Vary the phrasing and vocabulary.
Include at least one question using game development analogies (e.g. Unity, Godot).

Output as a numbered list only. No explanations.
"""


def _parse_queries(raw: str) -> list[str]:
    """Extract query strings from Claude's numbered or bulleted list response."""
    lines = raw.strip().splitlines()
    queries = []
    for line in lines:
        line = line.strip()
        # Remove leading number+dot or bullet
        cleaned = re.sub(r"^(\d+[\.\)]\s*|[-*]\s*)", "", line).strip()
        if cleaned:
            queries.append(cleaned)
    return queries


def generate_queries_for_chunk(
    chunk: dict,
    client,
    model: str,
    count: int,
) -> list[str]:
    """Call Claude API to generate `count` queries for a chunk.

    Returns list of query strings. Returns [] on API error.
    """
    prompt = _PROMPT_TEMPLATE.format(
        h2_title=chunk["h2_title"],
        doc_title=chunk["doc_title"],
        text=chunk["text"][:2000],   # truncate very long sections
        count=count,
    )
    try:
        response = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        return _parse_queries(raw)[:count]
    except Exception as e:
        logger.warning("Claude API error for chunk %s: %s", chunk.get("chunk_id"), e)
        return []


def process_chunks(
    chunks_path: Path,
    output_path: Path,
    client,
    model: str,
    count: int,
) -> int:
    """Generate queries for all chunks in chunks_path.

    Resumes: skips chunk_ids already present in output_path.
    Returns count of new pairs written.
    """
    # Load already-processed chunk_ids
    done_ids: set[str] = set()
    if output_path.exists():
        for line in output_path.read_text(encoding="utf-8").splitlines():
            try:
                done_ids.add(json.loads(line)["chunk_id"])
            except (json.JSONDecodeError, KeyError):
                pass

    output_path.parent.mkdir(parents=True, exist_ok=True)
    total = 0

    with open(output_path, "a", encoding="utf-8") as f:
        for line in chunks_path.read_text(encoding="utf-8").splitlines():
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue

            chunk_id = chunk.get("chunk_id", "")
            if chunk_id in done_ids:
                continue

            queries = generate_queries_for_chunk(chunk, client, model, count)
            for query in queries:
                pair = {
                    "query": query,
                    "positive": chunk["text"],
                    "chunk_id": chunk_id,
                    "source": chunk.get("source", ""),
                    "ace_type": "manual_chunk",  # manual chunk queries — not KT pairs
                }
                f.write(json.dumps(pair, ensure_ascii=False) + "\n")
                total += 1

            if queries:
                done_ids.add(chunk_id)
                f.flush()

    logger.info("Wrote %d new query pairs to %s", total, output_path)
    return total
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_synthetic_gen.py -v
```
Expected: All 7 tests PASS

- [ ] **Step 5: Cost estimate before running at scale**

Full run generates ~1200 chunks × 6 queries = ~7200 Claude API calls.
Estimated cost at claude-3-5-haiku pricing: ~$3-8 for full run.

**Always test with `--limit 10` first** to verify output quality before full run.

- [ ] **Step 6: Create `scripts/generate_synthetic.py`**

```python
"""CLI: generate synthetic queries from manual_chunks.jsonl.

Usage:
    python scripts/generate_synthetic.py [--chunks PATH] [--output PATH] [--limit N]

Reads config.yaml for model and API key. Supports --limit for testing
(process only first N chunks).
"""
import argparse
import os
import sys
from pathlib import Path

import yaml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", default=None, help="Input chunks JSONL path")
    parser.add_argument("--output", default=None, help="Output queries JSONL path")
    parser.add_argument("--limit", type=int, default=None, help="Process only first N chunks")
    args = parser.parse_args()

    config = yaml.safe_load(Path("config.yaml").read_text())
    pairs_dir = Path(config["paths"]["pairs_dir"])

    chunks_path = Path(args.chunks) if args.chunks else pairs_dir / "manual_chunks.jsonl"
    output_path = Path(args.output) if args.output else pairs_dir / "manual_queries.jsonl"

    if not chunks_path.exists():
        print(f"ERROR: {chunks_path} not found. Run manual_chunker first.", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get(config["api"]["claude_api_key_env"])
    if not api_key:
        print(f"ERROR: env var {config['api']['claude_api_key_env']} not set.", file=sys.stderr)
        sys.exit(1)

    import anthropic
    from src.collect.synthetic_gen import process_chunks

    # Apply --limit by writing a trimmed chunks file
    if args.limit:
        import tempfile, json
        lines = chunks_path.read_text().splitlines()[:args.limit]
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        tmp.write("\n".join(lines))
        tmp.close()
        chunks_path = Path(tmp.name)

    client = anthropic.Anthropic(api_key=api_key)
    count = process_chunks(
        chunks_path, output_path, client,
        model=config["api"]["claude_model"],
        count=config["api"]["queries_per_chunk"],
    )
    print(f"Done. Wrote {count} new pairs to {output_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Commit**

```bash
git add src/collect/synthetic_gen.py tests/test_synthetic_gen.py scripts/generate_synthetic.py
git commit -m "feat: add synthetic query generator with resume support"
```

- [ ] **Step 7: Create `scripts/generate_kt_pairs.py` (Knowledge Transfer pairs)**

The spec requires ~500 Unity/Godot→C3 analogy pairs with `ace_type="knowledge_transfer"`. These are
*separate* from the manual chunk queries above. Create this script:

```python
"""CLI: generate Knowledge Transfer pairs (game-dev analogies → C3 concepts).

Generates ~500 pairs mapping Unity/Godot/GameMaker vocabulary to Construct 3
equivalents. Output: data/pairs/kt_pairs.jsonl

Usage:
    python scripts/generate_kt_pairs.py [--count N] [--output PATH]
"""
import argparse
import json
import os
import sys
from pathlib import Path

import yaml


_PROMPT = """\
You are building training data for a Construct 3 embedding model.

Generate {count} training pairs mapping general game development concepts to Construct 3
equivalents. Each pair should be a JSON object with "query" and "positive" fields.

Rules:
- query: A natural Chinese question using Unity/Godot/GameMaker/JS terminology
- positive: A Chinese explanation of the equivalent Construct 3 concept
- Cover: Unity MonoBehaviour → C3 event sheets, Update() → Every tick,
  physics callbacks → collision conditions, Godot signals → C3 events, etc.
- Vary phrasing. No duplicates.

Output as a JSON array only.
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    config = yaml.safe_load(Path("config.yaml").read_text())
    pairs_dir = Path(config["paths"]["pairs_dir"])
    output_path = Path(args.output) if args.output else pairs_dir / "kt_pairs.jsonl"

    api_key = os.environ.get(config["api"]["claude_api_key_env"])
    if not api_key:
        print(f"ERROR: {config['api']['claude_api_key_env']} not set", file=sys.stderr)
        sys.exit(1)

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    # Generate in batches of 50 to stay within token limits
    batch_size = 50
    all_pairs = []
    for i in range(0, args.count, batch_size):
        n = min(batch_size, args.count - i)
        resp = client.messages.create(
            model=config["api"]["claude_model"],
            max_tokens=4096,
            messages=[{"role": "user", "content": _PROMPT.format(count=n)}],
        )
        try:
            batch = json.loads(resp.content[0].text)
            all_pairs.extend(batch)
        except (json.JSONDecodeError, IndexError) as e:
            print(f"Parse error in batch {i//batch_size}: {e}", file=sys.stderr)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for pair in all_pairs:
            pair["ace_type"] = "knowledge_transfer"
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")

    print(f"Wrote {len(all_pairs)} KT pairs to {output_path}")


if __name__ == "__main__":
    main()
```

```bash
git add scripts/generate_kt_pairs.py
git commit -m "feat: add knowledge transfer pair generator (game-dev analogies → C3)"
```

---

## Chunk 3: Dataset Builder + Trainer

### Task 5: Dataset Builder

**Files:**
- Create: `src/embedding/dataset.py`
- Create: `tests/test_dataset.py`

Loads all JSONL pair files from `data/pairs/`, applies query instruction prefix to anchors, outputs a HuggingFace `Dataset` with columns in correct order for `MultipleNegativesRankingLoss`.

**Critical:** Column order must be `anchor, positive` (optionally followed by negatives). HF Datasets sorts columns alphabetically by default — must be overridden explicitly.

- [ ] **Step 1: Write failing tests**

Create `tests/test_dataset.py`:

```python
import json
import pytest
from pathlib import Path
from src.embedding.dataset import load_pairs, build_dataset

INSTRUCTION = "Instruct: Test\nQuery: "


def test_load_pairs_reads_jsonl(tmp_path):
    pairs_file = tmp_path / "test.jsonl"
    pairs_file.write_text(
        json.dumps({"query": "q1", "positive": "p1"}) + "\n" +
        json.dumps({"query": "q2", "positive": "p2"}) + "\n",
        encoding="utf-8",
    )
    pairs = load_pairs([pairs_file])
    assert len(pairs) == 2
    assert pairs[0]["query"] == "q1"


def test_load_pairs_skips_invalid_json(tmp_path):
    pairs_file = tmp_path / "bad.jsonl"
    pairs_file.write_text("not json\n" + json.dumps({"query": "q", "positive": "p"}) + "\n")
    pairs = load_pairs([pairs_file])
    assert len(pairs) == 1


def test_build_dataset_applies_instruction(tmp_path):
    pairs = [{"query": "test query", "positive": "answer text"}]
    ds = build_dataset(pairs, query_instruction=INSTRUCTION)
    assert ds[0]["anchor"] == INSTRUCTION + "test query"
    assert ds[0]["positive"] == "answer text"


def test_build_dataset_column_order(tmp_path):
    """anchor must be first column, positive must be second."""
    pairs = [{"query": "q", "positive": "p"}]
    ds = build_dataset(pairs, query_instruction=INSTRUCTION)
    cols = ds.column_names
    assert cols[0] == "anchor"
    assert cols[1] == "positive"


def test_build_dataset_column_order_with_negatives():
    """anchor/positive order must be preserved even when negatives are present."""
    pairs = [{"query": "q", "positive": "p", "negatives": ["n1", "n2"]}]
    ds = build_dataset(pairs, query_instruction=INSTRUCTION, include_negatives=True)
    cols = ds.column_names
    assert cols[0] == "anchor", f"Expected anchor first, got {cols}"
    assert cols[1] == "positive", f"Expected positive second, got {cols}"
    assert "negative_0" in cols


def test_build_dataset_with_negatives(tmp_path):
    pairs = [{"query": "q", "positive": "p", "negatives": ["n1", "n2"]}]
    ds = build_dataset(pairs, query_instruction=INSTRUCTION, include_negatives=True)
    assert "negative_0" in ds.column_names
    assert ds[0]["negative_0"] == "n1"


def test_build_dataset_deduplicates_queries(tmp_path):
    pairs = [
        {"query": "q1", "positive": "p1"},
        {"query": "q1", "positive": "p1"},  # duplicate
        {"query": "q2", "positive": "p2"},
    ]
    ds = build_dataset(pairs, query_instruction=INSTRUCTION)
    assert len(ds) == 2


def test_build_dataset_train_eval_split(tmp_path):
    pairs = [{"query": f"q{i}", "positive": f"p{i}"} for i in range(20)]
    train_ds, eval_ds = build_dataset(pairs, query_instruction=INSTRUCTION, eval_split=0.2)
    assert len(train_ds) == 16
    assert len(eval_ds) == 4
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_dataset.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/embedding/dataset.py`**

```python
"""Dataset builder for embedding fine-tuning.

Loads JSONL pairs, applies query instruction prefix, builds HuggingFace Dataset.

IMPORTANT: MultipleNegativesRankingLoss requires column order anchor, positive,
[negatives...]. HF Dataset sorts columns alphabetically if not forced — this
module explicitly enforces the correct order.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from datasets import Dataset

logger = logging.getLogger(__name__)


def load_pairs(jsonl_paths: list[Path]) -> list[dict]:
    """Load all JSONL pair files into a flat list. Skips invalid lines."""
    pairs = []
    for path in jsonl_paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                pairs.append(json.loads(line))
            except json.JSONDecodeError:
                logger.debug("Skip invalid JSON line in %s", path)
    return pairs


def build_dataset(
    pairs: list[dict],
    query_instruction: str,
    include_negatives: bool = False,
    eval_split: float = 0.0,
) -> Dataset | tuple[Dataset, Dataset]:
    """Build HuggingFace Dataset from pairs.

    Applies query_instruction prefix to all queries.
    Deduplicates by (anchor, positive).
    Column order: anchor, positive, [negative_0, negative_1, ...]

    Args:
        pairs: List of {"query", "positive", optionally "negatives": [...]}
        query_instruction: Prefix applied to all queries (not to positives)
        include_negatives: Whether to include explicit negatives as extra columns
        eval_split: If > 0, return (train_dataset, eval_dataset)

    Returns:
        Dataset or (train_dataset, eval_dataset)
    """
    seen: set[tuple] = set()
    records: list[dict] = []

    for pair in pairs:
        query = pair.get("query", "").strip()
        positive = pair.get("positive", "").strip()
        if not query or not positive:
            continue

        anchor = query_instruction + query
        key = (anchor, positive)
        if key in seen:
            continue
        seen.add(key)

        record: dict = {"anchor": anchor, "positive": positive}

        if include_negatives:
            for i, neg in enumerate(pair.get("negatives", [])[:4]):
                if neg.strip():
                    record[f"negative_{i}"] = neg.strip()

        records.append(record)

    # Build with explicit column order: anchor first, positive second
    col_order = ["anchor", "positive"]
    if include_negatives:
        max_negs = max(
            (sum(1 for k in r if k.startswith("negative_")) for r in records),
            default=0,
        )
        col_order += [f"negative_{i}" for i in range(max_negs)]

    # Build with explicit column order using from_dict (from_list sorts alphabetically)
    present_cols = [c for c in col_order if any(c in r for r in records)]
    extra_cols = sorted({k for r in records for k in r if k not in col_order})
    ordered_cols = present_cols + extra_cols
    ds = Dataset.from_dict({
        col: [r.get(col, "") for r in records]
        for col in ordered_cols
    })

    logger.info("Built dataset: %d samples, columns: %s", len(ds), ds.column_names)

    if eval_split > 0:
        split = ds.train_test_split(test_size=eval_split, seed=42)
        return split["train"], split["test"]

    return ds
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_dataset.py -v
```
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/embedding/dataset.py tests/test_dataset.py
git commit -m "feat: add dataset builder with correct MNR column order"
```

---

### Task 6: Trainer

**Files:**
- Create: `src/embedding/trainer.py`
- Create: `scripts/train_embedding.py`
- (No unit tests for training itself — tested via smoke test only, as model loading is slow)

The LoRA integration follows a 4-step pattern:
1. `AutoModel.from_pretrained` → base model
2. `peft.get_peft_model()` → LoRA-wrapped model
3. Inject into `LoRATransformer(models.Transformer)` subclass
4. `SentenceTransformer([lora_transformer, pooling])` → trainable ST model

Curriculum = 3 sequential `SentenceTransformerTrainer.train()` calls, each loading from the previous checkpoint.

- [ ] **Step 1: Implement `src/embedding/trainer.py`**

```python
"""LoRA fine-tuning for Qwen3-Embedding-4B.

Uses sentence-transformers 5.x + peft. The LoRATransformer subclass injects
a PEFT model into sentence-transformers' Transformer wrapper before training.

Curriculum training = 3 sequential runs loading from previous checkpoint.
Stage 1: easy negatives (lookup_chain non-trigger + manual chunks)
Stage 2: hard negatives (same-plugin same-type ACE pairs)
Stage 3: full mix
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _check_environment() -> None:
    """Warn if PyTorch CUDA capability is wrong for RTX 5090."""
    try:
        import torch
        if torch.cuda.is_available():
            cap = torch.cuda.get_device_capability()
            if cap < (12, 0):
                logger.warning(
                    "CUDA capability %s.%s detected. RTX 5090 (sm_120) requires "
                    "PyTorch nightly cu128. Install with: "
                    "pip install --pre torch --index-url https://download.pytorch.org/whl/nightly/cu128",
                    *cap,
                )
    except ImportError:
        pass


def build_lora_model(
    base_model: str,
    lora_config_dict: dict,
    max_seq_length: int,
    gradient_checkpointing: bool,
    hf_cache_dir: str | None = None,
):
    """Build a SentenceTransformer with LoRA applied.

    Returns (model, hidden_size) tuple.
    """
    from peft import LoraConfig, TaskType, get_peft_model
    from sentence_transformers import SentenceTransformer, models

    class LoRATransformer(models.Transformer):
        """Transformer subclass that applies LoRA to the underlying AutoModel."""

        def __init__(self, model_name_or_path: str, lora_cfg: LoraConfig, **kwargs):
            super().__init__(model_name_or_path, **kwargs)
            self.auto_model = get_peft_model(self.auto_model, lora_cfg)
            self.auto_model.print_trainable_parameters()
            if gradient_checkpointing:
                self.auto_model.enable_input_require_grads()
                self.auto_model.base_model.gradient_checkpointing_enable()

    lora_cfg = LoraConfig(
        task_type=TaskType.FEATURE_EXTRACTION,
        r=lora_config_dict["r"],
        lora_alpha=lora_config_dict["lora_alpha"],
        target_modules=lora_config_dict["target_modules"],
        lora_dropout=lora_config_dict["lora_dropout"],
        bias=lora_config_dict["bias"],
    )

    kwargs = {"max_seq_length": max_seq_length, "trust_remote_code": True}
    if hf_cache_dir:
        kwargs["cache_folder"] = hf_cache_dir

    transformer = LoRATransformer(base_model, lora_cfg, **kwargs)
    hidden_size = transformer.get_word_embedding_dimension()
    pooling = models.Pooling(hidden_size, pooling_mode_lasttoken=True)
    model = SentenceTransformer(modules=[transformer, pooling])
    return model


def train_stage(
    model,
    train_dataset,
    output_dir: Path,
    num_epochs: int,
    batch_size: int,
    learning_rate: float,
    warmup_ratio: float,
    bf16: bool,
) -> None:
    """Run one curriculum stage.

    Model weights carry forward in-memory across stages — caller must not pass
    resume_from_checkpoint between stages (that would restore a different run's
    optimizer state and epoch counter).

    For crash recovery within a stage: use SentenceTransformerTrainer's
    resume_from_checkpoint pointing to the crashed stage's checkpoint subdir.
    """
    from sentence_transformers.losses import MultipleNegativesRankingLoss
    from sentence_transformers.trainer import SentenceTransformerTrainer
    from sentence_transformers.training_args import SentenceTransformerTrainingArguments

    loss = MultipleNegativesRankingLoss(model)

    args = SentenceTransformerTrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        learning_rate=learning_rate,
        warmup_ratio=warmup_ratio,
        bf16=bf16,
        fp16=False,
        dataloader_drop_last=True,   # MNR loss requires consistent batch size
        save_strategy="epoch",
        logging_steps=50,
    )

    trainer = SentenceTransformerTrainer(
        model=model,
        args=args,
        train_dataset=train_dataset,
        loss=loss,
    )
    trainer.train()


def export_merged_model(model, output_dir: Path) -> None:
    """Merge LoRA adapter into base model and save.

    The merged model is a full HuggingFace model — no peft dependency
    needed at inference time.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    # Merge LoRA into base weights
    transformer_module = model[0]
    transformer_module.auto_model = transformer_module.auto_model.merge_and_unload()
    model.save_pretrained(str(output_dir))
    logger.info("Merged model saved to %s", output_dir)
```

- [ ] **Step 2: Create `scripts/train_embedding.py`**

```python
"""CLI: run curriculum embedding fine-tuning.

Usage:
    python scripts/train_embedding.py [--stage {1,2,3,all}] [--dry-run]

Stages:
    1 = easy negatives (lookup_chain non-trigger + manual chunks)
    2 = hard negatives (lookup_chain triggered + ACE same-type pairs)
    3 = full mix
    all = run all 3 stages sequentially (default)

--dry-run loads the model and dataset but does not train (for VRAM check).
"""
import argparse
import os
import sys
from pathlib import Path

import yaml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="all", choices=["1", "2", "3", "all"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = yaml.safe_load(Path("config.yaml").read_text())
    os.environ["HF_HOME"] = config["model"]["hf_cache_dir"]

    from src.embedding.trainer import _check_environment, build_lora_model, train_stage, export_merged_model
    from src.embedding.dataset import load_pairs, build_dataset
    _check_environment()

    pairs_dir = Path(config["paths"]["pairs_dir"])
    output_dir = Path(config["paths"]["output_dir"])
    instruction = config["model"]["query_instruction"]
    tc = config["training"]
    cc = config["curriculum"]

    # --- Load all pair sources ---
    all_files = list(pairs_dir.glob("*.jsonl"))
    if not all_files:
        print(f"ERROR: No JSONL files found in {pairs_dir}", file=sys.stderr)
        sys.exit(1)

    all_pairs = load_pairs(all_files)
    print(f"Loaded {len(all_pairs)} total pairs from {len(all_files)} files")

    # Stage-specific filtering
    # Knowledge transfer pairs (ace_type="knowledge_transfer") are included in ALL stages
    # so they appear 3× total across the curriculum (spec requirement).
    kt_pairs = [p for p in all_pairs if p.get("ace_type") == "knowledge_transfer"]
    print(f"Knowledge transfer pairs: {len(kt_pairs)} (will appear in all 3 stages = 3× effective)")

    def stage1_pairs():
        # Stage 1: easy in-batch negatives only. Base = non-triggered ACE + manual chunks + KT.
        base = [p for p in all_pairs if p.get("ace_type") not in ("triggered", "knowledge_transfer")]
        return base + kt_pairs

    def stage2_pairs():
        # Stage 2: hard negatives. Use ALL lookup-chain pairs that have populated negatives fields.
        # (These are the ACE pairs from lookup_chain_miner — both triggered and non_triggered.)
        # include_negatives=True in build_dataset activates the explicit negatives column.
        base = [p for p in all_pairs if p.get("negatives")]
        return base + kt_pairs

    def stage3_pairs():
        # Stage 3: full mix (KT at 1× here; cumulative 3× across all stages)
        return all_pairs

    # Stage 2 uses include_negatives=True; stages 1 and 3 use in-batch negatives only
    stage_include_negatives = {"1": False, "2": True, "3": False}

    stage_map = {"1": (stage1_pairs, cc["stage1_epochs"]),
                 "2": (stage2_pairs, cc["stage2_epochs"]),
                 "3": (stage3_pairs, cc["stage3_epochs"])}

    stages = ["1", "2", "3"] if args.stage == "all" else [args.stage]

    # Build model once — LoRA weights stay in-memory across all stages.
    # NOTE: do NOT use resume_from_checkpoint between stages. That parameter restores
    # optimizer state + epoch counters from a previous run, causing wrong behavior when
    # chaining curriculum stages. Model weights carry forward automatically via Python object.
    model = build_lora_model(
        base_model=config["model"]["base_model"],
        lora_config_dict=config["lora"],
        max_seq_length=tc["max_seq_length"],
        gradient_checkpointing=tc["gradient_checkpointing"],
        hf_cache_dir=config["model"]["hf_cache_dir"],
    )

    if args.dry_run:
        print("Dry run: model built successfully. Exiting.")
        return

    for stage_num in stages:
        pairs_fn, num_epochs = stage_map[stage_num]
        pairs = pairs_fn()
        print(f"\n=== Stage {stage_num}: {len(pairs)} pairs, {num_epochs} epochs ===")

        train_ds = build_dataset(
            pairs, instruction,
            include_negatives=stage_include_negatives[stage_num],
        )

        stage_out = output_dir / f"stage{stage_num}"
        train_stage(
            model=model,
            train_dataset=train_ds,
            output_dir=stage_out,
            num_epochs=num_epochs,
            batch_size=tc["batch_size"],
            learning_rate=tc["learning_rate"],
            warmup_ratio=tc["warmup_ratio"],
            bf16=tc["bf16"],
        )
        # Save LoRA adapter after each stage for crash recovery.
        # To resume from a crash at Stage N: reload base model + PeftModel.from_pretrained(stage_N-1_adapter)
        adapter_dir = stage_out / "lora_adapter"
        model[0].auto_model.save_pretrained(str(adapter_dir))
        print(f"Stage {stage_num} complete. LoRA adapter saved to {adapter_dir}")

    # Export merged model
    merged_dir = output_dir / "merged"
    export_merged_model(model, merged_dir)
    print(f"\nTraining complete. Merged model at: {merged_dir}")
    print(f"\nTo use in RAG, update .env:")
    print(f"  EMBEDDING_MODEL={merged_dir.resolve()}")
    print(f"  EMBEDDING_DIMENSION=2560")
    print(f"Then run: python -m src.ingest.indexer --rebuild")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke test (dry run — loads model, no training)**

```bash
cd D:/Users/Administrator/Documents/GitHub/Construct3-LoRA
/c/Users/test/AppData/Local/Python/bin/python.exe scripts/train_embedding.py --dry-run
```
Expected: "Dry run: model built successfully. Exiting." — no OOM, no crash

- [ ] **Step 4: Commit**

```bash
git add src/embedding/trainer.py scripts/train_embedding.py
git commit -m "feat: add LoRA trainer with curriculum stages and merge export"
```

---

## Chunk 4: Evaluation + Final Integration

### Task 7: Evaluation

**Files:**
- Create: `src/embedding/evaluate.py`
- Create: `tests/test_evaluate.py`
- Create: `scripts/evaluate_embedding.py`

Computes Recall@K and MRR@K. Compares fine-tuned model vs baseline (unmodified `Qwen3-Embedding-4B`). Uses the eval split from `build_dataset`.

> ⚠️ **Eval set limitation:** The auto-split eval set is derived from the same Claude generation
> process as the training set — this measures whether the model memorised Claude's style, not true
> retrieval quality. Before running a real evaluation, create a manually curated eval set:
>
> 1. Collect 30-50 real user questions from the Scirra forum (https://www.construct.net/en/forum)
>    that have clear answers in the manual.
> 2. Save to `data/eval_manual.jsonl` format: `{"query": str, "positive": str}` (document chunk text).
> 3. Pass to `evaluate_model` in addition to the auto-split: `--eval-set data/eval_manual.jsonl`
>
> The manual set is the authoritative signal for whether fine-tuning improved real-world retrieval.
> The auto-split provides a quick sanity check only.

- [ ] **Step 1: Write failing tests**

Create `tests/test_evaluate.py`:

```python
import numpy as np
import pytest
from src.embedding.evaluate import recall_at_k, mrr_at_k, evaluate_model


def test_recall_at_k_perfect():
    # Each query's correct doc is ranked first
    query_embs = np.array([[1.0, 0.0], [0.0, 1.0]])
    doc_embs = np.array([[1.0, 0.0], [0.0, 1.0]])
    labels = [0, 1]
    assert recall_at_k(query_embs, doc_embs, labels, k=1) == 1.0


def test_recall_at_k_miss():
    # Correct doc is never in top-1
    query_embs = np.array([[1.0, 0.0]])
    doc_embs = np.array([[0.0, 1.0], [1.0, 0.0]])
    labels = [0]   # correct is doc 0, but query points toward doc 1
    assert recall_at_k(query_embs, doc_embs, labels, k=1) == 0.0


def test_recall_at_k_top5_finds_it():
    # Correct doc is rank 3 out of 5
    query_embs = np.array([[1.0, 0.0, 0.0]])
    doc_embs = np.array([
        [0.0, 1.0, 0.0],   # rank 4
        [0.0, 0.0, 1.0],   # rank 5
        [0.9, 0.1, 0.0],   # rank 2
        [0.95, 0.05, 0.0], # rank 1
        [0.85, 0.1, 0.05], # rank 3 ← correct
    ])
    labels = [4]
    assert recall_at_k(query_embs, doc_embs, labels, k=5) == 1.0
    assert recall_at_k(query_embs, doc_embs, labels, k=2) == 0.0


def test_mrr_at_k_perfect():
    query_embs = np.array([[1.0, 0.0]])
    doc_embs = np.array([[1.0, 0.0], [0.0, 1.0]])
    labels = [0]
    assert mrr_at_k(query_embs, doc_embs, labels, k=10) == 1.0


def test_mrr_at_k_rank2():
    # Correct doc is rank 2 → MRR = 0.5
    query_embs = np.array([[1.0, 0.0]])
    doc_embs = np.array([[0.9, 0.1], [1.0, 0.0]])
    labels = [1]   # correct is doc 1 (rank 2)
    mrr = mrr_at_k(query_embs, doc_embs, labels, k=10)
    assert abs(mrr - 0.5) < 1e-6


def test_evaluate_model_returns_dict(tmp_path):
    """evaluate_model returns a dict with recall and mrr keys."""
    from unittest.mock import MagicMock
    import numpy as np
    from datasets import Dataset

    eval_ds = Dataset.from_list([
        {"anchor": "q1", "positive": "p1"},
        {"anchor": "q2", "positive": "p2"},
    ])

    mock_model = MagicMock()
    # Return distinct embeddings so ranking is deterministic
    mock_model.encode.side_effect = lambda texts, **kw: np.eye(len(texts), 4)

    result = evaluate_model(mock_model, eval_ds)
    assert "recall@5" in result
    assert "mrr@10" in result
    assert 0.0 <= result["recall@5"] <= 1.0
    assert 0.0 <= result["mrr@10"] <= 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_evaluate.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/embedding/evaluate.py`**

```python
"""Retrieval evaluation metrics.

Computes Recall@K and MRR@K by embedding all eval queries and documents,
then measuring ranking quality.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def recall_at_k(
    query_embeddings: np.ndarray,
    doc_embeddings: np.ndarray,
    relevance_labels: list[int],
    k: int,
) -> float:
    """Fraction of queries where correct doc appears in top-K results."""
    scores = query_embeddings @ doc_embeddings.T  # (n_queries, n_docs)
    top_k = np.argsort(-scores, axis=1)[:, :k]
    hits = sum(
        relevance_labels[i] in top_k[i] for i in range(len(relevance_labels))
    )
    return hits / len(relevance_labels)


def mrr_at_k(
    query_embeddings: np.ndarray,
    doc_embeddings: np.ndarray,
    relevance_labels: list[int],
    k: int,
) -> float:
    """Mean Reciprocal Rank at K."""
    scores = query_embeddings @ doc_embeddings.T
    top_k = np.argsort(-scores, axis=1)[:, :k]
    reciprocal_ranks = []
    for i, label in enumerate(relevance_labels):
        rank_positions = np.where(top_k[i] == label)[0]
        if rank_positions.size > 0:
            reciprocal_ranks.append(1.0 / (rank_positions[0] + 1))
        else:
            reciprocal_ranks.append(0.0)
    return float(np.mean(reciprocal_ranks))


def evaluate_model(
    model,
    eval_dataset,
    recall_k: int = 5,
    mrr_k: int = 10,
    batch_size: int = 64,
) -> dict[str, float]:
    """Evaluate model on eval_dataset.

    Dataset must have 'anchor' and 'positive' columns.
    Returns {"recall@K": float, "mrr@K": float}.
    """
    queries = eval_dataset["anchor"]
    positives = eval_dataset["positive"]

    logger.info("Encoding %d queries and %d docs...", len(queries), len(positives))
    query_embs = np.array(model.encode(queries, batch_size=batch_size, show_progress_bar=True))
    doc_embs = np.array(model.encode(positives, batch_size=batch_size, show_progress_bar=True))

    # Normalize
    query_embs /= np.linalg.norm(query_embs, axis=1, keepdims=True) + 1e-8
    doc_embs /= np.linalg.norm(doc_embs, axis=1, keepdims=True) + 1e-8

    labels = list(range(len(queries)))  # each query's correct doc is at same index

    r_k = recall_at_k(query_embs, doc_embs, labels, k=recall_k)
    m_k = mrr_at_k(query_embs, doc_embs, labels, k=mrr_k)

    return {f"recall@{recall_k}": r_k, f"mrr@{mrr_k}": m_k}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/test_evaluate.py -v
```
Expected: All 7 tests PASS

- [ ] **Step 5: Create `scripts/evaluate_embedding.py`**

```python
"""CLI: evaluate fine-tuned model vs baseline.

Usage:
    python scripts/evaluate_embedding.py [--model PATH] [--baseline]

--model PATH: path to fine-tuned model (default: config output_dir/merged)
--baseline: also evaluate the unmodified base model for comparison
"""
import argparse
import os
import sys
from pathlib import Path

import yaml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None)
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()

    config = yaml.safe_load(Path("config.yaml").read_text())
    os.environ["HF_HOME"] = config["model"]["hf_cache_dir"]

    from sentence_transformers import SentenceTransformer
    from src.embedding.dataset import load_pairs, build_dataset
    from src.embedding.evaluate import evaluate_model

    pairs_dir = Path(config["paths"]["pairs_dir"])
    output_dir = Path(config["paths"]["output_dir"])
    instruction = config["model"]["query_instruction"]
    ev = config["evaluation"]

    all_pairs = load_pairs(list(pairs_dir.glob("*.jsonl")))
    _, eval_ds = build_dataset(all_pairs, instruction, eval_split=ev["eval_split"])
    print(f"Eval set: {len(eval_ds)} samples")

    model_path = args.model or str(output_dir / "merged")
    print(f"\nEvaluating fine-tuned: {model_path}")
    model = SentenceTransformer(model_path, trust_remote_code=True)
    results = evaluate_model(model, eval_ds, ev["recall_k"], ev["mrr_k"])
    print(f"  Recall@{ev['recall_k']}: {results[f'recall@{ev[\"recall_k\"]}']:.4f}")
    print(f"  MRR@{ev['mrr_k']}:    {results[f'mrr@{ev[\"mrr_k\"]}']:.4f}")

    if args.baseline:
        print(f"\nEvaluating baseline: {config['model']['base_model']}")
        baseline = SentenceTransformer(
            config["model"]["base_model"],
            trust_remote_code=True,
            cache_folder=config["model"]["hf_cache_dir"],
        )
        baseline_results = evaluate_model(baseline, eval_ds, ev["recall_k"], ev["mrr_k"])
        r_key = f"recall@{ev['recall_k']}"
        m_key = f"mrr@{ev['mrr_k']}"
        delta_r = results[r_key] - baseline_results[r_key]
        delta_m = results[m_key] - baseline_results[m_key]
        print(f"  Recall@{ev['recall_k']}: {baseline_results[r_key]:.4f}")
        print(f"  MRR@{ev['mrr_k']}:    {baseline_results[m_key]:.4f}")
        print(f"\nDelta (fine-tuned - baseline):")
        print(f"  Recall@{ev['recall_k']}: {delta_r:+.4f}", "✓" if delta_r >= ev["success_threshold"] else "✗")
        print(f"  MRR@{ev['mrr_k']}:    {delta_m:+.4f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Commit**

```bash
git add src/embedding/evaluate.py tests/test_evaluate.py scripts/evaluate_embedding.py
git commit -m "feat: add Recall@K / MRR@K evaluator"
```

---

### Task 8: Final integration test + README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Run full test suite**

```bash
cd D:/Users/Administrator/Documents/GitHub/Construct3-LoRA
/c/Users/test/AppData/Local/Python/bin/python.exe -m pytest tests/ -v
```
Expected: All tests PASS (no model loading required)

- [ ] **Step 2: End-to-end smoke test (data pipeline only, no training)**

```bash
# 1. Mine ACE pairs
/c/Users/test/AppData/Local/Python/bin/python.exe -c "
from pathlib import Path
from src.collect.lookup_chain_miner import build_ace_pairs
n = build_ace_pairs(
    Path('D:/Users/Administrator/Documents/GitHub/Construct3-RAG/data/schemas'),
    Path('D:/Users/Administrator/Documents/GitHub/Construct3-Manual/Construct3-Manual'),
    Path('data/pairs/lookup_chain.jsonl'),
)
print(f'ACE pairs: {n}')
"

# 2. Chunk manual
/c/Users/test/AppData/Local/Python/bin/python.exe -c "
from pathlib import Path
from src.collect.manual_chunker import chunk_manual
n = chunk_manual(
    Path('D:/Users/Administrator/Documents/GitHub/Construct3-Manual/Construct3-Manual'),
    Path('data/pairs/manual_chunks.jsonl'),
)
print(f'Manual chunks: {n}')
"

# 3. Build dataset from existing pairs (without synthetic queries)
/c/Users/test/AppData/Local/Python/bin/python.exe -c "
from pathlib import Path
from src.embedding.dataset import load_pairs, build_dataset
pairs = load_pairs(list(Path('data/pairs').glob('*.jsonl')))
train_ds, eval_ds = build_dataset(
    pairs,
    query_instruction='Instruct: Retrieve relevant Construct 3 documentation for the following query\nQuery: ',
    eval_split=0.1,
)
print(f'Train: {len(train_ds)}, Eval: {len(eval_ds)}')
print(f'Columns: {train_ds.column_names}')
assert train_ds.column_names[0] == 'anchor', 'Column order wrong!'
assert train_ds.column_names[1] == 'positive', 'Column order wrong!'
print('Column order OK')
"
```
Expected: ACE pairs ~2900+, Manual chunks ~1200-1400, Train/eval split ~90/10%, columns [anchor, positive, ...]

- [ ] **Step 3: Create `README.md`**

```markdown
# Construct3-LoRA

Fine-tunes `Qwen3-Embedding-4B` on Construct 3-specific data to improve
semantic retrieval in the RAG system.

## Quick start

```bash
pip install -r requirements.txt
# PyTorch nightly (RTX 5090 / sm_120):
pip install --pre torch --index-url https://download.pytorch.org/whl/nightly/cu128

# Step 1: Mine ACE pairs from schemas + manual
python -c "
from pathlib import Path
from src.collect.lookup_chain_miner import build_ace_pairs
build_ace_pairs(
    Path('D:/Users/Administrator/Documents/GitHub/Construct3-RAG/data/schemas'),
    Path('D:/Users/Administrator/Documents/GitHub/Construct3-Manual/Construct3-Manual'),
    Path('data/pairs/lookup_chain.jsonl'),
)
"

# Step 2: Chunk manual docs
python -c "
from pathlib import Path
from src.collect.manual_chunker import chunk_manual
chunk_manual(
    Path('D:/Users/Administrator/Documents/GitHub/Construct3-Manual/Construct3-Manual'),
    Path('data/pairs/manual_chunks.jsonl'),
)
"

# Step 3: Generate synthetic queries (requires ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY=your_key
python scripts/generate_synthetic.py --limit 50  # test with 50 chunks first

# Review data/pairs/manual_queries.jsonl before proceeding

# Step 4: Train (dry run first to check VRAM)
python scripts/train_embedding.py --dry-run
python scripts/train_embedding.py --stage all

# Step 5: Evaluate vs baseline
python scripts/evaluate_embedding.py --baseline
```

## Integration with RAG

After training, update `Construct3-RAG/.env`:
```
EMBEDDING_MODEL=D:/Users/Administrator/Documents/GitHub/Construct3-LoRA/output/qwen3-embedding-4b-c3/merged
EMBEDDING_DIMENSION=2560
```
Then rebuild Qdrant collections:
```bash
cd D:/Users/Administrator/Documents/GitHub/Construct3-RAG
python -m src.ingest.indexer --rebuild
```
```

- [ ] **Step 4: Final commit**

```bash
git add README.md
git commit -m "docs: add README with quick start and RAG integration instructions"
git log --oneline
```
Expected: 8 commits total

---

## Success Criteria

- [ ] `pytest tests/ -v` passes with 0 failures (no model loading required)
- [ ] `data/pairs/lookup_chain.jsonl` contains ≥2900 pairs
- [ ] `data/pairs/manual_chunks.jsonl` contains ≥1200 chunks
- [ ] Dataset column order: `anchor` first, `positive` second (verified in smoke test)
- [ ] Dry-run completes without OOM
- [ ] After full training + eval: `Recall@5` improves ≥5pp vs baseline
