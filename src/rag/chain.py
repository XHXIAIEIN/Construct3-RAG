"""
RAG Chain for Construct 3 Assistant
Combines retrieval with LLM generation
With anti-hallucination features:
- Increased retrieval (top_k=5 per collection)
- Cross-collection reranking
- Self-reflection verification
- Strict prompting with forced citations
"""
import time
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .retriever import HybridRetriever, SearchResult
from .prompts import (
    QA_PROMPT, EVENT_GENERATION_PROMPT, SYSTEM_MESSAGE,
    LOW_RELEVANCE_PROMPT, NO_RESULTS_RESPONSE, QUERY_REWRITE_PROMPT,
    STRICT_QA_PROMPT, SELF_REFLECTION_PROMPT, ANSWER_VERIFICATION_PROMPT,
    QUERY_DECOMPOSITION_PROMPT, LLM_UNAVAILABLE_RESPONSE,
    QDRANT_UNAVAILABLE_RESPONSE, LOW_CONFIDENCE_WARNING
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
    confidence: str = "unknown"  # high / medium / low
    verification_notes: str = ""


class LLMClient:
    """
    Client for LLM inference (Ollama or OpenAI-compatible).

    Includes health checking and graceful fallback support.

    Example:
        >>> llm = LLMClient(model="qwen2.5:7b")
        >>> available, msg = llm.check_health()
        >>> if available:
        ...     response = llm.generate("Hello")
        ... else:
        ...     print(f"LLM unavailable: {msg}")
    """

    def __init__(
        self,
        model: str = "qwen2.5:14b",
        base_url: str = "http://localhost:11434"
    ):
        self.model = model
        self.base_url = base_url
        self._client = None
        self._available = None  # Cache health status

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

    def check_health(self) -> tuple[bool, str]:
        """
        Check if LLM service is available.

        Returns:
            Tuple of (is_available, status_message)

        Example:
            >>> llm = LLMClient()
            >>> available, msg = llm.check_health()
            >>> if not available:
            ...     # Use fallback response
            ...     return LLM_UNAVAILABLE_RESPONSE.format(sources_summary="...")
        """
        if self.client is None:
            self._available = False
            return False, "Ollama client not installed"

        try:
            # Try to list models as health check
            self.client.list()
            self._available = True
            return True, "LLM service is healthy"
        except Exception as e:
            self._available = False
            return False, f"LLM connection failed: {str(e)}"

    @property
    def is_available(self) -> bool:
        """Check if LLM is available (uses cached status if recent)."""
        if self._available is None:
            self.check_health()
        return self._available or False

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
    With anti-hallucination features:
    1. Increased retrieval (top_k=5 per collection)
    2. Cross-collection reranking
    3. Self-reflection verification
    4. Strict prompting
    """

    # 检索结果阈值配置
    MIN_RESULTS_THRESHOLD = 3  # 低于此数量视为低相关度
    HIGH_SCORE_THRESHOLD = 0.7  # 高置信度分数阈值
    STRICT_MODE = True  # 启用严格模式（强制引用）

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
        return sub_queries[:4]  # 最多 4 个子问题

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
        # Indicators of complex queries
        complexity_indicators = [
            # Multi-step keywords
            "步骤", "流程", "实现", "workflow", "how to",
            # Multiple concepts
            "和", "以及", "同时", "并且", "both", "and",
            # Combined operations
            "然后", "之后", "接着", "first", "then",
        ]

        query_lower = query.lower()

        # Check for complexity indicators
        indicator_count = sum(1 for ind in complexity_indicators if ind in query_lower)

        # Check query length (longer queries tend to be more complex)
        word_count = len(query.split())

        return indicator_count >= 2 or word_count > 15

    def _format_sources_summary(self, results: List[SearchResult]) -> str:
        """Format search results as a readable summary for fallback responses."""
        if not results:
            return "无相关文档"

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
        """
        logger.info(f"[反思] 开始验证回答可靠性...")
        prompt = SELF_REFLECTION_PROMPT.format(
            question=query,
            answer=answer,
            source_context=context
        )

        reflection = self.llm.generate(prompt)

        is_reliable = False
        if "可靠" in reflection and "不可靠" not in reflection:
            is_reliable = True
        elif "不可靠" in reflection and "可靠" not in reflection:
            is_reliable = False
        else:
            is_reliable = "可靠" in reflection.split("不可靠")[0]

        logger.info(f"[反思] 可靠性: {'可靠' if is_reliable else '不可靠'}")

        return reflection, is_reliable

    def _verify_answer(self, query: str, answer: str) -> str:
        """Verify answer quality and return feedback"""
        prompt = ANSWER_VERIFICATION_PROMPT.format(
            question=query,
            answer=answer
        )

        result = self.llm.generate(prompt)
        return result

    def _format_reranked_context(self, results: List[SearchResult]) -> str:
        """Format reranked results as context with clear numbering"""
        context_parts = []

        def format_reranked_result(r: SearchResult, idx: int) -> str:
            source = r.metadata.get("source", "")
            if source.endswith(".md"):
                source_path = source[:-3]
            else:
                source_path = source
            breadcrumb = source_path.replace("/", " > ")

            h2 = r.metadata.get("h2_heading", "")
            header = f"[{idx}] {breadcrumb}"
            if h2:
                header += f" > {h2}"

            return f"{header}\n{r.text}\n来源: {source}\n"

        # Show all results (not just top 5) to avoid hallucinated citations
        if results:
            context_parts.append(f"## 参考资料（共 {len(results)} 条）\n")
            for i, r in enumerate(results, start=1):
                context_parts.append(format_reranked_result(r, i))

        return "\n".join(context_parts)

    def classify_query(self, query: str) -> str:
        """Classify query type (qa/code)"""
        query_lower = query.lower()

        # Simple rule-based classification
        if any(kw in query_lower for kw in ["生成", "写一个", "帮我写", "事件表", "代码"]):
            return "code"
        else:
            return "qa"

    def answer_qa(self, query: str, retry_count: int = 0, use_strict_mode: bool = True) -> RAGResponse:
        """Answer general Q&A queries with anti-hallucination measures"""
        # Step 1: Retrieve with increased top_k and reranking
        logger.info(f"[1/4] 检索相关文档... 查询: {query[:50]}...")
        t0 = time.time()

        # Try original query first
        results = self.retriever.search_all_with_rerank(
            query,
            top_k_per_collection=5,  # Increased from 2
            final_top_k=10
        )
        logger.info(f"[1/4] 检索完成 ({time.time()-t0:.1f}s), 找到 {len(results)} 条")

        # If no results, try query rewrite
        if len(results) == 0:
            if self.enable_query_rewrite and retry_count == 0:
                logger.info("[1/4] 未找到结果，尝试改写查询...")
                rewritten_queries = self._rewrite_query(query)
                logger.info(f"[1/4] 改写查询: {rewritten_queries}")

                for rq in rewritten_queries:
                    retry_results = self.retriever.search_all_with_rerank(
                        rq, top_k_per_collection=5, final_top_k=10
                    )
                    if len(retry_results) > 0:
                        logger.info(f"[1/4] 改写查询 '{rq}' 找到结果")
                        results = retry_results
                        break

            if len(results) == 0:
                logger.info("[1/4] 改写后仍无结果，返回无结果提示")
                return RAGResponse(
                    answer=NO_RESULTS_RESPONSE,
                    sources=[],
                    query_type="qa_no_results",
                    confidence="none"
                )

        # Step 2: Format context
        context = self._format_reranked_context(results)

        # Step 3: Generate answer with strict mode (anti-hallucination)
        logger.info(f"[2/4] LLM 生成回答 (严格模式: {use_strict_mode})...")
        t0 = time.time()

        if use_strict_mode and self.STRICT_MODE:
            prompt = STRICT_QA_PROMPT.format(context=context, question=query)
        else:
            prompt = QA_PROMPT.format(context=context, question=query)

        answer = self.llm.generate(prompt, system=SYSTEM_MESSAGE)
        logger.info(f"[2/4] 生成完成 ({time.time()-t0:.1f}s)")

        # Step 4: Self-reflection verification
        logger.info(f"[3/4] Self-Reflection 验证...")
        reflection, is_reliable = self._self_reflect(query, answer, context)

        # If unreliable, try with more context
        confidence = "high" if is_reliable else "medium"
        verification_notes = ""

        if not is_reliable and retry_count < 1:
            logger.info(f"[3/4] 初始回答不可靠，尝试改进...")
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
                    logger.info(f"[3/4] 改进后回答可靠")
                else:
                    verification_notes = f"初步验证发现问题:\n{reflection}\n\n改进后:\n{reflection2}"
            else:
                verification_notes = f"初步验证发现问题:\n{reflection}"

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

        logger.info(f"[4/4] 完成，回答置信度: {confidence}")

        return RAGResponse(
            answer=answer,
            sources=sources,
            query_type=query_type,
            confidence=confidence,
            verification_notes=verification_notes
        )

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
        return RAGResponse(
            answer=answer,
            sources=sources,
            query_type="code",
            confidence="medium",
            verification_notes="事件生成未经过 Self-Reflection 验证"
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

    def answer_high_confidence(self, query: str) -> RAGResponse:
        """
        High-confidence Q&A with maximum anti-hallucination measures.
        Use this for fact-critical questions.
        """
        # Multi-query retrieval for comprehensive coverage
        logger.info("[高置信度] 开始多查询检索...")
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

        # Use strict mode with expanded context
        context = self._format_reranked_context(unique_results)
        prompt = STRICT_QA_PROMPT.format(context=context, question=query)

        logger.info("[高置信度] 生成回答...")
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

    def answer_stream(self, query: str, use_strict_mode: bool = True):
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
            # QA with anti-hallucination retrieval
            results = self.retriever.search_all_with_rerank(
                query, top_k_per_collection=5, final_top_k=10
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

            context = self._format_reranked_context(results)

            # Select prompt based on mode
            if use_strict_mode and self.STRICT_MODE:
                prompt = STRICT_QA_PROMPT.format(context=context, question=query)
            else:
                prompt = QA_PROMPT.format(context=context, question=query)
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
            system_with_context = f"{SYSTEM_MESSAGE}\n\n## 参考资料（回答必须基于这些来源）\n{context}"
            enhanced_messages = [
                {"role": "system", "content": system_with_context}
            ] + messages

            return self.llm.chat(enhanced_messages)
        else:
            return self.llm.chat(messages)

    def answer_complex_workflow(self, query: str) -> RAGResponse:
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
        logger.info(f"[复杂查询] 开始处理: {query[:50]}...")

        # Step 1: Decompose query
        logger.info("[复杂查询] 分解查询...")
        sub_queries = self._decompose_query(query)
        logger.info(f"[复杂查询] 子查询: {sub_queries}")

        # Step 2: Retrieve for each sub-query
        all_result_lists: List[List[SearchResult]] = []

        # Original query
        original_results = self.retriever.search_all_with_rerank(
            query, top_k_per_collection=5, final_top_k=10
        )
        all_result_lists.append(original_results)

        # Sub-queries
        for sq in sub_queries:
            sq_results = self.retriever.search_all_with_rerank(
                sq, top_k_per_collection=3, final_top_k=8
            )
            if sq_results:
                all_result_lists.append(sq_results)
                logger.info(f"[复杂查询] 子查询 '{sq[:30]}...' 返回 {len(sq_results)} 条")

        # Step 3: Combine with RRF
        logger.info("[复杂查询] RRF 融合结果...")
        fused_results = self.retriever.reciprocal_rank_fusion(all_result_lists)

        # Step 4: Filter with adaptive threshold
        filtered_results = self.retriever.filter_by_adaptive_threshold(
            fused_results, min_results=5
        )
        logger.info(f"[复杂查询] 过滤后保留 {len(filtered_results)} 条")

        if not filtered_results:
            return RAGResponse(
                answer=NO_RESULTS_RESPONSE,
                sources=[],
                query_type="qa_complex_no_results",
                confidence="none"
            )

        # Step 5: Generate answer
        context = self._format_reranked_context(filtered_results[:15])
        prompt = STRICT_QA_PROMPT.format(context=context, question=query)

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

    def answer_with_fallback(self, query: str) -> RAGResponse:
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
            logger.warning(f"[Fallback] Qdrant 不可用: {qdrant_msg}")
            return RAGResponse(
                answer=QDRANT_UNAVAILABLE_RESPONSE,
                sources=[],
                query_type="fallback_qdrant_unavailable",
                confidence="none",
                verification_notes=qdrant_msg
            )

        # Retrieve results (Qdrant is available)
        results = self.retriever.search_all_with_rerank(
            query, top_k_per_collection=5, final_top_k=10
        )

        # Filter irrelevant results
        filtered_results = self.retriever.filter_by_adaptive_threshold(results)

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
            logger.warning(f"[Fallback] LLM 不可用: {llm_msg}")
            sources_summary = self._format_sources_summary(filtered_results)
            return RAGResponse(
                answer=LLM_UNAVAILABLE_RESPONSE.format(sources_summary=sources_summary),
                sources=sources,
                query_type="fallback_llm_unavailable",
                confidence="low",
                verification_notes=llm_msg
            )

        # No results found
        if not filtered_results:
            return RAGResponse(
                answer=NO_RESULTS_RESPONSE,
                sources=[],
                query_type="qa_no_results",
                confidence="none"
            )

        # Full answer generation (both services available)
        context = self._format_reranked_context(filtered_results)
        prompt = STRICT_QA_PROMPT.format(context=context, question=query)

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

        # Add low confidence warning if needed
        if not is_reliable:
            answer = answer + "\n\n" + LOW_CONFIDENCE_WARNING

        return RAGResponse(
            answer=answer,
            sources=sources,
            query_type="qa",
            confidence=confidence,
            verification_notes=reflection if not is_reliable else ""
        )

    def answer_smart(self, query: str) -> RAGResponse:
        """
        Smart answer routing with automatic complexity detection and fallback.

        This is the recommended entry point for production use. It:
        1. Detects query complexity
        2. Routes to appropriate handler (simple vs complex workflow)
        3. Provides graceful fallback on service failures
        4. Filters irrelevant results automatically

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
        # Route based on complexity
        if self._is_complex_query(query):
            logger.info(f"[Smart] 检测到复杂查询，使用分解策略")
            return self.answer_complex_workflow(query)
        else:
            logger.info(f"[Smart] 标准查询，使用 fallback 策略")
            return self.answer_with_fallback(query)
