/**
 * 从 r466 源码生成 Construct3 Schema（分目录分文件结构）
 *
 * 输出结构：
 * data/schemas/
 * ├── index.json
 * ├── plugins/
 * │   ├── index.json
 * │   ├── sprite.json
 * │   └── ...
 * ├── behaviors/
 * │   ├── index.json
 * │   ├── bullet.json
 * │   └── ...
 * ├── effects/
 * │   ├── index.json
 * │   ├── blur.json
 * │   └── ...
 * └── editor/
 *     ├── index.json
 *     ├── bars/
 *     ├── dialogs/
 *     └── views/
 */

const fs = require('fs');
const path = require('path');

// =============================================================================
// 路径配置 (所有外部资源路径统一在此定义)
// =============================================================================
const ROOT_DIR = path.join(__dirname, '..');

// 外部资料
const SOURCE_DIR = path.join(ROOT_DIR, 'source');
const TRANSLATION_CSV = 'zh-CN_R466.csv';  // 从 C3 编辑器导出: 菜单 → 语言 → 导出翻译

// 本地开发资源 (不纳入版本控制)
const LOCAL_DIR = path.join(ROOT_DIR, '.local');
const R466_SOURCE = 'construct-source/r466';  // Construct 3 r466 源码
const MANUAL_DATA = 'manual-data/data/construct-3';  // 手册数据

const R466_DIR = path.join(LOCAL_DIR, R466_SOURCE);
const MANUAL_DIR = path.join(LOCAL_DIR, MANUAL_DATA);

// 输出目录
const DATA_DIR = path.join(ROOT_DIR, 'data');
const OUTPUT_DIR = path.join(DATA_DIR, 'schemas');

// CSV 翻译缓存
let translationCache = null;

/**
 * 读取 JSON 文件（处理 BOM）
 */
function readJsonFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf-8');
  if (content.charCodeAt(0) === 0xFEFF) {
    content = content.slice(1);
  }
  return JSON.parse(content);
}

/**
 * 确保目录存在
 */
function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

/**
 * 写入 JSON 文件
 */
function writeJson(filePath, data) {
  ensureDir(path.dirname(filePath));
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf-8');
}

/**
 * 解析 CSV 翻译文件
 */
function parseTranslationCSV() {
  if (translationCache) return translationCache;

  const csvPath = path.join(SOURCE_DIR, TRANSLATION_CSV);
  const content = fs.readFileSync(csvPath, 'utf-8');
  const lines = content.split('\n');

  translationCache = {};

  for (const line of lines) {
    if (!line.trim() || !line.startsWith('text.')) continue;

    const match = line.match(/^([^,]+),(.+?),,,,(.*)$/);
    if (match) {
      const key = match[1].trim();
      let zh = match[2].trim().replace(/^"|"$/g, '');
      let en = match[3].trim().replace(/^"|"$/g, '');
      translationCache[key] = { zh, en };
    }
  }

  return translationCache;
}

/**
 * 获取插件/行为的翻译
 */
function getPluginTranslation(type, id) {
  const translations = parseTranslationCSV();
  const prefix = `text.${type}.${id.toLowerCase()}`;

  return {
    name_zh: translations[`${prefix}.name`]?.zh || '',
    name_en: translations[`${prefix}.name`]?.en || '',
    description_zh: translations[`${prefix}.description`]?.zh || '',
    description_en: translations[`${prefix}.description`]?.en || ''
  };
}

/**
 * 获取属性翻译 (properties)
 */
