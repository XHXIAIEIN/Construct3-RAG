/**
 * 从 r466 源码和 Manual 生成 Construct3 编辑器知识 Schema
 * 包含 UI 面板、对话框、菜单、项目属性等
 */

const fs = require('fs');
const path = require('path');

// =============================================================================
// 路径配置
// =============================================================================
const ROOT_DIR = path.join(__dirname, '..');

// 外部资料
const SOURCE_DIR = path.join(ROOT_DIR, 'source');
const TRANSLATION_CSV = 'zh-CN_R466.csv';

// 本地开发资源
const LOCAL_DIR = path.join(ROOT_DIR, '.local');
const MANUAL_DATA = 'manual-data/data/construct-3';
const MANUAL_DIR = path.join(LOCAL_DIR, MANUAL_DATA);

// 输出目录
const DATA_DIR = path.join(ROOT_DIR, 'data');
const OUTPUT_DIR = path.join(DATA_DIR, 'schemas');

// CSV 翻译缓存
let translationCache = null;

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

    // CSV 格式: key,zh,,,, en
    const match = line.match(/^([^,]+),(.+?),,,,(.*)$/);
    if (match) {
      const key = match[1].trim();
      let zh = match[2].trim();
      let en = match[3].trim();
      // 移除引号
      zh = zh.replace(/^"|"$/g, '');
      en = en.replace(/^"|"$/g, '');
      translationCache[key] = { zh, en };
    }
  }

  return translationCache;
}

/**
 * 从 HTML 中提取纯文本
 */
