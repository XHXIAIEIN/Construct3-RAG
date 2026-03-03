#!/bin/bash
# 仅索引示例项目
# Usage: ./scripts/index-examples.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "  索引示例项目"
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
from src.config import QDRANT_HOST, QDRANT_PORT, EXAMPLE_PROJECTS_DIR

indexer = DataIndexer(QDRANT_HOST, QDRANT_PORT)

print('索引示例项目...')
indexer.index_examples(str(EXAMPLE_PROJECTS_DIR))

print('示例项目索引完成!')
"

echo ""
echo "示例项目索引完成!"
