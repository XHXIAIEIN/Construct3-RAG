# 实施计划

## 阶段概览

```
阶段一: 基础设施搭建
         │
         ▼
阶段二: 数据处理与入库
         │
         ▼
阶段三: RAG 系统开发
         │
         ▼
阶段四: API 与界面
         │
         ▼
[可选] 阶段五: 微调优化
```

## 阶段一：基础设施搭建

### 任务清单

- [ ] Python 环境 (3.10+)
- [ ] Qdrant 向量数据库
- [ ] Ollama LLM 推理服务
- [ ] 依赖安装

### 操作步骤

```bash
# 1. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动 Qdrant (Docker)
docker run -d -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant

# 4. 安装 Ollama
# macOS: brew install ollama
# Linux: curl -fsSL https://ollama.com/install.sh | sh

# 5. 拉取模型
ollama pull qwen2.5:14b
ollama pull nomic-embed-text  # 备选嵌入模型
```

## 阶段二：数据处理与入库

### 任务清单

- [x] Markdown 文档解析脚本
- [x] CSV 术语表处理脚本
- [x] Schema 生成脚本 (JS)
- [x] 示例项目遍历脚本
- [x] 批量向量化入库

### 执行顺序

```bash
# 1. 生成 ACE Schema (可选，已包含在仓库中)
node scripts/generate-schema.js

# 2. 向量化入库 (包含 Markdown、术语、示例项目)
python -m src.data_processing.indexer --rebuild
```

## 阶段三：RAG 系统开发

### 任务清单

- [ ] 混合检索器 (向量 + BM25)
- [ ] Prompt 模板设计
- [ ] 多轮对话支持
- [ ] 来源引用功能

### 核心组件

```
src/rag/
├── retriever.py              # 检索器
├── chain.py                  # RAG 链
├── prompts.py                # Prompt 模板
└── eventsheet_generator.py   # 事件表生成器
```

## 阶段四：API 与界面

### 任务清单

- [ ] FastAPI 后端
- [ ] Gradio Web 界面
- [ ] 测试与优化

### 启动服务

```bash
# 启动 API 服务
uvicorn src.app.main:app --reload --port 8000

# 启动 Gradio 界面
python -m src.app.gradio_ui
```

## 阶段五（可选）：微调优化

### 准备工作

1. 收集用户问答数据
2. 构建微调数据集
3. 使用 LoRA/QLoRA 微调

### 微调目标

- 提高事件表代码生成准确率
- 优化术语翻译一致性
- 减少幻觉现象

## 验收标准

| 功能 | 验收标准 |
|------|----------|
| 文档问答 | 能正确回答 Construct 3 使用问题，并标注来源 |
| 术语翻译 | 术语翻译与官方一致，查询响应 < 1s |
| 代码生成 | 能生成可用的事件表 JSON 代码片段 |
| 系统性能 | 单次查询响应 < 5s（含 LLM 生成） |
