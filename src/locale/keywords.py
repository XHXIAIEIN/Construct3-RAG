"""
Chinese keyword constants for NLP matching and intent classification.

All values are Chinese text used for pattern matching — they must stay in Chinese.
"""

# ---------------------------------------------------------------------------
# ACE 意图关键词 — 用于 lookup.py 与 chain.py 的意图分类
# 用于将用户查询分类为 ACE 类型（条件/动作/表达式）
# 筛选标准：在该 ACE 类别中出现频率 ≥ 55% 且出现次数 ≥ 10
# 同一个词可属于多个类别（如 "查找" → conditions + expressions）
# ---------------------------------------------------------------------------

ACE_INTENT_KEYWORDS: dict[str, frozenset[str]] = {
    "conditions": frozenset({
        # 数据驱动的特征词
        "触发", "是否", "比较", "检测", "完成", "任意", "失败",
        "正在", "成功", "执行", "检查", "存在", "运行", "测试",
        "点击", "重叠", "碰撞", "可见",
        # 常见用户查询用词
        "包含", "判断", "筛选", "过滤", "满足", "相等",
        "查找", "搜索", "找到", "检索", "遍历",
    }),
    "actions": frozenset({
        # 数据驱动的特征词
        "设置", "添加", "播放", "启用", "停止", "禁用", "显示",
        "删除", "创建", "恢复", "效果", "模式",
        # 常见用户查询用词
        "清空", "移动", "修改", "排序", "插入", "替换", "复制",
        "加载", "保存", "暂停", "销毁", "生成", "旋转",
        "重置", "调整", "切换", "发送",
    }),
    "expressions": frozenset({
        # 数据驱动的特征词
        "获取", "返回", "单位", "坐标", "时间", "像素", "字符串",
        "索引", "数量", "转换", "每秒", "之间", "宽度", "高度",
        "计算", "获得", "范围",
        # 常见用户查询用词
        "读取", "查找", "搜索", "找到", "检索", "筛选",
        "位置", "角度", "速度",
        "长度", "大小", "取值", "提取", "统计", "计数",
    }),
    "properties": frozenset({
        "属性", "参数", "状态", "尺寸", "维度", "名称", "类型",
    }),
    "scripting": frozenset({
        "脚本", "代码", "编程", "函数", "方法", "接口", "调用",
        "对象", "实例", "事件", "回调", "异步", "runtime",
        "javascript", "typescript",
    }),
}


# ---------------------------------------------------------------------------
# ACE 类型别名 — 中英文 ACE 类型名 → 规范化 key
# ---------------------------------------------------------------------------

ACE_TYPE_ALIASES: dict[str, str] = {
    "action": "actions", "actions": "actions", "动作": "actions",
    "condition": "conditions", "conditions": "conditions", "条件": "conditions",
    "expression": "expressions", "expressions": "expressions", "表达式": "expressions",
    "属性": "properties", "property": "properties", "properties": "properties",
    "参数": "properties",
}


# ---------------------------------------------------------------------------
# 中文停用词 — jieba 分词噪声过滤
# ---------------------------------------------------------------------------

ZH_STOP_WORDS: frozenset[str] = frozenset({
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没", "看",
    "好", "自", "这", "他", "她", "它", "中", "把", "那", "被", "从", "对",
    "让", "给", "用", "与", "向", "于", "呢", "吗", "么", "吧", "的话", "谢谢",
    "怎么", "如何", "什么", "为什么", "哪个", "哪些", "进来", "进去", "放进",
    "能否", "帮我", "我想要", "嗯", "那里",
    "是否", "怎样", "请问", "一下", "还是", "这样", "那样", "搞定", "不然", "好嘛", "好吗",
    "或者", "以及", "对了", "其实", "要么", "并且", "但是", "然后", "虽然", "因为", "所以",
    "特定", "具体", "某个", "某些", "一些", "部分",
    # 口语方位词（不携带 C3 语义信息）
    "里边", "外边", "里面", "外面", "里头", "外头", "那边", "这边",
    # 网络用语 / 语气词（无检索价值）
    "大佬", "老哥", "老铁", "有没有", "有木有", "知道吗", "知道不",
})


