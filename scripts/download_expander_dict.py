"""Download and preprocess a Chinese synonym dictionary for DictExpander.

Usage:
    python scripts/download_expander_dict.py --source cilin [--filter-c3]

Downloads 同义词词林 (cilin) or OpenHowNet, optionally filters to C3-relevant
words using SchemaZhEnIndex vocabulary, then pre-embeds with bge-m3 and saves
a numpy .npz file for DictExpander to load at runtime.

Output: data/expander/dict_vectors.npz
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

_CILIN_URL = "https://raw.githubusercontent.com/huyingxi/Synonyms/master/synonyms/data/cilin.txt"
_OUT_DIR = Path("data/expander")

DICT_SOURCES = {
    "cilin": {
        "url": _CILIN_URL,
        "parse": "parse_cilin",
        "desc": "同义词词林（哈工大）~77K 词",
    },
}


def parse_cilin(text: str) -> list[str]:
    """Extract all words from cilin format (one group per line)."""
    words = []
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) > 1:
            words.extend(parts[1:])
    return list(set(words))


def filter_c3_relevant(words: list[str]) -> list[str]:
    """Keep only words semantically related to C3 schema vocabulary."""
    from src.rag.query_expander import SchemaZhEnIndex
    idx = SchemaZhEnIndex()
    c3_vocab = set(idx.token_to_nodes.keys())
    c3_chars = set("".join(c3_vocab))
    filtered = []
    for w in words:
        if w in c3_vocab:
            filtered.append(w)
        elif any(c in c3_chars for c in w):
            filtered.append(w)
    print(f"Filtered {len(words)} → {len(filtered)} words (C3-relevant)")
    return filtered


def embed_words(words: list[str]) -> "np.ndarray":
    import numpy as np
    from langchain_community.embeddings import HuggingFaceBgeEmbeddings
    from src.config import EMBEDDING_MODEL
    print(f"Embedding {len(words)} words with {EMBEDDING_MODEL}...")
    embedder = HuggingFaceBgeEmbeddings(
        model_name=EMBEDDING_MODEL,
        encode_kwargs={"normalize_embeddings": True},
    )
    batch_size = 256
    vectors = []
    for i in range(0, len(words), batch_size):
        batch = words[i:i + batch_size]
        vecs = embedder.embed_documents(batch)
        vectors.extend(vecs)
        print(f"  {min(i + batch_size, len(words))}/{len(words)}", end="\r")
    print()
    return np.array(vectors, dtype=np.float32)


def main():
    parser = argparse.ArgumentParser(description="Download & preprocess synonym dict")
    parser.add_argument("--source", default="cilin", choices=list(DICT_SOURCES))
    parser.add_argument("--filter-c3", action="store_true", help="Filter to C3-relevant words only")
    parser.add_argument("--no-embed", action="store_true", help="Skip embedding (test mode)")
    args = parser.parse_args()

    import urllib.request

    src = DICT_SOURCES[args.source]
    print(f"Downloading {src['desc']}...")
    with urllib.request.urlopen(src["url"]) as r:
        text = r.read().decode("utf-8", errors="replace")

    parse_fn = globals()[src["parse"]]
    words = parse_fn(text)
    print(f"Parsed {len(words)} words")

    if args.filter_c3:
        words = filter_c3_relevant(words)

    if args.no_embed:
        print("Skipping embedding (--no-embed)")
        return

    import numpy as np
    vectors = embed_words(words)

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _OUT_DIR / "dict_vectors.npz"
    np.savez_compressed(out_path, words=np.array(words), vectors=vectors)
    print(f"Saved → {out_path}  ({len(words)} words, {vectors.shape[1]}d)")


if __name__ == "__main__":
    main()
