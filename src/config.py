"""
Construct 3 RAG Assistant Configuration

支持环境变量覆盖默认配置:
  - LLM_MODEL: Ollama 模型名称 (默认 qwen2.5:7b)
  - QDRANT_HOST: Qdrant 地址 (默认 localhost)
  - EMBEDDING_MODEL: 嵌入模型 (默认 BAAI/bge-m3)
"""
import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "source"

# External Repositories (相对路径，位于父目录的兄弟仓库)
MANUAL_REPO = BASE_DIR.parent / "Construct3-Manual"
MANUAL_PDF_REPO = BASE_DIR.parent / "Construct3-Manual-PDF"
EXAMPLE_PROJECTS_DIR = BASE_DIR.parent / "Construct-Example-Projects-main" / "example-projects"

# Markdown Documentation (主要数据源)
MARKDOWN_DIR = MANUAL_REPO / "Construct3-Manual"
ADDON_SDK_DIR = MANUAL_REPO / "Construct3-Addon-SDK"

# Other Data Sources
CSV_TERMS = DATA_DIR / "zh-CN_R466.csv"

# Vector Database
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# Collections - 从 collections.py 导入
from src.collections import *

# Embedding Model
# 可选: BAAI/bge-m3 (多语言), BAAI/bge-large-zh-v1.5 (中文优化)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_DIMENSION = 1024

# LLM Configuration (Ollama)
# Mac M4 24GB 推荐: qwen2.5:7b (速度快) 或 qwen2.5:14b (效果好)
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:30b")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434")

# Chunking Settings (用于 H2 分块的后备分割)
MAX_CHUNK_SIZE = 2000  # 超长 H2 段落的分割阈值

# Retrieval Settings
TOP_K = 5
