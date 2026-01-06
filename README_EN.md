# Construct-3 Copilot

[中文](README.md) | **English**

An AI assistant for Construct 3 game development powered by RAG, supporting documentation Q&A, code generation, and term translation.

## Features

- **Documentation Q&A**: Answer Construct 3 questions with source citations
- **Term Translation**: Chinese-English terminology lookup, consistent with official translations
- **Code Generation**: Generate Construct 3 event sheet code from requirements
- **ACE Reference**: Query plugin/behavior Actions, Conditions, Expressions
- **Construct3-Copilot**: Generate JSON that can be directly pasted into the C3 editor

---

## Quick Start

### 1. Prepare Data Sources

All data should be placed in sibling directories:

```
Parent Directory/
├── Construct3-Copilot/                    # This project
├── Construct3-Manual/                 # Official manual Markdown version
└── Construct-Example-Projects-main/   # Official example projects
```

```bash
# Clone related repositories
git clone https://github.com/XHXIAIEIN/Construct3-Copilot.git
git clone https://github.com/XHXIAIEIN/Construct3-Manual.git Construct3-Manual
git clone https://github.com/Scirra/Construct-Example-Projects.git Construct-Example-Projects-main
```

| Data Source | How to Get | Purpose |
|-------------|------------|---------|
| `zh-CN_R466.csv` | POEditor | Term translation + ACE Schema generation |
| `Construct3-Manual` | [GitHub](https://github.com/XHXIAIEIN/Construct3-Manual) | Official manual Markdown |
| `Construct-Example-Projects` | [GitHub](https://github.com/Scirra/Construct-Example-Projects) | Official example projects |

### 2. Install Dependencies

```bash
cd Construct3-Copilot
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Start Services

```bash
# Start Qdrant (Docker)
docker run -d -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant

# Install Ollama and pull model
ollama pull qwen2.5:7b   # or qwen3:30b (stronger but slower)
```

### 4. Index Data

```bash
# Generate ACE Schema (optional, already included in repo)
node scripts/generate-schema.js

# Index data (first time takes ~15 minutes)
python -m src.data_processing.indexer --rebuild
```

### 5. Start Application

```bash
python -m src.app.gradio_ui
```

> **Note**: Vector database data is stored in Docker volume, not included in Git repo. First use requires `--rebuild` to build the index.

---

## Project Structure

```
Construct3-Copilot/
├── source/                    # External data (manual download required)
│   └── zh-CN_R466.csv         # Official translation file
├── data/
│   └── schemas/               # ACE Schema (72 plugins + 31 behaviors)
├── scripts/
│   └── generate-schema.js     # Schema generation script
├── src/
│   ├── config.py              # Global config
│   ├── collections.py         # Collection definitions
│   ├── data_processing/       # Data processing
│   ├── rag/                   # RAG core
│   └── app/                   # Web UI
├── .claude/
│   └── skills/                # Claude Code Skills
└── requirements.txt
```

---

## Claude Code Skill

This project includes a Claude Code Skill that enables AI to generate Construct 3 clipboard-format JSON.

### How to Use

1. Install [Claude Code CLI](https://claude.com/claude-code)
2. Run `claude` in the project directory
3. Describe the game logic you want in natural language

### Examples

```
> Create a breakout game with mouse-controlled paddle

AI generates two JSON files:
- layout.json  → Paste to Project Bar → Layouts
- events.json  → Paste to event sheet margin
```

```
> Add WASD-controlled 8-direction movement

AI generates events JSON → Paste to event sheet margin
```

### Features

| Feature | Description |
|---------|-------------|
| Generate Events | Game logic (movement, collision, scoring, etc.) |
| Generate Objects | Sprite, Text, TiledBackground, etc. |
| Generate Layouts | Complete scenes (objects + instances + positions) |
| Generate Images | Valid PNG base64 imageData |

### Available Scripts

```bash
# Generate imageData
python3 .claude/skills/construct3-copilot/scripts/generate_imagedata.py --color red -W 32 -H 32

# Generate complete layout
python3 .claude/skills/construct3-copilot/scripts/generate_layout.py --preset breakout -o layout.json

# Query ACE Schema
python3 .claude/skills/construct3-copilot/scripts/query_schema.py plugin sprite set-animation
```

---

## Tech Stack

| Component | Choice | Description |
|-----------|--------|-------------|
| LLM | Qwen3:30b | Local via Ollama |
| Vector DB | Qdrant | High-performance vector search |
| Embedding | BAAI/bge-m3 | Multilingual embedding model, 1024 dimensions |
| Chunking | H2 semantic chunking | Split by document structure |
| Framework | LangChain | RAG orchestration framework |
| Frontend | Gradio | Quick web UI building |

---

## Vector Collections

### Document Collections

| Collection | Source Directory | Content |
|------------|------------------|---------|
| `c3_guide` | `getting-started/`, `overview/`, `tips-and-guides/` | Tutorials, overview, tips |
| `c3_interface` | `interface/` | Editor interface, toolbars, dialogs |
| `c3_project` | `project-primitives/` | Events, objects, timeline, flowchart |
| `c3_plugins` | `plugin-reference/` | Plugin reference (65) |
| `c3_behaviors` | `behavior-reference/`, `system-reference/` | Behavior reference (31) |
| `c3_scripting` | `scripting/` | JavaScript/TypeScript API |

### Special Collections

| Collection | Source | Content |
|------------|--------|---------|
| `c3_terms` | `source/zh-CN_R466.csv` | Official term translations (23,255 entries) |
| `c3_examples` | Official example projects | Example events (490 projects, 7,148 events) |

### ACE Schema

```
data/schemas/
├── index.json          # Summary index
├── plugins/            # 72 plugins (677 conditions, 776 actions, 957 expressions)
├── behaviors/          # 31 behaviors (115 conditions, 248 actions, 138 expressions)
├── effects/            # 89 effects
└── editor/             # Editor configuration
```

**Statistics**: 2,911 ACE (792 conditions + 1,024 actions + 1,095 expressions)

### Vector Database Statistics

| Collection | Vectors | Content |
|------------|---------|---------|
| c3_guide | 121 | Tutorials |
| c3_interface | 146 | Editor interface |
| c3_project | 136 | Project elements |
| c3_plugins | 420 | Plugin reference |
| c3_behaviors | 156 | Behavior reference |
| c3_scripting | 201 | Script API |
| c3_terms | 23,255 | Term translations |
| c3_examples | 7,148 | Example code |
| **Total** | **31,583** | |

---

## RAG Principles

**RAG = Retrieval-Augmented Generation**

| Approach | Issue |
|----------|-------|
| Pure LLM | AI can only answer from "memory", may be outdated or hallucinate |
| RAG | AI first "looks up" relevant materials, then answers based on them |

### Workflow

```
User Question ──→ ① Retrieve ──→ ② Augment ──→ ③ Generate ──→ Answer
                   │              │              │
                   ↓              ↓              ↓
              Vector DB      Combine Context    LLM
```

### What is Vectorization?

**Vectorization = Converting text into a sequence of numbers (semantic fingerprint)**

```
"apple"  →  [0.12, -0.45, 0.78, ...]   (1024 numbers)
"fruit"  →  [0.15, -0.42, 0.75, ...]   (very close!)
"car"    →  [0.89, 0.12, -0.56, ...]   (completely different)
```

Similar words have close vector distances; different words have far distances. During search, the user's question is also converted to a vector, finding the closest documents in the database—this is **semantic search**.

### What is Chunking?

**Chunking = Splitting long documents into smaller paragraphs**

This project splits by H2 headings, each H2 section becomes an independent "document chunk":

```markdown
# Sprite                              ← H1 (file level)

## Sprite properties                  ← H2 → Chunk 1
## Sprite conditions                  ← H2 → Chunk 2
## Sprite actions                     ← H2 → Chunk 3
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Gradio Web UI                       │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    RAGChain (chain.py)                   │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │ Classify     │ → │ Retrieve     │ → │ LLM Gen    │ │
│  │ (qa/trans/   │    │ Context      │    │ (Qwen3)   │ │
│  │  code)       │    │ (multi-coll) │    │           │ │
│  └──────────────┘    └──────────────┘    └───────────┘ │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│              HybridRetriever (retriever.py)              │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                  Qdrant Vector Database                  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │c3_guide │ │c3_plugins│ │c3_terms │ │c3_examples│      │
│  │Tutorials│ │Plugin Ref│ │Terms    │ │Examples  │      │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘       │
└─────────────────────────────────────────────────────────┘
```

---

## More Documentation

- [Detailed RAG Explanation](doc/guides/rag-introduction.md) - In-depth explanation of vectorization, chunking, retrieval

## License

[MIT](LICENSE)
