"""
Recall@K evaluation for Construct 3 RAG embedding models.

Unlike compare_embeddings.py (which only measures cosine similarity between
query and its ground_truth), this script measures actual retrieval quality:
given a query, can the model find the correct document among all candidates?

Metrics:
  - Recall@K: fraction of queries where the correct document appears in top K
  - MRR (Mean Reciprocal Rank): average of 1/rank for correct document
  - Keyword Hit Rate: fraction of expected keywords found in top-K results

Usage:
    python scripts/eval_recall.py
    python scripts/eval_recall.py --models BAAI/bge-m3 Qwen/Qwen3-Embedding-0.6B
    python scripts/eval_recall.py --models Qwen/Qwen3-Embedding-0.6B Qwen/Qwen3-Embedding-4B
    python scripts/eval_recall.py --output recall_comparison.md
    python scripts/eval_recall.py --ks 1 3 5 10 20
"""
import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation.dataset import EvalDataset

# Default models to compare
DEFAULT_MODELS = [
    "BAAI/bge-m3",
    "Qwen/Qwen3-Embedding-0.6B",
]

DEFAULT_KS = [1, 3, 5, 10, 20]


@dataclass
class RecallScore:
    """Per-case retrieval result."""
    case_id: str
    query: str
    category: str
    difficulty: str
    rank: int  # 1-based rank of correct doc, 0 if not found
    top_k_texts: List[str] = field(default_factory=list, repr=False)
    keyword_hits: int = 0
    keyword_total: int = 0


@dataclass
class RecallReport:
    model_name: str
    dimension: int
    load_time_s: float
    encode_time_s: float
    num_cases: int
    num_documents: int
    scores: List[RecallScore] = field(default_factory=list)
    ks: List[int] = field(default_factory=lambda: DEFAULT_KS)

    def recall_at_k(self, k: int) -> float:
        """Fraction of queries where correct doc is in top-K."""
        if not self.scores:
            return 0.0
        hits = sum(1 for s in self.scores if 0 < s.rank <= k)
        return hits / len(self.scores)

    def mrr(self) -> float:
        """Mean Reciprocal Rank."""
        if not self.scores:
            return 0.0
        rrs = [1.0 / s.rank if s.rank > 0 else 0.0 for s in self.scores]
        return float(np.mean(rrs))

    def keyword_hit_rate(self) -> float:
        """Fraction of expected keywords found in top-K results."""
        total = sum(s.keyword_total for s in self.scores)
        hits = sum(s.keyword_hits for s in self.scores)
        return hits / total if total > 0 else 0.0

    def recall_at_k_by_category(self, k: int) -> Dict[str, float]:
        groups: Dict[str, List[RecallScore]] = {}
        for s in self.scores:
            groups.setdefault(s.category, []).append(s)
        return {
            cat: sum(1 for s in scores if 0 < s.rank <= k) / len(scores)
            for cat, scores in groups.items()
        }

    def recall_at_k_by_difficulty(self, k: int) -> Dict[str, float]:
        groups: Dict[str, List[RecallScore]] = {}
        for s in self.scores:
            if s.difficulty:
                groups.setdefault(s.difficulty, []).append(s)
        return {
            diff: sum(1 for s in scores if 0 < s.rank <= k) / len(scores)
            for diff, scores in groups.items()
        }


