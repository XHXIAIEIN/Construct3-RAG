/**
 * 用 zh_r475.csv 更新 data/schemas/ 里的 zh 字段
 * 不依赖 C3 源码，直接 patch 现有 JSON
 * 
 * Usage: node scripts/patch-schema-zh.js
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const CSV_PATH = path.join(ROOT, 'data', 'source', 'zh_r475.csv');
const SCHEMAS = path.join(ROOT, 'data', 'schemas');

// ── 解析 CSV ─────────────────────────────────────────────────────────────────
function parseCSV(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  const map = {};
  for (const rawLine of content.split('\n')) {
    const line = rawLine.trim();
    if (!line || !line.startsWith('text.')) continue;
    // 简单 CSV 解析：考虑带引号的字段
    const cols = splitCSVLine(line);
    if (cols.length < 6) continue;
    const key = cols[0].trim();
    const zh  = cols[1].replace(/^"|"$/g, '').trim();
    const en  = cols[5].replace(/^"|"$/g, '').trim();
    if (key) map[key] = { zh, en };
  }
  return map;
}

function splitCSVLine(line) {
  const cols = [];
  let cur = '', inQuote = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === '"') {
      if (inQuote && line[i+1] === '"') { cur += '"'; i++; }
      else inQuote = !inQuote;
    } else if (c === ',' && !inQuote) {
      cols.push(cur); cur = '';
    } else {
      cur += c;
    }
  }
  cols.push(cur);
  return cols;
}

// ── 打补丁工具 ────────────────────────────────────────────────────────────────
let patched = 0, skipped = 0;

function patch(obj, csvKey, t, fields) {
  // fields: array of [objField, csvSuffix]
  for (const [objField, csvSuffix] of fields) {
    const entry = t[`${csvKey}.${csvSuffix}`];
    if (!entry) continue;
    // always overwrite — CSV is the source of truth
    if (entry.zh) { obj[objField] = entry.zh; patched++; }
    const enField = objField.replace('_zh', '_en');
    if (entry.en) { obj[enField] = entry.en; }
  }
}

function patchAce(ace, csvBase, t) {
  patch(ace, csvBase, t, [
    ['name_zh', 'list-name'], ['name_zh', 'translated-name'],
    ['description_zh', 'description'],
    ['display_zh',     'display-text'],
  ]);
  for (const param of (ace.params || [])) {
    const pb = `${csvBase}.params.${param.id}`;
    patch(param, pb, t, [
      ['name_zh', 'name'],
      ['desc_zh', 'desc'],
    ]);
  }
}

// ── Plugins & Behaviors ───────────────────────────────────────────────────────
function patchDir(dirName, type) {
  const dir = path.join(SCHEMAS, dirName);
  const t = translationMap;
  let count = 0;

  for (const fname of fs.readdirSync(dir)) {
    if (!fname.endsWith('.json') || fname === 'index.json') continue;
    const fpath = path.join(dir, fname);
    const plugin = JSON.parse(fs.readFileSync(fpath, 'utf-8'));
    const id = plugin.id || fname.replace('.json', '');
    const base = `text.${type}.${id}`;

    // plugin-level
    patch(plugin, base, t, [
      ['name_zh',        'name'],
      ['description_zh', 'description'],
    ]);

    // ACEs
    for (const aceType of ['conditions', 'actions', 'expressions']) {
      for (const ace of (plugin[aceType] || [])) {
        patchAce(ace, `${base}.${aceType}.${ace.id}`, t);
      }
    }

    // properties
    for (const prop of (plugin.properties || [])) {
      const pb = `${base}.properties.${prop.id}`;
      patch(prop, pb, t, [
        ['name_zh', 'name'],
        ['description_zh', 'desc'],
      ]);
    }

    fs.writeFileSync(fpath, JSON.stringify(plugin, null, 2), 'utf-8');
    count++;
  }
  console.log(`  ${dirName}: ${count} 个文件`);
}

// ── Effects ───────────────────────────────────────────────────────────────────
function patchEffects() {
  const dir = path.join(SCHEMAS, 'effects');
  const t = translationMap;
  let count = 0;

  for (const fname of fs.readdirSync(dir)) {
    if (!fname.endsWith('.json') || fname === 'index.json') continue;
    const fpath = path.join(dir, fname);
    const effect = JSON.parse(fs.readFileSync(fpath, 'utf-8'));
    const id = effect.id || fname.replace('.json', '');
    const base = `text.effects.${id}`;

    patch(effect, base, t, [
      ['name_zh',        'name'],
      ['description_zh', 'description'],
    ]);

    for (const param of (effect.parameters || [])) {
      const pb = `${base}.params.${param.id}`;
      patch(param, pb, t, [
        ['name_zh', 'name'],
        ['desc_zh',  'description'],
      ]);
    }

    fs.writeFileSync(fpath, JSON.stringify(effect, null, 2), 'utf-8');
    count++;
  }
  console.log(`  effects: ${count} 个文件`);
}

// ── Main ──────────────────────────────────────────────────────────────────────
console.log('解析 CSV...');
const translationMap = parseCSV(CSV_PATH);
console.log(`  ${Object.keys(translationMap).length} 条翻译\n`);

console.log('打补丁...');
patchDir('plugins',   'plugins');
patchDir('behaviors', 'behaviors');
patchEffects();

console.log(`\n完成！写入 ${patched} 个字段。`);
