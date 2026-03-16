#!/usr/bin/env python3
"""
Benchmark embedding models on retrieval quality — no Qdrant re-indexing needed.

Pulls corpus documents from Qdrant once, re-encodes with each candidate model
in-memory, and measures IR metrics against ragas_dataset.json ground truth.

Usage:
    # Compare current model vs Qwen3-Embedding-0.6B (default)
    python scripts/benchmark_embeddings.py

    # Compare specific models
    python scripts/benchmark_embeddings.py \
        --models "BAAI/bge-m3" "Qwen/Qwen3-Embedding-0.6B" "Qwen/Qwen3-Embedding-4B"

    # Limit corpus size for quick test
    python scripts/benchmark_embeddings.py --max-docs 500

    # Save results to JSON
    python scripts/benchmark_embeddings.py --output results.json
"""
import argparse
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import (
    QDRANT_HOST, QDRANT_PORT, EMBEDDING_MODEL, DATA_DIR,
)
from src.evaluation.dataset import EvalDataset


# Qwen3-Embedding query instruction (same as src/ingest/indexer.py)
_QWEN3_QUERY_INSTRUCTION = (
    "Instruct: Retrieve relevant Construct 3 documentation for the following query\nQuery: "
)

# Default models to compare
DEFAULT_MODELS = [
    "BAAI/bge-m3",
    "Qwen/Qwen3-Embedding-0.6B",
]


@dataclass
class CorpusDoc:
    """A document extracted from Qdrant for in-memory evaluation."""
    text: str
    source: str          # metadata source path (e.g. "plugin-reference/sprite.md")
    collection: str      # collection key (e.g. "plugins")


@dataclass
class ModelResult:
    """Benchmark results for a single embedding model."""
    model: str
    dim: int
    n_queries: int
    n_corpus: int
    encode_time_s: float
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    hit_at_10: float
    mrr: float
    recall_at_10: float
    per_case: List[dict] = field(default_factory=list)


