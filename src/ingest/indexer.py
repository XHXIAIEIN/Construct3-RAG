"""
Vector Database Indexer for Construct 3 RAG
Indexes all processed data into Qdrant vector database
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
import hashlib

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from qdrant_client.http.models import Distance, VectorParams, PointStruct
except ImportError:
    print("Warning: qdrant-client not installed. Run: pip install qdrant-client")

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("Warning: sentence-transformers not installed. Run: pip install sentence-transformers")


# Query instruction for Qwen3-Embedding (applied only during retrieval, not indexing).
# Improves retrieval accuracy for asymmetric query-document pairs.
_QWEN3_QUERY_INSTRUCTION = (
    "Instruct: Retrieve relevant Construct 3 documentation for the following query\nQuery: "
)


class EmbeddingModel:
    """Wrapper for embedding model.

    Supports three backends:
    - Qwen3-Embedding (default): SentenceTransformer with query instruction, trust_remote_code=True
    - bge-m3 native sparse: FlagEmbedding BGEM3FlagModel with dense + lexical sparse vectors
    - Other models: plain SentenceTransformer
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-Embedding-0.6B",
        device: str = "cpu",
        native_sparse: bool = False,
    ):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._is_qwen3 = "qwen3-embedding" in model_name.lower()
        self._is_bge_m3_native = (model_name == "BAAI/bge-m3") and native_sparse

    @property
    def model(self):
        if self._model is None:
            if self._is_bge_m3_native:
                try:
                    from FlagEmbedding import BGEM3FlagModel
                    self._model = BGEM3FlagModel(
                        self.model_name, use_fp16=True, device=self.device
                    )
                except ImportError:
                    print(
                        "Warning: FlagEmbedding not installed. "
                        "Falling back to SentenceTransformer (no native sparse). "
                        "Run: pip install FlagEmbedding"
                    )
                    self._is_bge_m3_native = False
                    self._model = SentenceTransformer(self.model_name, device=self.device)
            elif self._is_qwen3:
                self._model = SentenceTransformer(
                    self.model_name, device=self.device, trust_remote_code=True
                )
            else:
                self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def encode(self, texts: List[str], batch_size: int = 8) -> List[List[float]]:
        """Encode document texts to dense vectors (no instruction prefix)."""
        if self._is_bge_m3_native:
            output = self.model.encode(
                texts, batch_size=batch_size,
                return_dense=True, return_sparse=False, return_colbert_vecs=False,
            )
            return output["dense_vecs"].tolist()
        return self.model.encode(
            texts, show_progress_bar=False, batch_size=batch_size
        ).tolist()

    def encode_single(self, text: str) -> List[float]:
        """Encode a single query to a dense vector (with instruction prefix for Qwen3)."""
        if self._is_bge_m3_native:
            output = self.model.encode(
                [text], return_dense=True, return_sparse=False, return_colbert_vecs=False
            )
            return output["dense_vecs"][0].tolist()
        if self._is_qwen3:
            return self.model.encode(
                _QWEN3_QUERY_INSTRUCTION + text, show_progress_bar=False
            ).tolist()
        return self.model.encode([text], show_progress_bar=False)[0].tolist()

    def encode_sparse(self, texts: List[str]) -> Optional[List[dict]]:
        """Return sparse vectors as list of {token_id: weight} dicts.

        Returns None when the backend does not support native sparse retrieval.
        Only available when EMBEDDING_MODEL=BAAI/bge-m3 and BGE_M3_NATIVE_SPARSE=true.
        """
        if not self._is_bge_m3_native:
            return None
        output = self.model.encode(
            texts, return_dense=False, return_sparse=True, return_colbert_vecs=False
        )
        return [dict(w) for w in output["lexical_weights"]]

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        if self._is_bge_m3_native:
            return 1024  # bge-m3 dense dimension is always 1024
        return self.model.get_sentence_embedding_dimension()


