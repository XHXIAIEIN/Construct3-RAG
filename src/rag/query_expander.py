"""Query Expander: semantic token expansion + schema zh→en bridging.

Two main components:
  - SemanticExpander (multi-backend): BaseExpander hierarchy for Chinese term expansion
      dict     — Chinese thesaurus + bge-m3 similarity search (default, offline)
      api      — Free LLM API (DashScope / DeepSeek)
      local    — Local small HuggingFace model (Qwen3-0.5B)
      disabled — No expansion
  - SchemaZhEnIndex: inverted index over all schema JSON files (zh tokens → ACE nodes)
  - QueryExpander: merges LLM + manual + auto expansions, scores nodes by term overlap
"""
from __future__ import annotations

import json
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jieba

from src.config import (
    DATA_DIR,
    EXPANDER_BACKEND, EXPANDER_TIMEOUT_S, EXPANDER_TOP_K,
    EXPANDER_API_KEY, EXPANDER_API_PROVIDER, EXPANDER_API_MODEL,
    EXPANDER_LOCAL_MODEL, EXPANDER_DEVICE,
)

logger = logging.getLogger(__name__)

_EXPAND_PROMPT = (
    "你是一个语义联想助手。给定技术文档查询中的关键词，"
    "列出相关的中文动词和名词（每行一个，不超过{top_k}个，只输出词语）：\n\n"
    "关键词：{keywords}\n\n相关词：\n"
)

# Schema root directory
_SCHEMA_DIR = Path(DATA_DIR) / "schemas"

# Tokens that should NOT trigger auto_expand even when they match few schema nodes.
# These are common Chinese query words that appear in node *descriptions* incidentally,
# producing spurious co-occurrence expansions that pollute schema matching.
_SCHEMA_EXPAND_STOPWORDS: frozenset[str] = frozenset({
    # Question / method words
    "如何", "怎么", "怎样", "怎样的", "如果", "是否",
    # Action / process words that are too generic
    "实现", "定义", "包括", "包含", "完成", "执行", "操作", "进行",
    "方法", "方式", "步骤", "功能", "作用",
    # Auxiliary / modifier words
    "使用", "通过", "根据", "基于", "用于", "用来",
    "可以", "需要", "应该", "能够", "允许",
    "一个", "多个", "各种", "某个", "所有", "每个",
    # Generic action results
    "获取", "返回", "显示", "加载", "保存",
    # English abbreviations that map to specific niche plugins (not general UI)
    "UI",
    # C3 structural meta-terms (describe the editing environment, not ACE actions)
    # Expanding these always leads to system/flowchart structural nodes, not ACE
    "事件表", "事件组", "对象类型", "布局",
    # Domain concepts not present in C3 itself — expanding only produces misleading
    # matches to unrelated plugins (e.g. "埋点"→googleplay achievements).
    "埋点", "统计", "分析", "监控", "上报", "打点",
    # Conversational filler words that appear in informal queries
    "大佬", "知道", "里边", "那个", "这个",
})

