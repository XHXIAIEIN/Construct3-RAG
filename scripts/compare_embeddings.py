"""
Embedding model comparison for Construct 3 RAG.

Compares semantic capture quality of different embedding models using the
RAGAS evaluation dataset. Measures cosine similarity between query embeddings
and ground-truth document embeddings — no Qdrant required.

Usage:
    python scripts/compare_embeddings.py
    python scripts/compare_embeddings.py --models BAAI/bge-m3 Qwen/Qwen3-Embedding-0.6B Qwen/Qwen3-Embedding-4B
    python scripts/compare_embeddings.py --verbose
    python scripts/compare_embeddings.py --output embedding_comparison.md
"""
import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation.dataset import EvalDataset

# Default models to compare
DEFAULT_MODELS = [
    "BAAI/bge-m3",
    "Qwen/Qwen3-Embedding-0.6B",
]


@dataclass
class CaseScore:
    case_id: str
    query: str
    category: str
    difficulty: str
    similarity: float  # cosine similarity between query and ground_truth


@dataclass
class ModelReport:
    model_name: str
    dimension: int
    load_time_s: float
    encode_time_s: float
    scores: List[CaseScore] = field(default_factory=list)

    @property
    def avg_similarity(self) -> float:
        return np.mean([s.similarity for s in self.scores]) if self.scores else 0.0

    @property
    def median_similarity(self) -> float:
        return float(np.median([s.similarity for s in self.scores])) if self.scores else 0.0

    def avg_by_category(self) -> dict[str, float]:
        groups: dict[str, list[float]] = {}
        for s in self.scores:
            groups.setdefault(s.category, []).append(s.similarity)
        return {k: np.mean(v) for k, v in groups.items()}

    def avg_by_difficulty(self) -> dict[str, float]:
        groups: dict[str, list[float]] = {}
        for s in self.scores:
            if s.difficulty:
                groups.setdefault(s.difficulty, []).append(s.similarity)
        return {k: np.mean(v) for k, v in groups.items()}


def cosine_similarity(a: List[float], b: List[float]) -> float:
    a_arr = np.array(a)
    b_arr = np.array(b)
    dot = np.dot(a_arr, b_arr)
    norm = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
    return float(dot / norm) if norm > 0 else 0.0


def evaluate_model(model_name: str, cases, verbose: bool = False) -> ModelReport:
    """Load a model and evaluate query-document similarity on all cases."""
    from src.ingest.indexer import EmbeddingModel

    print(f"\n{'='*60}")
    print(f"Loading: {model_name}")

    t0 = time.time()
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        device = "cpu"

    embedder = EmbeddingModel(model_name, device=device)
    # Force model load
    _ = embedder.model
    load_time = time.time() - t0
    dim = embedder.dimension
    print(f"  Loaded in {load_time:.1f}s  |  dim={dim}  |  device={device}")

    # Encode all queries and ground truths
    queries = [c.query for c in cases]
    ground_truths = [c.ground_truth for c in cases]

    t1 = time.time()
    # For Qwen3, queries get instruction prefix via encode_single
    if embedder._is_qwen3:
        query_vecs = [embedder.encode_single(q) for q in queries]
    else:
        query_vecs = embedder.encode(queries, batch_size=16)

    doc_vecs = embedder.encode(ground_truths, batch_size=8)
    encode_time = time.time() - t1
    print(f"  Encoded {len(queries)} queries + {len(ground_truths)} docs in {encode_time:.1f}s")

    # Compute per-case similarity
    scores = []
    for i, case in enumerate(cases):
        sim = cosine_similarity(query_vecs[i], doc_vecs[i])
        scores.append(CaseScore(
            case_id=case.id,
            query=case.query,
            category=case.category,
            difficulty=case.retrieval_difficulty,
            similarity=sim,
        ))
        if verbose:
            print(f"  {case.id}: {sim:.4f}  {case.query[:40]}")

    report = ModelReport(
        model_name=model_name,
        dimension=dim,
        load_time_s=load_time,
        encode_time_s=encode_time,
        scores=scores,
    )

    print(f"  Avg similarity: {report.avg_similarity:.4f}")
    print(f"  Median:         {report.median_similarity:.4f}")

    # Free GPU memory
    del embedder
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass

    return report