class BM25Vectorizer:
    """
    Simple BM25 vectorizer for sparse vector indexing.
    Produces {term_index: bm25_score} dicts compatible with Qdrant sparse vectors.

    k1=1.5, b=0.75 (standard BM25 parameters)
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.vocab: dict[str, int] = {}
        self.idf: dict[int, float] = {}
        self._avg_dl: float = 0.0
        self._fitted = False

    def _tokenize(self, text: str) -> list[str]:
        import jieba
        return [t for t in jieba.cut(text) if len(t.strip()) > 1]

    def fit(self, corpus: list[str]) -> "BM25Vectorizer":
        """Build vocabulary and IDF from corpus."""
        import math
        tokenized = [self._tokenize(doc) for doc in corpus]
        N = len(tokenized)
        self._avg_dl = sum(len(d) for d in tokenized) / max(N, 1)

        all_terms: set[str] = set()
        for doc in tokenized:
            all_terms.update(doc)
        self.vocab = {t: i for i, t in enumerate(sorted(all_terms))}

        df: dict[int, int] = {}
        for doc in tokenized:
            seen: set[int] = set()
            for t in doc:
                idx = self.vocab[t]
                if idx not in seen:
                    df[idx] = df.get(idx, 0) + 1
                    seen.add(idx)

        self.idf = {
            idx: math.log(1 + (N - freq + 0.5) / (freq + 0.5))
            for idx, freq in df.items()
        }
        self._fitted = True
        return self

    def encode(self, text: str) -> dict[int, float]:
        """Encode text to BM25 sparse vector {term_index: score}."""
        if not self._fitted:
            return {}
        tokens = self._tokenize(text)
        dl = len(tokens)
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1

        vec: dict[int, float] = {}
        for term, freq in tf.items():
            if term not in self.vocab:
                continue
            idx = self.vocab[term]
            idf = self.idf.get(idx, 0.0)
            tf_norm = (freq * (self.k1 + 1)) / (
                freq + self.k1 * (1 - self.b + self.b * dl / max(self._avg_dl, 1))
            )
            score = idf * tf_norm
            if score > 0:
                vec[idx] = round(score, 6)
        return vec

    def save(self, path: Path) -> None:
        """Persist vocab and IDF to JSON for later loading by the retriever."""
        data = {
            "vocab": self.vocab,
            "idf": {str(k): v for k, v in self.idf.items()},
            "avg_dl": self._avg_dl,
        }
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        print(f"[BM25] Saved vocab ({len(self.vocab)} terms) → {path}")

    def load(self, path: Path) -> "BM25Vectorizer":
        """Load vocab and IDF from JSON file."""
        data = json.loads(path.read_text(encoding="utf-8"))
        self.vocab = data["vocab"]
        self.idf = {int(k): v for k, v in data["idf"].items()}
        self._avg_dl = data["avg_dl"]
        self._fitted = True
        print(f"[BM25] Loaded vocab ({len(self.vocab)} terms) from {path}")
        return self


class Indexer:
    """Index documents into Qdrant vector database"""

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    ):
        from src.config import BGE_M3_NATIVE_SPARSE
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
        self.client = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.embedder = EmbeddingModel(
            embedding_model, device=device, native_sparse=BGE_M3_NATIVE_SPARSE
        )
        self._bm25: BM25Vectorizer | None = None

    def _generate_id(self, text: str) -> str:
        """Generate stable ID from text"""
        return hashlib.md5(text.encode()).hexdigest()

    def fit_bm25(self, corpus: list[str], vocab_path: Path | None = None) -> None:
        """Fit BM25 on corpus and save vocab to disk for retriever use."""
        from src.config import DATA_DIR, BM25_ENABLED
        if not BM25_ENABLED:
            return
        print(f"[BM25] Fitting on {len(corpus)} documents...")
        self._bm25 = BM25Vectorizer()
        self._bm25.fit(corpus)
        path = vocab_path or (DATA_DIR / "bm25_vocab.json")
        self._bm25.save(path)

    def create_collection(self, collection_name: str, recreate: bool = False):
        """Create or recreate a collection.

        When BM25_ENABLED: uses named dense + sparse vectors.
        Otherwise:         uses a single unnamed dense vector (legacy).
        """
        from src.config import BM25_ENABLED
        collections = [c.name for c in self.client.get_collections().collections]

        if collection_name in collections:
            if recreate:
                print(f"Deleting existing collection: {collection_name}")
                self.client.delete_collection(collection_name)
            else:
                print(f"Collection already exists: {collection_name}")
                return

        print(f"Creating collection: {collection_name}")
        if BM25_ENABLED:
            from qdrant_client.http.models import SparseVectorParams, SparseIndexParams
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config={"dense": VectorParams(
                    size=self.embedder.dimension,
                    distance=Distance.COSINE
                )},
                sparse_vectors_config={"sparse": SparseVectorParams(
                    index=SparseIndexParams()
                )},
            )
        else:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=self.embedder.dimension,
                    distance=Distance.COSINE
                )
            )

    def index_documents(
        self,
        collection_name: str,
        documents: List[Dict[str, Any]],
        batch_size: int = 100
    ):
        """Index documents into collection.

        When self._bm25 is fitted (BM25_ENABLED=True), each point is stored
        with both a named dense vector and a named sparse vector.
        """
        from src.config import BM25_ENABLED
        use_native_sparse = self.embedder._is_bge_m3_native
        use_bm25 = BM25_ENABLED and self._bm25 is not None and not use_native_sparse
        use_sparse = use_native_sparse or use_bm25
        label = " [dense+native-sparse]" if use_native_sparse else (" [dense+bm25]" if use_bm25 else "")
        print(f"Indexing {len(documents)} documents to {collection_name}{label}")

        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            texts = [doc["text"] for doc in batch]
            dense_vectors = self.embedder.encode(texts)
            sparse_vecs = self.embedder.encode_sparse(texts) if use_native_sparse else None

            points = []
            for j, (doc, dense_vec) in enumerate(zip(batch, dense_vectors)):
                point_id = doc.get("id", self._generate_id(doc["text"]))
                if isinstance(point_id, str):
                    point_id = int(hashlib.md5(point_id.encode()).hexdigest()[:15], 16)

                if use_sparse:
                    from qdrant_client.http.models import SparseVector
                    if use_native_sparse and sparse_vecs:
                        sv = sparse_vecs[j]
                    else:
                        sv = self._bm25.encode(doc["text"])
                    vector = {
                        "dense": dense_vec,
                        "sparse": SparseVector(
                            indices=list(sv.keys()),
                            values=list(sv.values()),
                        ),
                    }
                else:
                    vector = dense_vec

                points.append(PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={"text": doc["text"], **doc.get("metadata", {})}
                ))

            self.client.upsert(collection_name=collection_name, points=points)

            if (i + batch_size) % 500 == 0:
                print(f"  Indexed {i + batch_size}/{len(documents)}")

        print(f"  Completed indexing {len(documents)} documents")

    def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for similar documents"""
        query_vector = self.embedder.encode_single(query)

        results = self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k
        )

        return [
            {
                "score": result.score,
                "text": result.payload.get("text", ""),
                "metadata": {k: v for k, v in result.payload.items() if k != "text"}
            }
            for result in results
        ]

    def _load_chunk_contexts(self, cache_path=None) -> None:
        """Load pre-generated contextual chunk summaries from JSON cache."""
        from src.config import CONTEXTUAL_CHUNKING_CACHE
        path = Path(cache_path or CONTEXTUAL_CHUNKING_CACHE)
        if path.exists():
            self._chunk_contexts = json.loads(path.read_text(encoding="utf-8"))
            print(f"[ContextualChunking] Loaded {len(self._chunk_contexts)} contexts from {path}")
        else:
            self._chunk_contexts = {}
            print(f"[ContextualChunking] Cache not found at {path}, using raw chunks")

    def _prepend_context(self, chunk_key: str, chunk_text: str) -> str:
        """Prepend cached context summary to chunk text for embedding."""
        ctx = getattr(self, "_chunk_contexts", {}).get(chunk_key, "")
        return ctx + chunk_text if ctx else chunk_text