# ---------------------------------------------------------------------------
# "怎么做" 类查询检测 — 包含这些词的查询跳过 Tier 1.5
# "怎么"属于跳过词："怎么在数组中查找数字"需要操作说明，不只是 ACE 列表。
# Tier 1 的 _DETAIL_PATTERNS 仍会捕获"X 怎么用"。
# ---------------------------------------------------------------------------

HOWTO_SKIP_WORDS: frozenset[str] = frozenset({
    "如何", "怎么", "怎样", "怎么做", "怎么实现", "步骤", "流程", "教程",
    "是什么", "什么是", "区别", "对比", "概念", "原理", "介绍",
})


# ---------------------------------------------------------------------------
# 中文语法助词 / 连词 — 用作分词分隔符
# 多字连词优先（交替匹配），然后是单字助词
# ---------------------------------------------------------------------------

ZH_PARTICLES: str = (
    r'(?:以及|或者|但是|然后|并且|还是|而且|因为|所以|可以|怎么|如果|或是'
    r'|[\s,，、的。？！?!在中把了将用从到里跟和与])+'
)


# ---------------------------------------------------------------------------
# Tier 2：意图模板 — 用于 embedding 相似度匹配
# ---------------------------------------------------------------------------

INTENT_TEMPLATES: dict[str, list[str]] = {
    "ace_list": [
        "列出所有动作", "有哪些条件", "表达式列表", "属性列表",
        "有哪些 action", "所有 condition", "expressions 列表",
        "这个插件有什么动作", "这个行为的条件有哪些",
    ],
    "ace_detail": [
        "这个动作怎么用", "参数是什么", "怎么使用这个条件",
        "这个 action 的用法", "参数说明",
    ],
    "prop_list": [
        "有哪些属性", "属性列表", "properties",
        "这个插件有什么属性",
    ],
    "term_translate": [
        "中文翻译", "英文怎么说", "这个翻译成中文",
        "这个词的中文是什么", "翻译成英文",
    ],
}


# ---------------------------------------------------------------------------
# 复杂查询检测指标（用于 chain.py）
# ---------------------------------------------------------------------------

COMPLEXITY_INDICATORS: list[str] = [
    "步骤", "流程", "实现", "workflow", "how to",
    "和", "以及", "同时", "并且", "both", "and",
    "然后", "之后", "接着", "first", "then",
]


# ---------------------------------------------------------------------------
# 代码生成意图检测关键词（用于 chain.py）
# ---------------------------------------------------------------------------

CODE_GENERATION_KEYWORDS: list[str] = [
    "帮我写",  "写一个", "做一个", "弄一个", "搞一个",
    "生成", "实现", "修改", "修复", "优化",
    "事件表", "代码", "源码", "复制粘贴",
]


# ---------------------------------------------------------------------------
# 语义扩展词表 — 用于 QueryExpander 手工增补（与 schema 自动扩展合并）
# key: 用户查询中常见的中文动词/名词
# value: 在 C3 schema 描述中语义相近的词，帮助 zh→en 桥接
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# ACE 同义词集 — 关键词搜索时的语义扩展
# 如果查询中出现集合内任一词，其余词也加入过滤
# 例: 用户说 "保存进度" → 扩展出 "存储"/"store"/"set item" 匹配 ACE
# ---------------------------------------------------------------------------