function getPropertiesTranslation(type, pluginId) {
  const translations = parseTranslationCSV();
  const prefix = `text.${type}.${pluginId.toLowerCase()}.properties`;
  const properties = {};

  // 收集所有属性
  const propIds = new Set();
  for (const key of Object.keys(translations)) {
    if (key.startsWith(`${prefix}.`)) {
      const parts = key.slice(prefix.length + 1).split('.');
      propIds.add(parts[0]);
    }
  }

  for (const propId of propIds) {
    const propPrefix = `${prefix}.${propId}`;
    const prop = {
      id: propId,
      name_zh: translations[`${propPrefix}.name`]?.zh || '',
      name_en: translations[`${propPrefix}.name`]?.en || '',
      description_zh: translations[`${propPrefix}.desc`]?.zh || '',
      description_en: translations[`${propPrefix}.desc`]?.en || ''
    };

    // 收集 items (下拉选项)
    const items = {};
    for (const [key, value] of Object.entries(translations)) {
      if (key.startsWith(`${propPrefix}.items.`)) {
        const itemId = key.split('.items.')[1];
        items[itemId] = { zh: value.zh, en: value.en };
      }
    }
    if (Object.keys(items).length > 0) {
      prop.items = items;
    }

    if (prop.name_zh || prop.name_en) {
      properties[propId] = prop;
    }
  }

  return properties;
}

/**
 * 获取 ACE 项的翻译
 */
function getAceTranslation(type, pluginId, aceType, aceId) {
  const translations = parseTranslationCSV();
  const prefix = `text.${type}.${pluginId.toLowerCase()}.${aceType}.${aceId}`;

  return {
    name_zh: translations[`${prefix}.list-name`]?.zh || '',
    name_en: translations[`${prefix}.list-name`]?.en || '',
    description_zh: translations[`${prefix}.description`]?.zh || '',
    description_en: translations[`${prefix}.description`]?.en || ''
  };
}

/**
 * 获取参数翻译
 */
function getParamTranslation(type, pluginId, aceType, aceId, paramId) {
  const translations = parseTranslationCSV();
  const prefix = `text.${type}.${pluginId.toLowerCase()}.${aceType}.${aceId}.params.${paramId}`;

  const result = {
    name_zh: translations[`${prefix}.name`]?.zh || '',
    name_en: translations[`${prefix}.name`]?.en || ''
  };

  // 获取 combo items 翻译
  const items = {};
  for (const key of Object.keys(translations)) {
    if (key.startsWith(`${prefix}.items.`)) {
      const itemId = key.split('.items.')[1];
      items[itemId] = translations[key];
    }
  }
  if (Object.keys(items).length > 0) {
    result.items_i18n = items;
  }

  return result;
}

/**
 * 处理单个 ACE 项
 */
function processAceItem(type, pluginId, aceType, item, category) {
  const translation = getAceTranslation(type, pluginId, aceType, item.id);

  const result = {
    id: item.id,
    name_zh: translation.name_zh,
    name_en: translation.name_en,
    description_zh: translation.description_zh,
    description_en: translation.description_en
  };

  if (item.scriptName) result.scriptName = item.scriptName;
  if (item.expressionName) result.expressionName = item.expressionName;
  if (item.returnType) result.returnType = item.returnType;
  if (item.isTrigger) result.isTrigger = true;
  if (item.isAsync) result.isAsync = true;
  if (item.isDeprecated) result.isDeprecated = true;
  if (category) result.category = category;

  if (item.params && item.params.length > 0) {
    result.params = item.params.map(param => {
      const paramTrans = getParamTranslation(type, pluginId, aceType, item.id, param.id);
      const p = {
        id: param.id,
        type: param.type,
        name_zh: paramTrans.name_zh,
        name_en: paramTrans.name_en
      };
      if (param.initialValue !== undefined) p.initialValue = param.initialValue;
      if (param.items) {
        p.items = param.items;
        if (paramTrans.items_i18n) p.items_i18n = paramTrans.items_i18n;
      }
      return p;
    });
  }

  return result;
}

/**
 * 处理 allAces 数据
 */
function processAllAces(type, pluginId, pluginAces) {
  const conditions = [];
  const actions = [];
  const expressions = [];
  const categories = new Set();

  for (const [category, categoryData] of Object.entries(pluginAces)) {
    if (category) categories.add(category);

    if (categoryData.conditions) {
      for (const item of categoryData.conditions) {
        conditions.push(processAceItem(type, pluginId, 'conditions', item, category));
      }
    }
    if (categoryData.actions) {
      for (const item of categoryData.actions) {
        actions.push(processAceItem(type, pluginId, 'actions', item, category));
      }
    }
    if (categoryData.expressions) {
      for (const item of categoryData.expressions) {
        expressions.push(processAceItem(type, pluginId, 'expressions', item, category));
      }
    }
  }

  return { conditions, actions, expressions, categories: Array.from(categories) };
}

