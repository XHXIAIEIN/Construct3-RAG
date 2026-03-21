# Schema 更新流程

每次 Construct 3 发布新版本时，按以下步骤更新 ACE/效果/示例数据。

## 前置条件

- Python + 项目依赖
- Qdrant 运行中

## 架构说明

ACE Schema 数据现在通过 **CDN 直接获取**（`src/ingest/c3_fetcher.py`），不再使用 `generate-schema.js`。
`C3Fetcher` 从 `editor.construct.net/<version>/` 获取 `allAces.json`、`precompiled-{locale}.json` 等数据，
`SchemaParser` 在 CDN 模式下将 allAces + en-US lang + zh-CN lang 三方 join 为双语 ACE 条目。

缓存策略：每周三 08:00 北京时间自动过期（对齐 Scirra 的周二晚发布节奏）。

## 步骤

### 1. 确认新版本号

打开 https://editor.construct.net/beta，在页面源码或网络请求中找到版本号，
格式为 `r<版本>` 例如 `r476`。

### 2. 更新版本号配置

编辑 `.env` 或设置环境变量：

```bash
C3_VERSION=r476   # ← 改成新版本号
```

对应配置在 `src/config.py` 中的 `C3_VERSION`。

### 3. 清除 CDN 缓存（可选）

CDN 缓存位于 `data/c3-cdn-cache/<version>/`。如果需要强制刷新：

```bash
rm -rf data/c3-cdn-cache/r476/
```

正常情况下无需手动清除，缓存会按周三 08:00 自动过期。

### 4. 更新 CSV 翻译文件

从 POEditor 导出最新中文翻译，保存为 `data/source/zh_r<版本>.csv`。

### 5. 重建索引

```bash
python -m src.ingest.indexer --rebuild
```

这会自动：
- 通过 `C3Fetcher` 从 CDN 获取最新 ACE/效果/示例数据
- 解析 allAces.json + en-US/zh-CN lang 文件生成双语 ACE 条目
- 解析 allEffects.json 生成效果条目
- 从 CDN example-project-data.json 获取示例元数据
- 索引所有数据到 Qdrant

### 6. 运行测试

```bash
python -m pytest tests/ -v
```

### 7. Commit

```bash
git add .env data/source/
git commit -m "feat: update to r<版本>"
```

## CDN 数据端点

| 端点 | 用途 |
|------|------|
| `plugins/allAces.json` | 所有插件 ACE 结构定义 |
| `behaviors/allAces.json` | 所有行为 ACE 结构定义 |
| `effects/allEffects.json` | 所有效果定义和着色器 |
| `loader/lang/precompiled-en-US.json` | 英文名称/描述 |
| `loader/lang/precompiled-zh-CN.json` | 中文名称/描述 |
| `media/example-project-data.json` | 示例项目元数据 |
| `plugins/pluginList.json` | 插件 ID → 路径映射 |
| `behaviors/behaviorList.json` | 行为 ID → 路径映射 |
| `versions.json` | 所有发布版本 |

## 文件说明

| 文件 | 来源 | 说明 |
|------|------|------|
| `data/c3-cdn-cache/<version>/` | C3 编辑器 CDN | 本地缓存（自动管理，不纳入版本控制） |
| `data/source/zh_r<版本>.csv` | POEditor 导出 | 中文翻译（key,zh,,,,en 格式） |
| `src/ingest/c3_fetcher.py` | 本项目 | CDN 获取 + 缓存逻辑 |
| `src/ingest/schema_parser.py` | 本项目 | ACE/效果解析（CDN + legacy 双模式） |
