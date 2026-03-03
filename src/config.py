"""
Construct 3 RAG Assistant Configuration
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# =============================================================================
# Directory Structure
# =============================================================================
BASE_DIR = Path(__file__).parent.parent
SOURCE_DIR = BASE_DIR / "data" / "source"
DATA_DIR = BASE_DIR / "data"
SCHEMA_DIR = DATA_DIR / "schemas"

# =============================================================================
# External Sources
# =============================================================================

# Translation CSV (from POEditor)
TRANSLATION_CSV = "zh-CN_r473.csv"

# External repos (sibling directories of this repo)
MANUAL_REPO = "Construct3-Manual"  # https://github.com/XHXIAIEIN/Construct3-Manual
EXAMPLE_REPO = "Construct-Example-Projects"  # https://github.com/Scirra/Construct-Example-Projects

# Derived paths
MANUAL_DIR = BASE_DIR.parent / MANUAL_REPO
EXAMPLE_PROJECTS_DIR = BASE_DIR.parent / EXAMPLE_REPO / "example-projects"

# =============================================================================
# Vector Database
# =============================================================================
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# =============================================================================
# Embedding Model
# =============================================================================
# Options: BAAI/bge-m3 (multilingual), BAAI/bge-large-zh-v1.5 (Chinese-optimized)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_DIMENSION = 1024

# =============================================================================
# LLM Configuration
# =============================================================================
# provider=ollama:       LLM_MODEL=qwen2.5:7b
# provider=openai:       LLM_MODEL=moonshot-v1-128k / gpt-4o  (requires API Key)
# provider=huggingface:  LLM_MODEL=Qwen/Qwen2.5-7B-Instruct   (local inference)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")   # ollama | openai | huggingface
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

# =============================================================================
# Lookup Classifier (Tier 3: Ollama small model)
# =============================================================================
LOOKUP_OLLAMA_MODEL = os.getenv("LOOKUP_OLLAMA_MODEL", "qwen2.5:7b")
LOOKUP_OLLAMA_URL = os.getenv("LOOKUP_OLLAMA_URL", "http://localhost:11434")

# =============================================================================
# UI Language
# =============================================================================
UI_LANGUAGE: str = os.getenv("UI_LANGUAGE", "zh")

# =============================================================================
# RAG Settings
# =============================================================================
MAX_CHUNK_SIZE = 2000  # Chunk split threshold for long H2 sections
TOP_K = 5  # Number of documents returned per retrieval