# English word → Chinese zh_tokens bridge.
# Used to make English-only ACE nodes (no name_zh / description_zh) reachable
# from Chinese user queries. Keys are lowercase English words from name_en / id.
_EN_TO_ZH: dict[str, list[str]] = {
    # Media / ad
    "video":        ["视频", "广告"],
    "advert":       ["广告", "视频广告"],
    "advertise":    ["广告"],
    "ad":           ["广告"],
    "banner":       ["横幅广告", "广告"],
    "interstitial": ["插屏广告", "广告"],
    # Audio
    "audio":        ["音频", "音乐", "声音"],
    "sound":        ["声音", "音效"],
    "music":        ["音乐"],
    "microphone":   ["麦克风", "录音"],
    # Platform
    "browser":      ["浏览器"],
    "facebook":     ["Facebook", "社交"],
    "twitter":      ["Twitter", "社交"],
    "xbox":         ["Xbox"],
    "xboxlive":     ["Xbox Live", "Xbox"],
    "gamecenter":   ["Game Center", "游戏中心"],
    "win":          ["Windows"],
    "mobile":       ["移动", "手机"],
    "usermedia":    ["用户媒体", "摄像头", "麦克风"],
    # Network
    "multiplayer":  ["多人", "网络", "联机"],
    "ajax":         ["网络请求", "数据请求"],
    "websocket":    ["WebSocket", "网络"],
    # Storage / data
    "storage":      ["存储", "保存"],
    "localstorage": ["本地存储", "存储"],
    "file":         ["文件"],
    "json":         ["JSON", "数据"],
    "xml":          ["XML", "数据"],
    "csv":          ["CSV", "表格数据"],
    # State events
    "ready":        ["准备", "就绪", "可以"],
    "loaded":       ["加载", "完成", "就绪"],
    "complete":     ["完成"],
    "failed":       ["失败", "错误"],
    "cancelled":    ["取消"],
    "error":        ["错误", "失败"],
    "success":      ["成功", "完成"],
    # Actions
    "show":         ["显示", "展示"],
    "hide":         ["隐藏"],
    "play":         ["播放"],
    "pause":        ["暂停"],
    "stop":         ["停止"],
    "create":       ["创建"],
    "destroy":      ["销毁", "删除"],
    "set":          ["设置"],
    "get":          ["获取"],
    "load":         ["加载"],
    "save":         ["保存"],
    "send":         ["发送"],
    "receive":      ["接收"],
    "request":      ["请求"],
    "enable":       ["启用", "开启"],
    "disable":      ["禁用", "关闭"],
    # Game / 3D
    "timeline":     ["时间线", "动画"],
    "model":        ["模型", "3D"],
    "gamerecorder": ["游戏录制", "录制"],
    "instantgames": ["即时游戏"],
    "pubcenter":    ["广告"],
    # User
    "user":         ["用户"],
    "login":        ["登录"],
    "logout":       ["登出"],
    "score":        ["分数", "得分"],
    "leaderboard":  ["排行榜"],
    "achievement":  ["成就"],
    "personaliz":   ["个性化"],
}


def _en_word_to_zh(en_text: str) -> set[str]:
    """Derive Chinese zh tokens from English name/id for untranslated ACEs."""
    zh: set[str] = set()
    # Split on common separators
    words = en_text.lower().replace("-", " ").replace("_", " ").replace("/", " ").split()
    for w in words:
        # Strip "on", "is", "get", "set" prefixes from event/condition names
        # to get the core concept (e.g. "on-video-ready" → "video", "ready")
        for zh_list in [_EN_TO_ZH.get(w, [])]:
            zh.update(zh_list)
        # Partial prefix match (e.g. "personaliz" prefix matches "personaliz")
        for key, vals in _EN_TO_ZH.items():
            if len(key) >= 4 and w.startswith(key):
                zh.update(vals)
    return zh

# Node type weights
_WEIGHTS: dict[str, float] = {
    "plugin":   1.0,
    "behavior": 1.0,
    "effect":   0.9,
    "feature":  0.8,
    "editor":   0.4,
}

# Chinese tokens to skip when building zh vocab
_ZH_SKIP: frozenset[str] = frozenset({
    "的", "了", "在", "是", "有", "和", "就", "不", "都", "一",
    "上", "也", "到", "要", "去", "会", "着", "没", "好", "这",
    "他", "她", "它", "中", "把", "那", "被", "从", "对", "让",
    "给", "用", "与", "向", "于", "某", "其", "将", "该", "或",
    "以", "及", "并", "但", "而", "如", "当", "若", "为", "由",
    "可", "能", "应", "需", "至", "等", "种", "个", "件", "些",
})


def _parse_output(text: str, top_k: int = EXPANDER_TOP_K) -> set[str]:
    """Parse one-word-per-line LLM/API output, filter noise."""
    result: set[str] = set()
    for line in text.strip().splitlines():
        word = line.strip().strip("、，。,.1234567890. ")
        if len(word) >= 2 and word not in _ZH_SKIP:
            result.add(word)
        if len(result) >= top_k:
            break
    return result


def _run_with_timeout(fn, timeout: float) -> set[str]:
    """Run fn() in a thread; return empty set if it exceeds timeout."""
    result: list[set[str]] = []
    exc: list[Exception] = []

    def _target():
        try:
            result.append(fn())
        except Exception as e:
            exc.append(e)

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        return set()
    if exc:
        logger.warning(f"[Expander] Error: {exc[0]}")
        return set()
    return result[0] if result else set()


