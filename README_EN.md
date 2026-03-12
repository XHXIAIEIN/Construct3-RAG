# Construct3-RAG

[中文](README.md) | **English**

A Construct 3 documentation Q&A assistant powered by RAG (Retrieval-Augmented Generation).

## Features

- **Documentation Q&A**: Answer Construct 3 questions with source citations and confidence levels
- **Hybrid Retrieval**: Vector semantic search + BM25 keyword search + cross-collection RRF reranking
- **Query Expansion**: Auto-expands Chinese queries to ACE Schema terms for better retrieval
- **Multi-turn Conversation**: Continuous Q&A with context memory
- **Streaming Output**: Real-time display of LLM generation
- **Hallucination Prevention**: Self-Reflection validation + strict citation mode
- **Evaluation System**: Heuristic + RAGAS semantic metrics, composite score 0.96–0.98

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
| `zh_r475.csv` | POEditor | ACE Schema generation |
| `Construct3-Manual` | [GitHub](https://github.com/XHXIAIEIN/Construct3-Manual) | Official manual Markdown |
| `Construct-Example-Projects` | [GitHub](https://github.com/Scirra/Construct-Example-Projects) | Official example projects |

### 2. Install Dependencies

```bash
cd Construct3-RAG
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Start Qdrant

```bash
docker run -d -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
```

### 4. Configure LLM

Choose one of the following:

**Option A: HuggingFace local model (default)**
```bash
# Download a model (example: Qwen3.5-9B)
# Recommended path: D:/Models/ or any local path
```
`.env` configuration:
```
LLM_PROVIDER=huggingface
LLM_MODEL=D:/Models/Qwen3.5-9B
```

**Option B: Ollama**
```bash
ollama pull qwen2.5:7b   # or qwen3:8b, qwen3:30b
```
`.env` configuration:
```
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b
LLM_BASE_URL=http://localhost:11434
```

**Option C: OpenAI-compatible API**
```
LLM_PROVIDER=openai
LLM_MODEL=your-model-name
LLM_BASE_URL=https://your-api-endpoint
LLM_API_KEY=your-api-key
```

### 5. Index Data

```bash
# Generate ACE Schema (optional, already included in repo)
node scripts/generate-schema.js

# Index data (first time takes ~15 minutes)
python -m src.ingest.indexer --rebuild
```

### 6. Start Chat

```bash
python scripts/chat.py
```

> **Note**: Vector database data is stored in Docker volume, not included in Git repo. First use requires running step 5 to build the index.

## Tech Stack

| Component | Choice | Description |
|-----------|--------|-------------|
| LLM | Qwen3.5-9B | Local via HuggingFace / Ollama / OpenAI-compatible |
| Vector DB | Qdrant | High-performance vector search |
| Embedding | BAAI/bge-m3 | Multilingual embedding model, 1024 dimensions |
| Chunking | H2 semantic chunking | Split by document structure |
| Hybrid Retrieval | BM25 + Vector | Keyword + semantic dual-path recall |

## Project Structure

```
Construct3-RAG/
├── data/
│   ├── source/                # External data (manual download required)
│   │   └── zh_r475.csv     # Official translation file
│   └── schemas/               # ACE Schema (72 plugins + 31 behaviors)
├── docs/                      # Design docs, guides, knowledge base
├── scripts/                   # Operations scripts (start/index/evaluate)
│   ├── chat.py                # Chat client entry point
│   └── evaluate.py            # Evaluation system entry point
├── src/
│   ├── config.py              # Global config
│   ├── collections.py         # Collection definitions
│   ├── ingest/                # Data processing and indexing
│   ├── rag/                   # RAG core
│   └── locale/                # Internationalization (zh/en)
├── tests/                     # Unit tests (206)
└── requirements.txt
```

## Vector Collections

| Collection | Content | Vectors |
|------------|---------|---------|
| `c3_guide` | Tutorials, overview, tips | 124 |
| `c3_interface` | Editor interface, toolbars, dialogs | 146 |
| `c3_project` | Events, objects, timeline, flowchart | 136 |
| `c3_plugins` | Plugin reference (65) | 420 |
| `c3_behaviors` | Behavior reference (31) | 156 |
| `c3_effects` | Effects reference | 89 |
| `c3_scripting` | JavaScript/TypeScript API | 201 |
| `c3_ace` | ACE Schema (action/condition/expression definitions) | 2,927 |
| `c3_terms` | Terminology table (Chinese/English) | 23,824 |
| `c3_examples` | Official example events (490 projects) | 7,148 |

**Statistics**: 35,171 vectors, 10 collections

## Evaluation Results

Results on 15 representative questions (heuristic metrics, Qwen3.5-9B, smart mode):

| Metric | Score |
|--------|-------|
| Composite Score | **0.96–0.98** |
| Grade Distribution | 15/15 A |

## More Documentation

- [Detailed RAG Explanation](docs/rag-introduction.md)

## License

[MIT](LICENSE)