def index_scripting_api(indexer: "Indexer", collection: str):
    """Index Scripting API reference from d.ts files"""
    from src.config import DATA_DIR

    api_json = DATA_DIR / "scripting-api-reference.json"
    if not api_json.exists():
        print("  Scripting API reference not found, skipping...")
        return

    import json
    data = json.loads(api_json.read_text(encoding='utf-8'))

    docs = []

    for class_name, cls in data.items():
        # 创建类的概述文档
        props = cls.get("properties", [])
        methods = cls.get("methods", [])

        overview = f"脚本接口 {class_name}"
        if cls.get("extends"):
            overview += f" (继承自 {cls['extends']})"
        overview += f": {len(props)} 个属性, {len(methods)} 个方法。\n"

        # 属性列表
        if props:
            prop_names = [f"{p['name']}: {p['type']}" for p in props[:10]]
            overview += "属性: " + ", ".join(prop_names)
            if len(props) > 10:
                overview += f" ... 等 {len(props)} 个"
            overview += "\n"

        # 方法列表
        if methods:
            method_sigs = []
            for m in methods[:10]:
                params = ", ".join([f"{p['name']}: {p['type']}" for p in m.get('params', [])])
                method_sigs.append(f"{m['name']}({params})")
            overview += "方法: " + ", ".join(method_sigs)
            if len(methods) > 10:
                overview += f" ... 等 {len(methods)} 个"

        docs.append({
            "id": f"api_{class_name}",
            "text": overview,
            "metadata": {
                "source": "scripting-api",
                "class_name": class_name,
                "extends": cls.get("extends", ""),
                "properties_count": len(props),
                "methods_count": len(methods)
            }
        })

    print(f"  Found {len(docs)} API classes")
    if docs:
        indexer.index_documents(collection, docs)