def _tokenize_zh(text: str) -> set[str]:
    """Jieba-tokenize Chinese text, return filtered token set."""
    tokens = set()
    for tok in jieba.lcut(text):
        tok = tok.strip()
        if len(tok) >= 2 and tok not in _ZH_SKIP:
            tokens.add(tok)
    return tokens


def _extract_en_tokens(data: dict[str, Any], *keys: str) -> set[str]:
    """Extract non-empty English tokens from given keys."""
    tokens: set[str] = set()
    for k in keys:
        val = data.get(k, "")
        if val and isinstance(val, str):
            for part in val.replace("-", " ").replace("/", " ").split():
                if len(part) >= 2:
                    tokens.add(part)
    return tokens


# =============================================================================
# SemanticExpander backends
# =============================================================================

class BaseExpander(ABC):
    _cache: dict[frozenset, set[str]]

    @abstractmethod
    def expand(self, tokens: list[str]) -> set[str]: ...

    @property
    @abstractmethod
    def available(self) -> bool: ...

    def _parse_output(self, text: str) -> set[str]:
        return _parse_output(text)

    def _cached(self, tokens: list[str], fn) -> set[str]:
        key = frozenset(tokens)
        if key in self._cache:
            return self._cache[key]
        result = fn()
        self._cache[key] = result
        return result


class DisabledExpander(BaseExpander):
    _cache: dict = {}

    @property
    def available(self) -> bool:
        return False

    def expand(self, tokens: list[str]) -> set[str]:
        return set()


class LocalLLMExpander(BaseExpander):
    """Local small HuggingFace model (e.g. Qwen3-0.5B)."""

    def __init__(self, model_path: str = EXPANDER_LOCAL_MODEL, device: str = EXPANDER_DEVICE) -> None:
        self._model_path = model_path
        self._device = device
        self._model = None
        self._tokenizer = None
        self._cache: dict[frozenset, set[str]] = {}
        if model_path:
            self._load()

    def _load(self) -> None:
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM
            import torch
            logger.info(f"[LocalLLM] Loading {self._model_path}...")
            self._tokenizer = AutoTokenizer.from_pretrained(self._model_path, trust_remote_code=True)
            self._model = AutoModelForCausalLM.from_pretrained(
                self._model_path, torch_dtype=torch.float32, trust_remote_code=True
            )
            if self._device != "cpu":
                self._model = self._model.to(self._device)
            self._model.eval()
            logger.info("[LocalLLM] Ready")
        except Exception as e:
            logger.warning(f"[LocalLLM] Load failed: {e}")

    @property
    def available(self) -> bool:
        return self._model is not None

    def expand(self, tokens: list[str]) -> set[str]:
        if not self.available:
            return set()
        return self._cached(tokens, lambda: _run_with_timeout(
            lambda: self._infer(tokens), EXPANDER_TIMEOUT_S
        ))

    def _infer(self, tokens: list[str]) -> set[str]:
        import torch
        prompt = _EXPAND_PROMPT.format(keywords=" / ".join(tokens), top_k=EXPANDER_TOP_K)
        inputs = self._tokenizer(prompt, return_tensors="pt")
        if self._device != "cpu":
            inputs = {k: v.to(self._device) for k, v in inputs.items()}
        with torch.no_grad():
            out = self._model.generate(
                **inputs, max_new_tokens=EXPANDER_TOP_K * 6,
                do_sample=False, pad_token_id=self._tokenizer.eos_token_id,
            )
        new_tokens = out[0][inputs["input_ids"].shape[1]:]
        return self._parse_output(self._tokenizer.decode(new_tokens, skip_special_tokens=True))


# Alias used in QueryExpander and tests
SmallLLMExpander = LocalLLMExpander


