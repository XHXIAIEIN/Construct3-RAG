"""
RAG Chain for Construct 3 Assistant
Combines retrieval with LLM generation
"""
import time
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .retriever import HybridRetriever, SearchResult
from .prompts import QA_PROMPT, TRANSLATION_PROMPT, EVENT_GENERATION_PROMPT, SYSTEM_MESSAGE

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

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        llm_model: str = "qwen2.5:14b",
        llm_base_url: str = "http://localhost:11434"
    ):
        self.retriever = HybridRetriever(qdrant_host, qdrant_port)
        self.llm = LLMClient(model=llm_model, base_url=llm_base_url)

    def classify_query(self, query: str) -> str:
        """Classify query type (qa/translation/code)"""
        query_lower = query.lower()

        # Simple rule-based classification
        if any(kw in query_lower for kw in ["翻译", "translate", "怎么说", "英文", "中文"]):
            return "translation"
        elif any(kw in query_lower for kw in ["生成", "写一个", "帮我写", "事件表", "代码"]):
            return "code"
        else:
            return "qa"

    def answer_qa(self, query: str) -> RAGResponse:
        """Answer general Q&A queries"""
        # Retrieve relevant context
        logger.info(f"[1/3] 检索相关文档... 查询: {query[:50]}...")
        t0 = time.time()
        results = self.retriever.search_all(query, top_k_per_collection=3)
        logger.info(f"[1/3] 检索完成 ({time.time()-t0:.1f}s)")

        context = self.retriever.format_context(results)

        # Generate answer
        logger.info(f"[2/3] LLM 生成回答...")
        t0 = time.time()
        prompt = QA_PROMPT.format(context=context, question=query)
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

        return RAGResponse(answer=answer, sources=sources, query_type="qa")

    def answer_translation(self, query: str) -> RAGResponse:
        """Handle translation queries"""
        # Search terms collection
        results = self.retriever.search_terms(query, top_k=10)

        # Format matched terms
        matched_terms = "\n".join([
            f"- {r.metadata.get('zh', '')} = {r.metadata.get('en', '')}"
            for r in results
        ])

        # Detect source language and target
        is_chinese = any('\u4e00' <= c <= '\u9fff' for c in query)
        target_lang = "英文" if is_chinese else "中文"

        prompt = TRANSLATION_PROMPT.format(
            matched_terms=matched_terms,
            source_text=query,
            target_lang=target_lang
        )
        answer = self.llm.generate(prompt)

        sources = [{"type": "terms", "text": r.text, "score": r.score} for r in results]
        return RAGResponse(answer=answer, sources=sources, query_type="translation")

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

        if query_type == "translation":
            return self.answer_translation(query)
        elif query_type == "code":
            return self.answer_code(query)
        else:
            return self.answer_qa(query)

    def answer_stream(self, query: str):
        """
        Streaming version of answer - yields chunks as they're generated
        """
        query_type = self.classify_query(query)

        # Retrieve context first
        if query_type == "translation":
            results = self.retriever.search_terms(query, top_k=10)
            matched_terms = "\n".join([
                f"- {r.metadata.get('zh', '')} = {r.metadata.get('en', '')}"
                for r in results
            ])
            is_chinese = any('\u4e00' <= c <= '\u9fff' for c in query)
            target_lang = "英文" if is_chinese else "中文"
            from .prompts import TRANSLATION_PROMPT
            prompt = TRANSLATION_PROMPT.format(
                matched_terms=matched_terms,
                source_text=query,
                target_lang=target_lang
            )
            system = ""
        elif query_type == "code":
            results = self.retriever.search_examples(query, top_k=5)
            examples = "\n\n".join([
                f"### {r.metadata.get('project', 'Example')}\n{r.text}"
                for r in results
            ])
            from .prompts import EVENT_GENERATION_PROMPT
            prompt = EVENT_GENERATION_PROMPT.format(
                similar_examples=examples,
                user_requirement=query
            )
            system = ""
        else:
            results = self.retriever.search_all(query, top_k_per_collection=3)
            context = self.retriever.format_context(results)
            from .prompts import QA_PROMPT
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