def index_ace_reference(indexer: "Indexer", collection: str, rebuild: bool = False):
    """Index ACE reference document (legacy)"""
    from src.config import DATA_DIR

    ace_json = DATA_DIR / "ace-reference.json"
    if not ace_json.exists():
        print("  ACE reference not found, skipping...")
        return

    import json
    data = json.loads(ace_json.read_text(encoding='utf-8'))

    docs = []

    # Process plugins
    for name, obj in data.get("plugins", {}).items():
        # Create overview doc
        c_count = len(obj.get("conditions", []))
        a_count = len(obj.get("actions", []))
        e_count = len(obj.get("expressions", []))

        overview = f"插件 {name}: {c_count} 个条件, {a_count} 个动作, {e_count} 个表达式。"

        # Conditions
        if obj.get("conditions"):
            cond_text = "条件: " + ", ".join([c["name"] for c in obj["conditions"]])
            overview += "\n" + cond_text

        # Actions
        if obj.get("actions"):
            act_text = "动作: " + ", ".join([a["name"] for a in obj["actions"]])
            overview += "\n" + act_text

        # Expressions
        if obj.get("expressions"):
            expr_text = "表达式: " + ", ".join([e["name"] for e in obj["expressions"]])
            overview += "\n" + expr_text

        docs.append({
            "id": f"ace_plugin_{name}",
            "text": overview,
            "metadata": {
                "source": "ace-reference",
                "object_name": name,
                "object_type": "plugin",
                "conditions_count": c_count,
                "actions_count": a_count,
                "expressions_count": e_count
            }
        })

    # Process behaviors
    for name, obj in data.get("behaviors", {}).items():
        c_count = len(obj.get("conditions", []))
        a_count = len(obj.get("actions", []))
        e_count = len(obj.get("expressions", []))

        overview = f"行为 {name}: {c_count} 个条件, {a_count} 个动作, {e_count} 个表达式。"

        if obj.get("conditions"):
            cond_text = "条件: " + ", ".join([c["name"] for c in obj["conditions"]])
            overview += "\n" + cond_text

        if obj.get("actions"):
            act_text = "动作: " + ", ".join([a["name"] for a in obj["actions"]])
            overview += "\n" + act_text

        if obj.get("expressions"):
            expr_text = "表达式: " + ", ".join([e["name"] for e in obj["expressions"]])
            overview += "\n" + expr_text

        docs.append({
            "id": f"ace_behavior_{name}",
            "text": overview,
            "metadata": {
                "source": "ace-reference",
                "object_name": name,
                "object_type": "behavior",
                "conditions_count": c_count,
                "actions_count": a_count,
                "expressions_count": e_count
            }
        })

    print(f"  Found {len(docs)} ACE entries")
    if docs:
        indexer.index_documents(collection, docs)


