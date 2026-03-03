#!/bin/bash
# 停止所有服务
# Usage: ./scripts/stop-services.sh

echo "=========================================="
echo "  停止后端服务"
echo "=========================================="

# 停止 Qdrant
echo ""
echo "[1/2] 停止 Qdrant..."
if docker ps --format '{{.Names}}' | grep -q '^qdrant$'; then
    docker stop qdrant
    echo "Qdrant 已停止"
else
    echo "Qdrant 未运行"
fi

# 停止 Ollama
echo ""
echo "[2/2] 停止 Ollama..."
if pgrep -x "ollama" > /dev/null; then
    pkill -x ollama
    echo "Ollama 已停止"
else
    echo "Ollama 未运行"
fi

echo ""
echo "=========================================="
echo "  所有服务已停止"
echo "=========================================="
