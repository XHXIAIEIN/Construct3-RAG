/**
 * 从 r466 源码生成增强版 Construct3 Schema
 * 合并 ACE 技术数据与中文翻译
 */

const fs = require('fs');
const path = require('path');

/**
 * 读取 JSON 文件（处理 BOM）
 */
function readJsonFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf-8');
  // 移除 BOM
  if (content.charCodeAt(0) === 0xFEFF) {
    content = content.slice(1);
  }
  return JSON.parse(content);
}

// =============================================================================
// 路径配置
// =============================================================================
const ROOT_DIR = path.join(__dirname, '..');

// 外部资料
const SOURCE_DIR = path.join(ROOT_DIR, 'source');
const TRANSLATION_CSV = 'zh-CN_R466.csv';

// 本地开发资源
const LOCAL_DIR = path.join(ROOT_DIR, '.local');
const R466_SOURCE = 'construct-source/r466';
const R466_DIR = path.join(LOCAL_DIR, R466_SOURCE);

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
    if (!line.trim()) continue;

    // CSV 格式: key,zh,,,, en
    // 使用正则处理可能包含逗号的值
    const match = line.match(/^([^,]+),(.+?),,,,(.*)$/);
    if (match) {
      const key = match[1].trim();
      const zh = match[2].trim().replace(/^"|"$/g, '');
      const en = match[3].trim().replace(/^"|"$/g, '');
      translationCache[key] = { zh, en };
    }
  }

  return translationCache;
}

/**
 * 获取翻译
 */
function getTranslation(key, field = 'list-name') {
  const translations = parseTranslationCSV();
  const fullKey = `${key}.${field}`;
  return translations[fullKey] || { zh: '', en: '' };
}

/**
 * 获取插件/行为的名称和描述翻译
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
 * 获取 ACE 项的翻译
 */
function getAceTranslation(type, pluginId, aceType, aceId) {
  const translations = parseTranslationCSV();
  const prefix = `text.${type}.${pluginId.toLowerCase()}.${aceType}.${aceId}`;

  return {
    name_zh: translations[`${prefix}.list-name`]?.zh || '',
    name_en: translations[`${prefix}.list-name`]?.en || '',
    description_zh: translations[`${prefix}.description`]?.zh || '',
    description_en: translations[`${prefix}.description`]?.en || '',
    display_zh: translations[`${prefix}.display-text`]?.zh || '',
    display_en: translations[`${prefix}.display-text`]?.en || ''
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
    name_en: translations[`${prefix}.name`]?.en || '',
    desc_zh: translations[`${prefix}.desc`]?.zh || '',
    desc_en: translations[`${prefix}.desc`]?.en || ''
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
    result.items = items;
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

  // 添加技术属性
  if (item.scriptName) result.scriptName = item.scriptName;
  if (item.expressionName) result.expressionName = item.expressionName;
  if (item.returnType) result.returnType = item.returnType;
  if (item.isTrigger) result.isTrigger = true;
  if (item.isAsync) result.isAsync = true;
  if (item.isDeprecated) result.isDeprecated = true;
  if (item.canDebug) result.canDebug = true;
  if (item.isStatic) result.isStatic = true;
  if (item.highlight) result.highlight = true;
  if (item.isVariadicParameters) result.isVariadicParameters = true;
  if (category) result.category = category;

  // 处理参数
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
        // 添加 items 翻译
        if (paramTrans.items) {
          p.items_i18n = paramTrans.items;
        }
      }

      return p;
    });
  }

  return result;
}

/**
 * 处理 allAces 数据，按类别收集 ACE
 */