def extract_corpus(max_docs: int = 0) -> List[CorpusDoc]:
    """Pull all document texts from Qdrant collections."""
    from qdrant_client import QdrantClient
    from src.collections import COLLECTIONS

    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    # Map collection name -> key
    name_to_key = {v: k for k, v in COLLECTIONS.items()}

    corpus = []
    for coll_name in COLLECTIONS.values():
        try:
            info = client.get_collection(coll_name)
            count = info.points_count or 0
        except Exception:
            continue
        if count == 0:
            continue

        # Scroll through all points
        offset = None
        while True:
            records, next_offset = client.scroll(
                collection_name=coll_name,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for r in records:
                text = r.payload.get("text", "")
                source = r.payload.get("source", "")
                if text.strip():
                    corpus.append(CorpusDoc(
                        text=text,
                        source=source,
                        collection=name_to_key.get(coll_name, coll_name),
                    ))
            if next_offset is None:
                break
            offset = next_offset

    if max_docs > 0 and len(corpus) > max_docs:
        # Deterministic sampling
        rng = np.random.RandomState(42)
        indices = rng.choice(len(corpus), max_docs, replace=False)
        corpus = [corpus[i] for i in sorted(indices)]

    return corpus


def load_model(model_name: str, device: str):
    """Load a SentenceTransformer model."""
    from sentence_transformers import SentenceTransformer

    is_qwen3 = "qwen3-embedding" in model_name.lower()
    kwargs = {"device": device}
    if is_qwen3:
        kwargs["trust_remote_code"] = True

    return SentenceTransformer(model_name, **kwargs)


def encode_corpus(model, texts: List[str], batch_size: int = 32) -> np.ndarray:
    """Encode document texts (no instruction prefix)."""
    vecs = model.encode(texts, batch_size=batch_size, show_progress_bar=True,
                        normalize_embeddings=True)
    return np.asarray(vecs)


def encode_queries(model, queries: List[str], model_name: str,
                   batch_size: int = 32) -> np.ndarray:
    """Encode queries (with instruction prefix for Qwen3)."""
    is_qwen3 = "qwen3-embedding" in model_name.lower()
    if is_qwen3:
        queries = [_QWEN3_QUERY_INSTRUCTION + q for q in queries]
    vecs = model.encode(queries, batch_size=batch_size, show_progress_bar=True,
                        normalize_embeddings=True)
    return np.asarray(vecs)


def source_matches(actual: str, expected: str) -> bool:
    """Check if actual source path matches expected pattern."""
    a = actual.replace("\\", "/").lower()
    e = expected.replace("\\", "/").lower()
    if a == e:
        return True
    if a.endswith(e):
        return True
    if a.startswith(e):
        return True
    return False


def evaluate_model(
    model_name: str,
    corpus: List[CorpusDoc],
    cases: list,
    device: str = "cuda",
    top_k: int = 10,
) -> ModelResult:
    """Evaluate a single embedding model on retrieval quality."""
    print(f"\n{'='*60}")
    print(f"Model: {model_name}")
    print(f"{'='*60}")

    # Load model
    print(f"  Loading model...")
    t0 = time.time()
    model = load_model(model_name, device)
    print(f"  Loaded ({time.time()-t0:.1f}s)")

    # Encode corpus
    corpus_texts = [d.text for d in corpus]
    print(f"  Encoding {len(corpus_texts)} corpus documents...")
    t1 = time.time()
    corpus_vecs = encode_corpus(model, corpus_texts)

    # Encode queries
    queries = [c.query for c in cases]
    print(f"  Encoding {len(queries)} queries...")
    query_vecs = encode_queries(model, queries, model_name)
    encode_time = time.time() - t1
    print(f"  Encoding done ({encode_time:.1f}s)")

    dim = corpus_vecs.shape[1]

    # Compute similarity matrix: (n_queries, n_corpus)
    sims = query_vecs @ corpus_vecs.T

    # Evaluate each case
    hits = {1: 0, 3: 0, 5: 0, 10: 0}
    rr_sum = 0.0
    recall_sum = 0.0
    n_valid = 0
    per_case = []

    for i, case in enumerate(cases):
        expected_sources = case.expected_sources or []
        if not expected_sources:
            per_case.append({
                "id": case.id, "query": case.query,
                "hit": None, "mrr": None, "recall": None,
                "note": "no expected_sources",
            })
            continue

        n_valid += 1
        ranked_indices = np.argsort(-sims[i])[:top_k]

        # Find which expected sources appear in top-K
        sources_found = []
        first_hit_rank = None

        for exp_src in expected_sources:
            for rank_pos, idx in enumerate(ranked_indices):
                actual_src = corpus[idx].source
                if source_matches(actual_src, exp_src):
                    sources_found.append(exp_src)
                    if first_hit_rank is None:
                        first_hit_rank = rank_pos + 1
                    break

        recall = len(sources_found) / len(expected_sources)
        mrr = 1.0 / first_hit_rank if first_hit_rank else 0.0
        is_hit = len(sources_found) > 0

        recall_sum += recall
        rr_sum += mrr
        for k in hits:
            if first_hit_rank is not None and first_hit_rank <= k:
                hits[k] += 1

        per_case.append({
            "id": case.id,
            "query": case.query,
            "hit": is_hit,
            "mrr": round(mrr, 4),
            "recall": round(recall, 4),
            "sources_found": sources_found,
            "sources_missed": [s for s in expected_sources if s not in sources_found],
            "top3_retrieved": [
                {"source": corpus[idx].source, "collection": corpus[idx].collection,
                 "score": round(float(sims[i][idx]), 4)}
                for idx in ranked_indices[:3]
            ],
        })

    return ModelResult(
        model=model_name,
        dim=dim,
        n_queries=len(cases),
        n_corpus=len(corpus),
        encode_time_s=round(encode_time, 1),
        hit_at_1=hits[1] / n_valid if n_valid else 0,
        hit_at_3=hits[3] / n_valid if n_valid else 0,
        hit_at_5=hits[5] / n_valid if n_valid else 0,
        hit_at_10=hits[10] / n_valid if n_valid else 0,
        mrr=rr_sum / n_valid if n_valid else 0,
        recall_at_10=recall_sum / n_valid if n_valid else 0,
        per_case=per_case,
    )


def print_comparison(results: List[ModelResult]):
    """Print side-by-side comparison table."""
    print(f"\n{'='*80}")
    print("EMBEDDING MODEL COMPARISON")
    print(f"{'='*80}")
    print(f"  Corpus: {results[0].n_corpus} docs | Queries: {results[0].n_queries} "
          f"(valid: {sum(1 for c in results[0].per_case if c.get('hit') is not None)})")
    print()

    header = f"{'Model':<35} {'Dim':>4} {'Hit@1':>6} {'Hit@3':>6} {'Hit@5':>6} {'Hit@10':>6} {'MRR':>6} {'R@10':>6} {'Time':>6}"
    print(header)
    print("-" * 80)

    for r in results:
        name = r.model.split("/")[-1]
        print(
            f"{name:<35} {r.dim:>4} "
            f"{r.hit_at_1:>6.3f} {r.hit_at_3:>6.3f} {r.hit_at_5:>6.3f} {r.hit_at_10:>6.3f} "
            f"{r.mrr:>6.3f} {r.recall_at_10:>6.3f} {r.encode_time_s:>5.0f}s"
        )

    # Delta if exactly 2 models
    if len(results) == 2:
        a, b = results
        print("-" * 80)
        print(
            f"  {'Delta (B-A)':<31} {'':>4} "
            f"{b.hit_at_1-a.hit_at_1:>+6.3f} {b.hit_at_3-a.hit_at_3:>+6.3f} "
            f"{b.hit_at_5-a.hit_at_5:>+6.3f} {b.hit_at_10-a.hit_at_10:>+6.3f} "
            f"{b.mrr-a.mrr:>+6.3f} {b.recall_at_10-a.recall_at_10:>+6.3f}"
        )
    print("=" * 80)

    # Per-case comparison for misses
    print("\nPer-case breakdown (misses only):")
    for case_data in results[0].per_case:
        case_id = case_data["id"]
        if case_data.get("hit") is None:
            continue
        # Check if any model missed
        any_miss = False
        for r in results:
            case = next(c for c in r.per_case if c["id"] == case_id)
            if not case.get("hit"):
                any_miss = True
        if not any_miss:
            continue

        print(f"\n  [{case_id}] {case_data['query'][:60]}")
        for r in results:
            case = next(c for c in r.per_case if c["id"] == case_id)
            name = r.model.split("/")[-1]
            status = "HIT" if case.get("hit") else "MISS"
            print(f"    {name:<30} {status}  MRR={case.get('mrr', 0):.2f}  "
                  f"Recall={case.get('recall', 0):.0%}")
            if case.get("sources_missed"):
                print(f"      missed: {', '.join(case['sources_missed'][:3])}")


def main():
    parser = argparse.ArgumentParser(
        description="Compare embedding models on retrieval quality (no re-indexing)"
    )
    parser.add_argument(
        "--models", nargs="+", default=None,
        help=f"Models to compare (default: {DEFAULT_MODELS})"
    )
    parser.add_argument("--max-docs", type=int, default=0,
                        help="Limit corpus size for quick testing (0=all)")
    parser.add_argument("--device", default="cuda",
                        help="Device for encoding (default: cuda)")
    parser.add_argument("--top-k", type=int, default=10,
                        help="Top-K for retrieval metrics (default: 10)")
    parser.add_argument("--output", "-o", type=str,
                        help="Save results to JSON file")
    args = parser.parse_args()

    model_list = args.models or DEFAULT_MODELS

    # Load eval dataset
    dataset = EvalDataset.load()
    cases = dataset.cases
    print(f"Loaded {len(cases)} eval cases from ragas_dataset.json")

    # Extract corpus from Qdrant
    print(f"Extracting corpus from Qdrant ({QDRANT_HOST}:{QDRANT_PORT})...")
    t0 = time.time()
    corpus = extract_corpus(max_docs=args.max_docs)
    print(f"Extracted {len(corpus)} documents ({time.time()-t0:.1f}s)")

    if not corpus:
        print("ERROR: No documents in Qdrant. Run indexing first: python -m src.ingest.indexer --rebuild")
        sys.exit(1)

    # Collection distribution
    from collections import Counter
    dist = Counter(d.collection for d in corpus)
    print(f"  Collections: {dict(sorted(dist.items()))}")

    # Benchmark each model
    results = []
    for model_name in model_list:
        try:
            r = evaluate_model(model_name, corpus, cases,
                               device=args.device, top_k=args.top_k)
            results.append(r)
        except Exception as e:
            print(f"\nERROR evaluating {model_name}: {e}")
            import traceback
            traceback.print_exc()

    if not results:
        print("No models evaluated successfully.")
        sys.exit(1)

    # Print comparison
    print_comparison(results)

    # Save results
    if args.output:
        out = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "corpus_size": len(corpus),
            "n_queries": len(cases),
            "top_k": args.top_k,
            "results": [asdict(r) for r in results],
        }
        Path(args.output).write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
