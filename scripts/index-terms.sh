#!/bin/bash
# 仅索引翻译术语表
# Usage: ./scripts/index-terms.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "  索引翻译术语表"
echo "=========================================="

cd "$PROJECT_ROOT"

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 检查 Qdrant 是否运行
if ! curl -s http://${QDRANT_HOST:-localhost}:${QDRANT_PORT:-6333}/collections > /dev/null 2>&1; then
    echo "错误: 无法连接到 Qdrant，请先启动服务"
    exit 1
fi

python -c "
from src.ingest.indexer import DataIndexer
from src.config import QDRANT_HOST, QDRANT_PORT, CSV_TERMS

indexer = DataIndexer(QDRANT_HOST, QDRANT_PORT)

print('索引翻译术语表...')
indexer.index_terms(str(CSV_TERMS))

print('术语表索引完成!')
"

echo ""
echo "翻译术语表索引完成!"
