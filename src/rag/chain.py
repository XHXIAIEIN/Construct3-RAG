"""
RAG Chain for Construct 3 Assistant
Combines retrieval with LLM generation
"""
import time
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .retriever import HybridRetriever, SearchResult
from .prompts import (
    QA_PROMPT, EVENT_GENERATION_PROMPT, SYSTEM_MESSAGE,
    LOW_RELEVANCE_PROMPT, NO_RESULTS_RESPONSE, QUERY_REWRITE_PROMPT
)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class RAGResponse:
    """Response from RAG chain"""
    answer: str
    sources: List[Dict[str, Any]]
    query_type: str


class LLMClient:
    """Client for LLM inference (Ollama or OpenAI-compatible)"""

    def __init__(
        self,
        model: str = "qwen2.5:14b",
        base_url: str = "http://localhost:11434"
    ):
        self.model = model
        self.base_url = base_url
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import ollama
                self._client = ollama.Client(host=self.base_url)
            except ImportError:
                print("Warning: ollama not installed. Run: pip install ollama")
                self._client = None
        return self._client

    def generate(self, prompt: str, system: str = "") -> str:
        """Generate response from LLM"""
        if self.client is None:
            return "LLM client not available. Please install ollama."

        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            response = self.client.chat(
                model=self.model,
                messages=messages
            )
            return response["message"]["content"]
        except Exception as e:
            return f"LLM error: {str(e)}"

    def generate_stream(self, prompt: str, system: str = ""):
        """Generate response from LLM with streaming"""
        if self.client is None:
            yield "LLM client not available. Please install ollama."
            return

        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            stream = self.client.chat(
                model=self.model,
                messages=messages,
                stream=True
            )
            for chunk in stream:
                if "message" in chunk and "content" in chunk["message"]:
                    yield chunk["message"]["content"]
        except Exception as e:
            yield f"LLM error: {str(e)}"

    def chat(self, messages: List[Dict[str, str]]) -> str:
        """Multi-turn chat"""
        if self.client is None:
            return "LLM client not available."

        try:
            response = self.client.chat(
                model=self.model,
                messages=messages
            )
            return response["message"]["content"]
        except Exception as e:
            return f"LLM error: {str(e)}"