// ============ Plugins ============

function generatePlugins() {
  console.log('生成 plugins/...');

  const outputDir = path.join(OUTPUT_DIR, 'plugins');
  ensureDir(outputDir);

  const allAces = readJsonFile(path.join(R466_DIR, 'plugins/allAces.json'));
  const pluginList = readJsonFile(path.join(R466_DIR, 'plugins/pluginList.json')).pluginList;

  const index = { version: '1.0', plugins: {} };
  let totalC = 0, totalA = 0, totalE = 0;

  for (const [pluginId, pluginAces] of Object.entries(allAces)) {
    const id = pluginId.toLowerCase();
    const pluginInfo = pluginList[pluginId] || {};
    const translation = getPluginTranslation('plugins', pluginId);
    const properties = getPropertiesTranslation('plugins', pluginId);
    const { conditions, actions, expressions, categories } = processAllAces('plugins', pluginId, pluginAces);

    const plugin = {
      id,
      originalId: pluginId,
      name_zh: translation.name_zh,
      name_en: translation.name_en,
      description_zh: translation.description_zh,
      description_en: translation.description_en,
      path: pluginInfo.path || '',
      categories,
      conditions,
      actions,
      expressions
    };

    // 添加属性 (如果有)
    if (Object.keys(properties).length > 0) {
      plugin.properties = Object.values(properties);
    }

    if (pluginInfo.productTypes) plugin.productTypes = pluginInfo.productTypes;

    // 写入单独文件
    writeJson(path.join(outputDir, `${id}.json`), plugin);

    // 更新索引
    index.plugins[id] = {
      name_zh: translation.name_zh,
      name_en: translation.name_en,
      conditions: conditions.length,
      actions: actions.length,
      expressions: expressions.length
    };

    totalC += conditions.length;
    totalA += actions.length;
    totalE += expressions.length;
  }

  index.stats = {
    count: Object.keys(index.plugins).length,
    conditions: totalC,
    actions: totalA,
    expressions: totalE
  };

  writeJson(path.join(outputDir, 'index.json'), index);
  console.log(`  ✓ ${index.stats.count} 个插件`);

  return index.stats;
}

// ============ Behaviors ============

function generateBehaviors() {
  console.log('生成 behaviors/...');

  const outputDir = path.join(OUTPUT_DIR, 'behaviors');
  ensureDir(outputDir);

  const allAces = readJsonFile(path.join(R466_DIR, 'behaviors/allAces.json'));
  const behaviorList = readJsonFile(path.join(R466_DIR, 'behaviors/behaviorList.json')).behaviorList;

  const index = { version: '1.0', behaviors: {} };
  let totalC = 0, totalA = 0, totalE = 0;

  for (const [behaviorId, behaviorAces] of Object.entries(allAces)) {
    const id = behaviorId.toLowerCase();
    const behaviorInfo = behaviorList[behaviorId] || {};
    const translation = getPluginTranslation('behaviors', behaviorId);
    const properties = getPropertiesTranslation('behaviors', behaviorId);
    const { conditions, actions, expressions, categories } = processAllAces('behaviors', behaviorId, behaviorAces);

    const behavior = {
      id,
      originalId: behaviorId,
      name_zh: translation.name_zh,
      name_en: translation.name_en,
      description_zh: translation.description_zh,
      description_en: translation.description_en,
      path: behaviorInfo.path || '',
      categories,
      conditions,
      actions,
      expressions
    };

    // 添加属性 (如果有)
    if (Object.keys(properties).length > 0) {
      behavior.properties = Object.values(properties);
    }

    if (behaviorInfo.productTypes) behavior.productTypes = behaviorInfo.productTypes;

    writeJson(path.join(outputDir, `${id}.json`), behavior);

    index.behaviors[id] = {
      name_zh: translation.name_zh,
      name_en: translation.name_en,
      conditions: conditions.length,
      actions: actions.length,
      expressions: expressions.length
    };

    totalC += conditions.length;
    totalA += actions.length;
    totalE += expressions.length;
  }

  index.stats = {
    count: Object.keys(index.behaviors).length,
    conditions: totalC,
    actions: totalA,
    expressions: totalE
  };

  writeJson(path.join(outputDir, 'index.json'), index);
  console.log(`  ✓ ${index.stats.count} 个行为`);

  return index.stats;
}

