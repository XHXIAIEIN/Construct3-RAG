#!/bin/bash
# Run RAG chain interactively (CLI)
# Usage: ./scripts/run.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "  Construct 3 RAG Assistant"
echo "=========================================="

cd "$PROJECT_ROOT"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Check service status
echo ""
echo "检查服务状态..."

# Check Qdrant
if ! curl -s http://${QDRANT_HOST:-localhost}:${QDRANT_PORT:-6333}/collections > /dev/null 2>&1; then
    echo "警告: Qdrant 未运行"
    echo "请先运行: ./scripts/start-services.sh"
    exit 1
fi
echo "  ✓ Qdrant 正常"

# Check data
COLLECTIONS=$(curl -s http://${QDRANT_HOST:-localhost}:${QDRANT_PORT:-6333}/collections | grep -o '"name":"[^"]*"' | wc -l)
if [ "$COLLECTIONS" -eq 0 ]; then
    echo ""
    echo "警告: 向量数据库为空"
    echo "请先运行: ./scripts/index-all.sh"
    exit 1
fi
echo "  ✓ 数据已索引"

echo ""
echo "=========================================="
echo "  使用方式"
echo "=========================================="
echo ""
echo "  Python API:"
echo "    from src.rag.chain import RAGChain"
echo "    chain = RAGChain()"
echo "    resp = chain.answer_smart('Sprite 是什么？')"
echo ""
echo "  Benchmark:"
echo "    python scripts/benchmark.py --mode smart"
echo ""
