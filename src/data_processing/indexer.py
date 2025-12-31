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

    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            print(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: List[str]) -> List[List[float]]:
        """Encode texts to vectors"""
        return self.model.encode(texts, show_progress_bar=True).tolist()

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
        self.embedder = EmbeddingModel(embedding_model)

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


def index_all_data(rebuild: bool = False):
    """Index all Construct 3 data into Qdrant"""
    from src.config import (
        QDRANT_HOST, QDRANT_PORT, EMBEDDING_MODEL, CSV_TERMS,
        DOC_COLLECTIONS, ALL_COLLECTIONS,
        COLLECTION_TERMS, COLLECTION_EXAMPLES,
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
    indexer.create_collection(COLLECTION_TERMS, recreate=rebuild)
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
        indexer.index_documents(COLLECTION_TERMS, docs)

    # Index example projects
    print("\n=== Indexing Example Projects ===")
    indexer.create_collection(COLLECTION_EXAMPLES, recreate=rebuild)
    project_parser = process_example_projects()
    if project_parser:
        docs = project_parser.export_for_vectordb()
        indexer.index_documents(COLLECTION_EXAMPLES, docs)

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
