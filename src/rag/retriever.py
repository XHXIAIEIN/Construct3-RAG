"""
Hybrid Retriever for Construct 3 RAG
Combines vector search with optional BM25 for better results
"""
import time
import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from qdrant_client import QdrantClient
except ImportError:
    print("Warning: qdrant-client not installed")


@dataclass
class SearchResult:
    """Represents a search result"""
    text: str
    score: float
    source: str  # collection name
    metadata: Dict[str, Any]


class HybridRetriever:
    """
    Hybrid retriever combining:
    - Vector search (semantic similarity)
    - Optional keyword matching for terms
    """

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        embedding_model_name: str = "BAAI/bge-m3"
    ):
        self.client = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.embedding_model_name = embedding_model_name
        self._embedder = None

    @property
    def embedder(self):
        if self._embedder is None:
            logger.info(f"[加载] Embedding 模型: {self.embedding_model_name} ...")
            t0 = time.time()
            from src.data_processing.indexer import EmbeddingModel
            self._embedder = EmbeddingModel(self.embedding_model_name, device="cpu")
            logger.info(f"[加载] Embedding 模型完成 ({time.time()-t0:.1f}s)")
        return self._embedder

    def search_collection(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.5
    ) -> List[SearchResult]:
        """Search a single collection"""
        query_vector = self.embedder.encode_single(query)

        try:
            results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=top_k,
                score_threshold=score_threshold
            )
        except Exception as e:
            print(f"Search error in {collection_name}: {e}")
            return []

        return [
            SearchResult(
                text=r.payload.get("text", ""),
                score=r.score,
                source=collection_name,
                metadata={k: v for k, v in r.payload.items() if k != "text"}
            )
            for r in results
        ]

    def search_guide(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search guide documentation (getting started, tips, overview)"""
        from src.collections import COLLECTIONS
        return self.search_collection(COLLECTIONS["guide"], query, top_k)

    def search_interface(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search interface documentation (editor UI, dialogs, debugger)"""
        from src.collections import COLLECTIONS
        return self.search_collection(COLLECTIONS["interface"], query, top_k)

    def search_project(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search project primitives (events, objects, timelines)"""
        from src.collections import COLLECTIONS
        return self.search_collection(COLLECTIONS["project"], query, top_k)

    def search_plugins(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search plugin reference documentation"""
        from src.collections import COLLECTIONS
        return self.search_collection(COLLECTIONS["plugins"], query, top_k)

    def search_behaviors(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search behavior reference documentation"""
        from src.collections import COLLECTIONS
        return self.search_collection(COLLECTIONS["behaviors"], query, top_k)

    def search_scripting(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search scripting API documentation"""
        from src.collections import COLLECTIONS
        return self.search_collection(COLLECTIONS["scripting"], query, top_k)

    def search_terms(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """Search translation terms"""
        from src.collections import COLLECTIONS
        return self.search_collection(COLLECTIONS["terms"], query, top_k, score_threshold=0.3)

    def search_examples(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search example projects"""
        from src.collections import COLLECTIONS
        return self.search_collection(COLLECTIONS["examples"], query, top_k)

    def search_all(
        self,
        query: str,
        top_k_per_collection: int = 5
    ) -> Dict[str, List[SearchResult]]:
        """Search all collections and return organized results"""
        results = {
            "guide": self.search_guide(query, top_k_per_collection),
            "interface": self.search_interface(query, top_k_per_collection),
            "project": self.search_project(query, top_k_per_collection),
            "plugins": self.search_plugins(query, top_k_per_collection),
            "behaviors": self.search_behaviors(query, top_k_per_collection),
            "scripting": self.search_scripting(query, top_k_per_collection),
            "terms": self.search_terms(query, top_k_per_collection),
            "examples": self.search_examples(query, top_k_per_collection)
        }
        return results

    def search_all_with_rerank(
        self,
        query: str,
        top_k_per_collection: int = 5,
        final_top_k: int = 10
    ) -> List[SearchResult]:
        """
        Search all collections with cross-collection reranking.

        Args:
            query: Search query
            top_k_per_collection: Results per collection before reranking
            final_top_k: Final number of results after reranking

        Returns:
            Reranked list of SearchResults
        """
        import time
        logger.info(f"[检索] 开始多 collection 检索 (每 collection top_k={top_k_per_collection})...")
        t0 = time.time()

        # Collect all results from all collections
        all_results: List[SearchResult] = []

        # Define collection mapping
        collection_map = {
            "guide": self.search_guide,
            "interface": self.search_interface,
            "project": self.search_project,
            "plugins": self.search_plugins,
            "behaviors": self.search_behaviors,
            "scripting": self.search_scripting,
            "terms": self.search_terms,
            "examples": self.search_examples,
        }

        for coll_name, search_fn in collection_map.items():
            try:
                results = search_fn(query, top_k_per_collection)
                for r in results:
                    all_results.append(r)
                logger.info(f"[检索] {coll_name}: {len(results)} 条")
            except Exception as e:
                logger.warning(f"[检索] {coll_name} 失败: {e}")

        logger.info(f"[检索] 原始结果共 {len(all_results)} 条 ({time.time()-t0:.1f}s)")

        if not all_results:
            return []

        # Cross-collection reranking using score normalization
        logger.info(f"[重排] 开始跨 collection 重排序...")

        # Compute min/max scores per collection for normalization
        collection_scores: Dict[str, List[float]] = {}
        for r in all_results:
            if r.source not in collection_scores:
                collection_scores[r.source] = []
            collection_scores[r.source].append(r.score)

        # Normalize scores and compute final score
        reranked: List[SearchResult] = []
        seen_texts: Set[str] = set()  # Deduplication

        for r in all_results:
            # Min-max normalization per collection
            coll_scores = collection_scores[r.source]
            min_s, max_s = min(coll_scores), max(coll_scores)
            if max_s > min_s:
                normalized = (r.score - min_s) / (max_s - min_s)
            else:
                normalized = r.score if max_s > 0 else 0

            # Boost for certain collections (more authoritative)
            collection_boost = {
                "c3_plugins": 1.1,
                "c3_behaviors": 1.1,
                "c3_project": 1.05,
            }
            boost = collection_boost.get(r.source, 1.0)
            final_score = normalized * boost

            # Deduplication by text content
            text_key = r.text[:100].lower().strip()
            if text_key not in seen_texts:
                seen_texts.add(text_key)
                reranked.append(SearchResult(
                    text=r.text,
                    score=final_score,
                    source=r.source,
                    metadata=r.metadata
                ))

        # Sort by final score and return top-k
        reranked.sort(key=lambda x: x.score, reverse=True)
        final_results = reranked[:final_top_k]

        logger.info(f"[重排] 完成，返回 top-{len(final_results)}")
        return final_results

    def format_context(self, results: Dict[str, List[SearchResult]]) -> str:
        """Format search results as context for LLM"""
        context_parts = []

        def format_doc_result(r: SearchResult) -> str:
            # 从 source 推导 breadcrumb: "plugin-reference/sprite.md" → "plugin-reference > sprite"
            source = r.metadata.get("source", "")
            if source.endswith(".md"):
                source_path = source[:-3]
            else:
                source_path = source
            breadcrumb = source_path.replace("/", " > ")

            h2 = r.metadata.get("h2_heading", "")
            header = f"[{breadcrumb}"
            if h2:
                header += f" > {h2}"
            header += "]"
            return f"{header}\n{r.text}\n来源: {source}\n"

        # Document collections with their display names
        doc_sections = [
            ("guide", "入门指南"),
            ("interface", "编辑器界面"),
            ("project", "项目元素"),
            ("plugins", "插件参考"),
            ("behaviors", "行为参考"),
            ("scripting", "脚本 API"),
        ]

        for key, title in doc_sections:
            if results.get(key):
                context_parts.append(f"\n### {title}\n")
                for r in results[key]:
                    context_parts.append(format_doc_result(r))

        # Term results
        if results.get("terms"):
            context_parts.append("\n### 术语表\n")
            for r in results["terms"]:
                zh = r.metadata.get("zh", "")
                en = r.metadata.get("en", "")
                context_parts.append(f"- {zh} = {en}")

        # Example results
        if results.get("examples"):
            context_parts.append("\n### 示例代码\n")
            for r in results["examples"]:
                project = r.metadata.get("project", "unknown")
                context_parts.append(f"[项目: {project}]\n{r.text}\n")

        return "\n".join(context_parts)


class TermMatcher:
    """
    Exact term matching for translation assistance
    Uses in-memory term dictionary for fast lookups
    """

    def __init__(self):
        self.terms: Dict[str, Dict[str, str]] = {}  # zh -> {en, key}
        self.terms_en: Dict[str, Dict[str, str]] = {}  # en -> {zh, key}
        self._loaded = False

    def load_terms(self, csv_path: str):
        """Load terms from CSV file"""
        from src.data_processing.csv_parser import CSVParser

        parser = CSVParser()
        entries = parser.parse_file(csv_path)

        for entry in entries:
            self.terms[entry.zh] = {"en": entry.en, "key": entry.term_key}
            self.terms_en[entry.en.lower()] = {"zh": entry.zh, "key": entry.term_key}

        self._loaded = True
        print(f"Loaded {len(self.terms)} terms for matching")

    def match_zh(self, text: str) -> List[Dict[str, str]]:
        """Find exact Chinese term matches in text"""
        matches = []
        for zh, data in self.terms.items():
            if zh in text:
                matches.append({
                    "zh": zh,
                    "en": data["en"],
                    "key": data["key"]
                })
        return matches

    def match_en(self, text: str) -> List[Dict[str, str]]:
        """Find exact English term matches in text"""
        matches = []
        text_lower = text.lower()
        for en, data in self.terms_en.items():
            if en in text_lower:
                matches.append({
                    "zh": data["zh"],
                    "en": en,
                    "key": data["key"]
                })
        return matches

    def translate(self, term: str, to_lang: str = "zh") -> Optional[str]:
        """Translate a single term"""
        if to_lang == "zh":
            data = self.terms_en.get(term.lower())
            return data["zh"] if data else None
        else:
            data = self.terms.get(term)
            return data["en"] if data else None
