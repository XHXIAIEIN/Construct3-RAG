# Construct3-RAG

[中文](README.md) | **English**

A Construct 3 documentation Q&A assistant powered by RAG (Retrieval-Augmented Generation).

## Features

- **Documentation Q&A**: Answer Construct 3 questions with source citations
- **Semantic Search**: Intelligent retrieval based on vector database

## Quick Start

### 1. Prepare Data Sources

All data should be placed in sibling directories:

```
Parent Directory/
├── Construct3-RAG/                    # This project
├── Construct3-Manual/                 # Official manual Markdown version
└── Construct-Example-Projects/        # Official example projects
```

```bash
git clone https://github.com/XHXIAIEIN/Construct3-RAG.git
git clone https://github.com/XHXIAIEIN/Construct3-Manual.git
git clone https://github.com/Scirra/Construct-Example-Projects.git
```

| Data Source | How to Get | Purpose |
|-------------|------------|---------|
| `zh-CN_R466.csv` | POEditor | ACE Schema generation |
| `Construct3-Manual` | [GitHub](https://github.com/XHXIAIEIN/Construct3-Manual) | Official manual Markdown |
| `Construct-Example-Projects` | [GitHub](https://github.com/Scirra/Construct-Example-Projects) | Official example projects |

### 2. Install Dependencies

```bash
cd Construct3-RAG
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

## Tech Stack

| Component | Choice | Description |
|-----------|--------|-------------|
| LLM | Qwen3:30b | Local via Ollama |
| Vector DB | Qdrant | High-performance vector search |
| Embedding | BAAI/bge-m3 | Multilingual embedding model, 1024 dimensions |
| Chunking | H2 semantic chunking | Split by document structure |
| Framework | LangChain | RAG orchestration framework |
| Frontend | Gradio | Quick web UI building |

## Project Structure

```
Construct3-RAG/
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
└── requirements.txt
```

## Vector Collections

| Collection | Source Directory | Content |
|------------|------------------|---------|
| `c3_guide` | `getting-started/`, `overview/`, `tips-and-guides/` | Tutorials, overview, tips |
| `c3_interface` | `interface/` | Editor interface, toolbars, dialogs |
| `c3_project` | `project-primitives/` | Events, objects, timeline, flowchart |
| `c3_plugins` | `plugin-reference/` | Plugin reference (65) |
| `c3_behaviors` | `behavior-reference/`, `system-reference/` | Behavior reference (31) |
| `c3_scripting` | `scripting/` | JavaScript/TypeScript API |
| `c3_examples` | Official example projects | Example events (490 projects, 7,148 events) |

**Statistics**: 8,328 vectors

## More Documentation

- [Detailed RAG Explanation](doc/guides/rag-introduction.md)

## License

[MIT](LICENSE)
