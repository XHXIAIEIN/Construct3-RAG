# AGENTS.md

This file provides guidance for AI agents operating in the Construct3-RAG repository.

## Project Overview

Construct3-RAG is a RAG (Retrieval Augmented Generation) assistant for Construct 3 game engine documentation. It uses:
- **LLM**: Qwen3 via Ollama (local model)
- **Vector DB**: Qdrant
- **Embedding**: BAAI/bge-m3
- **Framework**: LangChain
- **UI**: Gradio

## Build, Lint, and Test Commands

### Setup
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Start Qdrant (required for full functionality)
docker run -d -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant

# Pull LLM model (optional, defaults to qwen2.5:7b)
ollama pull qwen2.5:7b
```

### Running the Application
```bash
# Start Gradio web interface
python -m src.app.gradio_ui

# Index data to vector database (rebuild from scratch)
python -m src.data_processing.indexer --rebuild

# Generate ACE Schema from translation CSV
node scripts/generate-schema.js
```

### Testing
```bash
# Run all tests
python -m pytest tests/

# Run a single test file
python -m pytest tests/test_event_generator.py

# Run a single test function
python -m pytest tests/test_event_generator.py::test_json_validation

# Run with verbose output
python -m pytest tests/ -v

# Run test file directly (legacy style)
python tests/test_event_generator.py
```

### No Lint Configuration
This project does not currently have lint/format tooling configured. Future improvements could include:
- `ruff` for linting and formatting
- `mypy` for type checking

## Code Style Guidelines

### General Principles
- Write clear, self-documenting code with descriptive names
- Keep functions focused and single-purpose
- Use comments sparingly (code should explain itself); add comments only for complex logic or non-obvious decisions
- Follow Python PEP 8 conventions

### Imports
```python
# Standard library imports first
import os
from pathlib import Path
from typing import List, Optional

# Third-party imports
import gradio as gr
from langchain_core.prompts import PromptTemplate

# Local application imports
from src.config import QDRANT_HOST, QDRANT_PORT
from src.rag.chain import RAGChain
```

### Naming Conventions
| Element | Convention | Example |
|---------|------------|---------|
| Variables | `snake_case` | `qdrant_host`, `embedding_model` |
| Functions | `snake_case` | `build_prompt()`, `extract_json_from_response()` |
| Classes | `PascalCase` | `RAGChain`, `EventGenerator`, `SchemaLoader` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_CHUNK_SIZE`, `TOP_K` |
| Private methods | `_leading_underscore` | `_init_retriever()`, `_build_index()` |
| Module-private | `__dunder__` | `__init__`, `__call__` |

### Type Hints
Use type hints for function signatures and complex variables:

```python
from typing import Dict, List, Optional, Any

def process_response(response: str) -> Dict[str, Any]:
    """Process LLM response and extract JSON."""
    ...

def find_schema_by_keyword(keyword: str) -> Optional[Dict[str, str]]:
    """Find schema matching keyword, returns None if not found."""
    ...

def load_all_plugins() -> List[Dict[str, Any]]:
    """Load all plugin schemas from disk."""
    ...
```

### Function Design
- Keep functions under 50 lines when possible
- Use clear parameter names; prefer keyword arguments for complex calls
- Return early for error cases
- Document public API functions with docstrings

```python
def validate_clipboard_json(json_str: str) -> tuple[bool, List[str], Any]:
    """
    Validate Construct 3 clipboard JSON format.

    Args:
        json_str: JSON string to validate

    Returns:
        Tuple of (is_valid, errors_list, parsed_data)
    """
    ...
```

### Error Handling
- Use specific exception types rather than bare `except:`
- Let exceptions propagate for unexpected errors; catch only recoverable cases
- Log errors with context before re-raising

```python
try:
    result = retriever.search(query)
except ConnectionError as e:
    logger.error(f"Qdrant connection failed: {e}")
    raise  # Re-raise for caller to handle
except ValueError as e:
    logger.warning(f"Invalid query: {e}")
    return []
```

### File Organization
```
src/
├── app/           # Web UI (Gradio)
├── config.py      # Configuration constants
├── collections.py # Vector collection definitions
├── data_processing/  # Indexing and parsing
│   ├── csv_parser.py
│   ├── indexer.py
│   ├── markdown_parser.py
│   ├── project_parser.py
│   └── schema_parser.py
└── rag/           # RAG core logic
    ├── chain.py
    ├── eventsheet_generator.py
    ├── prompts.py
    └── retriever.py
```

### Configuration
All configuration lives in `src/config.py` using environment variables with defaults:

```python
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b")
```

### Data Files
- **Schemas**: `data/schemas/behaviors/`, `data/schemas/plugins/`
- **CSV**: `source/zh-CN_R466.csv` (external translation file)
- **Generated**: `data/` and `__pycache__/` are gitignored

### Path Handling
Use `pathlib.Path` for all file operations:

```python
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SCHEMA_DIR = BASE_DIR / "data" / "schemas"
```

### JSON Handling
For Construct 3 clipboard format:
- Always include `"is-c3-clipboard-data": true`
- Use `validate_clipboard_json()` for validation
- Use `extract_json_from_response()` to parse LLM outputs

### Markdown Generation
When generating responses:
- Use Gradio's `gr.Markdown` for rendered output
- Include source citations from retrieved documents
- Reference Construct 3 schema IDs explicitly

## Documentation
- Use `doc/` for design docs and guides
- Keep README.md updated for user-facing instructions
- Code comments only for non-obvious logic (e.g., "HACK: Workaround for C3 quirk")
