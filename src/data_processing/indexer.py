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


class EmbeddingModel:
    """Wrapper for embedding model"""

    def __init__(self, model_name: str = "BAAI/bge-m3", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._model = None

    @property
    def model(self):
        if self._model is None:
            print(f"Loading embedding model: {self.model_name} (device: {self.device})")
            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def encode(self, texts: List[str], batch_size: int = 8) -> List[List[float]]:
        """Encode texts to vectors"""
        return self.model.encode(texts, show_progress_bar=True, batch_size=batch_size).tolist()

    def encode_single(self, text: str) -> List[float]:
        """Encode single text to vector"""
        return self.model.encode([text])[0].tolist()

    @property
    def dimension(self) -> int:
        """Get embedding dimension"""
        return self.model.get_sentence_embedding_dimension()


class Indexer:
    """Index documents into Qdrant vector database"""

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        embedding_model: str = "BAAI/bge-m3"
    ):
        self.client = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.embedder = EmbeddingModel(embedding_model, device="cpu")

    def _generate_id(self, text: str) -> str:
        """Generate stable ID from text"""
        return hashlib.md5(text.encode()).hexdigest()

    def create_collection(self, collection_name: str, recreate: bool = False):
        """Create or recreate a collection"""
        collections = [c.name for c in self.client.get_collections().collections]

        if collection_name in collections:
            if recreate:
                print(f"Deleting existing collection: {collection_name}")
                self.client.delete_collection(collection_name)
            else:
                print(f"Collection already exists: {collection_name}")
                return

        print(f"Creating collection: {collection_name}")
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
        """Index documents into collection"""
        print(f"Indexing {len(documents)} documents to {collection_name}")

        # Process in batches
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]

            # Extract texts for embedding
            texts = [doc["text"] for doc in batch]
            vectors = self.embedder.encode(texts)

            # Create points
            points = []
            for j, (doc, vector) in enumerate(zip(batch, vectors)):
                point_id = doc.get("id", self._generate_id(doc["text"]))
                # Convert string ID to integer if needed
                if isinstance(point_id, str):
                    point_id = int(hashlib.md5(point_id.encode()).hexdigest()[:15], 16)

                point = PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "text": doc["text"],
                        **doc.get("metadata", {})
                    }
                )
                points.append(point)

            # Upsert batch
            self.client.upsert(
                collection_name=collection_name,
                points=points
            )

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


def index_ace_schema(indexer: "Indexer", collection: str, rebuild: bool = False):
    """Index ACE schema from Construct3-Schema (使用 Schema 数据)"""
    from src.data_processing.schema_parser import SchemaParser

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
    from src.data_processing.schema_parser import SchemaParser

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
    """Index all Construct 3 data into Qdrant"""
    from src.config import (
        QDRANT_HOST, QDRANT_PORT, EMBEDDING_MODEL, CSV_TERMS,
        DOC_COLLECTIONS, ALL_COLLECTIONS, COLLECTIONS,
    )
    from src.data_processing.markdown_parser import MarkdownParser
    from src.data_processing.csv_parser import CSVParser
    from src.data_processing.project_parser import process_example_projects

    indexer = Indexer(
        qdrant_host=QDRANT_HOST,
        qdrant_port=QDRANT_PORT,
        embedding_model=EMBEDDING_MODEL
    )

    # Parse all markdown files once
    print("\n=== Parsing Markdown Documentation ===")
    md_parser = MarkdownParser()
    all_chunks = md_parser.parse_directory()

    # Group chunks by collection
    chunks_by_collection = {col: [] for col in DOC_COLLECTIONS}
    for chunk in all_chunks:
        collection = chunk.metadata.get('collection')
        if collection in chunks_by_collection:
            chunks_by_collection[collection].append(chunk)

    # Index each document collection
    for collection in DOC_COLLECTIONS:
        chunks = chunks_by_collection[collection]
        print(f"\n=== Indexing {collection} ({len(chunks)} chunks) ===")
        indexer.create_collection(collection, recreate=rebuild)
        if chunks:
            docs = [
                {
                    "id": f"{collection}_{i}",
                    "text": chunk.text,
                    "metadata": chunk.metadata
                }
                for i, chunk in enumerate(chunks)
            ]
            indexer.index_documents(collection, docs)

    # Index translation terms
    print("\n=== Indexing Translation Terms ===")
    indexer.create_collection(COLLECTIONS["terms"], recreate=rebuild)
    csv_parser = CSVParser()
    if CSV_TERMS.exists():
        entries = csv_parser.parse_file(CSV_TERMS)
        docs = [
            {
                "id": f"term_{i}",
                "text": entry.full_text,
                "metadata": {
                    "term_key": entry.term_key,
                    "category": entry.category,
                    "type": entry.term_type,
                    "zh": entry.zh,
                    "en": entry.en
                }
            }
            for i, entry in enumerate(entries)
        ]
        indexer.index_documents(COLLECTIONS["terms"], docs)

    # Index example projects
    print("\n=== Indexing Example Projects ===")
    indexer.create_collection(COLLECTIONS["examples"], recreate=rebuild)
    project_parser = process_example_projects()
    if project_parser:
        docs = project_parser.export_for_vectordb()
        indexer.index_documents(COLLECTIONS["examples"], docs)

    # Index ACE Schema (from Construct3-Schema - 完整双语数据)
    print("\n=== Indexing ACE Schema (from Construct3-Schema) ===")
    indexer.create_collection(COLLECTIONS["ace"], recreate=rebuild)
    index_ace_schema(indexer, COLLECTIONS["ace"], rebuild)

    # Index Effects Schema (from Construct3-Schema)
    print("\n=== Indexing Effects Schema (from Construct3-Schema) ===")
    indexer.create_collection(COLLECTIONS["effects"], recreate=rebuild)
    index_effects_schema(indexer, COLLECTIONS["effects"], rebuild)

    print("\n=== Indexing Complete ===")

    # Print collection stats
    for collection in ALL_COLLECTIONS:
        try:
            info = indexer.client.get_collection(collection)
            print(f"  {collection}: {info.points_count} vectors")
        except Exception:
            pass


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Index Construct 3 data into Qdrant")
    parser.add_argument("--rebuild", action="store_true", help="Recreate collections")
    args = parser.parse_args()

    index_all_data(rebuild=args.rebuild)