class APIExpander(BaseExpander):
    """Free LLM API backend (DashScope / DeepSeek)."""

    def __init__(
        self,
        api_key: str = EXPANDER_API_KEY,
        provider: str = EXPANDER_API_PROVIDER,
        model: str = EXPANDER_API_MODEL,
    ) -> None:
        self._api_key = api_key
        self._provider = provider
        self._model = model
        self._cache: dict[frozenset, set[str]] = {}

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def expand(self, tokens: list[str]) -> set[str]:
        if not self.available:
            return set()
        return self._cached(tokens, lambda: _run_with_timeout(
            lambda: self._parse_output(self._call_api(tokens)), EXPANDER_TIMEOUT_S
        ))

    def _call_api(self, tokens: list[str]) -> str:
        prompt = _EXPAND_PROMPT.format(keywords=" / ".join(tokens), top_k=EXPANDER_TOP_K)
        if self._provider == "dashscope":
            return self._call_dashscope(prompt)
        if self._provider == "deepseek":
            return self._call_openai_compat(prompt, "https://api.deepseek.com/v1", "deepseek-chat")
        raise ValueError(f"Unknown provider: {self._provider}")

    def _call_dashscope(self, prompt: str) -> str:
        import urllib.request
        body = json.dumps({
            "model": self._model,
            "input": {"messages": [{"role": "user", "content": prompt}]},
            "parameters": {"max_tokens": EXPANDER_TOP_K * 6, "temperature": 0},
        }).encode()
        req = urllib.request.Request(
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
            data=body,
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=EXPANDER_TIMEOUT_S).read())
        return resp["output"]["text"]

    def _call_openai_compat(self, prompt: str, base_url: str, model: str) -> str:
        import urllib.request
        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": EXPANDER_TOP_K * 6, "temperature": 0,
        }).encode()
        req = urllib.request.Request(
            f"{base_url}/chat/completions", data=body,
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=EXPANDER_TIMEOUT_S).read())
        return resp["choices"][0]["message"]["content"]