def index_properties_schema(indexer: "Indexer", collection: str, rebuild: bool = False):
    """Index plugin/behavior properties from Construct3-Schema into the ACE collection."""
    from src.ingest.schema_parser import SchemaParser

    print("  Parsing property schema from Construct3-Schema...")
    parser = SchemaParser()
    entries = parser.parse_properties()

    if not entries:
        print("  No property entries found, skipping...")
        return

    print(f"  Found {len(entries)} property entries")
    docs = parser.export_properties_for_vectordb(entries)
    indexer.index_documents(collection, docs)


def index_ace_schema(indexer: "Indexer", collection: str, rebuild: bool = False):
    """Index ACE schema from Construct3-Schema (使用 Schema 数据)"""
    from src.ingest.schema_parser import SchemaParser

    print(f"  Parsing ACE schema from Construct3-Schema...")
    parser = SchemaParser()
    entries = parser.parse_ace_entries()

    if not entries:
        print("  No ACE entries found, skipping...")
        return

    stats = parser.get_stats(entries)
    print(f"  Found {stats['total_aces']} ACE entries:")
    print(f"    - Conditions: {stats['by_type']['condition']}")
    print(f"    - Actions: {stats['by_type']['action']}")
    print(f"    - Expressions: {stats['by_type']['expression']}")
    print(f"    - Plugins: {stats['plugins']}, Behaviors: {stats['behaviors']}")

    docs = parser.export_ace_for_vectordb(entries)
    indexer.index_documents(collection, docs)


def index_effects_schema(indexer: "Indexer", collection: str, rebuild: bool = False):
    """Index effects schema from Construct3-Schema (使用 Schema 数据)"""
    from src.ingest.schema_parser import SchemaParser

    print(f"  Parsing Effects schema from Construct3-Schema...")
    parser = SchemaParser()
    entries = parser.parse_effects()

    if not entries:
        print("  No effect entries found, skipping...")
        return

    # 按分类统计
    by_category = {}
    for entry in entries:
        cat = entry.category or "other"
        by_category[cat] = by_category.get(cat, 0) + 1

    print(f"  Found {len(entries)} effects:")
    for cat, count in sorted(by_category.items()):
        print(f"    - {cat}: {count}")

    docs = parser.export_effects_for_vectordb(entries)
    indexer.index_documents(collection, docs)


