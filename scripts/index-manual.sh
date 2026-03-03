#!/bin/bash
# 仅索引手册文档
# Usage: ./scripts/index-manual.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "  索引手册文档"
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
from src.config import QDRANT_HOST, QDRANT_PORT, PDF_MANUAL, PDF_SDK

indexer = DataIndexer(QDRANT_HOST, QDRANT_PORT)

# 索引主手册
print('索引主手册...')
indexer.index_pdf(str(PDF_MANUAL))

# 索引 SDK 手册
print('索引 SDK 手册...')
indexer.index_pdf(str(PDF_SDK))

print('手册索引完成!')
"

echo ""
echo "手册文档索引完成!"
