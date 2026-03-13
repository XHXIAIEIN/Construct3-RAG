"""
RAG Chain for Construct 3 Assistant
Combines retrieval with LLM generation
With anti-hallucination features:
- Increased retrieval (top_k=5 per collection)
- Cross-collection reranking
- Self-reflection verification
- Strict prompting with forced citations
"""
import json
import re
import time
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

import jieba

from src.config import (
    QDRANT_HOST, QDRANT_PORT,
    LLM_MODEL, LLM_BASE_URL, LLM_API_KEY, LLM_PROVIDER,
    EMBEDDING_MODEL,
)
from .retriever import HybridRetriever, SearchResult, weighted_rrf
from src.locale.keywords import (
    ACE_INTENT_KEYWORDS, ZH_STOP_WORDS,
    COMPLEXITY_INDICATORS, CODE_GENERATION_KEYWORDS,
)
from src.locale import (
    ACE_SECTION_LABELS,
    CONTEXT_HEADER, CONTEXT_HEADER_STRICT, SOURCE_LABEL,
    REFLECTION_VERDICT_KEY, REFLECTION_UNRELIABLE, REFLECTION_RELIABLE,
)
from ._trace import _trace, _trace_local
from .query_expander import QueryExpander, SchemaMatch
from .prompts import (
    QA_PROMPT, EVENT_GENERATION_PROMPT, SYSTEM_MESSAGE,
    LOW_RELEVANCE_PROMPT, NO_RESULTS_RESPONSE, QUERY_REWRITE_PROMPT,
    STRICT_QA_PROMPT, SELF_REFLECTION_PROMPT,
    QUERY_DECOMPOSITION_PROMPT, LLM_UNAVAILABLE_RESPONSE,
    QDRANT_UNAVAILABLE_RESPONSE, LOW_CONFIDENCE_WARNING,
    JS_HINT_FOOTER, JS_INCLUDE_INSTRUCTION,
    CLIPBOARD_CONTEXT_HEADER, CLIPBOARD_DEFAULT_QUERY,
    SEMANTIC_DECOMPOSE_PROMPT,
)
from .semantic_chain import (
    SemanticChain, CollectionRouter, RawLLMBackend, InstructorBackend,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# ── Context structuring constants ──────────────────────────────────────────────
# Source collections grouped by semantic role
_ACE_SOURCES     = frozenset({"c3_ace", "c3_effects"})
_DOC_SOURCES     = frozenset({"c3_guide", "c3_interface", "c3_project",
                               "c3_plugins", "c3_behaviors", "c3_scripting"})
_TERM_SOURCES    = frozenset({"c3_terms"})
_EXAMPLE_SOURCES = frozenset({"c3_examples"})

# Ordered groups: (source_set, section_header, description_line)
_CONTEXT_GROUPS: list[tuple[frozenset, str, str]] = [
    (_ACE_SOURCES,     "编辑器 ACE 参考",
     "以下是 Construct 3 编辑器中实际可用的动作/条件/表达式定义（名称、参数、简述）："),
    (_DOC_SOURCES,     "官方文档说明",
     "以下是 Construct 3 Manual 对相关功能的详细解释与用法："),
    (_TERM_SOURCES,    "术语对照", ""),
    (_EXAMPLE_SOURCES, "示例项目", ""),
]

_CONTEXT_CHAR_BUDGET = 8000   # ~3000–4000 tokens for mixed ZH/EN
_DEDUP_THRESHOLD     = 0.70   # Jaccard word-overlap above this → duplicate

_jieba_c3_loaded = False


def _load_jieba_c3_dict():
    """Load C3-specific terms into jieba for domain-aware tokenization."""
    global _jieba_c3_loaded
    if _jieba_c3_loaded:
        return
    _jieba_c3_loaded = True

    from src.config import SCHEMA_DIR, SOURCE_DIR, TRANSLATION_CSV
    terms: set[str] = set()

    # Schema JSONs: plugin/behavior names + ACE names
    for subdir in ("plugins", "behaviors"):
        schema_path = SCHEMA_DIR / subdir
        if not schema_path.is_dir():
            continue
        for fp in schema_path.glob("*.json"):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            name = data.get("name_zh", "")
            if len(name) >= 2:
                terms.add(name)
            for ace_type in ("actions", "conditions", "expressions", "properties"):
                for ace in data.get(ace_type, []):
                    n = ace.get("name_zh", "")
                    if len(n) >= 2:
                        terms.add(n)

    # Translation CSV: zh column
    csv_path = SOURCE_DIR / TRANSLATION_CSV
    if csv_path.is_file():
        import csv as csv_mod
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv_mod.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                zh = row[1].strip() if len(row) > 1 else ""
                if len(zh) >= 2 and re.search(r'[\u4e00-\u9fff]', zh):
                    terms.add(zh)

    for term in terms:
        jieba.add_word(term)
    logger.info(f"[jieba] Loaded {len(terms)} C3 terms")


@dataclass
class RAGResponse:
    """Response from RAG chain"""
    answer: str
    sources: List[Dict[str, Any]]
    query_type: str
    confidence: str = "unknown"  # high / medium / low
    verification_notes: str = ""
    trace: list = field(default_factory=list)  # processing path events


class LLMClient:
    """
    Client for LLM inference. Supports three providers:

    - "ollama":       local Ollama service  (default)
    - "openai":       OpenAI-compatible API (Kimi, DeepSeek, OpenAI, ...)
    - "huggingface":  local HuggingFace transformers model

    Examples:
        >>> LLMClient(provider="ollama",  model="qwen2.5:7b")
        >>> LLMClient(provider="openai",  model="moonshot-v1-128k",
        ...           base_url="https://api.moonshot.cn/v1", api_key="sk-...")
        >>> LLMClient(provider="huggingface", model="Qwen/Qwen2.5-7B-Instruct")
    """

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        base_url: str = "http://localhost:11434",
        api_key: str = "",
        provider: str = "ollama"
    ):
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.provider = provider
        self._client = None       # Ollama / OpenAI client
        self._hf_model = None     # HuggingFace model
        self._hf_tokenizer = None
        self._available = None

    # ── API-based clients (Ollama / OpenAI) ──────────────────────────────────

    @property
    def client(self):
        """Lazy-load API client. Returns None for huggingface provider."""
        if self.provider == "huggingface":
            return None
        if self._client is None:
            if self.provider == "ollama":
                try:
                    import ollama
                    self._client = ollama.Client(host=self.base_url)
                except ImportError:
                    print("Warning: ollama not installed. Run: pip install ollama")
            else:  # openai
                try:
                    from openai import OpenAI
                    self._client = OpenAI(base_url=self.base_url, api_key=self.api_key)
                except ImportError:
                    print("Warning: openai not installed. Run: pip install openai")
        return self._client

    def _chat_ollama(self, messages: List[Dict[str, str]]) -> str:
        response = self.client.chat(model=self.model, messages=messages)
        return response["message"]["content"]

    def _chat_openai(self, messages: List[Dict[str, str]]) -> str:
        response = self.client.chat.completions.create(
            model=self.model, messages=messages
        )
        return response.choices[0].message.content

    # ── HuggingFace local inference ───────────────────────────────────────────

    def _load_hf(self):
        """Lazy-load HuggingFace model and tokenizer."""
        if self._hf_model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        logger.info(f"[HF] Loading model: {self.model} ...")
        self._hf_tokenizer = AutoTokenizer.from_pretrained(self.model)

        model_cls = self._resolve_model_class(AutoModelForCausalLM)
        load_kwargs = dict(low_cpu_mem_usage=True)
        if torch.cuda.is_available():
            logger.info("[HF] GPU detected, loading to CUDA ...")
            load_kwargs["dtype"] = torch.bfloat16
            self._hf_model = model_cls.from_pretrained(
                self.model, **load_kwargs
            )
            self._strip_vision_modules(self._hf_model)
            self._hf_model = self._hf_model.to("cuda")
            torch.cuda.empty_cache()
        else:
            load_kwargs["dtype"] = "auto"
            self._hf_model = model_cls.from_pretrained(
                self.model, **load_kwargs
            )

        device = next(self._hf_model.parameters()).device
        logger.info(f"[HF] Model loaded, device: {device}")

    def _strip_vision_modules(self, model):
        """Remove vision encoder and multimodal modules to save VRAM."""
        import gc
        removed = []
        for attr in ("visual", "mtp"):
            if hasattr(model, attr):
                delattr(model, attr)
                removed.append(attr)
            elif hasattr(model, "model") and hasattr(model.model, attr):
                delattr(model.model, attr)
                removed.append(f"model.{attr}")
        if removed:
            gc.collect()
            logger.info(f"[HF] Stripped vision modules: {removed}")

    def _resolve_model_class(self, default_cls):
        """Pick the right model class based on config.json architectures."""
        import json
        from pathlib import Path

        config_path = Path(self.model) / "config.json"
        if not config_path.exists():
            return default_cls

        with open(config_path) as f:
            arch_list = json.load(f).get("architectures", [])

        if not arch_list:
            return default_cls

        arch_name = arch_list[0]
        # VLM models (e.g. Qwen3_5ForConditionalGeneration) need their
        # specific class instead of AutoModelForCausalLM.
        if arch_name.endswith("ForConditionalGeneration"):
            import transformers
            cls = getattr(transformers, arch_name, None)
            if cls is not None:
                logger.info(f"[HF] Using {arch_name} (VLM architecture)")
                return cls

        return default_cls

    @property
    def _is_qwen3(self) -> bool:
        return "qwen3" in self.model.lower()

    def _apply_chat_template(self, messages: List[Dict[str, str]]) -> str:
        """Apply chat template, disabling Qwen3 thinking mode for RAG."""
        kwargs = {"tokenize": False, "add_generation_prompt": True}
        if self._is_qwen3:
            kwargs["enable_thinking"] = False  # Non-thinking mode: faster for doc QA
        return self._hf_tokenizer.apply_chat_template(messages, **kwargs)

    def _generate_kwargs(self) -> dict:
        """Sampling parameters per model family."""
        if self._is_qwen3:
            # Qwen3 non-thinking mode recommended params
            return {"temperature": 0.7, "top_p": 0.8, "top_k": 20}
        return {"temperature": 0.7, "top_p": 0.9}

    def _chat_hf(self, messages: List[Dict[str, str]]) -> str:
        import torch
        self._load_hf()
        tok = self._hf_tokenizer
        text = self._apply_chat_template(messages)
        inputs = tok([text], return_tensors="pt").to(self._hf_model.device)
        with torch.no_grad():
            output = self._hf_model.generate(
                **inputs,
                max_new_tokens=2048,
                do_sample=True,
                pad_token_id=tok.eos_token_id,
                **self._generate_kwargs()
            )
        generated = output[0][inputs.input_ids.shape[-1]:]
        return tok.decode(generated, skip_special_tokens=True)

    def _stream_hf(self, messages: List[Dict[str, str]]):
        import torch
        from transformers import TextIteratorStreamer
        from threading import Thread

        self._load_hf()
        tok = self._hf_tokenizer
        text = self._apply_chat_template(messages)
        inputs = tok([text], return_tensors="pt").to(self._hf_model.device)
        streamer = TextIteratorStreamer(tok, skip_prompt=True, skip_special_tokens=True)

        def _run():
            with torch.no_grad():
                self._hf_model.generate(
                    **inputs,
                    max_new_tokens=2048,
                    do_sample=True,
                    pad_token_id=tok.eos_token_id,
                    streamer=streamer,
                    **self._generate_kwargs()
                )

        Thread(target=_run, daemon=True).start()
        for token in streamer:
            yield token

    # ── Health check ──────────────────────────────────────────────────────────

    def check_health(self) -> tuple[bool, str]:
        """Check if LLM service / model is available."""
        if self.provider == "huggingface":
            try:
                from transformers import AutoConfig
                AutoConfig.from_pretrained(self.model, local_files_only=True)
                self._available = True
                return True, f"HuggingFace model cached: {self.model}"
            except Exception as e:
                self._available = False
                return False, f"Model not cached locally: {e}"

        if self.client is None:
            self._available = False
            return False, f"{self.provider} package not installed"
        try:
            if self.provider == "ollama":
                self.client.list()
            else:
                self.client.models.list()
            self._available = True
            return True, "LLM service is healthy"
        except Exception as e:
            self._available = False
            return False, f"LLM connection failed: {str(e)}"

    @property
    def is_available(self) -> bool:
        if self._available is None:
            self.check_health()
        return self._available or False

    # ── Public generation methods ─────────────────────────────────────────────

    def generate(self, prompt: str, system: str = "") -> str:
        """Single-turn generation."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            return self.chat(messages)
        except Exception as e:
            return f"LLM error: {str(e)}"

    def generate_stream(self, prompt: str, system: str = ""):
        """Single-turn streaming generation."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            if self.provider == "huggingface":
                yield from self._stream_hf(messages)
            elif self.provider == "ollama":
                stream = self.client.chat(model=self.model, messages=messages, stream=True)
                for chunk in stream:
                    if "message" in chunk and "content" in chunk["message"]:
                        yield chunk["message"]["content"]
            else:
                stream = self.client.chat.completions.create(
                    model=self.model, messages=messages, stream=True
                )
                for chunk in stream:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
        except Exception as e:
            yield f"LLM error: {str(e)}"

    def chat(self, messages: List[Dict[str, str]]) -> str:
        """Multi-turn chat."""
        try:
            if self.provider == "huggingface":
                return self._chat_hf(messages)
            elif self.provider == "ollama":
                return self._chat_ollama(messages)
            else:
                return self._chat_openai(messages)
        except Exception as e:
            return f"LLM error: {str(e)}"


