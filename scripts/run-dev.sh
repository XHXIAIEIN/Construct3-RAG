#!/bin/bash
# Dev mode: run tests in watch mode
# Usage: ./scripts/run-dev.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "  开发模式 - 运行测试"
echo "=========================================="

cd "$PROJECT_ROOT"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo ""
echo "运行测试..."
echo ""

python -m pytest tests/ -v
