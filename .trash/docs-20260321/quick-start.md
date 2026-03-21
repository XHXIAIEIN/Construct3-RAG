# 快速开始指南

## 环境要求

- macOS (Apple Silicon M1/M2/M3/M4) 或 Linux
- Python 3.10+
- Docker Desktop
- 24GB+ RAM (推荐)

### Mac M4 24GB 配置

本项目已针对 Mac mini 2024 (M4, 24GB) 进行优化：
- 默认模型: `qwen2.5:7b` (速度快，约 5GB 内存)
- 可选模型: `qwen2.5:14b` (效果更好，约 10GB 内存)

## 一键启动

```bash
# 首次运行会自动安装依赖、启动服务、索引数据
./scripts/run-all.sh
```

访问 http://localhost:7860 使用 Web 界面。

## 分步安装

如果需要分步操作：

### 1. 安装依赖

```bash
./scripts/install.sh
```

### 2. 启动后端服务

```bash
./scripts/start-services.sh
```

这会自动：
- 启动 Qdrant 向量数据库 (Docker)
- 启动 Ollama LLM 服务
- 下载所需模型

### 3. 索引数据

```bash
# 索引所有数据（首次运行约 5-10 分钟）
./scripts/index-all.sh

# 或分别索引
./scripts/index-manual.sh   # 仅手册
./scripts/index-terms.sh    # 仅术语表
./scripts/index-examples.sh # 仅示例项目
```

### 4. 启动应用

```bash
./scripts/run.sh
```

## 脚本目录结构

```
scripts/
├── run-all.sh              # 一键启动完整系统
├── run.sh                  # 启动 Web 界面
├── run-dev.sh              # 开发模式（自动重载）
├── status.sh               # 查看系统状态
├── install.sh              # 安装 Python 依赖
├── start-services.sh       # 启动 Qdrant + Ollama
├── stop-services.sh        # 停止所有服务
├── index-all.sh            # 索引所有数据
├── index-manual.sh         # 索引手册文档
├── index-terms.sh          # 索引翻译术语表
├── index-examples.sh       # 索引示例项目
└── clear-all.sh            # 清空数据库
```

## 查看状态

```bash
./scripts/status.sh
```

输出示例：
```
Docker:
  ✓ 运行中

Qdrant (向量数据库):
  ✓ 运行中 - http://localhost:6333
  数据集合:
    - c3_manual: 1234 条记录
    - c3_terms: 23513 条记录
    - c3_examples: 4567 条记录

Ollama (LLM 推理):
  ✓ 运行中 - http://localhost:11434
  已安装模型:
    - qwen2.5:7b
```

## 访问地址

| 服务 | 地址 |
|-----|------|
| Web 界面 | http://localhost:7860 |
| Qdrant Dashboard | http://localhost:6333/dashboard |
| Ollama API | http://localhost:11434 |

## 环境变量配置

可通过环境变量自定义配置：

```bash
# 使用 14B 模型（效果更好）
export LLM_MODEL=qwen2.5:14b

# 自定义 Qdrant 地址
export QDRANT_HOST=192.168.1.100
export QDRANT_PORT=6333

# 然后运行
./scripts/run-all.sh
```

## 常见问题

### Q: Docker 未运行？

打开 Docker Desktop 应用程序，等待其启动完成。

### Q: 首次运行很慢？

首次运行需要：
1. 下载 LLM 模型 (~5GB)
2. 下载 Embedding 模型 (~1GB)
3. 索引所有数据 (~10分钟)

后续启动会很快。

### Q: 内存不足？

使用更小的模型：

```bash
export LLM_MODEL=qwen2.5:3b
./scripts/run-all.sh
```

### Q: 如何更新数据？

```bash
# 清空旧数据
./scripts/clear-all.sh

# 重新索引
./scripts/index-all.sh
```

### Q: 如何停止所有服务？

```bash
./scripts/stop-services.sh
```
