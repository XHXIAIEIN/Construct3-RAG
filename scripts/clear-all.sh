#!/bin/bash
# 清空所有向量数据库集合
# Usage: ./scripts/clear-all.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "  清空向量数据库"
echo "=========================================="

cd "$PROJECT_ROOT"

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
fi

QDRANT_URL="http://${QDRANT_HOST:-localhost}:${QDRANT_PORT:-6333}"

# 检查 Qdrant 是否运行
if ! curl -s "$QDRANT_URL/collections" > /dev/null 2>&1; then
    echo "错误: 无法连接到 Qdrant"
    exit 1
fi

echo ""
read -p "确定要删除所有数据吗? (y/N) " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "已取消"
    exit 0
fi

echo ""
echo "删除集合..."

# 删除各个集合
for collection in c3_manual c3_terms c3_examples; do
    if curl -s "$QDRANT_URL/collections/$collection" | grep -q "\"status\":\"ok\""; then
        curl -X DELETE "$QDRANT_URL/collections/$collection" > /dev/null 2>&1
        echo "  已删除: $collection"
    else
        echo "  不存在: $collection"
    fi
done

echo ""
echo "=========================================="
echo "  清空完成!"
echo "=========================================="
echo ""
echo "重新索引: ./scripts/index-all.sh"
