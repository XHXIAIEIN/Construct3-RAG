#!/bin/bash
# 安装项目依赖
# Usage: ./scripts/install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "  Construct 3 RAG Assistant - 安装依赖"
echo "=========================================="

cd "$PROJECT_ROOT"

# 检查 Python 版本
echo ""
echo "[1/4] 检查 Python 版本..."
python3 --version || {
    echo "错误: 未找到 Python3，请先安装 Python 3.10+"
    exit 1
}

# 创建虚拟环境（如果不存在）
echo ""
echo "[2/4] 创建虚拟环境..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "虚拟环境已创建: venv/"
else
    echo "虚拟环境已存在: venv/"
fi

# 激活虚拟环境
echo ""
echo "[3/4] 激活虚拟环境..."
source venv/bin/activate

# 安装依赖
echo ""
echo "[4/4] 安装 Python 依赖..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "=========================================="
echo "  安装完成!"
echo "=========================================="
echo ""
echo "后续步骤:"
echo "  1. 启动服务: ./scripts/start-services.sh"
echo "  2. 索引数据: ./scripts/index-all.sh"
echo "  3. 运行应用: ./scripts/run.sh"
echo ""
echo "或者一键运行: ./scripts/run-all.sh"
