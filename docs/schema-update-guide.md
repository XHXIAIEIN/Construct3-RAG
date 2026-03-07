# Schema 更新流程

每次 Construct 3 发布新版本时，按以下步骤更新 `data/schemas/`。

## 前置条件

- Node.js（用于 generate-schema.js、patch-schema-zh.js）
- Python + 项目依赖（用于 download_expander_dict.py）

## 步骤

### 1. 确认新版本号

打开 https://editor.construct.net/beta，在页面源码或网络请求中找到版本号，
格式为 `r<版本>-<修订>` 例如 `r475-2`。

### 2. 下载新版源码 JSON

```bash
VERSION="r475-2"   # ← 改成新版本号
BASE="https://editor.construct.net/$VERSION"
LOCAL=".local/construct-source/$VERSION"

mkdir -p "$LOCAL/plugins" "$LOCAL/behaviors" "$LOCAL/effects"

curl -s "$BASE/plugins/allAces.json"        -o "$LOCAL/plugins/allAces.json"
curl -s "$BASE/plugins/pluginList.json"     -o "$LOCAL/plugins/pluginList.json"
curl -s "$BASE/behaviors/allAces.json"      -o "$LOCAL/behaviors/allAces.json"
curl -s "$BASE/behaviors/behaviorList.json" -o "$LOCAL/behaviors/behaviorList.json"
curl -s "$BASE/effects/allEffects.json"     -o "$LOCAL/effects/allEffects.json"
```

文件保存在 `.local/`（不纳入版本控制）。

### 3. 更新 CSV 翻译文件

从 POEditor 导出最新中文翻译，保存为 `data/source/zh_r<版本>.csv`。

### 4. 更新脚本路径

编辑 `scripts/generate-schema.js`，将两处路径改为新版本：

```js
const TRANSLATION_CSV = 'zh_r475.csv';          // ← 新 CSV 文件名
const R466_SOURCE = 'construct-source/r475-2';  // ← 新源码目录
```

### 5. 全量生成 Schema

```bash
node scripts/generate-schema.js
```

输出到 `data/schemas/`（72 插件 / 31 行为 / 89 特效）。

### 6. 覆盖中文翻译

```bash
node scripts/patch-schema-zh.js
```

用 CSV 覆盖所有 `name_zh` / `description_zh` / `display_zh` 字段。
目标覆盖率 ≥ 90%。

### 7. 重建字典向量

```bash
python scripts/download_expander_dict.py
```

从更新后的 schema zh_tokens 重新嵌入，保存到 `data/expander/dict_vectors.npz`。

### 8. 运行测试

```bash
python -m pytest tests/ -v
```

### 9. Commit

```bash
git add data/schemas/ data/expander/dict_vectors.npz scripts/generate-schema.js
git commit -m "feat: update schemas to r<版本> and rebuild dict vectors"
```

## 文件说明

| 文件 | 来源 | 说明 |
|------|------|------|
| `.local/construct-source/<版本>/plugins/allAces.json` | C3 编辑器 CDN | 所有插件 ACE 结构定义 |
| `.local/construct-source/<版本>/plugins/pluginList.json` | C3 编辑器 CDN | 插件列表和路径 |
| `.local/construct-source/<版本>/behaviors/allAces.json` | C3 编辑器 CDN | 所有行为 ACE 结构定义 |
| `.local/construct-source/<版本>/behaviors/behaviorList.json` | C3 编辑器 CDN | 行为列表和路径 |
| `.local/construct-source/<版本>/effects/allEffects.json` | C3 编辑器 CDN | 所有特效定义和着色器 |
| `data/source/zh_r<版本>.csv` | POEditor 导出 | 中文翻译（key,zh,,,,en 格式） |
| `data/schemas/` | 生成产物 | 最终 schema JSON，纳入版本控制 |
| `data/expander/dict_vectors.npz` | 生成产物 | bge-m3 向量字典，纳入版本控制 |