class DictExpander(BaseExpander):
    """Chinese thesaurus + bge-m3 embedding similarity search.

    The dictionary vector file is built by scripts/download_expander_dict.py.
    If the file does not exist, DictExpander is unavailable (graceful fallback).
    """

    _DEFAULT_PATH = Path(DATA_DIR) / "expander" / "dict_vectors.npz"

    def __init__(self, dict_path: Path | None = None) -> None:
        self._path = dict_path or self._DEFAULT_PATH
        self._words: list[str] = []
        self._vectors = None        # np.ndarray shape (N, D)
        self._cache: dict[frozenset, set[str]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            logger.info(f"[DictExpander] Dict not found: {self._path} — run download_expander_dict.py")
            return
        try:
            import numpy as np
            data = np.load(self._path, allow_pickle=True)
            self._words = [str(w) for w in data["words"]]   # ensure plain str
            vecs = data["vectors"].astype(np.float32)
            # Normalize rows so cosine sim = dot product
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self._vectors = vecs / norms
            logger.info(f"[DictExpander] Loaded {len(self._words)} words")
        except Exception as e:
            logger.warning(f"[DictExpander] Load failed: {e}")

    @property
    def available(self) -> bool:
        return self._vectors is not None and len(self._words) > 0

    def expand(self, tokens: list[str]) -> set[str]:
        if not self.available:
            return set()
        return self._cached(tokens, lambda: self._search(tokens))

    def _search(self, tokens: list[str]) -> set[str]:
        """Embed tokens with bge-m3 and find Top-K nearest words."""
        import numpy as np
        try:
            embedder = _get_shared_embedder()
        except Exception:
            return set()

        result: set[str] = set()
        for tok in tokens:
            try:
                vec = np.array(embedder.encode_single(tok), dtype=np.float32)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                sims = self._vectors @ vec
                top_idx = np.argsort(sims)[::-1][:EXPANDER_TOP_K]
                for i in top_idx:
                    word = self._words[i]
                    if word != tok and len(word) >= 2 and word not in _ZH_SKIP:
                        result.add(word)
            except Exception as e:
                logger.debug(f"[DictExpander] embed error for '{tok}': {e}")
        return result


_shared_embedder = None


def _get_shared_embedder():
    """Return module-level cached embedder to avoid repeated model loads."""
    global _shared_embedder
    if _shared_embedder is None:
        from src.ingest.indexer import EmbeddingModel
        from src.config import EMBEDDING_MODEL
        _shared_embedder = EmbeddingModel(model_name=EMBEDDING_MODEL)
    return _shared_embedder


def create_expander() -> BaseExpander:
    """Instantiate the expander backend selected by EXPANDER_BACKEND."""
    backend = EXPANDER_BACKEND
    if backend == "api":
        return APIExpander()
    if backend == "local":
        return LocalLLMExpander()
    if backend == "dict":
        return DictExpander()
    return DisabledExpander()


# =============================================================================
# SchemaZhEnIndex — inverted index from schema files
# =============================================================================

@dataclass
class NodeData:
    node_id: str
    schema_type: str          # plugin/behavior/effect/feature/editor
    plugin_id: str            # parent plugin id (same as node_id for plugin nodes)
    ace_type: str | None      # conditions/actions/expressions/properties or None
    weight: float
    zh_tokens: frozenset[str]
    en_tokens: frozenset[str]


@dataclass
class SchemaMatch:
    node_id: str
    plugin_id: str
    schema_type: str
    ace_type: str | None
    score: float
    en_tokens: frozenset[str]


class SchemaZhEnIndex:
    """Inverted index from Chinese schema tokens to ACE nodes.

    Supports five schema types with different weights:
      plugins/behaviors (1.0) > effects (0.9) > features (0.8) > editor (0.4)
    """

    def __init__(self) -> None:
        self.token_to_nodes: dict[str, set[str]] = {}
        self.node_data: dict[str, NodeData] = {}
        self._build()

    def _build(self) -> None:
        plugins   = _load_json_dir(_SCHEMA_DIR / "plugins")
        behaviors = _load_json_dir(_SCHEMA_DIR / "behaviors")
        effects   = _load_json_dir(_SCHEMA_DIR / "effects")
        features  = _load_json_dir(_SCHEMA_DIR / "features")
        editor    = _load_editor(_SCHEMA_DIR / "editor" / "index.json")
        self._build_from_fixtures(plugins, behaviors, effects, features, editor)
        logger.info(
            f"[SchemaZhEnIndex] Built: {len(self.node_data)} nodes, "
            f"{len(self.token_to_nodes)} zh tokens"
        )

    def _build_from_fixtures(
        self,
        plugins: list[dict],
        behaviors: list[dict],
        effects: list[dict],
        features: list[dict],
        editor: dict,
    ) -> None:
        """Build index from pre-loaded data (also used in tests)."""
        self.token_to_nodes = {}
        self.node_data = {}
        for schema in plugins:
            self._index_plugin_or_behavior(schema, "plugin")
        for schema in behaviors:
            self._index_plugin_or_behavior(schema, "behavior")
        for schema in effects:
            self._index_effect(schema)
        for schema in features:
            self._index_feature(schema)
        self._index_editor(editor)

    def _index_plugin_or_behavior(self, d: dict, schema_type: str) -> None:
        plugin_id = d.get("id", "")
        weight = _WEIGHTS[schema_type]

        zh = _tokenize_zh(
            " ".join(filter(None, [d.get("name_zh"), d.get("description_zh")]))
        )
        en = _extract_en_tokens(d, "name_en", "description_en")
        for part in d.get("path", "").replace("/", " ").split():
            if len(part) >= 2:
                en.add(part)
        en.update(d.get("categories", []))

        # Bridge: derive zh tokens from English when no Chinese text available
        if not zh:
            zh.update(_en_word_to_zh(f"{plugin_id} {d.get('name_en', '')}"))

        self._add_node(NodeData(
            node_id=plugin_id, schema_type=schema_type, plugin_id=plugin_id,
            ace_type=None, weight=weight,
            zh_tokens=frozenset(zh), en_tokens=frozenset(en),
        ))

        for ace_type in ("conditions", "actions", "expressions", "properties"):
            for ace in d.get(ace_type, []):
                self._index_ace(ace, plugin_id, ace_type, schema_type, weight)

    def _index_ace(
        self, ace: dict, plugin_id: str, ace_type: str,
        schema_type: str, weight: float,
    ) -> None:
        ace_id = ace.get("id", "")
        node_id = f"{plugin_id}/{ace_id}"

        zh = _tokenize_zh(
            " ".join(filter(None, [ace.get("name_zh"), ace.get("description_zh")]))
        )
        en = _extract_en_tokens(ace, "name_en", "description_en", "scriptName")

        for param in ace.get("params", []):
            zh.update(_tokenize_zh(param.get("name_zh", "")))
            for key in ("name_en", "id"):
                en_tok = param.get(key, "").strip().replace("-", " ")
                for part in en_tok.split():
                    if len(part) >= 2:
                        en.add(part)
            for item_val in param.get("items_i18n", {}).values():
                if isinstance(item_val, dict):
                    zh.update(_tokenize_zh(item_val.get("zh", "")))
                    en_tok = item_val.get("en", "").strip()
                    if en_tok and len(en_tok) >= 2:
                        en.add(en_tok)

        # Bridge: derive zh tokens from English when no Chinese text available
        if not zh:
            zh.update(_en_word_to_zh(
                f"{plugin_id} {ace_id} {ace.get('name_en', '')} {ace.get('description_en', '')}"
            ))

        self._add_node(NodeData(
            node_id=node_id, schema_type=schema_type, plugin_id=plugin_id,
            ace_type=ace_type, weight=weight,
            zh_tokens=frozenset(zh), en_tokens=frozenset(en),
        ))

    def _index_effect(self, d: dict) -> None:
        effect_id = d.get("id", "")
        zh = _tokenize_zh(
            " ".join(filter(None, [d.get("name_zh"), d.get("description_zh")]))
        )
        en = _extract_en_tokens(d, "name_en", "description_en")
        cat = d.get("category", "")
        if cat:
            en.add(cat)
        for param in d.get("parameters", []):
            zh.update(_tokenize_zh(param.get("name_zh", "")))
            en_tok = param.get("name_en", "").strip()
            if en_tok and len(en_tok) >= 2:
                en.add(en_tok)
        self._add_node(NodeData(
            node_id=effect_id, schema_type="effect", plugin_id=effect_id,
            ace_type=None, weight=_WEIGHTS["effect"],
            zh_tokens=frozenset(zh), en_tokens=frozenset(en),
        ))

    def _index_feature(self, d: dict) -> None:
        feat_id = d.get("id", "")
        zh = _tokenize_zh(
            " ".join(filter(None, [d.get("name_zh"), d.get("description_zh")]))
        )
        en = _extract_en_tokens(d, "name_en", "description_en")
        en.update(str(t) for t in d.get("tags", []) if isinstance(t, str))
        for ex in d.get("examples", []):
            zh.update(_tokenize_zh(ex.get("description_zh", "")))
        for ace_ref in d.get("relatedACE", []):
            if isinstance(ace_ref, str) and len(ace_ref) >= 2:
                en.add(ace_ref)
        self._add_node(NodeData(
            node_id=feat_id, schema_type="feature", plugin_id=feat_id,
            ace_type=None, weight=_WEIGHTS["feature"],
            zh_tokens=frozenset(zh), en_tokens=frozenset(en),
        ))

    def _index_editor(self, d: dict) -> None:
        weight = _WEIGHTS["editor"]
        for group_key in ("bars", "dialogs", "views"):
            for elem_id, elem in d.get(group_key, {}).items():
                if not isinstance(elem, dict):
                    continue
                node_id = f"{group_key[:-1]}/{elem_id}"  # "bars"→"bar"
                name_zh = elem.get("name_zh", "")
                name_en = elem.get("name_en", "")
                zh = _tokenize_zh(name_zh)
                en: set[str] = set()
                for part in name_en.split():
                    if len(part) >= 2:
                        en.add(part)
                if not zh and not en:
                    continue
                self._add_node(NodeData(
                    node_id=node_id, schema_type="editor", plugin_id=elem_id,
                    ace_type=None, weight=weight,
                    zh_tokens=frozenset(zh), en_tokens=frozenset(en),
                ))

    def _add_node(self, node: NodeData) -> None:
        self.node_data[node.node_id] = node
        for tok in node.zh_tokens:
            self.token_to_nodes.setdefault(tok, set()).add(node.node_id)

    def search(self, term_set: set[str]) -> list[SchemaMatch]:
        """Score all nodes by zh token overlap with term_set, return sorted."""
        scores: dict[str, float] = {}
        for tok in term_set:
            for node_id in self.token_to_nodes.get(tok, set()):
                node = self.node_data[node_id]
                if not node.zh_tokens:
                    continue
                overlap = len(term_set & node.zh_tokens)
                # Skip small-token nodes with only partial overlap — prevents coincidental
                # 1.0 scores (e.g. "始终" in term_set partially matching "始终置顶").
                # Exception: perfect matches (all node tokens hit) are always kept.
                if overlap < 2 and len(node.zh_tokens) < 3 and overlap < len(node.zh_tokens):
                    continue
                raw = overlap / len(node.zh_tokens)
                scores[node_id] = max(scores.get(node_id, 0.0), raw * node.weight)

        return sorted(
            [
                SchemaMatch(
                    node_id=nid,
                    plugin_id=self.node_data[nid].plugin_id,
                    schema_type=self.node_data[nid].schema_type,
                    ace_type=self.node_data[nid].ace_type,
                    score=score,
                    en_tokens=self.node_data[nid].en_tokens,
                )
                for nid, score in scores.items()
            ],
            key=lambda m: -m.score,
        )

    def auto_expand(self, token: str) -> set[str]:
        """Return zh tokens co-occurring with this token across matched nodes."""
        result: set[str] = set()
        for node_id in self.token_to_nodes.get(token, set()):
            result.update(self.node_data[node_id].zh_tokens)
        result.discard(token)
        return result


def _load_json_dir(path: Path) -> list[dict]:
    if not path.exists():
        return []
    result = []
    for f in sorted(path.glob("*.json")):
        try:
            result.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:
            logger.warning(f"[SchemaZhEnIndex] Skip {f.name}: {e}")
    return result


def _load_editor(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"[SchemaZhEnIndex] Skip editor/index.json: {e}")
        return {}


# =============================================================================
# QueryExpander — three-layer merge
# =============================================================================

class QueryExpander:
    """Three-layer semantic expander + schema zh→en bridge.

    Expansion sources (all merged via union):
      1. SmallLLMExpander  — neural semantic association (primary)
      2. SEMANTIC_EXPAND   — manual fallback dict (fast, always available)
      3. SchemaZhEnIndex   — schema co-occurrence (C3-specific vocabulary)
    """

    def __init__(
        self,
        schema_index: SchemaZhEnIndex | None = None,
        manual_expand: dict[str, list[str]] | None = None,
        llm_expander: BaseExpander | None = None,
    ) -> None:
        self._index = schema_index if schema_index is not None else SchemaZhEnIndex()
        if manual_expand is not None:
            self._manual = manual_expand
        else:
            from src.locale.keywords import SEMANTIC_EXPAND
            self._manual = SEMANTIC_EXPAND
        self._llm = llm_expander if llm_expander is not None else create_expander()

    def expand(self, tokens: list[str]) -> dict[str, set[str]]:
        """For each token, return union of LLM + manual + auto expansions."""
        llm_all = self._llm.expand(tokens)

        result: dict[str, set[str]] = {}
        for tok in tokens:
            manual = set(self._manual.get(tok, []))
            auto   = self._index.auto_expand(tok)
            result[tok] = llm_all | manual | auto
        return result

    def get_term_set(self, tokens: list[str]) -> set[str]:
        """Return flattened union: original tokens + all expansions."""
        term_set = set(tokens)
        for expansions in self.expand(tokens).values():
            term_set.update(expansions)
        return term_set

    def search(self, term_set: set[str]) -> list[SchemaMatch]:
        """Score schema nodes by term_set overlap. Returns sorted matches."""
        return self._index.search(term_set)

    def schema_term_set(self, segments: list[str], max_nodes: int = 10) -> set[str]:
        """Build term set for schema matching using selective auto_expand.

        Only tokens that (a) are not generic query stop-words, and (b) match
        <= max_nodes schema nodes, get auto-expanded.  Generic tokens like
        "系统" (36), "碰撞" (31), "变量" (16), or query function words like
        "如何"/"实现" are kept as-is to prevent co-occurrence cascade that
        matches unrelated plugins.
        """
        result = set(segments)
        for tok in segments:
            if tok in _SCHEMA_EXPAND_STOPWORDS:
                continue
            if len(self._index.token_to_nodes.get(tok, set())) <= max_nodes:
                result.update(self._index.auto_expand(tok))
        return result
