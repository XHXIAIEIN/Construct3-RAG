"""
Construct 3 RAG Assistant Configuration
"""

import os
from pathlib import Path

# =============================================================================
# 目录结构
# =============================================================================
BASE_DIR = Path(__file__).parent.parent
SOURCE_DIR = BASE_DIR / "source"  # 外部资料 (CSV 翻译文件等)
DATA_DIR = BASE_DIR / "data"  # 生成的数据 (Schema 等)
SCHEMA_DIR = DATA_DIR / "schemas"  # 生成的数据 (Generated Data)

# =============================================================================
# 外部资料 (External Sources)
# 这些资料需要从外部获取，统一在此配置
# =============================================================================

# 翻译文件 (来自 POEditor)
TRANSLATION_CSV = "zh-CN_R466.csv"

# 外部仓库 (位于父目录的兄弟仓库)
MANUAL_REPO = "Construct3-Manual"  # https://github.com/XHXIAIEIN/Construct3-Manual
EXAMPLE_REPO = "Construct-Example-Projects"  # https://github.com/Scirra/Construct-Example-Projects

# =============================================================================
# Vector Database
# =============================================================================
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# =============================================================================
# Embedding Model
# =============================================================================
# 可选: BAAI/bge-m3 (多语言), BAAI/bge-large-zh-v1.5 (中文优化)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_DIMENSION = 1024

# =============================================================================
# LLM Configuration (Ollama)
# =============================================================================
# Mac M4 24GB 推荐: qwen2.5:7b (速度快) 或 qwen2.5:14b (效果好)
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434")

# =============================================================================
# RAG Settings
# =============================================================================
MAX_CHUNK_SIZE = 2000  # 超长 H2 段落的分割阈值
TOP_K = 5  # 检索返回的文档数量