class RAGChain:
    """
    RAG Chain for Construct 3 Q&A
    """

    # 检索结果阈值配置
    MIN_RESULTS_THRESHOLD = 3  # 低于此数量视为低相关度
    HIGH_SCORE_THRESHOLD = 0.7  # 高置信度分数阈值

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        llm_model: str = "qwen2.5:14b",
        llm_base_url: str = "http://localhost:11434",
        enable_query_rewrite: bool = True
    ):
        self.retriever = HybridRetriever(qdrant_host, qdrant_port)
        self.llm = LLMClient(model=llm_model, base_url=llm_base_url)
        self.enable_query_rewrite = enable_query_rewrite

    def _count_results(self, results: Dict[str, List[SearchResult]]) -> int:
        """统计检索结果总数"""
        return sum(len(items) for items in results.values())

    def _get_max_score(self, results: Dict[str, List[SearchResult]]) -> float:
        """获取最高相关度分数"""
        max_score = 0.0
        for items in results.values():
            for item in items:
                if item.score > max_score:
                    max_score = item.score
        return max_score

    def _rewrite_query(self, query: str) -> List[str]:
        """使用 LLM 改写查询以提高检索效果"""
        prompt = QUERY_REWRITE_PROMPT.format(original_query=query)
        response = self.llm.generate(prompt)
        # 解析改写结果，每行一个查询
        rewritten = [q.strip() for q in response.strip().split('\n') if q.strip()]
        return rewritten[:3]  # 最多返回 3 个改写

    def classify_query(self, query: str) -> str:
        """Classify query type (qa/code)"""
        query_lower = query.lower()

        # Simple rule-based classification
        if any(kw in query_lower for kw in ["生成", "写一个", "帮我写", "事件表", "代码"]):
            return "code"
        else:
            return "qa"

    def answer_qa(self, query: str, retry_count: int = 0) -> RAGResponse:
        """Answer general Q&A queries with fallback handling"""
        # Retrieve relevant context
        logger.info(f"[1/3] 检索相关文档... 查询: {query[:50]}...")
        t0 = time.time()
        results = self.retriever.search_all(query, top_k_per_collection=3)
        logger.info(f"[1/3] 检索完成 ({time.time()-t0:.1f}s)")

        # 统计检索结果
        result_count = self._count_results(results)
        max_score = self._get_max_score(results)
        logger.info(f"[1/3] 找到 {result_count} 条结果，最高分: {max_score:.2f}")

        # 情况1: 完全没有结果 - 尝试改写查询
        if result_count == 0:
            if self.enable_query_rewrite and retry_count == 0:
                logger.info("[1/3] 未找到结果，尝试改写查询...")
                rewritten_queries = self._rewrite_query(query)
                logger.info(f"[1/3] 改写查询: {rewritten_queries}")

                # 用改写后的查询重新搜索
                for rq in rewritten_queries:
                    retry_results = self.retriever.search_all(rq, top_k_per_collection=3)
                    if self._count_results(retry_results) > 0:
                        logger.info(f"[1/3] 改写查询 '{rq}' 找到结果")
                        results = retry_results
                        result_count = self._count_results(results)
                        max_score = self._get_max_score(results)
                        break

            # 改写后仍然没有结果
            if self._count_results(results) == 0:
                logger.info("[1/3] 改写后仍无结果，返回无结果提示")
                return RAGResponse(
                    answer=NO_RESULTS_RESPONSE,
                    sources=[],
                    query_type="qa_no_results"
                )

        context = self.retriever.format_context(results)

        # 情况2: 结果较少或分数较低 - 使用谨慎回答模式
        if result_count < self.MIN_RESULTS_THRESHOLD or max_score < self.HIGH_SCORE_THRESHOLD:
            logger.info(f"[2/3] 结果较少/分数较低，使用谨慎回答模式")
            prompt = LOW_RELEVANCE_PROMPT.format(
                context=context,
                question=query,
                result_count=result_count
            )
        else:
            # 情况3: 正常结果 - 使用标准回答模式
            prompt = QA_PROMPT.format(context=context, question=query)

        # Generate answer
        logger.info(f"[2/3] LLM 生成回答...")
        t0 = time.time()
        answer = self.llm.generate(prompt, system=SYSTEM_MESSAGE)
        logger.info(f"[2/3] 生成完成 ({time.time()-t0:.1f}s)")

        # Collect sources
        sources = []
        for source_type, items in results.items():
            for item in items:
                sources.append({
                    "type": source_type,
                    "text": item.text[:100] + "..." if len(item.text) > 100 else item.text,
                    "score": item.score,
                    "metadata": item.metadata
                })

        query_type = "qa"
        if result_count < self.MIN_RESULTS_THRESHOLD:
            query_type = "qa_low_relevance"

        return RAGResponse(answer=answer, sources=sources, query_type=query_type)

    def answer_code(self, query: str) -> RAGResponse:
        """Handle code/event generation queries"""
        # Search example projects
        results = self.retriever.search_examples(query, top_k=5)

        # Format examples
        examples = "\n\n".join([
            f"### {r.metadata.get('project', 'Example')}\n{r.text}"
            for r in results
        ])

        prompt = EVENT_GENERATION_PROMPT.format(
            similar_examples=examples,
            user_requirement=query
        )
        answer = self.llm.generate(prompt)

        sources = [{"type": "example", "text": r.text[:100], "metadata": r.metadata} for r in results]
        return RAGResponse(answer=answer, sources=sources, query_type="code")

    def answer(self, query: str) -> RAGResponse:
        """
        Main entry point - routes query to appropriate handler
        """
        query_type = self.classify_query(query)

        if query_type == "code":
            return self.answer_code(query)
        else:
            return self.answer_qa(query)

    def answer_stream(self, query: str):
        """
        Streaming version of answer - yields chunks as they're generated
        """
        query_type = self.classify_query(query)

        # Retrieve context first
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
            # QA with fallback handling
            results = self.retriever.search_all(query, top_k_per_collection=3)
            result_count = self._count_results(results)
            max_score = self._get_max_score(results)

            # 尝试改写查询
            if result_count == 0 and self.enable_query_rewrite:
                rewritten_queries = self._rewrite_query(query)
                for rq in rewritten_queries:
                    retry_results = self.retriever.search_all(rq, top_k_per_collection=3)
                    if self._count_results(retry_results) > 0:
                        results = retry_results
                        result_count = self._count_results(results)
                        max_score = self._get_max_score(results)
                        break

            # 无结果时直接返回提示
            if result_count == 0:
                yield NO_RESULTS_RESPONSE
                return

            context = self.retriever.format_context(results)

            # 选择合适的 prompt
            if result_count < self.MIN_RESULTS_THRESHOLD or max_score < self.HIGH_SCORE_THRESHOLD:
                prompt = LOW_RELEVANCE_PROMPT.format(
                    context=context,
                    question=query,
                    result_count=result_count
                )
            else:
                prompt = QA_PROMPT.format(context=context, question=query)
            system = SYSTEM_MESSAGE

        # Stream the response
        for chunk in self.llm.generate_stream(prompt, system=system):
            yield chunk

    def chat(self, messages: List[Dict[str, str]]) -> str:
        """
        Multi-turn chat with context
        """
        # Get last user message for retrieval
        last_user_msg = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break

        if last_user_msg:
            # Retrieve context for last message
            results = self.retriever.search_all(last_user_msg, top_k_per_collection=2)
            context = self.retriever.format_context(results)

            # Inject context into system message
            system_with_context = f"{SYSTEM_MESSAGE}\n\n## 参考资料\n{context}"
            enhanced_messages = [
                {"role": "system", "content": system_with_context}
            ] + messages

            return self.llm.chat(enhanced_messages)
        else:
            return self.llm.chat(messages)
