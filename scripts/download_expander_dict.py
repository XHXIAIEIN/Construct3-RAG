"""Build DictExpander vector file from schema zh_tokens vocabulary.

Usage:
    python scripts/download_expander_dict.py

Extracts all Chinese tokens from SchemaZhEnIndex (~2604 words, 100% C3-relevant),
embeds them with bge-m3, and saves a numpy .npz file for DictExpander to load
at runtime. At query time, DictExpander finds the nearest schema tokens to each
query token via cosine similarity — this is the distributional hypothesis bridge.

Output: data/expander/dict_vectors.npz
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

_OUT_DIR = Path("data/expander")


def build_schema_vocab_vectors() -> None:
    """Extract SchemaZhEnIndex zh_tokens and embed with bge-m3."""
    import logging
    logging.disable(logging.WARNING)

    import numpy as np
    from src.rag.query_expander import SchemaZhEnIndex
    from src.config import EMBEDDING_MODEL

    print("Building SchemaZhEnIndex...")
    idx = SchemaZhEnIndex()
    words = sorted(idx.token_to_nodes.keys())
    print(f"Schema vocab: {len(words)} zh tokens")

    print(f"Embedding with {EMBEDDING_MODEL}...")
    from src.ingest.indexer import EmbeddingModel
    embedder = EmbeddingModel(model_name=EMBEDDING_MODEL)

    batch_size = 256
    vectors = []
    for i in range(0, len(words), batch_size):
        batch = words[i:i + batch_size]
        vecs = embedder.encode(batch, batch_size=batch_size)
        vectors.extend(vecs)
        print(f"  {min(i + batch_size, len(words))}/{len(words)}", end="\r")
    print()

    arr = np.array(vectors, dtype=np.float32)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _OUT_DIR / "dict_vectors.npz"
    np.savez_compressed(out_path, words=np.array(words), vectors=arr)
    print(f"Saved → {out_path}  ({len(words)} words, {arr.shape[1]}d)")


if __name__ == "__main__":
    build_schema_vocab_vectors()