// ============ Effects ============

function generateEffects() {
  console.log('生成 effects/...');

  const outputDir = path.join(OUTPUT_DIR, 'effects');
  ensureDir(outputDir);

  const allEffects = readJsonFile(path.join(R466_DIR, 'effects/allEffects.json'));
  const translations = parseTranslationCSV();

  const index = { version: '1.0', effects: {} };

  for (const effect of allEffects.all) {
    const json = effect.json;
    const id = json.id;

    const nameKey = `text.effects.${id}.name`;
    const descKey = `text.effects.${id}.description`;

    const effectData = {
      id,
      name_zh: translations[nameKey]?.zh || id,
      name_en: translations[nameKey]?.en || id,
      description_zh: translations[descKey]?.zh || '',
      description_en: translations[descKey]?.en || '',
      category: json.category,
      author: json.author,
      supportedRenderers: json['supported-renderers'],
      blendsBackground: json['blends-background'],
      preservesOpaqueness: json['preserves-opaqueness'],
      animated: json.animated
    };

    if (json.parameters && json.parameters.length > 0) {
      effectData.parameters = json.parameters.map(param => {
        const paramNameKey = `text.effects.${id}.params.${param.id}.name`;
        const paramDescKey = `text.effects.${id}.params.${param.id}.description`;
        return {
          id: param.id,
          type: param.type,
          name_zh: translations[paramNameKey]?.zh || param.id,
          name_en: translations[paramNameKey]?.en || param.id,
          initialValue: param['initial-value'],
          interpolatable: param.interpolatable
        };
      });
    }

    writeJson(path.join(outputDir, `${id}.json`), effectData);

    index.effects[id] = {
      name_zh: effectData.name_zh,
      name_en: effectData.name_en,
      category: effectData.category,
      parameters: effectData.parameters?.length || 0
    };
  }

  index.stats = { count: Object.keys(index.effects).length };

  writeJson(path.join(outputDir, 'index.json'), index);
  console.log(`  ✓ ${index.stats.count} 个特效`);

  return index.stats;
}

// ============ Editor ============

function htmlToText(html) {
  if (!html) return '';
  return html
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/\s+/g, ' ')
    .trim();
}

function extractManualContent(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    const data = JSON.parse(content);
    return {
      title: data.title || '',
      toc: data.toc || [],
      content: htmlToText(data.html || ''),
      url: data.url || ''
    };
  } catch (e) {
    return null;
  }
}