def generate_comparison_report(reports: List[ModelReport]) -> str:
    """Generate markdown comparison report."""
    lines = [
        "# Embedding Model Comparison Report",
        "",
        f"- **Date**: {time.strftime('%Y-%m-%d %H:%M')}",
        f"- **Cases**: {len(reports[0].scores)}",
        f"- **Models**: {len(reports)}",
        "",
        "## Summary",
        "",
        "| Model | Dim | Load (s) | Encode (s) | Avg Cosine Sim | Median |",
        "|-------|-----|----------|------------|----------------|--------|",
    ]

    for r in reports:
        lines.append(
            f"| {r.model_name} | {r.dimension} | {r.load_time_s:.1f} | "
            f"{r.encode_time_s:.1f} | **{r.avg_similarity:.4f}** | {r.median_similarity:.4f} |"
        )
    lines.append("")

    # Delta (if exactly 2 models)
    if len(reports) == 2:
        a, b = reports
        delta = b.avg_similarity - a.avg_similarity
        direction = "higher" if delta > 0 else "lower"
        lines.extend([
            f"**Delta**: {b.model_name} is {abs(delta):.4f} {direction} than {a.model_name}",
            "",
        ])

    # By category
    lines.extend(["## By Category", ""])
    categories = sorted({s.category for s in reports[0].scores})
    header = "| Category |" + " | ".join(r.model_name.split("/")[-1] for r in reports) + " | Winner |"
    sep = "|----------|" + " | ".join("------" for _ in reports) + " | ------ |"
    lines.extend([header, sep])

    for cat in categories:
        vals = []
        for r in reports:
            by_cat = r.avg_by_category()
            vals.append(by_cat.get(cat, 0.0))
        best_idx = int(np.argmax(vals))
        winner = reports[best_idx].model_name.split("/")[-1]
        val_strs = []
        for i, v in enumerate(vals):
            val_strs.append(f"**{v:.4f}**" if i == best_idx else f"{v:.4f}")
        lines.append(f"| {cat} | " + " | ".join(val_strs) + f" | {winner} |")
    lines.append("")

    # By difficulty
    lines.extend(["## By Difficulty", ""])
    difficulties = ["easy", "medium", "hard"]
    header = "| Difficulty |" + " | ".join(r.model_name.split("/")[-1] for r in reports) + " |"
    sep = "|------------|" + " | ".join("------" for _ in reports) + " |"
    lines.extend([header, sep])

    for diff in difficulties:
        vals = []
        for r in reports:
            by_diff = r.avg_by_difficulty()
            vals.append(by_diff.get(diff, 0.0))
        if any(v > 0 for v in vals):
            best_idx = int(np.argmax(vals))
            val_strs = []
            for i, v in enumerate(vals):
                val_strs.append(f"**{v:.4f}**" if i == best_idx else f"{v:.4f}")
            lines.append(f"| {diff} | " + " | ".join(val_strs) + " |")
    lines.append("")

    # Per-case comparison (sorted by biggest delta)
    if len(reports) == 2:
        lines.extend(["## Per-Case Comparison (sorted by delta)", ""])
        lines.extend([
            f"| ID | Query | {reports[0].model_name.split('/')[-1]} | {reports[1].model_name.split('/')[-1]} | Delta |",
            "|----|-------|------|------|-------|",
        ])
        deltas = []
        for i, case_score in enumerate(reports[0].scores):
            s0 = case_score.similarity
            s1 = reports[1].scores[i].similarity
            deltas.append((case_score, s0, s1, s1 - s0))

        # Sort by absolute delta descending
        deltas.sort(key=lambda x: abs(x[3]), reverse=True)
        for cs, s0, s1, d in deltas:
            sign = "+" if d >= 0 else ""
            query_short = cs.query[:30].replace("|", "\\|")
            lines.append(f"| {cs.case_id} | {query_short} | {s0:.4f} | {s1:.4f} | {sign}{d:.4f} |")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Compare embedding models on RAGAS eval set")
    parser.add_argument(
        "--models", nargs="+", default=DEFAULT_MODELS,
        help="Model names to compare (default: bge-m3 vs Qwen3-Embedding-0.6B)"
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--output", "-o", type=str, help="Write markdown report to file")
    args = parser.parse_args()

    dataset = EvalDataset.load()
    cases = dataset.cases
    print(f"Loaded {len(cases)} evaluation cases")

    reports = []
    for model_name in args.models:
        report = evaluate_model(model_name, cases, verbose=args.verbose)
        reports.append(report)

    # Print comparison
    print(f"\n{'='*60}")
    print("COMPARISON SUMMARY")
    print(f"{'='*60}")
    for r in reports:
        print(f"  {r.model_name:40s}  avg={r.avg_similarity:.4f}  median={r.median_similarity:.4f}")

    if len(reports) == 2:
        delta = reports[1].avg_similarity - reports[0].avg_similarity
        winner = reports[1].model_name if delta > 0 else reports[0].model_name
        print(f"\n  Winner: {winner} (delta={abs(delta):.4f})")

    # Write report
    if args.output:
        md = generate_comparison_report(reports)
        Path(args.output).write_text(md, encoding="utf-8")
        print(f"\nReport written to {args.output}")
    else:
        # Always print the markdown to stdout
        print("\n" + generate_comparison_report(reports))


if __name__ == "__main__":
    main()