ACE_SYNONYMS: list[frozenset[str]] = [
    frozenset({"碰撞", "重叠", "collision", "overlap", "collisions"}),
    frozenset({"动画", "animation", "animations", "播放", "帧"}),
    frozenset({"移动", "位置", "坐标", "position", "move"}),
    frozenset({"销毁", "删除", "destroy", "remove"}),
    frozenset({"可见", "显示", "隐藏", "visible", "show", "hide"}),
    frozenset({"计时", "计时器", "定时器", "timer", "wait", "等待", "延迟", "delay",
               "倒计时", "间隔", "countdown", "interval"}),
    frozenset({"本地存档", "持久化储存", "storage", "memory"}),
    frozenset({"保存", "存储", "存档", "slot", "save", "set item", "保存词条"}),
    frozenset({"读取", "加载", "获取", "load", "get item", "获取词条"}),
    frozenset({"速度", "speed", "velocity", "加速", "减速", "向量", "停止", "静止", "停下"}),
    frozenset({"角度", "旋转", "摇晃", "摇摆", "抖动", "振动", "shake", "rotation", "angle", "rotate"}),
    frozenset({"大小", "尺寸", "缩放", "宽度", "高度", "膨胀", "收缩", "大", "小", "高",
              "矮", "胖", "瘦", "size", "width", "height", "zoom", "scale"}),
    frozenset({"按键", "键盘", "回车", "空格",  "keyboard", "pressed", "keycode"}),
    frozenset({"点击", "点按", "触屏", "触摸", "手势", "长按", "多指", "滑动", "划动", "触控",
              "虚拟按键", "虚拟按钮", "手机按钮", "移动适配", "tap", "click", "touch"}),
    frozenset({"声音", "音效", "音乐", "audio", "sound", "music", "mp3", "ogg"}),
    # --- 物理与刚体 ---
    frozenset({"物理", "刚体", "重力", "质量", "摩擦力", "弹力", "力", "动量",
               "physics", "rigidbody", "gravity", "mass", "friction", "bounce",
               "velocity", "force", "momentum"}),
    # --- 场景与布局 ---
    frozenset({"布局", "场景", "切换", "跳转", "加载", "layout", "scene", "goto", "switch", "load"}),
    # --- 图层与深度 ---
    frozenset({"图层", "层", "深度", "顺序", "layer", "depth", "z-order", "order"}),
    # --- 视口与相机 ---
    frozenset({"视口", "相机", "镜头", "视野", "滚动", "viewport", "camera", "scroll", "field of view"}),
    # --- 手柄输入 ---
    frozenset({"手柄", "控制器", "摇杆", "扳机", "gamepad", "controller", "joystick", "trigger", "xbox"}),
    # --- 文件操作 ---
    frozenset({"文件", "目录", "文件夹", "本地目录", "安装目录", "永久保存", "读写", "保存", "加载", "导出", "导入",
               "file", "read", "write", "save", "load", "export", "import"}),
    # --- JSON 数据 ---
    frozenset({"json", "数据",  "解析", "回调", "数据结构", "字典", "数组", "序列化", "parse", "stringify", "data"}),
    # --- 网络请求 ---
    frozenset({"网络", "请求", "项目文件", "http", "ajax", "fetch", "下载", "上传", "回调", "api", "get", "post",
               "network", "request", "download", "upload"}),
    # --- UI 控件 ---
    frozenset({"按钮", "按下", "button", "press"}),
    frozenset({"文本输入", "输入框", "文本框", "textbox", "input", "editbox"}),
    frozenset({"下拉框", "选择", "选项", "combobox", "dropdown", "select"}),
    frozenset({"滑块", "滑动条", "slider", "drag"}),
    # --- 绘制与颜色 ---
    frozenset({"绘制", "画图", "canvas", "图形", "矩形", "线条", "圆",
               "draw", "rectangle", "line", "circle"}),
    frozenset({"颜色", "rgb", "rgba", "十六进制", "透明度", "color", "hex", "alpha", "opacity"}),
    # --- 音频通道与音量 ---
    frozenset({"音频通道", "音轨", "分组", "channel", "track", "group"}),
    frozenset({"音量", "静音", "平衡", "volume", "mute", "gain", "balance"}),
    # --- 事件表核心概念 ---
    frozenset({"事件", "触发", "子事件", "条件", "动作", "event", "trigger", "sub-event"}),
    frozenset({"变量", "全局变量", "实例变量", "局部变量", "variable", "global", "instance", "local"}),
    frozenset({"函数", "方法", "调用", "返回", "参数", "function", "method", "call", "return", "parameter"}),
    # --- 性能与调试 ---
    frozenset({"性能", "帧率", "fps", "内存", "优化", "performance", "framerate", "memory", "optimization"}),
    frozenset({"调试", "日志", "输出", "断点", "debug", "log", "console", "breakpoint"}),
]

