#!/bin/bash
# 索引所有数据到向量数据库
# Usage: ./scripts/index-all.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "  索引所有数据"
echo "=========================================="

cd "$PROJECT_ROOT"

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 检查 Qdrant 是否运行
echo ""
echo "检查 Qdrant 连接..."
if ! curl -s http://${QDRANT_HOST:-localhost}:${QDRANT_PORT:-6333}/collections > /dev/null 2>&1; then
    echo "错误: 无法连接到 Qdrant"
    echo "请先运行: ./scripts/start-services.sh"
    exit 1
fi
echo "Qdrant 连接正常"

# 运行索引
echo ""
echo "开始索引数据..."
echo "这可能需要几分钟，请耐心等待..."
echo ""

python -m src.ingest.indexer

echo ""
echo "=========================================="
echo "  索引完成!"
echo "=========================================="