def index_all_data(rebuild: bool = False):
    """Index all Construct 3 data into Qdrant."""
    from src.config import (
        QDRANT_HOST, QDRANT_PORT, EMBEDDING_MODEL,
        SOURCE_DIR, TRANSLATION_CSV,
        CONTEXTUAL_CHUNKING_ENABLED, BM25_ENABLED,
        EXAMPLE_PROJECTS_DIR,
        C3_VERSION, C3_CDN_BASE, C3_CACHE_DIR,
    )
    from src.collections import DOC_COLLECTIONS, ALL_COLLECTIONS, COLLECTIONS
    from src.ingest.markdown_parser import MarkdownParser
    from src.ingest.csv_parser import CSVParser
    from src.ingest.c3_fetcher import C3Fetcher

    # Initialize CDN fetcher for ACE schemas and example metadata
    fetcher = C3Fetcher(version=C3_VERSION, base_url=C3_CDN_BASE, cache_dir=C3_CACHE_DIR)
    print(f"[CDN] Construct 3 version: {C3_VERSION}")

    # Export CDN data to per-plugin JSON (for lookup.py / query_expander.py)
    schemas_dir = fetcher.export_schemas()
    print(f"[CDN] Schemas exported to {schemas_dir}")

    indexer = Indexer(
        qdrant_host=QDRANT_HOST,
        qdrant_port=QDRANT_PORT,
        embedding_model=EMBEDDING_MODEL
    )

    if CONTEXTUAL_CHUNKING_ENABLED:
        indexer._load_chunk_contexts()

    # ── Parse markdown docs ────────────────────────────────────────────────────
    print("\n=== Parsing Markdown Documentation ===")
    md_parser = MarkdownParser()
    all_chunks = md_parser.parse_directory()

    chunks_by_collection: dict[str, list] = {col: [] for col in DOC_COLLECTIONS}
    for chunk in all_chunks:
        col = chunk.metadata.get("collection")
        if col in chunks_by_collection:
            chunks_by_collection[col].append(chunk)

    # ── BM25: collect full corpus and fit ─────────────────────────────────────
    if BM25_ENABLED:
        print("\n=== Fitting BM25 on full corpus ===")
        from src.ingest.examples_parser import load_examples_for_vectordb
        from src.ingest.schema_parser import SchemaParser
        corpus: list[str] = [c.text for c in all_chunks]
        try:
            corpus += [d["text"] for d in load_examples_for_vectordb(fetcher=fetcher)]
        except FileNotFoundError:
            pass
        sp = SchemaParser(fetcher=fetcher)
        corpus += [d["text"] for d in sp.export_ace_for_vectordb()]
        corpus += [d["text"] for d in sp.export_effects_for_vectordb()]
        corpus += [d["text"] for d in sp.export_properties_for_vectordb()]
        csv_parser_bm25 = CSVParser()
        csv_path_bm25 = SOURCE_DIR / TRANSLATION_CSV
        if csv_path_bm25.exists():
            csv_parser_bm25.parse_file(csv_path_bm25)
            corpus += [d["text"] for d in csv_parser_bm25.export_for_vectordb()]
        indexer.fit_bm25(corpus)

    # ── Index each markdown doc collection ────────────────────────────────────
    for collection in DOC_COLLECTIONS:
        chunks = chunks_by_collection[collection]
        print(f"\n=== Indexing {collection} ({len(chunks)} chunks) ===")
        indexer.create_collection(collection, recreate=rebuild)
        if chunks:
            docs = []
            for i, chunk in enumerate(chunks):
                chunk_key = hashlib.md5(chunk.text[:500].encode()).hexdigest()
                text = indexer._prepend_context(chunk_key, chunk.text)
                docs.append({"id": f"{collection}_{i}", "text": text, "metadata": chunk.metadata})
            indexer.index_documents(collection, docs)

    # ── Translation terms (via CSVParser.export_for_vectordb) ─────────────────
    print("\n=== Indexing Translation Terms ===")
    indexer.create_collection(COLLECTIONS["terms"], recreate=rebuild)
    csv_parser = CSVParser()
    csv_path = SOURCE_DIR / TRANSLATION_CSV
    if csv_path.exists():
        csv_parser.parse_file(csv_path)
        indexer.index_documents(COLLECTIONS["terms"], csv_parser.export_for_vectordb())

    # ── Example projects ──────────────────────────────────────────────────────
    print("\n=== Indexing Example Projects ===")
    indexer.create_collection(COLLECTIONS["examples"], recreate=rebuild)
    from src.ingest.examples_parser import load_examples_for_vectordb
    from src.ingest.event_parser import load_event_and_script_docs
    try:
        # 1. Project metadata (from CDN + c3proj)
        example_docs = load_examples_for_vectordb(fetcher=fetcher)
        if example_docs:
            indexer.index_documents(COLLECTIONS["examples"], example_docs)
            print(f"  Indexed {len(example_docs)} project metadata docs")

        # 2. Event blocks + scripts (from actual project files)
        if EXAMPLE_PROJECTS_DIR.exists():
            slug_title_map = {
                d["metadata"]["slug"]: {
                    "title_en": d["metadata"]["title_en"],
                    "title_zh": d["metadata"]["title_zh"],
                }
                for d in example_docs
                if d["metadata"].get("slug")
            }
            event_docs = load_event_and_script_docs(EXAMPLE_PROJECTS_DIR, slug_title_map)
            if event_docs:
                indexer.index_documents(COLLECTIONS["examples"], event_docs)
                print(f"  Indexed {len(event_docs)} event/script docs")
        else:
            print(f"  Skipping event/script indexing: {EXAMPLE_PROJECTS_DIR} not found")

    except FileNotFoundError as e:
        print(f"  Skipping examples: {e}")

    # ── ACE Schema (from CDN) ─────────────────────────────────────────────────
    print(f"\n=== Indexing ACE Schema (from CDN {C3_VERSION}) ===")
    indexer.create_collection(COLLECTIONS["ace"], recreate=rebuild)
    from src.ingest.schema_parser import SchemaParser
    schema_parser = SchemaParser(fetcher=fetcher)
    ace_entries = schema_parser.parse_ace_entries()
    ace_docs = schema_parser.export_ace_for_vectordb(ace_entries)
    indexer.index_documents(COLLECTIONS["ace"], ace_docs)
    print(f"  Indexed {len(ace_docs)} ACE docs")

    # ── Plugin/Behavior Properties (from CDN) ─────────────────────────────────
    print(f"\n=== Indexing Properties (from CDN {C3_VERSION}) ===")
    prop_docs = schema_parser.export_properties_for_vectordb()
    if prop_docs:
        indexer.index_documents(COLLECTIONS["ace"], prop_docs)
        print(f"  Indexed {len(prop_docs)} property docs")

    # ── Effects Schema (from CDN) ──────────────────────────────────────────────
    print(f"\n=== Indexing Effects (from CDN {C3_VERSION}) ===")
    indexer.create_collection(COLLECTIONS["effects"], recreate=rebuild)
    effect_docs = schema_parser.export_effects_for_vectordb()
    if effect_docs:
        indexer.index_documents(COLLECTIONS["effects"], effect_docs)
        print(f"  Indexed {len(effect_docs)} effect docs")

    # ── Scripting API (append to markdown-indexed c3_scripting) ──────────────
    print("\n=== Indexing Scripting API ===")
    # NOTE: Do NOT recreate here — markdown scripting docs are already indexed
    # in the DOC_COLLECTIONS loop above. This only appends structured API data.
    index_scripting_api(indexer, COLLECTIONS["scripting"])

    print("\n=== Indexing Complete ===")
    for collection in ALL_COLLECTIONS:
        try:
            info = indexer.client.get_collection(collection)
            print(f"  {collection}: {info.points_count} vectors")
        except Exception:
            pass


if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Index Construct 3 data into Qdrant")
    parser.add_argument("--rebuild", action="store_true", help="Recreate collections")
    args = parser.parse_args()

    index_all_data(rebuild=args.rebuild)