function generateEditor() {
  console.log('生成 editor/...');

  const editorDir = path.join(OUTPUT_DIR, 'editor');
  const barsDir = path.join(editorDir, 'bars');
  const dialogsDir = path.join(editorDir, 'dialogs');
  const viewsDir = path.join(editorDir, 'views');

  ensureDir(barsDir);
  ensureDir(dialogsDir);
  ensureDir(viewsDir);

  const translations = parseTranslationCSV();
  const index = { version: '1.0', bars: {}, dialogs: {}, views: {} };

  // ---- Bars ----
  const barIds = [
    'project', 'properties', 'layers', 'instances', 'tilemap',
    'timeline', 'zOrder', 'bookmarks', 'findResults', 'findAllReferences',
    'textEditor', 'asset-browser'
  ];

  for (const barId of barIds) {
    const prefix = `text.ui.bars.${barId}`;
    const titleKey = `${prefix}.title`;

    if (!translations[titleKey]) continue;

    const bar = {
      id: barId,
      name_zh: translations[titleKey].zh,
      name_en: translations[titleKey].en,
      menuItems: []
    };

    // 收集菜单项
    for (const [key, value] of Object.entries(translations)) {
      if ((key.startsWith(`${prefix}.menu.`) || key.startsWith(`${prefix}.context-menu.`))
          && !key.includes('.items.')) {
        const parts = key.split('.');
        bar.menuItems.push({
          id: parts.slice(5).join('.'),
          name_zh: value.zh,
          name_en: value.en
        });
      }
    }

    // 从 Manual 获取描述
    const manualFile = path.join(MANUAL_DIR, `interface_bars_${barId.replace(/([A-Z])/g, '-$1').toLowerCase()}-bar.json`);
    if (fs.existsSync(manualFile)) {
      const manual = extractManualContent(manualFile);
      if (manual) {
        bar.description_en = manual.content.substring(0, 500);
        bar.url = manual.url;
        bar.sections = manual.toc.map(t => t.text);
      }
    }

    writeJson(path.join(barsDir, `${barId}.json`), bar);
    index.bars[barId] = { name_zh: bar.name_zh, name_en: bar.name_en };
  }

  // ---- Dialogs ----
  const dialogIds = new Set();
  for (const key of Object.keys(translations)) {
    if (key.startsWith('text.ui.dialogs.')) {
      const parts = key.split('.');
      if (parts.length >= 4) dialogIds.add(parts[3]);
    }
  }

  for (const dialogId of dialogIds) {
    const prefix = `text.ui.dialogs.${dialogId}`;
    const title = translations[`${prefix}.title`] || translations[`${prefix}.caption`];
    if (!title) continue;

    const dialog = {
      id: dialogId,
      name_zh: title.zh,
      name_en: title.en
    };

    // 收集所有相关翻译，按类型分组
    const strings = {};      // 普通字符串 (header, name 等)
    const buttons = {};      // 按钮
    const tips = {};         // 提示消息
    const errors = {};       // 错误消息
    const contextMenu = {};  // 右键菜单
    const items = {};        // 下拉选项等

    for (const [key, value] of Object.entries(translations)) {
      if (!key.startsWith(prefix + '.')) continue;

      const subKey = key.slice(prefix.length + 1); // 移除 prefix.
      const parts = subKey.split('.');

      // 跳过 title/caption（已处理）
      if (subKey === 'title' || subKey === 'caption') continue;

      // 分类处理
      if (subKey.includes('.items.')) {
        // 下拉选项: xxx.items.yyy
        const [fieldPath, , itemId] = subKey.split(/\.items\./);
        if (!items[fieldPath]) items[fieldPath] = {};
        items[fieldPath][itemId || parts[parts.length - 1]] = { zh: value.zh, en: value.en };
      } else if (parts[0] === 'context-menu') {
        contextMenu[parts.slice(1).join('.')] = { zh: value.zh, en: value.en };
      } else if (parts[0] === 'errors') {
        errors[parts.slice(1).join('.')] = { zh: value.zh, en: value.en };
      } else if (subKey.includes('-tip.') || subKey.endsWith('-tip')) {
        tips[subKey] = { zh: value.zh, en: value.en };
      } else if (['ok', 'cancel', 'confirm', 'close', 'insert', 'add', 'remove', 'delete', 'save', 'apply', 'done', 'next', 'back', 'finish'].includes(parts[parts.length - 1])) {
        buttons[parts[parts.length - 1]] = { zh: value.zh, en: value.en };
      } else {
        strings[subKey] = { zh: value.zh, en: value.en };
      }
    }

    // 添加非空字段
    if (Object.keys(strings).length > 0) dialog.strings = strings;
    if (Object.keys(buttons).length > 0) dialog.buttons = buttons;
    if (Object.keys(tips).length > 0) dialog.tips = tips;
    if (Object.keys(errors).length > 0) dialog.errors = errors;
    if (Object.keys(contextMenu).length > 0) dialog.contextMenu = contextMenu;
    if (Object.keys(items).length > 0) dialog.items = items;

    // 从 Manual 获取描述
    const manualFile = path.join(MANUAL_DIR, `interface_dialogs_${dialogId.replace(/([A-Z])/g, '-$1').toLowerCase()}.json`);
    if (fs.existsSync(manualFile)) {
      const manual = extractManualContent(manualFile);
      if (manual) {
        dialog.description_en = manual.content.substring(0, 500);
        dialog.url = manual.url;
      }
    }

    writeJson(path.join(dialogsDir, `${dialogId}.json`), dialog);
    index.dialogs[dialogId] = { name_zh: dialog.name_zh, name_en: dialog.name_en };
  }

  // ---- Views ----
  const viewFiles = [
    { id: 'layout-view', file: 'interface_layout-view.json' },
    { id: 'event-sheet-view', file: 'interface_event-sheet-view.json' },
    { id: 'animations-editor', file: 'interface_animations-editor.json' },
    { id: 'debugger', file: 'interface_debugger.json' },
  ];

  for (const { id, file } of viewFiles) {
    const filePath = path.join(MANUAL_DIR, file);
    if (!fs.existsSync(filePath)) continue;

    const manual = extractManualContent(filePath);
    if (!manual) continue;

    const view = {
      id,
      name_en: manual.title,
      name_zh: '',
      description_en: manual.content.substring(0, 800),
      url: manual.url,
      sections: manual.toc.map(t => t.text)
    };

    writeJson(path.join(viewsDir, `${id}.json`), view);
    index.views[id] = { name_en: view.name_en };
  }

  index.stats = {
    bars: Object.keys(index.bars).length,
    dialogs: Object.keys(index.dialogs).length,
    views: Object.keys(index.views).length
  };

  writeJson(path.join(editorDir, 'index.json'), index);
  console.log(`  ✓ ${index.stats.bars} 栏目, ${index.stats.dialogs} 对话框, ${index.stats.views} 视图`);

  return index.stats;
}