function processAllAces(type, pluginId, pluginAces) {
  const conditions = [];
  const actions = [];
  const expressions = [];
  const categories = new Set();

  // 遍历所有类别
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

/**
 * 生成增强版 plugins.json
 */
function generatePluginsSchema() {
  console.log('生成 plugins.json...');

  const allAcesPath = path.join(R466_DIR, 'plugins/allAces.json');
  const pluginListPath = path.join(R466_DIR, 'plugins/pluginList.json');

  const allAces = readJsonFile(allAcesPath);
  const pluginList = readJsonFile(pluginListPath).pluginList;

  const result = {};

  for (const [pluginId, pluginAces] of Object.entries(allAces)) {
    const id = pluginId.toLowerCase();
    const pluginInfo = pluginList[pluginId] || {};
    const translation = getPluginTranslation('plugins', pluginId);

    const { conditions, actions, expressions, categories } = processAllAces('plugins', pluginId, pluginAces);

    result[id] = {
      id: id,
      originalId: pluginId,
      name_zh: translation.name_zh,
      name_en: translation.name_en,
      description_zh: translation.description_zh,
      description_en: translation.description_en,
      path: pluginInfo.path || '',
      categories: categories,
      conditions: conditions,
      actions: actions,
      expressions: expressions
    };

    if (pluginInfo.productTypes) {
      result[id].productTypes = pluginInfo.productTypes;
    }
  }

  return result;
}

/**
 * 生成增强版 behaviors.json
 */
function generateBehaviorsSchema() {
  console.log('生成 behaviors.json...');

  const allAcesPath = path.join(R466_DIR, 'behaviors/allAces.json');
  const behaviorListPath = path.join(R466_DIR, 'behaviors/behaviorList.json');

  const allAces = readJsonFile(allAcesPath);
  const behaviorList = readJsonFile(behaviorListPath).behaviorList;

  const result = {};

  for (const [behaviorId, behaviorAces] of Object.entries(allAces)) {
    const id = behaviorId.toLowerCase();
    const behaviorInfo = behaviorList[behaviorId] || {};
    const translation = getPluginTranslation('behaviors', behaviorId);

    const { conditions, actions, expressions, categories } = processAllAces('behaviors', behaviorId, behaviorAces);

    result[id] = {
      id: id,
      originalId: behaviorId,
      name_zh: translation.name_zh,
      name_en: translation.name_en,
      description_zh: translation.description_zh,
      description_en: translation.description_en,
      path: behaviorInfo.path || '',
      categories: categories,
      conditions: conditions,
      actions: actions,
      expressions: expressions
    };

    if (behaviorInfo.productTypes) {
      result[id].productTypes = behaviorInfo.productTypes;
    }
  }

  return result;
}

/**
 * 生成 effects.json
 */
function generateEffectsSchema() {
  console.log('生成 effects.json...');

  const allEffectsPath = path.join(R466_DIR, 'effects/allEffects.json');
  const allEffects = readJsonFile(allEffectsPath);
  const translations = parseTranslationCSV();

  const result = {};

  for (const effect of allEffects.all) {
    const json = effect.json;
    const id = json.id;

    // 获取翻译
    const nameKey = `text.effects.${id}.name`;
    const descKey = `text.effects.${id}.description`;

    result[id] = {
      id: id,
      name_zh: translations[nameKey]?.zh || id,
      name_en: translations[nameKey]?.en || id,
      description_zh: translations[descKey]?.zh || '',
      description_en: translations[descKey]?.en || '',
      category: json.category,
      author: json.author,
      supportedRenderers: json['supported-renderers'],
      blendsBackground: json['blends-background'],
      preservesOpaqueness: json['preserves-opaqueness'],
      animated: json.animated,
      extendBox: json['extend-box']
    };

    // 处理参数
    if (json.parameters && json.parameters.length > 0) {
      result[id].parameters = json.parameters.map(param => {
        const paramNameKey = `text.effects.${id}.params.${param.id}.name`;
        const paramDescKey = `text.effects.${id}.params.${param.id}.description`;

        return {
          id: param.id,
          type: param.type,
          name_zh: translations[paramNameKey]?.zh || param.id,
          name_en: translations[paramNameKey]?.en || param.id,
          description_zh: translations[paramDescKey]?.zh || '',
          description_en: translations[paramDescKey]?.en || '',
          initialValue: param['initial-value'],
          interpolatable: param.interpolatable,
          uniform: param.uniform
        };
      });
    }
  }

  return result;
}

/**
 * 更新 index.json
 */
function generateIndexJson(plugins, behaviors, effects) {
  console.log('更新 index.json...');

  const pluginStats = {};
  let totalConditions = 0, totalActions = 0, totalExpressions = 0;

  for (const [id, plugin] of Object.entries(plugins)) {
    pluginStats[id] = {
      name_zh: plugin.name_zh,
      name_en: plugin.name_en,
      conditions: plugin.conditions.length,
      actions: plugin.actions.length,
      expressions: plugin.expressions.length
    };
    totalConditions += plugin.conditions.length;
    totalActions += plugin.actions.length;
    totalExpressions += plugin.expressions.length;
  }

  const behaviorStats = {};
  for (const [id, behavior] of Object.entries(behaviors)) {
    behaviorStats[id] = {
      name_zh: behavior.name_zh,
      name_en: behavior.name_en,
      conditions: behavior.conditions.length,
      actions: behavior.actions.length,
      expressions: behavior.expressions.length
    };
    totalConditions += behavior.conditions.length;
    totalActions += behavior.actions.length;
    totalExpressions += behavior.expressions.length;
  }

  const effectStats = {};
  for (const [id, effect] of Object.entries(effects)) {
    effectStats[id] = {
      name_zh: effect.name_zh,
      name_en: effect.name_en,
      category: effect.category,
      parameters: effect.parameters?.length || 0
    };
  }

  return {
    version: '3.0',
    source: 'r466',
    generatedAt: new Date().toISOString(),
    languages: ['zh', 'en'],
    files: {
      plugins: 'plugins.json',
      behaviors: 'behaviors.json',
      effects: 'effects.json'
    },
    plugins: pluginStats,
    behaviors: behaviorStats,
    effects: effectStats,
    stats: {
      plugins_count: Object.keys(plugins).length,
      behaviors_count: Object.keys(behaviors).length,
      effects_count: Object.keys(effects).length,
      total_conditions: totalConditions,
      total_actions: totalActions,
      total_expressions: totalExpressions,
      total_aces: totalConditions + totalActions + totalExpressions
    }
  };
}

/**
 * 主函数
 */
function main() {
  console.log('开始生成增强版 Construct3 Schema...\n');

  // 确保输出目录存在
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  // 生成各个 schema
  const plugins = generatePluginsSchema();
  const behaviors = generateBehaviorsSchema();
  const effects = generateEffectsSchema();
  const index = generateIndexJson(plugins, behaviors, effects);

  // 写入文件
  fs.writeFileSync(
    path.join(OUTPUT_DIR, 'plugins.json'),
    JSON.stringify(plugins, null, 2),
    'utf-8'
  );
  console.log(`✓ plugins.json (${Object.keys(plugins).length} 个插件)`);

  fs.writeFileSync(
    path.join(OUTPUT_DIR, 'behaviors.json'),
    JSON.stringify(behaviors, null, 2),
    'utf-8'
  );
  console.log(`✓ behaviors.json (${Object.keys(behaviors).length} 个行为)`);

  fs.writeFileSync(
    path.join(OUTPUT_DIR, 'effects.json'),
    JSON.stringify(effects, null, 2),
    'utf-8'
  );
  console.log(`✓ effects.json (${Object.keys(effects).length} 个特效)`);

  fs.writeFileSync(
    path.join(OUTPUT_DIR, 'index.json'),
    JSON.stringify(index, null, 2),
    'utf-8'
  );
  console.log(`✓ index.json`);

  console.log('\n统计信息:');
  console.log(`  - 插件: ${index.stats.plugins_count}`);
  console.log(`  - 行为: ${index.stats.behaviors_count}`);
  console.log(`  - 特效: ${index.stats.effects_count}`);
  console.log(`  - 条件: ${index.stats.total_conditions}`);
  console.log(`  - 动作: ${index.stats.total_actions}`);
  console.log(`  - 表达式: ${index.stats.total_expressions}`);
  console.log(`  - ACE 总计: ${index.stats.total_aces}`);

  console.log('\n生成完成!');
}

main();
