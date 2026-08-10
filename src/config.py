"""Compatibility constants derived from typed application settings.

New composition code may consume :data:`SETTINGS`. Existing scripts and tests
can continue importing the historical module constants unchanged.
"""

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from src.settings import load_settings

SETTINGS = load_settings()

# Directory structure
BASE_DIR = SETTINGS.paths.base_dir
DATA_DIR = SETTINGS.paths.data_dir

# Construct schema/CDN
C3_VERSION = SETTINGS.schema.version
C3_CDN_BASE = SETTINGS.schema.cdn_base
C3_CACHE_DIR = SETTINGS.schema.cache_dir
BUNDLED_SCHEMA_DIR = SETTINGS.schema.bundled_dir
GENERATED_SCHEMA_DIR = SETTINGS.schema.generated_dir
SCHEMA_DIR = SETTINGS.schema.directory

# Optional sibling repositories and derived paths
MANUAL_REPO = SETTINGS.paths.manual_repo
EXAMPLE_REPO = SETTINGS.paths.example_repo
ADDON_SDK_REPO = SETTINGS.paths.addon_sdk_repo
MANUAL_DIR = SETTINGS.paths.manual_dir
EXAMPLE_PROJECTS_DIR = SETTINGS.paths.example_projects_dir
ADDON_SDK_MANUAL_DIR = SETTINGS.paths.addon_sdk_manual_dir
ADDON_SDK_CODE_DIR = SETTINGS.paths.addon_sdk_code_dir

# Compatibility snapshots. Typed settings expose dynamic availability properties.
MANUAL_AVAILABLE = SETTINGS.paths.manual_available
EXAMPLES_AVAILABLE = SETTINGS.paths.examples_available
ADDON_SDK_MANUAL_AVAILABLE = SETTINGS.paths.addon_sdk_manual_available
ADDON_SDK_CODE_AVAILABLE = SETTINGS.paths.addon_sdk_code_available

# Runtime
QDRANT_HOST = SETTINGS.runtime.qdrant_host
QDRANT_PORT = SETTINGS.runtime.qdrant_port
RAG_SERVER_PORT = SETTINGS.runtime.server_port
UI_LANGUAGE = SETTINGS.runtime.ui_language

# Vector/reranker
EMBEDDING_MODEL_REGISTRY = dict(SETTINGS.vector.embedding_model_registry)
EMBEDDING_MODEL = SETTINGS.vector.embedding_model
EMBEDDING_DIMENSION = SETTINGS.vector.embedding_dimension
MAX_CHUNK_SIZE = SETTINGS.vector.max_chunk_size
TOP_K = SETTINGS.vector.top_k
RERANKER_MODEL = SETTINGS.vector.reranker_model
RERANKER_TOP_K = SETTINGS.vector.reranker_top_k
CONTEXTUAL_CHUNKING_CACHE = SETTINGS.vector.contextual_chunking_cache

# Feature flags
LITE_MODE = SETTINGS.features.lite_mode
BGE_M3_NATIVE_SPARSE = SETTINGS.features.bge_m3_native_sparse
RERANKER_ENABLED = SETTINGS.features.reranker_enabled
BM25_ENABLED = SETTINGS.features.bm25_enabled
CONTEXTUAL_CHUNKING_ENABLED = SETTINGS.features.contextual_chunking_enabled

# LLM and lookup classifier
LLM_PROVIDER = SETTINGS.llm.provider
LLM_MODEL = SETTINGS.llm.model
LLM_BASE_URL = SETTINGS.llm.base_url
LLM_API_KEY = SETTINGS.llm.api_key
LOOKUP_OLLAMA_MODEL = SETTINGS.lookup.ollama_model
LOOKUP_OLLAMA_URL = SETTINGS.lookup.ollama_url

# Query expansion
EXPANDER_BACKEND = SETTINGS.expander.backend
EXPANDER_DICT_SOURCE = SETTINGS.expander.dict_source
EXPANDER_DICT_FILTER = SETTINGS.expander.dict_filter
EXPANDER_API_PROVIDER = SETTINGS.expander.api_provider
EXPANDER_API_KEY = SETTINGS.expander.api_key
EXPANDER_API_MODEL = SETTINGS.expander.api_model
EXPANDER_LOCAL_MODEL = SETTINGS.expander.local_model
EXPANDER_DEVICE = SETTINGS.expander.device
EXPANDER_TIMEOUT_S = SETTINGS.expander.timeout_s
EXPANDER_MAX_TOKENS = SETTINGS.expander.max_tokens
EXPANDER_TOP_K = SETTINGS.expander.top_k

__all__ = [
    "ADDON_SDK_CODE_AVAILABLE",
    "ADDON_SDK_CODE_DIR",
    "ADDON_SDK_MANUAL_AVAILABLE",
    "ADDON_SDK_MANUAL_DIR",
    "ADDON_SDK_REPO",
    "BASE_DIR",
    "BGE_M3_NATIVE_SPARSE",
    "BM25_ENABLED",
    "BUNDLED_SCHEMA_DIR",
    "C3_CACHE_DIR",
    "C3_CDN_BASE",
    "C3_VERSION",
    "CONTEXTUAL_CHUNKING_CACHE",
    "CONTEXTUAL_CHUNKING_ENABLED",
    "DATA_DIR",
    "EMBEDDING_DIMENSION",
    "EMBEDDING_MODEL",
    "EMBEDDING_MODEL_REGISTRY",
    "EXPANDER_API_KEY",
    "EXPANDER_API_MODEL",
    "EXPANDER_API_PROVIDER",
    "EXPANDER_BACKEND",
    "EXPANDER_DEVICE",
    "EXPANDER_DICT_FILTER",
    "EXPANDER_DICT_SOURCE",
    "EXPANDER_LOCAL_MODEL",
    "EXPANDER_MAX_TOKENS",
    "EXPANDER_TIMEOUT_S",
    "EXPANDER_TOP_K",
    "EXAMPLE_PROJECTS_DIR",
    "EXAMPLE_REPO",
    "EXAMPLES_AVAILABLE",
    "GENERATED_SCHEMA_DIR",
    "LITE_MODE",
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_PROVIDER",
    "LOOKUP_OLLAMA_MODEL",
    "LOOKUP_OLLAMA_URL",
    "MANUAL_AVAILABLE",
    "MANUAL_DIR",
    "MANUAL_REPO",
    "MAX_CHUNK_SIZE",
    "QDRANT_HOST",
    "QDRANT_PORT",
    "RAG_SERVER_PORT",
    "RERANKER_ENABLED",
    "RERANKER_MODEL",
    "RERANKER_TOP_K",
    "SCHEMA_DIR",
    "SETTINGS",
    "TOP_K",
    "UI_LANGUAGE",
]