class RAGChain:
    """
    RAG Chain for Construct 3 Q&A
    With anti-hallucination features:
    1. Increased retrieval (top_k=5 per collection)
    2. Cross-collection reranking
    3. Self-reflection verification
    4. Strict prompting
    """

    # Retrieval threshold configuration
    MIN_RESULTS_THRESHOLD = 3
    HIGH_SCORE_THRESHOLD = 0.7
    STRICT_MODE = True

    def __init__(
        self,
        qdrant_host: str = QDRANT_HOST,
        qdrant_port: int = QDRANT_PORT,
        llm_model: str = LLM_MODEL,
        llm_base_url: str = LLM_BASE_URL,
        llm_api_key: str = LLM_API_KEY,
        llm_provider: str = LLM_PROVIDER,
        enable_query_rewrite: bool = True
    ):
        self.retriever = HybridRetriever(qdrant_host, qdrant_port, embedding_model_name=EMBEDDING_MODEL)
        self.llm = LLMClient(
            model=llm_model,
            base_url=llm_base_url,
            api_key=llm_api_key,
            provider=llm_provider
        )
        self.enable_query_rewrite = enable_query_rewrite
        self._query_expander: QueryExpander | None = None  # lazy init

        # SemanticChain: zero-dictionary LLM-driven query decomposition
        import os as _os
        _sc_enabled = _os.getenv("SEMANTIC_CHAIN_ENABLED", "true").lower() != "false"
        if _sc_enabled:
            _instructor_b = InstructorBackend(self.llm, SEMANTIC_DECOMPOSE_PROMPT)
            _active_backend = _instructor_b if _instructor_b.available else RawLLMBackend(self.llm, SEMANTIC_DECOMPOSE_PROMPT)
            _router = CollectionRouter(self.retriever.embedder)
            self.semantic_chain: SemanticChain | None = SemanticChain(
                backend=_active_backend,
                router=_router,
                retriever=self.retriever,
            )
        else:
            self.semantic_chain = None

    @property
    def query_expander(self) -> QueryExpander:
        if self._query_expander is None:
            self._query_expander = QueryExpander()
            # Share the retriever's already-loaded embedder to avoid
            # loading a second bge-m3 instance for DictExpander.
            import src.rag.query_expander as _qe_mod
            _qe_mod._shared_embedder = self.retriever.embedder
        return self._query_expander

    @staticmethod
    def _append_js_note(prompt: str, include_js: bool) -> str:
        if include_js:
            return prompt + JS_INCLUDE_INSTRUCTION
        return prompt + JS_HINT_FOOTER

    def _rewrite_query(self, query: str) -> List[str]:
        """Rewrite query using LLM to improve retrieval."""
        prompt = QUERY_REWRITE_PROMPT.format(original_query=query)
        response = self.llm.generate(prompt)
        rewritten = [q.strip() for q in response.strip().split('\n') if q.strip()]
        return rewritten[:3]

    def _decompose_query(self, query: str) -> List[str]:
        """
        Decompose a complex multi-step query into sub-queries.

        This improves retrieval accuracy for complex workflows by breaking
        them into focused, independent searches.

        Args:
            query: Complex query to decompose

        Returns:
            List of 2-4 sub-queries

        Example:
            >>> chain = RAGChain()
            >>> subs = chain._decompose_query(
            ...     "如何实现带二段跳和墙跳的平台游戏角色？"
            ... )
            >>> # Returns: ["Platform 行为设置", "二段跳实现", "墙跳检测逻辑"]
        """
        prompt = QUERY_DECOMPOSITION_PROMPT.format(original_query=query)
        response = self.llm.generate(prompt)
        sub_queries = [q.strip() for q in response.strip().split('\n') if q.strip()]
        return sub_queries[:4]  # max 4 sub-queries

    def _is_complex_query(self, query: str) -> bool:
        """
        Detect if a query is complex and would benefit from decomposition.

        Complex queries typically involve:
        - Multiple objects/behaviors
        - Multi-step workflows
        - Combined concepts (setup + runtime)

        Args:
            query: Query to analyze

        Returns:
            True if query appears complex
        """
        query_lower = query.lower()

        # Check for complexity indicators
        indicator_count = sum(1 for ind in COMPLEXITY_INDICATORS if ind in query_lower)

        # Use jieba word count for Chinese (space-split badly underestimates density);
        # threshold 12 ≈ equivalent density to English 20 words.
        if self._is_chinese(query):
            _load_jieba_c3_dict()
            word_count = len([w for w in jieba.lcut(query) if len(w.strip()) >= 2])
            return indicator_count >= 2 or word_count > 12
        else:
            word_count = len(query.split())
            return indicator_count >= 2 or word_count > 20

    _EXAMPLE_KEYWORDS = frozenset({"示例", "example", "案例", "样例", "模板", "template"})

    def _wants_examples(self, query: str) -> bool:
        """Return True if the query is seeking example projects."""
        q = query.lower()
        return any(kw in q for kw in self._EXAMPLE_KEYWORDS)

    # ── Query enhancement (migrated from gradio_ui.py) ───────────────────────

    @staticmethod
    def _is_chinese(text: str) -> bool:
        """Detect Chinese query (>15% CJK characters)."""
        zh = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        return zh / max(len(text.strip()), 1) > 0.15

    @staticmethod
    def _split_zh_segments(text: str) -> list[str]:
        """Jieba tokenization: keep 2+ char Chinese tokens, remove stop words, dedup."""
        _load_jieba_c3_dict()
        words = jieba.lcut(text)
        segments = [w for w in words if len(w) >= 2 and re.fullmatch(r'[\u4e00-\u9fff]+', w)]
        return list(dict.fromkeys(s for s in segments if s not in ZH_STOP_WORDS))

    @staticmethod
    def _classify_ace_intent(query: str) -> list[str]:
        """Classify which ACE sections to search based on query intent keywords.

        Returns matched section_type list, e.g. ["conditions", "expressions"].
        Returns all types (incl. properties) when no match.
        """
        _load_jieba_c3_dict()
        words = set(jieba.lcut(query))
        intents = []
        for ace_type, keywords in ACE_INTENT_KEYWORDS.items():
            if words & keywords:
                intents.append(ace_type)
        # expressions and properties are tightly coupled
        if "expressions" in intents and "properties" not in intents:
            intents.append("properties")
        elif "properties" in intents and "expressions" not in intents:
            intents.append("expressions")
        return intents if intents else ["conditions", "actions", "expressions", "properties"]

    def _extract_term_keywords(
        self, query: str, threshold: float = 0.5, top_k: int = 3
    ) -> list[dict]:
        """Search term collection per jieba segment, extract English keywords.

        Flow: query -> jieba tokenize -> search top_k per segment -> filter -> dedup
        Returns list of adopted keyword dicts with zh/en/score.
        """
        segments = self._split_zh_segments(query)
        _trace(f"{' / '.join(segments) if segments else '无'}", "tokenize")

        keywords: list[dict] = []
        seen_en: set[str] = set()

        for seg in segments:
            results = self.retriever.search_terms(seg, top_k=top_k)
            seg_hits = []
            for r in results:
                en = r.metadata.get("en", "")
                zh = r.metadata.get("zh", "")
                if en and en.lower() in seen_en:
                    continue
                if en:
                    seen_en.add(en.lower())
                if r.score >= threshold and en:
                    # Lexical filter: zh result must share enough characters
                    # with the query segment to prevent semantic drift.
                    # Rule: intersection must cover ≥50% of seg's chars,
                    # or be ≥ 2 unique characters — whichever is less strict.
                    # This blocks single-char accidents like "里边"→"右边" (only '边' shared)
                    # while still accepting "数组"→"数组" (100% overlap).
                    seg_zh_chars = {c for c in seg if '\u4e00' <= c <= '\u9fff'}
                    if seg_zh_chars:
                        overlap = seg_zh_chars.intersection(zh)
                        overlap_ratio = len(overlap) / len(seg_zh_chars)
                        # Require strict majority (>50%) or at least 2 shared chars.
                        # Blocks accidental single-char matches like "里边"→"右边" (only '边')
                        # while accepting "查找"→"查找值" (2 chars) and "数组"→"数组" (100%).
                        if overlap_ratio <= 0.5 and len(overlap) < 2:
                            continue
                    keywords.append({"zh": zh, "en": en, "score": r.score})
                    seg_hits.append(f"{zh}→{en}({r.score:.2f})")
            if seg_hits:
                _trace(f"[{seg}]: {', '.join(seg_hits)}", "term_hit")
            elif results:
                top = results[0]
                top_en = top.metadata.get("en", "?")
                _trace(f"[{seg}]: 最高分 {top.score:.2f}<阈值 ({top_en}，丢弃)", "term_hit")
            else:
                _trace(f"[{seg}]: 无结果", "term_hit")

        if keywords:
            expansions = [f"{kw['zh']}→{kw['en']}" for kw in keywords]
            _trace(', '.join(expansions), "expand")
        else:
            _trace("无", "expand")

        return keywords


    def _enrich_with_ace_search(
        self, query: str, term_keywords: list[dict],
        existing_results: List[SearchResult],
    ) -> List[SearchResult]:
        """Enrich results with plugin-specific ACE search based on term hits.

        Returns extended results list (original + new ACE hits, deduplicated).
        """
        if not term_keywords:
            _trace("跳过", "ace")
            return existing_results

        ace_intents = self._classify_ace_intent(query)
        seen_texts = {r.text[:200] for r in existing_results}
        extra: List[SearchResult] = []

        for kw in term_keywords:
            plugin_results = self.retriever.search_plugin_by_name(
                query=query, plugin_en=kw["en"],
                section_types=ace_intents,
            )
            for doc in plugin_results:
                if doc.text[:200] not in seen_texts:
                    seen_texts.add(doc.text[:200])
                    extra.append(doc)

        if extra:
            plugin_names = [kw["en"] for kw in term_keywords]
            _trace(f"{', '.join(plugin_names)}  +{len(extra)} 条", "ace")
        else:
            _trace("无命中", "ace")

        return existing_results + extra

    def _enrich_query(
        self, query: str, skip_schema: bool = False
    ) -> tuple[str, list[dict]]:
        """Expand a Chinese query with English term and schema tokens.

        Returns (search_query, term_keywords).
        Non-Chinese queries are returned unchanged with an empty keyword list.
        When *skip_schema* is True, the schema expansion step is skipped
        (used when a dict-lookup has already supplied precise plugin context).
        """
        if not self._is_chinese(query):
            return query, []

        search_query = query
        term_keywords = self._extract_term_keywords(query, threshold=0.65)
        if term_keywords:
            en_terms = " ".join(kw["en"] for kw in term_keywords)
            search_query = f"{query} {en_terms}"
            logger.info(f"[TermExpand] +{[kw['en'] for kw in term_keywords]}")

        if not skip_schema:
            segments = self._split_zh_segments(query)
            if segments:
                schema_term_set = self.query_expander.schema_term_set(segments)
                schema_matches = self.query_expander.search(schema_term_set)
                high = [m for m in schema_matches if m.score > 0.7]
                mid  = [m for m in schema_matches if 0.5 <= m.score <= 0.7]
                if high or mid:
                    boost_matches = (high if high else mid)[:5]
                    en_boost = " ".join(
                        part
                        for m in boost_matches
                        for part in m.node_id.replace("/", " ").replace("-", " ").split()
                        if len(part) >= 3
                    )
                    search_query = f"{search_query} {en_boost}".strip()
                    logger.info(f"[SchemaExpand] +{[m.node_id for m in boost_matches]}")
                if schema_matches:
                    top3 = schema_matches[:3]
                    summary = "  ".join(f"{m.node_id}({m.score:.2f})" for m in top3)
                    _trace(summary, "schema_match")

        if search_query != query:
            _trace(f'"{search_query[:80]}"', "query")

        return search_query, term_keywords

    def _format_sources_summary(self, results: List[SearchResult]) -> str:
        """Format search results as a readable summary for fallback responses."""
        if not results:
            return "No relevant documents found"

        summary_parts = []
        for i, r in enumerate(results[:5], start=1):
            source = r.metadata.get("source", "unknown")
            h2 = r.metadata.get("h2_heading", "")
            title = f"{source}"
            if h2:
                title += f" > {h2}"
            # Truncate text
            snippet = r.text[:200] + "..." if len(r.text) > 200 else r.text
            summary_parts.append(f"**[{i}] {title}**\n{snippet}\n")

        return "\n".join(summary_parts)

    def check_services(self) -> Dict[str, tuple[bool, str]]:
        """
        Check health of all required services.

        Returns:
            Dict with service names and (is_available, message) tuples

        Example:
            >>> chain = RAGChain()
            >>> status = chain.check_services()
            >>> for service, (ok, msg) in status.items():
            ...     print(f"{service}: {'✓' if ok else '✗'} {msg}")
        """
        return {
            "llm": self.llm.check_health(),
            "qdrant": self.retriever.check_health()
        }

    def _self_reflect(self, query: str, answer: str, context: str) -> tuple[str, bool]:
        """
        Self-reflection: Verify if answer is supported by sources.
        Returns: (reflection_result, is_reliable)

        Fast-path: skip LLM verification when the answer already cites 3+ sources —
        well-cited answers are unlikely to contain unsupported claims.
        """
        if len(re.findall(r'\[来源', answer)) >= 3:
            _trace("引用充足 (≥3)，跳过验证", "reflect")
            return "", True

        logger.info("[Reflect] Verifying answer reliability...")
        t_reflect = time.time()
        prompt = SELF_REFLECTION_PROMPT.format(
            question=query,
            answer=answer,
            source_context=context
        )

        reflection = self.llm.generate(prompt)

        # Parse verdict from the structured output line (e.g. "可靠性：[可靠 / 不可靠]")
        # NOTE: REFLECTION_RELIABLE may be a substring of REFLECTION_UNRELIABLE,
        # so we must check REFLECTION_UNRELIABLE first.
        is_reliable = False
        for line in reflection.split("\n"):
            stripped = line.strip()
            if REFLECTION_VERDICT_KEY in stripped:
                if REFLECTION_UNRELIABLE in stripped:
                    is_reliable = False
                elif REFLECTION_RELIABLE in stripped:
                    is_reliable = True
                break

        elapsed = time.time() - t_reflect
        verdict = "可靠" if is_reliable else "不可靠"
        _trace(f"{verdict}  ({elapsed:.1f}s)", "reflect")
        if not is_reliable:
            # Extract first issue/problem line from reflection for quick diagnosis
            for line in reflection.split("\n"):
                stripped = line.strip()
                if stripped and REFLECTION_VERDICT_KEY not in stripped and len(stripped) > 5:
                    _trace(f"问题: {stripped[:80]}", "reflect_issue")
                    break
        logger.info(f"[Reflect] Reliability: {'reliable' if is_reliable else 'unreliable'}")

        return reflection, is_reliable

    # section_type → context label (from locale)
    _SECTION_TYPE_LABELS = ACE_SECTION_LABELS

    def _format_single_result(self, r: SearchResult, idx: int) -> str:
        """Format one search result as a numbered context block."""
        source = r.metadata.get("source", "")
        source_path = source[:-3] if source.endswith(".md") else source
        breadcrumb = source_path.replace("/", " > ")

        h2 = r.metadata.get("h2_heading", "")
        header = f"[{idx}] {breadcrumb}"
        if h2:
            header += f" > {h2}"

        section_type = r.metadata.get("section_type", "")
        type_label = self._SECTION_TYPE_LABELS.get(section_type, "")
        if type_label:
            header += f"  [{type_label}]"

        return f"{header}\n{r.text}\n{SOURCE_LABEL.format(source=source)}\n"

    def _deduplicate_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Remove near-duplicate chunks using word-level Jaccard similarity."""
        kept: List[SearchResult] = []
        for r in results:
            words_r = set(r.text.split())
            is_dup = False
            for k in kept:
                words_k = set(k.text.split())
                union = words_r | words_k
                if union and len(words_r & words_k) / len(union) > _DEDUP_THRESHOLD:
                    is_dup = True
                    break
            if not is_dup:
                kept.append(r)
        return kept

    def _format_reranked_context(self, results: List[SearchResult]) -> str:
        """Format results grouped by source type, deduplicated, within char budget."""
        if not results:
            return ""

        # 1. Deduplicate near-identical chunks
        results = self._deduplicate_results(results)

        # 2. Group by source collection
        grouped: dict[str, List[SearchResult]] = {}
        for r in results:
            grouped.setdefault(r.source, []).append(r)

        # 3. Build grouped sections within char budget
        sections: list[str] = []
        idx = 1
        total_chars = 0

        for src_set, header, desc in _CONTEXT_GROUPS:
            group_results = [
                r for src in src_set
                for r in grouped.get(src, [])
            ]
            if not group_results:
                continue

            lines: list[str] = [f"### {header}"]
            if desc:
                lines.append(desc)
            lines.append("")

            for r in group_results:
                entry = self._format_single_result(r, idx)
                if total_chars + len(entry) > _CONTEXT_CHAR_BUDGET:
                    lines.append(f"[{idx}] （已达上下文长度限制，更多结果省略）\n")
                    break
                lines.append(entry)
                total_chars += len(entry)
                idx += 1

            sections.append("\n".join(lines))

        return "\n---\n\n".join(sections)

    def classify_query(self, query: str) -> str:
        """Classify query type (qa/code)"""
        query_lower = query.lower()

        if any(kw in query_lower for kw in CODE_GENERATION_KEYWORDS):
            return "code"
        else:
            return "qa"

    def answer_qa(self, query: str, retry_count: int = 0, use_strict_mode: bool = True, include_js: bool = False) -> RAGResponse:
        """Answer general Q&A queries with anti-hallucination measures"""
        # Step 1: Retrieve with increased top_k and reranking
        logger.info(f"[1/4] Retrieving docs... query: {query[:50]}...")
        t0 = time.time()

        # Try original query first
        results = self.retriever.search_all_with_rerank(
            query,
            top_k_per_collection=5,  # Increased from 2
            final_top_k=10
        )
        logger.info(f"[1/4] Retrieval done ({time.time()-t0:.1f}s), found {len(results)} results")

        # If no results, try query rewrite
        if len(results) == 0:
            if self.enable_query_rewrite and retry_count == 0:
                logger.info("[1/4] No results, trying query rewrite...")
                rewritten_queries = self._rewrite_query(query)
                logger.info(f"[1/4] Rewritten queries: {rewritten_queries}")

                for rq in rewritten_queries:
                    retry_results = self.retriever.search_all_with_rerank(
                        rq, top_k_per_collection=5, final_top_k=10
                    )
                    if len(retry_results) > 0:
                        logger.info(f"[1/4] Rewritten query '{rq}' found results")
                        results = retry_results
                        break

            if len(results) == 0:
                logger.info("[1/4] Still no results after rewrite")
                return RAGResponse(
                    answer=NO_RESULTS_RESPONSE,
                    sources=[],
                    query_type="qa_no_results",
                    confidence="none"
                )

        # Step 1.5: Filter noise via adaptive threshold
        results = self.retriever.filter_by_adaptive_threshold(results)

        # Step 2: Format context
        context = self._format_reranked_context(results)

        # Step 3: Generate answer with strict mode (anti-hallucination)
        logger.info(f"[2/4] LLM generating answer (strict: {use_strict_mode})...")
        t0 = time.time()

        if use_strict_mode and self.STRICT_MODE:
            prompt = STRICT_QA_PROMPT.format(context=context, question=query)
        else:
            prompt = QA_PROMPT.format(context=context, question=query)
        prompt = self._append_js_note(prompt, include_js)

        answer = self.llm.generate(prompt, system=SYSTEM_MESSAGE)
        logger.info(f"[2/4] Generation done ({time.time()-t0:.1f}s)")

        # Step 4: Self-reflection verification
        logger.info("[3/4] Self-Reflection verification...")
        reflection, is_reliable = self._self_reflect(query, answer, context)

        # If unreliable, try with more context
        confidence = "high" if is_reliable else "medium"
        verification_notes = ""

        if not is_reliable and retry_count < 1:
            logger.info("[3/4] Initial answer unreliable, attempting improvement...")
            # Try with even more results
            results_expanded = self.retriever.search_all_with_rerank(
                query, top_k_per_collection=8, final_top_k=15
            )
            # Check if we got new results (not just expanded version of same results)
            new_results_found = False
            for r in results_expanded:
                is_duplicate = False
                for existing in results:
                    if r.text[:100] == existing.text[:100]:
                        is_duplicate = True
                        break
                if not is_duplicate:
                    new_results_found = True
                    break

            if new_results_found:
                context_expanded = self._format_reranked_context(results_expanded)
                prompt_expanded = STRICT_QA_PROMPT.format(
                    context=context_expanded, question=query
                )
                answer_improved = self.llm.generate(prompt_expanded, system=SYSTEM_MESSAGE)

                # Re-verify
                reflection2, is_reliable2 = self._self_reflect(query, answer_improved, context_expanded)

                if is_reliable2:
                    answer = answer_improved
                    results = results_expanded
                    confidence = "high"
                    logger.info("[3/4] Improved answer is reliable")
                else:
                    verification_notes = f"Initial verification issues:\n{reflection}\n\nAfter improvement:\n{reflection2}"
            else:
                verification_notes = f"Initial verification issues:\n{reflection}"

        # Collect sources
        sources = []
        for i, item in enumerate(results[:10], start=1):
            sources.append({
                "id": i,
                "type": item.source,
                "text": item.text[:150] + "..." if len(item.text) > 150 else item.text,
                "score": item.score,
                "metadata": item.metadata
            })

        query_type = "qa"
        if confidence != "high":
            query_type = "qa_low_confidence"

        logger.info(f"[4/4] Done, confidence: {confidence}")

        return RAGResponse(
            answer=answer,
            sources=sources,
            query_type=query_type,
            confidence=confidence,
            verification_notes=verification_notes
        )

    def answer_code(self, query: str) -> RAGResponse:
        """Generate Construct 3 clipboard JSON via schema-driven EventGenerator pipeline.

        Pipeline:
          1. EventGenerator extracts relevant ACE schemas from query keywords
          2. Builds a schema-aware prompt (EVENT_JSON_GENERATION_PROMPT)
          3. Optionally appends retrieved example project snippets
          4. LLM generates clipboard JSON
          5. ClipboardValidator extracts and validates the JSON
        """
        from src.rag.eventsheet_generator import EventGenerator

        generator = EventGenerator()

        # 1. Build schema-aware prompt with ACE context
        prompt = generator.build_prompt(query)

        # 2. Append retrieved example snippets as additional context
        example_results = self.retriever.search_examples(query, top_k=3)
        if example_results:
            examples_text = "\n\n".join([
                f"### {r.metadata.get('project', 'Example')}\n{r.text}"
                for r in example_results
            ])
            prompt += f"\n\n## 相关示例项目（供参考）\n{examples_text}"

        # 3. Generate
        llm_response = self.llm.generate(prompt)

        # 4. Extract JSON and validate via ClipboardValidator
        result = generator.process_response(llm_response)

        # 5. Format RAGResponse based on validation outcome
        if result["success"]:
            answer = result["json"]
            confidence = "high"
            warning_note = f"，{len(result['warnings'])} 个警告" if result["warnings"] else ""
            notes = f"ClipboardValidator 验证通过{warning_note}"
        else:
            # Return best-effort JSON (or raw response) with error notes
            answer = result["json"] or llm_response
            confidence = "low"
            error_summary = "；".join(result["errors"][:3])
            notes = f"验证未通过：{error_summary}"
            if result["warnings"]:
                notes += f"（{len(result['warnings'])} 个警告）"

        sources = [
            {"type": "example", "text": r.text[:100], "metadata": r.metadata}
            for r in example_results
        ]
        return RAGResponse(
            answer=answer,
            sources=sources,
            query_type="code",
            confidence=confidence,
            verification_notes=notes,
        )

    def answer(self, query: str) -> RAGResponse:
        """
        Main entry point - routes query to appropriate handler with anti-hallucination
        """
        query_type = self.classify_query(query)

        if query_type == "code":
            return self.answer_code(query)
        else:
            return self.answer_qa(query, use_strict_mode=True)

    def answer_high_confidence(self, query: str, include_js: bool = False) -> RAGResponse:
        """
        High-confidence Q&A with maximum anti-hallucination measures.
        Use this for fact-critical questions.
        """
        # Multi-query retrieval for comprehensive coverage
        logger.info("[HighConf] Starting multi-query retrieval...")
        all_results: List[SearchResult] = []

        # Original query
        results = self.retriever.search_all_with_rerank(
            query, top_k_per_collection=5, final_top_k=10
        )
        all_results.extend(results)

        # Query rewrite for additional perspectives
        if self.enable_query_rewrite:
            rewritten = self._rewrite_query(query)
            for rq in rewritten[:2]:  # Try 2 rewrites
                retry = self.retriever.search_all_with_rerank(
                    rq, top_k_per_collection=5, final_top_k=10
                )
                for r in retry:
                    # Avoid duplicates (100 chars for more reliable comparison)
                    is_duplicate = False
                    for existing in all_results:
                        if r.text[:100] == existing.text[:100]:
                            is_duplicate = True
                            break
                    if not is_duplicate:
                        all_results.append(r)

        if not all_results:
            return RAGResponse(
                answer=NO_RESULTS_RESPONSE,
                sources=[],
                query_type="qa_no_results",
                confidence="none"
            )

        # Deduplicate
        unique_results: List[SearchResult] = []
        seen = set()
        for r in all_results:
            key = r.text[:100].lower().strip()
            if key not in seen:
                seen.add(key)
                unique_results.append(r)

        # Sort by score
        unique_results.sort(key=lambda x: x.score, reverse=True)

        # Filter noise via adaptive threshold
        unique_results = self.retriever.filter_by_adaptive_threshold(unique_results)

        # Use strict mode with expanded context
        context = self._format_reranked_context(unique_results)
        prompt = STRICT_QA_PROMPT.format(context=context, question=query)
        prompt = self._append_js_note(prompt, include_js)

        logger.info("[HighConf] Generating answer...")
        answer = self.llm.generate(prompt, system=SYSTEM_MESSAGE)

        # Self-reflection
        reflection, is_reliable = self._self_reflect(query, answer, context)

        # Format sources
        sources = []
        for i, item in enumerate(unique_results[:10], start=1):
            sources.append({
                "id": i,
                "type": item.source,
                "text": item.text[:150] + "..." if len(item.text) > 150 else item.text,
                "score": item.score,
                "metadata": item.metadata
            })

        confidence = "high" if is_reliable else "medium"

        return RAGResponse(
            answer=answer,
            sources=sources,
            query_type="qa_high_confidence",
            confidence=confidence,
            verification_notes=reflection if not is_reliable else ""
        )

    def answer_stream(self, query: str, use_strict_mode: bool = True, include_js: bool = False):
        """
        Streaming version of answer with anti-hallucination measures
        """
        query_type = self.classify_query(query)

        # Retrieve context first with increased top_k
        if query_type == "code":
            results = self.retriever.search_examples(query, top_k=5)
            examples = "\n\n".join([
                f"### {r.metadata.get('project', 'Example')}\n{r.text}"
                for r in results
            ])
            prompt = EVENT_GENERATION_PROMPT.format(
                similar_examples=examples,
                user_requirement=query
            )
            system = ""
        else:
            # QA: use the same enrichment pipeline as answer_with_fallback
            search_query, term_keywords = self._enrich_query(query)
            results = self.retriever.search_all_with_rerank(
                search_query, top_k_per_collection=5, final_top_k=10
            )

            # Try query rewrite if no results
            if len(results) == 0 and self.enable_query_rewrite:
                rewritten_queries = self._rewrite_query(query)
                for rq in rewritten_queries:
                    retry_results = self.retriever.search_all_with_rerank(
                        rq, top_k_per_collection=5, final_top_k=10
                    )
                    if len(retry_results) > 0:
                        results = retry_results
                        break

            # No results - return directly
            if len(results) == 0:
                yield NO_RESULTS_RESPONSE
                return

            results = self._enrich_with_ace_search(query, term_keywords, results)
            results = self.retriever.filter_by_adaptive_threshold(results)

            context = self._format_reranked_context(results)

            # Select prompt based on mode
            if use_strict_mode and self.STRICT_MODE:
                prompt = STRICT_QA_PROMPT.format(context=context, question=query)
            else:
                prompt = QA_PROMPT.format(context=context, question=query)
            prompt = self._append_js_note(prompt, include_js)
            system = SYSTEM_MESSAGE

        # Stream the response
        for chunk in self.llm.generate_stream(prompt, system=system):
            yield chunk

    def chat(self, messages: List[Dict[str, str]]) -> str:
        """
        Multi-turn chat with context and anti-hallucination
        """
        # Get last user message for retrieval
        last_user_msg = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break

        if last_user_msg:
            # Retrieve context with anti-hallucination measures
            results = self.retriever.search_all_with_rerank(
                last_user_msg, top_k_per_collection=5, final_top_k=10
            )
            context = self._format_reranked_context(results)

            # Use strict mode for chat
            system_with_context = f"{SYSTEM_MESSAGE}\n\n{CONTEXT_HEADER_STRICT}\n{context}"
            enhanced_messages = [
                {"role": "system", "content": system_with_context}
            ] + messages

            return self.llm.chat(enhanced_messages)
        else:
            return self.llm.chat(messages)

    def answer_complex_workflow(self, query: str, include_js: bool = False, schema_context: str = "", pre_fetched_results: list | None = None) -> RAGResponse:
        """
        Answer complex multi-step workflow queries using query decomposition.

        This method is specifically designed for queries that involve:
        - Multiple Construct 3 features working together
        - Multi-step implementation processes
        - Combined setup and runtime logic

        Strategy:
            1. Decompose query into focused sub-queries
            2. Retrieve results for each sub-query
            3. Combine using Reciprocal Rank Fusion (RRF)
            4. Filter irrelevant results with adaptive thresholding
            5. Generate comprehensive answer

        Args:
            query: Complex multi-step query

        Returns:
            RAGResponse with comprehensive answer and sources

        Example:
            >>> chain = RAGChain()
            >>> response = chain.answer_complex_workflow(
            ...     "如何实现一个带有二段跳、墙跳和冲刺的平台游戏角色？"
            ... )
            >>> print(response.answer)
        """
        logger.info(f"[Complex] Processing: {query[:50]}...")

        # Query enhancement: term + schema expansion
        search_query, term_keywords = self._enrich_query(query, skip_schema=bool(schema_context))

        # Step 1: Decompose query
        logger.info("[Complex] Decomposing query...")
        sub_queries = self._decompose_query(query)
        logger.info(f"[Complex] Sub-queries: {sub_queries}")

        # Step 2: Retrieve for each sub-query
        all_result_lists: List[List[SearchResult]] = []

        # Original query (with term enrichment)
        if pre_fetched_results is not None:
            original_results = pre_fetched_results
        else:
            original_results = self.retriever.search_all_with_rerank(
                search_query, top_k_per_collection=5, final_top_k=10
            )
        all_result_lists.append(original_results)

        # Sub-queries
        for sq in sub_queries:
            sq_results = self.retriever.search_all_with_rerank(
                sq, top_k_per_collection=3, final_top_k=8
            )
            if sq_results:
                all_result_lists.append(sq_results)
                logger.info(f"[Complex] Sub-query '{sq[:30]}...' returned {len(sq_results)} results")

        # Extra examples retrieval for example-seeking queries
        if self._wants_examples(query):
            extra_examples = self.retriever.search_examples(query, top_k=3)
            if extra_examples:
                all_result_lists.append(extra_examples)

        # Step 3: Combine with RRF
        logger.info("[Complex] Fusing results with RRF...")
        fused_results = self.retriever.reciprocal_rank_fusion(all_result_lists)

        # Enrich with plugin-specific ACE search
        fused_results = self._enrich_with_ace_search(query, term_keywords, fused_results)

        # Step 4: Filter with adaptive threshold
        filtered_results = self.retriever.filter_by_adaptive_threshold(
            fused_results, min_results=5
        )
        logger.info(f"[Complex] Filtered to {len(filtered_results)} results")

        if not filtered_results:
            return RAGResponse(
                answer=NO_RESULTS_RESPONSE,
                sources=[],
                query_type="qa_complex_no_results",
                confidence="none"
            )

        # Step 5: Generate answer
        context = self._format_reranked_context(filtered_results[:15])
        if schema_context:
            context = (
                "### 编辑器功能定义（ACE Schema）\n"
                "以下是 Construct 3 编辑器中实际显示的功能，包含精确名称、参数及简短说明。"
                "与下方官方文档说明互为补充，共同构成完整的功能描述。\n\n"
                f"{schema_context}\n\n---\n\n"
                f"{context}"
            )
            _trace("字典数据已注入上下文", "info")
        prompt = STRICT_QA_PROMPT.format(context=context, question=query)
        prompt = self._append_js_note(prompt, include_js)

        answer = self.llm.generate(prompt, system=SYSTEM_MESSAGE)

        # Self-reflection
        reflection, is_reliable = self._self_reflect(query, answer, context)

        # Format sources
        sources = []
        for i, item in enumerate(filtered_results[:10], start=1):
            sources.append({
                "id": i,
                "type": item.source,
                "text": item.text[:150] + "..." if len(item.text) > 150 else item.text,
                "score": item.score,
                "metadata": item.metadata
            })

        confidence = "high" if is_reliable else "medium"

        return RAGResponse(
            answer=answer,
            sources=sources,
            query_type="qa_complex_workflow",
            confidence=confidence,
            verification_notes=reflection if not is_reliable else ""
        )

    def answer_with_fallback(self, query: str, include_js: bool = False, schema_context: str = "", pre_fetched_results: list | None = None) -> RAGResponse:
        """
        Answer query with graceful fallback for service unavailability.

        This method provides graceful degradation when services are unavailable:
        - If Qdrant is down: Returns error message with recovery instructions
        - If LLM is down: Returns retrieved sources without AI answer
        - If both work: Returns full AI-generated answer

        The method maintains source attribution even in fallback scenarios,
        ensuring users always have access to relevant documentation.

        Args:
            query: User query

        Returns:
            RAGResponse with answer or fallback message

        Example:
            >>> chain = RAGChain()
            >>> response = chain.answer_with_fallback("Sprite 碰撞检测")
            >>> if response.query_type == "fallback_llm_unavailable":
            ...     print("LLM 不可用，但找到了相关文档：")
            ...     for src in response.sources:
            ...         print(f"  - {src['metadata'].get('source')}")
        """
        # Check Qdrant availability
        qdrant_ok, qdrant_msg = self.retriever.check_health()
        if not qdrant_ok:
            logger.warning(f"[Fallback] Qdrant unavailable: {qdrant_msg}")
            return RAGResponse(
                answer=QDRANT_UNAVAILABLE_RESPONSE,
                sources=[],
                query_type="fallback_qdrant_unavailable",
                confidence="none",
                verification_notes=qdrant_msg
            )

        # Query enhancement: term + schema expansion
        # Skip schema expansion when dict-lookup already provided precise plugin context
        # (schema_match searches all plugins and may add noise, e.g. "数字"→sqrt)
        search_query, term_keywords = self._enrich_query(query, skip_schema=bool(schema_context))

        # Retrieve results (Qdrant is available)
        if pre_fetched_results is not None:
            results = pre_fetched_results
        else:
            results = self.retriever.search_all_with_rerank(
                search_query, top_k_per_collection=5, final_top_k=10
            )

        # Extra examples retrieval for example-seeking queries
        if self._wants_examples(query):
            results += self.retriever.search_examples(query, top_k=3)

        # Enrich with plugin-specific ACE search based on term hits
        results = self._enrich_with_ace_search(query, term_keywords, results)

        # Filter irrelevant results
        filtered_results = self.retriever.filter_by_adaptive_threshold(results)

        # c3_terms is supplementary (translation dict), not primary content.
        # Only include term entries in LLM context when at least one substantive
        # result (doc / ACE / example) was also retrieved. When terms are the only
        # results, they add noise without semantic value; the LLM will fall back
        # to general-knowledge Path B via the empty context.
        substantive = [r for r in filtered_results if r.source not in _TERM_SOURCES]
        context_results = filtered_results if substantive else []

        # Trace top results going to LLM
        for i, r in enumerate(context_results[:3], 1):
            src = r.metadata.get("source", r.source)
            src_name = src.split("/")[-1].replace(".md", "")[:18] if "/" in src else src[:18]
            h2 = r.metadata.get("h2_heading", "")
            section = r.metadata.get("section_type", "")
            loc = src_name + (f" > {h2[:12]}" if h2 else "") + (f" ({section})" if section else "")
            snippet = r.text[:30].replace("\n", " ")
            _trace(f"#{i} [{r.source}] {loc}  {r.score:.2f}  {snippet}…", "context")
        if not context_results and filtered_results:
            _trace(f"仅词典词条 ({len(filtered_results)} 条)，已从 LLM 上下文排除", "context")

        # Format sources for potential fallback
        sources = []
        for i, item in enumerate(filtered_results[:10], start=1):
            sources.append({
                "id": i,
                "type": item.source,
                "text": item.text[:150] + "..." if len(item.text) > 150 else item.text,
                "score": item.score,
                "metadata": item.metadata
            })

        # Check LLM availability
        llm_ok, llm_msg = self.llm.check_health()
        if not llm_ok:
            logger.warning(f"[Fallback] LLM unavailable: {llm_msg}")
            _trace("LLM: 不可用", "route")
            sources_summary = self._format_sources_summary(filtered_results)
            return RAGResponse(
                answer=LLM_UNAVAILABLE_RESPONSE.format(sources_summary=sources_summary),
                sources=sources,
                query_type="fallback_llm_unavailable",
                confidence="low",
                verification_notes=llm_msg
            )

        # No results found — try query rewrite before giving up
        if not filtered_results:
            if self.enable_query_rewrite:
                logger.info("[Fallback] No results, trying query rewrite...")
                rewritten_queries = self._rewrite_query(query)
                logger.info(f"[Fallback] Rewritten queries: {rewritten_queries}")
                for rq in rewritten_queries:
                    rq_results = self.retriever.search_all_with_rerank(
                        rq, top_k_per_collection=5, final_top_k=10
                    )
                    rq_filtered = self.retriever.filter_by_adaptive_threshold(rq_results)
                    substantive_rq = [r for r in rq_filtered if r.source not in _TERM_SOURCES]
                    if substantive_rq:
                        logger.info(f"[Fallback] Rewritten query '{rq}' found results")
                        filtered_results = rq_filtered
                        context_results = rq_filtered
                        sources = [
                            {"id": i, "type": r.source,
                             "text": r.text[:150] + "..." if len(r.text) > 150 else r.text,
                             "score": r.score, "metadata": r.metadata}
                            for i, r in enumerate(rq_filtered[:10], 1)
                        ]
                        break

            if not filtered_results:
                return RAGResponse(
                    answer=NO_RESULTS_RESPONSE,
                    sources=[],
                    query_type="qa_no_results",
                    confidence="none"
                )

        # Full answer generation (both services available)
        context = self._format_reranked_context(context_results)
        if schema_context:
            context = (
                "### 编辑器功能定义（ACE Schema）\n"
                "以下是 Construct 3 编辑器中实际显示的功能，包含精确名称、参数及简短说明。"
                "与下方官方文档说明互为补充，共同构成完整的功能描述。\n\n"
                f"{schema_context}\n\n---\n\n"
                f"{context}"
            )
            _trace("字典数据已注入上下文", "info")
        prompt = STRICT_QA_PROMPT.format(context=context, question=query)
        prompt = self._append_js_note(prompt, include_js)

        answer = self.llm.generate(prompt, system=SYSTEM_MESSAGE)

        # Check for LLM errors in response
        if answer.startswith("LLM error:"):
            sources_summary = self._format_sources_summary(filtered_results)
            return RAGResponse(
                answer=LLM_UNAVAILABLE_RESPONSE.format(sources_summary=sources_summary),
                sources=sources,
                query_type="fallback_llm_error",
                confidence="low",
                verification_notes=answer
            )

        # Self-reflection for quality assurance
        reflection, is_reliable = self._self_reflect(query, answer, context)
        confidence = "high" if is_reliable else "medium"
        _trace(confidence, "confidence")

        # Confidence is surfaced via RAGResponse.confidence; UI handles display.

        return RAGResponse(
            answer=answer,
            sources=sources,
            query_type="qa",
            confidence=confidence,
            verification_notes=reflection if not is_reliable else ""
        )

    # ------------------------------------------------------------------
    # Clipboard / event-sheet parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_clipboard_json(text: str) -> bool:
        """Return True if text looks like a C3 clipboard JSON payload."""
        s = text.strip()
        return s.startswith("{") and '"is-c3-clipboard-data"' in s and '"type":"events"' in s

    @staticmethod
    def _is_clipboard_text(text: str) -> bool:
        """Return True if text looks like C3 'Copy as text' output."""
        lines = [l for l in text.splitlines() if l.strip()]
        markers = sum(1 for l in lines if l.startswith(("+ ", "-> ", "// ")))
        return markers >= 2

    @staticmethod
    def _clipboard_json_to_text(json_str: str) -> str:
        """Convert C3 clipboard JSON to a compact human-readable event sheet."""
        import json as _json
        try:
            data = _json.loads(json_str)
        except Exception:
            return json_str
        lines = []
        for item in data.get("items", []):
            etype = item.get("eventType")
            if etype == "comment":
                lines.append(f"// {item.get('text', '')}")
            elif etype == "block":
                for c in item.get("conditions", []):
                    obj = c.get("objectClass", "System")
                    cid = c.get("id", "")
                    params = c.get("parameters", {})
                    param_str = ", ".join(f"{k}={v}" for k, v in params.items()) if params else ""
                    lines.append(f"+ {obj}: {cid}" + (f"({param_str})" if param_str else ""))
                for a in item.get("actions", []):
                    obj = a.get("objectClass", "")
                    aid = a.get("id", "")
                    params = a.get("parameters", {})
                    param_str = ", ".join(f"{k}={v}" for k, v in params.items()) if params else ""
                    lines.append(f"-> {obj}: {aid}" + (f"({param_str})" if param_str else ""))
                lines.append("")
        return "\n".join(lines).strip()

    def answer_smart(self, query: str, include_js: bool = False) -> RAGResponse:
        """
        Smart answer routing with automatic complexity detection and fallback.

        This is the recommended entry point for production use. It:
        1. Tries direct lookup (zero LLM cost, instant)
        2. Detects query complexity
        3. Routes to appropriate handler (simple vs complex workflow)
        4. Provides graceful fallback on service failures
        5. Filters irrelevant results automatically

        Args:
            query: User query

        Returns:
            RAGResponse with best-effort answer

        Example:
            >>> chain = RAGChain()
            >>> # Simple query - uses standard handler
            >>> r1 = chain.answer_smart("Sprite 是什么？")
            >>> # Complex query - uses decomposition
            >>> r2 = chain.answer_smart("如何实现带存档功能的平台游戏？")
        """
        _trace_local.events = []

        # Clipboard detection — handle C3 event sheet pasted as JSON or text
        # Format: "<clipboard content>\n---\n<user question>"
        # OR just clipboard alone (infers "explain this")
        clipboard_context = ""
        if "\n---\n" in query:
            parts = query.split("\n---\n", 1)
            clipboard_raw, user_question = parts[0].strip(), parts[1].strip()
            if self._is_clipboard_json(clipboard_raw):
                clipboard_context = self._clipboard_json_to_text(clipboard_raw)
                _trace("clipboard: JSON converted", "route")
            elif self._is_clipboard_text(clipboard_raw):
                clipboard_context = clipboard_raw
                _trace("clipboard: text format", "route")
            if clipboard_context:
                query = user_question or CLIPBOARD_DEFAULT_QUERY
        elif self._is_clipboard_json(query):
            clipboard_context = self._clipboard_json_to_text(query)
            query = CLIPBOARD_DEFAULT_QUERY
            _trace("clipboard: JSON converted", "route")
        elif self._is_clipboard_text(query):
            clipboard_context = query
            query = CLIPBOARD_DEFAULT_QUERY
            _trace("clipboard: text format", "route")

        # Lookup shortcut — direct JSON/CSV lookup, no LLM needed
        if not hasattr(self, '_lookup'):
            from src.rag.lookup import LookupEngine
            self._lookup = LookupEngine()
        lookup_resp = self._lookup.try_lookup(query)
        schema_context = ""
        if lookup_resp:
            _intent = lookup_resp.intent
            _schema = self._lookup.schema_index.get_schema(_intent.plugin_id, _intent.is_behavior)
            _name = _schema.get("name_en", _intent.plugin_id) if _schema else _intent.plugin_id
            _trace("路由: 字典注入", "route")
            _trace(f"{_intent.intent_type} · {_name}", "route")
            schema_context = lookup_resp.answer

        # Semantic chain pre-dispatch (after lookup, before complexity routing)
        pre_fetched: list | None = None
        if self.semantic_chain:
            _sc_result = self.semantic_chain.run(query)
            if _sc_result is not None:
                sc_result_lists, sc_weights = _sc_result
                if sc_result_lists:
                    existing = self.retriever.search_all_with_rerank(
                        self._enrich_query(query)[0],
                        top_k_per_collection=5, final_top_k=10,
                    )
                    blend = max(0.2, (sc_weights[0] if sc_weights else 0.3))
                    pre_fetched = weighted_rrf(
                        [existing, *sc_result_lists],
                        [1.0 - blend, *sc_weights],
                    )
                    _trace(f"semantic: {len(pre_fetched)} results merged", "retrieve")

        # Prepend clipboard event sheet to schema_context so LLM sees it as structured input
        if clipboard_context:
            clipboard_header = CLIPBOARD_CONTEXT_HEADER + "\n\n" + clipboard_context
            schema_context = clipboard_header + ("\n\n---\n\n" + schema_context if schema_context else "")
            # Clipboard queries always use complex path for better analysis
            _trace("route: clipboard analysis (forced complex path)", "route")
            resp = self.answer_complex_workflow(query, include_js=include_js, schema_context=schema_context)
        # Route based on complexity
        elif self._is_complex_query(query):
            logger.info("[Smart] Complex query detected, using decomposition")
            import jieba
            word_count = len([w for w in jieba.cut(query) if w.strip()])
            indicators = [ind for ind in COMPLEXITY_INDICATORS if ind in query.lower()]
            reason_parts = [f"词数={word_count}"]
            if indicators:
                reason_parts.append(f"指标=[{', '.join(indicators[:3])}]")
            _trace(f"路由: QA 复杂（{'，'.join(reason_parts)}）", "route")
            resp = self.answer_complex_workflow(query, include_js=include_js, schema_context=schema_context, pre_fetched_results=pre_fetched)
        else:
            import jieba
            word_count = len([w for w in jieba.cut(query) if w.strip()])
            logger.info("[Smart] Standard query, using fallback strategy")
            _trace(f"路由: QA 简单（词数={word_count}）", "route")
            resp = self.answer_with_fallback(query, include_js=include_js, schema_context=schema_context, pre_fetched_results=pre_fetched)

        resp.trace = list(_trace_local.events)
        return resp