# ACE 分类扩展 — 命中这些分类的 ACE 时，拉入同分类的所有 ACE
ACE_CATEGORY_EXPAND: frozenset[str] = frozenset({
    "collisions", "animations", "size-position",
})

# ---------------------------------------------------------------------------
# 歧义插件名 / 通用查询词 — 防止 "custom action" 误匹配 Custom 行为
# ---------------------------------------------------------------------------

AMBIGUOUS_PLUGIN_NAMES: frozenset[str] = frozenset({
    "custom", "system", "audio", "text", "video", "browser", "touch",
    "mouse", "list", "button", "timer", "json", "array",
})

GENERIC_QUERY_WORDS: frozenset[str] = frozenset({
    "action", "actions", "condition", "conditions", "expression", "expressions",
    "event", "events", "function", "functions", "property", "properties",
    "variable", "variables", "how", "what", "use", "create", "add", "make",
})


# ---------------------------------------------------------------------------
# 语义扩展词表 — 用于 QueryExpander 手工增补（与 schema 自动扩展合并）
# ---------------------------------------------------------------------------

SEMANTIC_EXPAND: dict[str, list[str]] = {
    # --- 基础操作 ---
    '查找': ['包含', '检测', '遍历', '存在', '检索', '条件', '表达式', '比较'],
    '搜索': ['包含', '检测', '遍历', '存在', '检索', '查询'],
    '排序': ['升序', '降序', '动作', '顺序', '比较'],
    '设置': ['修改', '动作', '属性', '值'],
    '获取': ['读取', '表达式', '返回', '值'],
    '条件': ['判断', '比较', '检测', '触发', '如果'],
    '动作': ['执行', '操作', '设置', '调用'],
    '表达式': ['返回', '计算', '获取', '值'],

    # --- 游戏对象生命周期 ---
    '创建': ['实例', '生成', '动作', '对象', '克隆', 'spawn', 'instantiate'],
    '生成': ['创建', '实例', '对象', '克隆', 'spawn', 'instantiate', 'clone'],
    '克隆': ['复制', '副本', '实例', '生成', 'duplicate', 'copy'],
    '删除': ['销毁', '移除', '动作', '实例', 'destroy', 'remove', 'delete'],
    '销毁': ['删除', '移除', '实例', '释放', 'destroy', 'remove', 'delete'],

    # --- 移动与物理 ---
    '移动': ['速度', '方向', '动作', '位置', '角度'],
    '旋转': ['角度', '动作', '方向'],
    '缩放': ['大小', '尺寸', '宽度', '高度', '动作'],
    '碰撞': ['重叠', '检测', '条件', '触发', '反弹', 'collision', 'overlap'],
    '物理': ['重力', '质量', '弹力', '摩擦力', '速度', '力', '刚体', 'physics', 'gravity', 'mass', 'bounce', 'friction'],
    '弹跳': ['碰撞', '反弹', '物理', 'bounce', 'collision'],
    '重力': ['下落', '物理', '质量', 'gravity', 'mass', 'fall'],

    # --- 场景与布局 ---
    '布局': ['场景', '切换', '加载', 'layout', 'scene', 'goto', 'switch'],
    '切换场景': ['布局', '加载', '跳转', '场景', 'layout', 'goto', 'scene', 'switch'],

    # --- 图层与视口 ---
    '图层': ['层', '顺序', '深度', 'layer', 'z-order', 'depth'],
    '视口': ['相机', '镜头', '视野', '滚动', 'viewport', 'camera', 'scroll'],

    # --- 可见性 ---
    '显示': ['可见', '透明度', '动作', '隐藏'],
    '隐藏': ['可见', '透明度', '动作', '显示'],

    # --- 用户输入 ---
    '鼠标': ['点击', '位置', '光标', '滚轮', 'mouse', 'click', 'cursor', 'wheel'],
    '键盘': ['按键', '热键', '按下', '释放', 'keyboard', 'key', 'hotkey'],
    '手柄': ['控制器', '摇杆', '扳机', 'gamepad', 'controller', 'joystick'],

    # --- 文件与数据 ---
    '文件': ['读取', '写入', '保存', '加载', '导出', '导入', 'file', 'read', 'write', 'load', 'save', 'export', 'import'],
    '存储': ['保存', '数据', '变量', '文件'],
    '加载': ['读取', '文件', '数据', '动作'],
    '本地存储': ['存档', '缓存', '保存', 'webstorage', 'localstorage', 'save', 'slot'],
    'json': ['数据', '结构', '解析', '序列化', 'parse', 'stringify', 'data'],
    '数组': ['数据结构', '列表', '索引', '元素'],

    # --- 网络 ---
    '网络': ['请求', 'ajax', 'fetch', 'http', '下载', '上传', 'network', 'request', 'download', 'upload'],
    '多人': ['联机', '同步', '房间', 'multiplayer', 'sync', 'room', 'peer'],

    # --- 时间与异步 ---
    '计时': ['时间', '延迟', '等待', '秒'],
    '计时器': ['定时', '间隔', '倒计时', 'timer', 'interval', 'countdown', 'settimeout'],
    '异步': ['等待', '延迟', '回调', 'promise', 'async', 'await', 'callback', 'wait', 'delay'],

    # --- 动画与渲染 ---
    '播放': ['动画', '音频', '声音', '动作'],
    '帧': ['动画帧', '图片', '索引', 'frame', 'animation frame', 'image', 'index'],
    '骨骼动画': ['蒙皮', 'spine', 'dragonbones', 'skeletal', 'mesh'],
    '绘制': ['画图', '矩形', '线条', '颜色', '填充', 'canvas', 'draw', 'rectangle', 'line', 'color', 'fill'],
    '颜色': ['rgb', 'rgba', '十六进制', '透明度', 'color', 'hex', 'alpha', 'opacity'],
    '粒子': ['特效', '系统', '发射器', 'particle', 'effect', 'emitter'],

    # --- 音频 ---
    '音量': ['静音', '大小', '平衡', 'volume', 'mute', 'gain', 'balance'],
    '音频通道': ['音轨', '分组', 'channel', 'track', 'group'],

    # --- UI 控件 ---
    '按钮': ['点击', '按下', '响应', 'button', 'click', 'press'],
    '文本输入': ['输入框', '键盘', '文本框', 'textbox', 'input', 'editbox'],
    '下拉框': ['选择', '选项', 'combobox', 'dropdown', 'select'],
    '滑块': ['滑动条', '数值', 'slider', 'value', 'drag'],

    # --- 文本与数值 ---
    '文本': ['字符串', '内容', '表达式', '属性'],
    '数字': ['值', '变量', '表达式', '参数', '整数', '浮点'],

    # --- 事件表核心 ---
    '事件': ['触发', '条件', '动作', '子事件', 'event', 'trigger', 'condition', 'action', 'sub-event'],
    '变量': ['全局', '实例', '局部', '数字', '字符串', '布尔', 'variable', 'global', 'instance', 'local', 'number', 'string', 'boolean'],
    '函数': ['调用', '返回', '参数', '自定义', 'function', 'call', 'return', 'parameter', 'custom'],

    # --- 性能与调试 ---
    '性能': ['帧率', '内存', '优化', 'performance', 'fps', 'memory', 'profiling'],
    '调试': ['输出', '日志', '断点', 'debug', 'console', 'log', 'breakpoint'],
}
