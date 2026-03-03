#!/bin/bash
# 启动 Qdrant 和 Ollama 服务
# Usage: ./scripts/start-services.sh

set -e

echo "=========================================="
echo "  启动后端服务"
echo "=========================================="

# 检查并启动 Qdrant
echo ""
echo "[1/2] 启动 Qdrant 向量数据库..."

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo "警告: Docker 未运行，请先启动 Docker Desktop"
    echo "提示: 打开 Docker Desktop 应用程序"
    exit 1
fi

# 检查 Qdrant 容器是否已存在
if docker ps -a --format '{{.Names}}' | grep -q '^qdrant$'; then
    # 容器存在，检查是否运行中
    if docker ps --format '{{.Names}}' | grep -q '^qdrant$'; then
        echo "Qdrant 已在运行中"
    else
        echo "启动已有的 Qdrant 容器..."
        docker start qdrant
    fi
else
    echo "创建并启动 Qdrant 容器..."
    docker run -d \
        --name qdrant \
        -p 6333:6333 \
        -p 6334:6334 \
        -v qdrant_storage:/qdrant/storage \
        qdrant/qdrant
fi

echo "Qdrant 地址: http://localhost:6333"
echo "Qdrant Dashboard: http://localhost:6333/dashboard"

# 检查并启动 Ollama
echo ""
echo "[2/2] 检查 Ollama..."

if ! command -v ollama &> /dev/null; then
    echo "Ollama 未安装，正在安装..."
    brew install ollama
fi

# 检查 Ollama 是否运行
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "启动 Ollama 服务..."
    ollama serve &
    sleep 3
else
    echo "Ollama 已在运行中"
fi

# 检查并下载模型
MODEL="${LLM_MODEL:-qwen2.5:7b}"
echo ""
echo "检查模型: $MODEL"

if ! ollama list | grep -q "$MODEL"; then
    echo "下载模型 $MODEL (可能需要几分钟)..."
    ollama pull "$MODEL"
else
    echo "模型 $MODEL 已存在"
fi

echo ""
echo "=========================================="
echo "  服务启动完成!"
echo "=========================================="
echo ""
echo "服务状态:"
echo "  - Qdrant: http://localhost:6333"
echo "  - Ollama: http://localhost:11434"
echo "  - 模型: $MODEL"