// ============ Main ============

function generateMainIndex(pluginStats, behaviorStats, effectStats, editorStats) {
  const index = {
    version: '3.0',
    source: 'r466',
    generatedAt: new Date().toISOString(),
    languages: ['zh', 'en'],
    directories: {
      plugins: 'plugins/',
      behaviors: 'behaviors/',
      effects: 'effects/',
      editor: 'editor/'
    },
    stats: {
      plugins: pluginStats,
      behaviors: behaviorStats,
      effects: effectStats,
      editor: editorStats,
      total_aces: pluginStats.conditions + pluginStats.actions + pluginStats.expressions +
                  behaviorStats.conditions + behaviorStats.actions + behaviorStats.expressions
    }
  };

  writeJson(path.join(OUTPUT_DIR, 'index.json'), index);
  console.log('\n✓ index.json');
}

function cleanOldFiles() {
  console.log('\n清理旧文件...');

  const oldFiles = [
    'plugins.json', 'behaviors.json', 'effects.json', 'editor.json'
  ];

  for (const file of oldFiles) {
    const filePath = path.join(OUTPUT_DIR, file);
    if (fs.existsSync(filePath)) {
      fs.unlinkSync(filePath);
      console.log(`  删除 ${file}`);
    }
  }
}

function main() {
  console.log('开始生成 Construct3 Schema（分目录结构）...\n');

  // 清理旧文件
  cleanOldFiles();

  // 生成各部分
  const pluginStats = generatePlugins();
  const behaviorStats = generateBehaviors();
  const effectStats = generateEffects();
  const editorStats = generateEditor();

  // 生成主索引
  generateMainIndex(pluginStats, behaviorStats, effectStats, editorStats);

  console.log('\n========== 统计 ==========');
  console.log(`插件: ${pluginStats.count} (${pluginStats.conditions}C/${pluginStats.actions}A/${pluginStats.expressions}E)`);
  console.log(`行为: ${behaviorStats.count} (${behaviorStats.conditions}C/${behaviorStats.actions}A/${behaviorStats.expressions}E)`);
  console.log(`特效: ${effectStats.count}`);
  console.log(`编辑器: ${editorStats.bars} 栏目, ${editorStats.dialogs} 对话框, ${editorStats.views} 视图`);
  console.log('\n生成完成!');
}

main();