def _build_corpus_index(
    doc_vecs: np.ndarray,
) -> np.ndarray:
    """Normalize document vectors for fast cosine similarity via dot product."""
    norms = np.linalg.norm(doc_vecs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return doc_vecs / norms


def _search_topk(
    query_vec: np.ndarray,
    corpus_normed: np.ndarray,
    k: int,
) -> List[int]:
    """Return top-K document indices by cosine similarity."""
    q_norm = query_vec / (np.linalg.norm(query_vec) or 1)
    scores = corpus_normed @ q_norm
    # Partial sort for top-K
    if k >= len(scores):
        topk_idx = np.argsort(-scores)
    else:
        topk_idx = np.argpartition(-scores, k)[:k]
        topk_idx = topk_idx[np.argsort(-scores[topk_idx])]
    return topk_idx.tolist()


def evaluate_recall(
    model_name: str,
    cases,
    ks: List[int],
    verbose: bool = False,
) -> RecallReport:
    """Evaluate recall@K for a single model.

    Strategy:
    1. Treat all ground_truth texts as the document corpus
    2. For each query, search the corpus and check if the correct document
       (the one paired with that query) appears in top-K
    3. Also check keyword presence in top-K retrieved texts
    """
    from src.ingest.indexer import EmbeddingModel

    print(f"\n{'=' * 60}")
    print(f"Evaluating: {model_name}")

    t0 = time.time()
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        device = "cpu"

    embedder = EmbeddingModel(model_name, device=device)
    _ = embedder.model  # Force load
    load_time = time.time() - t0
    dim = embedder.dimension
    print(f"  Loaded in {load_time:.1f}s  |  dim={dim}  |  device={device}")

    # Build document corpus from ground_truths
    ground_truths = [c.ground_truth for c in cases]
    queries = [c.query for c in cases]
    max_k = max(ks)

    t1 = time.time()

    # Encode documents (no instruction prefix)
    print(f"  Encoding {len(ground_truths)} documents...")
    doc_vecs = np.array(embedder.encode(ground_truths, batch_size=8))
    corpus_normed = _build_corpus_index(doc_vecs)

    # Encode queries (with instruction prefix for Qwen3)
    print(f"  Encoding {len(queries)} queries...")
    if embedder._is_qwen3:
        query_vecs = np.array([embedder.encode_single(q) for q in queries])
    else:
        query_vecs = np.array(embedder.encode(queries, batch_size=16))

    encode_time = time.time() - t1
    print(f"  Encoded in {encode_time:.1f}s")

    # Evaluate each case
    all_scores = []
    for i, case in enumerate(cases):
        topk_indices = _search_topk(query_vecs[i], corpus_normed, max_k)

        # Rank of correct document (1-based)
        if i in topk_indices:
            rank = topk_indices.index(i) + 1
        else:
            rank = 0

        # Keyword hit check in top-10 retrieved texts
        top_texts = " ".join(ground_truths[idx] for idx in topk_indices[:10])
        kw_hits = sum(
            1 for kw in case.expected_keywords
            if kw.lower() in top_texts.lower()
        )

        score = RecallScore(
            case_id=case.id,
            query=case.query,
            category=case.category,
            difficulty=case.retrieval_difficulty,
            rank=rank,
            keyword_hits=kw_hits,
            keyword_total=len(case.expected_keywords),
        )
        all_scores.append(score)

        if verbose:
            status = f"rank={rank}" if rank > 0 else "MISS"
            print(f"  {case.id}: {status:8s}  kw={kw_hits}/{len(case.expected_keywords)}  {case.query[:40]}")

    report = RecallReport(
        model_name=model_name,
        dimension=dim,
        load_time_s=load_time,
        encode_time_s=encode_time,
        num_cases=len(cases),
        num_documents=len(ground_truths),
        scores=all_scores,
        ks=ks,
    )

    # Print summary
    print(f"  MRR:         {report.mrr():.4f}")
    for k in ks:
        print(f"  Recall@{k:<3d}:  {report.recall_at_k(k):.4f}  ({int(report.recall_at_k(k) * len(cases))}/{len(cases)})")
    print(f"  Keyword Hit: {report.keyword_hit_rate():.4f}")

    # Free GPU memory
    del embedder, doc_vecs, query_vecs, corpus_normed
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass

    return report


def generate_recall_report(reports: List[RecallReport]) -> str:
    """Generate markdown comparison report."""
    ks = reports[0].ks
    lines = [
        "# Recall@K Embedding Model Comparison",
        "",
        f"- **Date**: {time.strftime('%Y-%m-%d %H:%M')}",
        f"- **Eval Cases**: {reports[0].num_cases}",
        f"- **Corpus Size**: {reports[0].num_documents} ground-truth documents",
        f"- **Models**: {len(reports)}",
        "",
    ]

    # Summary table
    lines.extend(["## Summary", ""])
    header_parts = ["Model", "Dim", "Load(s)", "Encode(s)", "MRR", "KW Hit"]
    header_parts.extend(f"R@{k}" for k in ks)
    lines.append("| " + " | ".join(header_parts) + " |")
    lines.append("|" + "|".join("---" for _ in header_parts) + "|")

    for r in reports:
        short_name = r.model_name.split("/")[-1]
        row = [
            short_name,
            str(r.dimension),
            f"{r.load_time_s:.1f}",
            f"{r.encode_time_s:.1f}",
            f"{r.mrr():.4f}",
            f"{r.keyword_hit_rate():.4f}",
        ]
        row.extend(f"{r.recall_at_k(k):.4f}" for k in ks)
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # Delta (if 2 models)
    if len(reports) == 2:
        a, b = reports
        lines.append("### Delta (Model B − Model A)")
        lines.append("")
        delta_mrr = b.mrr() - a.mrr()
        lines.append(f"- MRR: {'+' if delta_mrr >= 0 else ''}{delta_mrr:.4f}")
        for k in ks:
            delta = b.recall_at_k(k) - a.recall_at_k(k)
            lines.append(f"- Recall@{k}: {'+' if delta >= 0 else ''}{delta:.4f}")
        delta_kw = b.keyword_hit_rate() - a.keyword_hit_rate()
        lines.append(f"- Keyword Hit: {'+' if delta_kw >= 0 else ''}{delta_kw:.4f}")
        lines.append("")

    # By category
    lines.extend(["## Recall@10 by Category", ""])
    categories = sorted({s.category for s in reports[0].scores})
    header = "| Category | " + " | ".join(r.model_name.split("/")[-1] for r in reports) + " |"
    sep = "|---|" + "|".join("---" for _ in reports) + "|"
    lines.extend([header, sep])

    for cat in categories:
        vals = [r.recall_at_k_by_category(10).get(cat, 0.0) for r in reports]
        best_idx = int(np.argmax(vals))
        val_strs = [f"**{v:.4f}**" if i == best_idx and len(reports) > 1 else f"{v:.4f}" for i, v in enumerate(vals)]
        lines.append(f"| {cat} | " + " | ".join(val_strs) + " |")
    lines.append("")

    # By difficulty
    lines.extend(["## Recall@10 by Difficulty", ""])
    diffs = ["easy", "medium", "hard"]
    header = "| Difficulty | " + " | ".join(r.model_name.split("/")[-1] for r in reports) + " |"
    sep = "|---|" + "|".join("---" for _ in reports) + "|"
    lines.extend([header, sep])

    for diff in diffs:
        vals = [r.recall_at_k_by_difficulty(10).get(diff, 0.0) for r in reports]
        if any(v > 0 for v in vals):
            best_idx = int(np.argmax(vals))
            val_strs = [
                f"**{v:.4f}**" if i == best_idx and len(reports) > 1 else f"{v:.4f}"
                for i, v in enumerate(vals)
            ]
            lines.append(f"| {diff} | " + " | ".join(val_strs) + " |")
    lines.append("")

    # Per-case comparison (2 models)
    if len(reports) == 2:
        a, b = reports
        lines.extend(["## Per-Case Rank Comparison (sorted by rank improvement)", ""])
        a_name = a.model_name.split("/")[-1]
        b_name = b.model_name.split("/")[-1]
        lines.extend([
            f"| ID | Query | {a_name} rank | {b_name} rank | Δ |",
            "|---|---|---|---|---|",
        ])

        pairs = []
        for sa, sb in zip(a.scores, b.scores):
            ra = sa.rank if sa.rank > 0 else 999
            rb = sb.rank if sb.rank > 0 else 999
            pairs.append((sa, ra, rb, ra - rb))  # positive = B is better

        pairs.sort(key=lambda x: x[3], reverse=True)
        for sa, ra, rb, delta in pairs:
            ra_str = str(ra) if ra < 999 else "miss"
            rb_str = str(rb) if rb < 999 else "miss"
            d_str = f"+{delta}" if delta > 0 else str(delta)
            if ra >= 999 and rb >= 999:
                d_str = "="
            query_short = sa.query[:35].replace("|", "\\|")
            lines.append(f"| {sa.case_id} | {query_short} | {ra_str} | {rb_str} | {d_str} |")
        lines.append("")

    # Missed cases
    lines.extend(["## Missed Cases (not in top-20)", ""])
    for r in reports:
        missed = [s for s in r.scores if s.rank == 0]
        if missed:
            lines.append(f"### {r.model_name.split('/')[-1]} ({len(missed)} misses)")
            for s in missed:
                lines.append(f"- `{s.case_id}`: {s.query[:60]}")
            lines.append("")
        else:
            lines.append(f"### {r.model_name.split('/')[-1]}: **0 misses** ✓")
            lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Recall@K evaluation for embedding models on RAGAS eval set"
    )
    parser.add_argument(
        "--models", nargs="+", default=DEFAULT_MODELS,
        help="Model names to compare (default: bge-m3 vs Qwen3-Embedding-0.6B)"
    )
    parser.add_argument(
        "--ks", nargs="+", type=int, default=DEFAULT_KS,
        help="K values for Recall@K (default: 1 3 5 10 20)"
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--output", "-o", type=str, help="Write markdown report to file")
    parser.add_argument(
        "--category", type=str, default=None,
        help="Filter eval cases by category (e.g. ace_lookup, doc_section)"
    )
    args = parser.parse_args()

    dataset = EvalDataset.load()
    if args.category:
        dataset = dataset.filter_by_category(args.category)
    cases = dataset.cases
    print(f"Loaded {len(cases)} evaluation cases")

    reports = []
    for model_name in args.models:
        report = evaluate_recall(model_name, cases, args.ks, verbose=args.verbose)
        reports.append(report)

    # Print comparison
    print(f"\n{'=' * 60}")
    print("RECALL COMPARISON SUMMARY")
    print(f"{'=' * 60}")
    for r in reports:
        print(f"  {r.model_name:40s}  MRR={r.mrr():.4f}  R@10={r.recall_at_k(10):.4f}")

    if len(reports) >= 2:
        # Find best model by MRR
        best = max(reports, key=lambda r: r.mrr())
        print(f"\n  Best by MRR: {best.model_name}")

    # Generate report
    md = generate_recall_report(reports)
    if args.output:
        Path(args.output).write_text(md, encoding="utf-8")
        print(f"\nReport written to {args.output}")
    else:
        print("\n" + md)


if __name__ == "__main__":
    main()