function htmlToText(html) {
  if (!html) return '';
  return html
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * 从 Manual JSON 提取内容
 */
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

/**
 * 收集 UI 栏目（Bars）信息
 */
function collectBars() {
  console.log('收集 UI 栏目信息...');
  const translations = parseTranslationCSV();
  const bars = {};

  // 定义已知的栏目
  const barIds = [
    'project', 'properties', 'layers', 'instances', 'tilemap',
    'timeline', 'zOrder', 'bookmarks', 'findResults', 'findAllReferences',
    'textEditor', 'asset-browser'
  ];

  for (const barId of barIds) {
    const prefix = `text.ui.bars.${barId}`;
    const titleKey = `${prefix}.title`;

    if (translations[titleKey]) {
      const bar = {
        id: barId,
        name_zh: translations[titleKey].zh,
        name_en: translations[titleKey].en,
        description_zh: '',
        description_en: '',
        features: [],
        menuItems: []
      };

      // 收集菜单项
      for (const [key, value] of Object.entries(translations)) {
        if (key.startsWith(`${prefix}.menu.`) || key.startsWith(`${prefix}.context-menu.`)) {
          const parts = key.split('.');
          const itemId = parts[parts.length - 1];
          if (itemId === 'name' || !key.includes('.items.')) {
            bar.menuItems.push({
              id: parts.slice(5).join('.'),
              name_zh: value.zh,
              name_en: value.en
            });
          }
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

      bars[barId] = bar;
    }
  }

  return bars;
}

/**
 * 收集对话框信息
 */
function collectDialogs() {
  console.log('收集对话框信息...');
  const translations = parseTranslationCSV();
  const dialogs = {};

  // 从翻译中收集所有对话框 ID
  const dialogIds = new Set();
  for (const key of Object.keys(translations)) {
    if (key.startsWith('text.ui.dialogs.')) {
      const parts = key.split('.');
      if (parts.length >= 4) {
        dialogIds.add(parts[3]);
      }
    }
  }

  for (const dialogId of dialogIds) {
    const prefix = `text.ui.dialogs.${dialogId}`;
    const titleKey = `${prefix}.title`;
    const captionKey = `${prefix}.caption`;

    const title = translations[titleKey] || translations[captionKey];
    if (!title) continue;

    const dialog = {
      id: dialogId,
      name_zh: title.zh,
      name_en: title.en,
      description_zh: '',
      description_en: '',
      fields: [],
      buttons: []
    };

    // 收集字段和按钮
    for (const [key, value] of Object.entries(translations)) {
      if (key.startsWith(prefix) && !key.includes('.items.')) {
        const parts = key.split('.');
        const lastPart = parts[parts.length - 1];

        if (lastPart === 'label' || lastPart === 'placeholder') {
          dialog.fields.push({
            id: parts.slice(4, -1).join('.'),
            type: lastPart,
            name_zh: value.zh,
            name_en: value.en
          });
        } else if (lastPart === 'ok' || lastPart === 'cancel' || lastPart === 'confirm' || lastPart === 'close') {
          dialog.buttons.push({
            id: lastPart,
            name_zh: value.zh,
            name_en: value.en
          });
        }
      }
    }

    // 从 Manual 获取描述
    const manualFile = path.join(MANUAL_DIR, `interface_dialogs_${dialogId.replace(/([A-Z])/g, '-$1').toLowerCase()}.json`);
    if (fs.existsSync(manualFile)) {
      const manual = extractManualContent(manualFile);
      if (manual) {
        dialog.description_en = manual.content.substring(0, 500);
        dialog.url = manual.url;
      }
    }

    dialogs[dialogId] = dialog;
  }

  return dialogs;
}

/**
 * 收集主菜单信息
 */
function collectMainMenu() {
  console.log('收集主菜单信息...');
  const translations = parseTranslationCSV();
  const menu = {};

  // 定义主菜单结构
  const menuCategories = ['project', 'view', 'help'];

  for (const [key, value] of Object.entries(translations)) {
    if (key.startsWith('text.main-menu.')) {
      const parts = key.split('.');
      if (parts.length >= 4) {
        const category = parts[2];
        const itemPath = parts.slice(3).join('.');

        if (!menu[category]) {
          menu[category] = {
            id: category,
            name_zh: '',
            name_en: '',
            items: []
          };
        }

        // 设置分类名称
        if (parts.length === 4 && parts[3] === 'name') {
          menu[category].name_zh = value.zh;
          menu[category].name_en = value.en;
        } else if (!itemPath.includes('.items.')) {
          menu[category].items.push({
            id: itemPath,
            name_zh: value.zh,
            name_en: value.en
          });
        }
      }
    }
  }

  return menu;
}

/**
 * 收集编辑器视图信息
 */
function collectViews() {
  console.log('收集编辑器视图信息...');
  const views = {};

  // 从 Manual 收集视图信息
  const viewFiles = [
    { id: 'layout-view', file: 'interface_layout-view.json' },
    { id: 'event-sheet-view', file: 'interface_event-sheet-view.json' },
    { id: 'animations-editor', file: 'interface_animations-editor.json' },
    { id: 'image-editor', file: 'interface_image-editor.json' },
    { id: 'debugger', file: 'interface_debugger.json' },
  ];

  for (const { id, file } of viewFiles) {
    const filePath = path.join(MANUAL_DIR, file);
    if (fs.existsSync(filePath)) {
      const manual = extractManualContent(filePath);
      if (manual) {
        views[id] = {
          id: id,
          name_en: manual.title,
          name_zh: '',  // 需要翻译
          description_en: manual.content.substring(0, 800),
          url: manual.url,
          sections: manual.toc.map(t => t.text)
        };
      }
    }
  }

  return views;
}

/**
 * 收集编辑器功能列表
 */
function collectFeatures() {
  console.log('收集编辑器功能列表...');
  const features = [];

  // 从 Manual 目录收集所有 interface 相关文档
  const files = fs.readdirSync(MANUAL_DIR).filter(f => f.startsWith('interface_'));

  for (const file of files) {
    const filePath = path.join(MANUAL_DIR, file);
    const manual = extractManualContent(filePath);
    if (manual && manual.title) {
      features.push({
        id: file.replace('.json', '').replace('interface_', ''),
        name_en: manual.title,
        url: manual.url,
        sections: manual.toc.map(t => t.text)
      });
    }
  }

  return features;
}

/**
 * 收集项目属性
 */
function collectProjectProperties() {
  console.log('收集项目属性...');
  const translations = parseTranslationCSV();
  const properties = {};

  // 收集 model.project 相关的属性
  for (const [key, value] of Object.entries(translations)) {
    if (key.startsWith('text.model.project.') || key.startsWith('text.model.layout.')) {
      const parts = key.split('.');
      const category = parts[2]; // project or layout
      const propName = parts.slice(3).join('.');

      if (!properties[category]) {
        properties[category] = [];
      }

      if (propName.endsWith('.name') || propName.endsWith('.desc')) {
        const propId = propName.replace(/\.(name|desc)$/, '');
        const type = propName.endsWith('.name') ? 'name' : 'desc';

        let prop = properties[category].find(p => p.id === propId);
        if (!prop) {
          prop = { id: propId };
          properties[category].push(prop);
        }

        if (type === 'name') {
          prop.name_zh = value.zh;
          prop.name_en = value.en;
        } else {
          prop.desc_zh = value.zh;
          prop.desc_en = value.en;
        }
      }
    }
  }

  return properties;
}

/**
 * 生成编辑器知识 Schema
 */
function generateEditorSchema() {
  console.log('生成编辑器知识 Schema...\n');

  const schema = {
    version: '1.0',
    generatedAt: new Date().toISOString(),
    bars: collectBars(),
    dialogs: collectDialogs(),
    mainMenu: collectMainMenu(),
    views: collectViews(),
    features: collectFeatures(),
    projectProperties: collectProjectProperties()
  };

  // 统计信息
  schema.stats = {
    bars_count: Object.keys(schema.bars).length,
    dialogs_count: Object.keys(schema.dialogs).length,
    menu_categories: Object.keys(schema.mainMenu).length,
    views_count: Object.keys(schema.views).length,
    features_count: schema.features.length
  };

  return schema;
}

/**
 * 主函数
 */
function main() {
  console.log('开始生成 Construct3 编辑器知识 Schema...\n');

  // 检查目录
  if (!fs.existsSync(MANUAL_DIR)) {
    console.log(`警告: Manual 目录不存在: ${MANUAL_DIR}`);
  }

  // 确保输出目录存在
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  // 生成 schema
  const schema = generateEditorSchema();

  // 写入文件
  const outputPath = path.join(OUTPUT_DIR, 'editor.json');
  fs.writeFileSync(outputPath, JSON.stringify(schema, null, 2), 'utf-8');

  console.log(`\n✓ editor.json 已生成`);
  console.log('\n统计信息:');
  console.log(`  - UI 栏目: ${schema.stats.bars_count}`);
  console.log(`  - 对话框: ${schema.stats.dialogs_count}`);
  console.log(`  - 菜单分类: ${schema.stats.menu_categories}`);
  console.log(`  - 视图: ${schema.stats.views_count}`);
  console.log(`  - 功能文档: ${schema.stats.features_count}`);

  console.log('\n生成完成!');
}

main();
