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
DATA_DIR = BASE_DIR / "data"
# Schema directory: CDN-exported schemas
SCHEMA_DIR = Path(os.getenv("C3_CACHE_DIR", str(BASE_DIR / ".cache" / "c3-cdn"))) / os.getenv("C3_VERSION", "r495.2") / "schemas"

# =============================================================================
# External Sources
# =============================================================================

# External repos (sibling directories of this repo).
# Both are optional — the pipeline degrades gracefully when missing.
MANUAL_REPO = "Construct3-Manual"  # https://github.com/XHXIAIEIN/Construct3-Manual
EXAMPLE_REPO = "Construct-Example-Projects"  # https://github.com/Scirra/Construct-Example-Projects
ADDON_SDK_REPO = "Construct-Addon-SDK"  # https://github.com/Scirra/Construct-Addon-SDK

# Derived paths (may not exist)
MANUAL_DIR = BASE_DIR.parent / MANUAL_REPO / "Construct3-Manual"
EXAMPLE_PROJECTS_DIR = BASE_DIR.parent / EXAMPLE_REPO / "example-projects"
ADDON_SDK_MANUAL_DIR = BASE_DIR.parent / MANUAL_REPO / "Construct3-Addon-SDK"
ADDON_SDK_CODE_DIR = BASE_DIR.parent / ADDON_SDK_REPO

# Availability flags — checked once at import time
MANUAL_AVAILABLE: bool = MANUAL_DIR.exists()
EXAMPLES_AVAILABLE: bool = EXAMPLE_PROJECTS_DIR.exists()
ADDON_SDK_MANUAL_AVAILABLE: bool = ADDON_SDK_MANUAL_DIR.exists()
ADDON_SDK_CODE_AVAILABLE: bool = ADDON_SDK_CODE_DIR.exists()

# =============================================================================
# Construct 3 CDN (official data source)
# =============================================================================
C3_VERSION = os.getenv("C3_VERSION", "r495.2")
C3_CDN_BASE = os.getenv("C3_CDN_BASE", "https://editor.construct.net")
C3_CACHE_DIR = Path(os.getenv("C3_CACHE_DIR", str(BASE_DIR / ".cache" / "c3-cdn")))

# =============================================================================
# Vector Database
# =============================================================================
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# =============================================================================
# Embedding Model
# =============================================================================
# Options:
#   Qwen/Qwen3-Embedding-0.6B  — multilingual SOTA, 1024 dims, instruction-tuned (default)
#   Qwen/Qwen3-Embedding-4B    — higher quality, 2560 dims
#   Qwen/Qwen3-Embedding-8B    — MTEB multilingual #1, 4096 dims
#   BAAI/bge-m3                — multilingual, 1024 dims; supports native sparse (BGE_M3_NATIVE_SPARSE)
#
# Model registry (name → expected dimension) for validation and quick reference.
# Dimension is auto-detected from the model; this dict is informational + used by eval scripts.
EMBEDDING_MODEL_REGISTRY: dict[str, int] = {
    "BAAI/bge-m3": 1024,
    "Qwen/Qwen3-Embedding-0.6B": 1024,
    "Qwen/Qwen3-Embedding-4B": 2560,
    "Qwen/Qwen3-Embedding-8B": 4096,
}

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1024"))

# Enable bge-m3 native lexical sparse vectors (FlagEmbedding) instead of BM25.
# Only applies when EMBEDDING_MODEL=BAAI/bge-m3. Requires: pip install FlagEmbedding
BGE_M3_NATIVE_SPARSE = os.getenv("BGE_M3_NATIVE_SPARSE", "false").lower() == "true"

# =============================================================================
# LLM Configuration
# =============================================================================
# provider=ollama:       LLM_MODEL=qwen2.5:7b
# provider=openai:       LLM_MODEL=moonshot-v1-128k / gpt-4o  (requires API Key)
# provider=huggingface:  LLM_MODEL=Qwen/Qwen3.5-9B             (local inference)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")   # ollama | openai | huggingface
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

# =============================================================================
# Server
# =============================================================================
RAG_SERVER_PORT = int(os.getenv("RAG_SERVER_PORT", "8765"))

# Lite mode: lookup only, skip Qdrant/embedding/reranker.
# Set LITE_MODE=true to run without Docker or GPU.
LITE_MODE = os.getenv("LITE_MODE", "false").lower() == "true"

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

# =============================================================================
# Query Expander — semantic token expansion backend
# =============================================================================
# EXPANDER_BACKEND controls which backend is used:
#   dict     — Chinese thesaurus + bge-m3 embedding search (default, offline)
#   api      — Free LLM API (DashScope or DeepSeek)
#   local    — Local small model (Qwen3-0.5B, HuggingFace)
#   disabled — Skip semantic expansion entirely

EXPANDER_BACKEND = os.getenv("EXPANDER_BACKEND", "dict")

# dict backend
EXPANDER_DICT_SOURCE = os.getenv("EXPANDER_DICT_SOURCE", "cilin")   # cilin | hownet
EXPANDER_DICT_FILTER = os.getenv("EXPANDER_DICT_FILTER", "true")    # filter to C3 vocab

# api backend
EXPANDER_API_PROVIDER = os.getenv("EXPANDER_API_PROVIDER", "dashscope")  # dashscope | deepseek
EXPANDER_API_KEY      = os.getenv("EXPANDER_API_KEY",      "")
EXPANDER_API_MODEL    = os.getenv("EXPANDER_API_MODEL",    "qwen-turbo")

# local backend
EXPANDER_LOCAL_MODEL = os.getenv("EXPANDER_LOCAL_MODEL", "Qwen/Qwen3-0.5B")
EXPANDER_DEVICE      = os.getenv("EXPANDER_DEVICE",      "cpu")

# shared
EXPANDER_TIMEOUT_S  = float(os.getenv("EXPANDER_TIMEOUT_S",  "5.0"))
EXPANDER_MAX_TOKENS = int(os.getenv("EXPANDER_MAX_TOKENS",   "80"))
EXPANDER_TOP_K      = int(os.getenv("EXPANDER_TOP_K",        "12"))

# =============================================================================
# Cross-Encoder Reranking
# =============================================================================
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "true").lower() == "true"
RERANKER_TOP_K   = int(os.getenv("RERANKER_TOP_K", "20"))   # candidates fed to reranker
RERANKER_MODEL   = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")

# =============================================================================
# BM25 Hybrid Search
# =============================================================================
# Set to True after rebuilding index with sparse vectors
BM25_ENABLED = os.getenv("BM25_ENABLED", "false").lower() == "true"

# =============================================================================
# Contextual Chunking
# =============================================================================
# Set to True after generating contexts via scripts/generate_chunk_contexts.py
CONTEXTUAL_CHUNKING_ENABLED = os.getenv("CONTEXTUAL_CHUNKING_ENABLED", "false").lower() == "true"
CONTEXTUAL_CHUNKING_CACHE   = Path(os.getenv("CONTEXTUAL_CHUNKING_CACHE",
                                              str(BASE_DIR / "data" / "chunk_contexts.json")))
