"""
Standalone retrieval quality evaluation.

Measures IR metrics (Recall@K, MRR, Hit Rate) independently from LLM generation.
No LLM required — only needs Qdrant + embedding model.

Usage:
    python scripts/evaluate_retrieval.py
    python scripts/evaluate_retrieval.py --cases B01,B08,B12
    python scripts/evaluate_retrieval.py --top-k 10 --verbose
    python scripts/evaluate_retrieval.py --output retrieval_report.md
"""
import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import QDRANT_HOST, QDRANT_PORT, EMBEDDING_MODEL
from src.evaluation.dataset import EvalDataset

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    case_id: str
    query: str
    recall: float  # fraction of expected_sources found in top-K
    mrr: float  # reciprocal rank of first expected source hit
    hit: bool  # at least one expected source in top-K
    sources_found: List[str] = field(default_factory=list)
    sources_missed: List[str] = field(default_factory=list)
    collections_hit: List[str] = field(default_factory=list)
    collection_recall: float = 0.0  # fraction of expected collections covered
    top_k_sources: List[dict] = field(default_factory=list)  # actual results for inspection
    latency_ms: float = 0.0
    difficulty: str = ""


def source_matches(actual_source: str, expected_source: str) -> bool:
    """Check if an actual source path matches an expected source pattern.

    Supports partial matching: expected "plugin-reference/sprite.md" matches
    actual "plugin-reference\\sprite.md" or "plugin-reference/sprite.md".
    Also supports prefix matching for directories like "scripting/scripting-reference".
    """
    # Normalize separators
    actual = actual_source.replace("\\", "/").lower()
    expected = expected_source.replace("\\", "/").lower()
    # Exact match
    if actual == expected:
        return True
    # Actual ends with expected (handles absolute vs relative paths)
    if actual.endswith(expected):
        return True
    # Expected is a prefix (for directory-level matches like "scripting/scripting-reference")
    if actual.startswith(expected):
        return True
    return False


def collection_name_to_key(collection_name: str) -> str:
    """Map Qdrant collection name back to key. e.g. 'c3_plugins' -> 'plugins'"""
    from src.collections import COLLECTIONS
    for key, name in COLLECTIONS.items():
        if name == collection_name:
            return key
    return collection_name


def evaluate_single(
    retriever,
    case,
    top_k: int = 10,
    verbose: bool = False,
) -> RetrievalResult:
    """Evaluate retrieval quality for a single query."""
    t0 = time.time()
    results = retriever.search_all_with_rerank(
        case.query, top_k_per_collection=5, final_top_k=top_k
    )
    latency_ms = (time.time() - t0) * 1000

    # Extract source paths from results
    top_k_sources = []
    for r in results:
        source = r.metadata.get("source", r.source)
        top_k_sources.append({
            "source": source,
            "collection": collection_name_to_key(r.source),
            "score": round(r.score, 4),
            "text_preview": r.text[:80].replace("\n", " "),
        })

    # Compute recall: what fraction of expected_sources are found?
    expected = case.expected_sources or []
    if not expected:
        # No expected sources defined — skip recall/MRR, just record what we got
        return RetrievalResult(
            case_id=case.id,
            query=case.query,
            recall=float("nan"),
            mrr=float("nan"),
            hit=True,  # vacuously true
            collections_hit=list({s["collection"] for s in top_k_sources}),
            collection_recall=float("nan"),
            top_k_sources=top_k_sources,
            latency_ms=latency_ms,
            difficulty=case.retrieval_difficulty,
        )

    sources_found = []
    sources_missed = []
    first_hit_rank = None

    for exp_src in expected:
        found = False
        for rank, r in enumerate(results):
            actual_src = r.metadata.get("source", "")
            if source_matches(actual_src, exp_src):
                found = True
                if first_hit_rank is None:
                    first_hit_rank = rank + 1  # 1-indexed
                break
        if found:
            sources_found.append(exp_src)
        else:
            sources_missed.append(exp_src)

    recall = len(sources_found) / len(expected) if expected else 0.0
    mrr = 1.0 / first_hit_rank if first_hit_rank else 0.0
    hit = len(sources_found) > 0

    # Collection recall
    expected_colls = set(case.expected_collections or [])
    actual_colls = {s["collection"] for s in top_k_sources}
    if expected_colls:
        coll_recall = len(expected_colls & actual_colls) / len(expected_colls)
    else:
        coll_recall = float("nan")

    result = RetrievalResult(
        case_id=case.id,
        query=case.query,
        recall=recall,
        mrr=mrr,
        hit=hit,
        sources_found=sources_found,
        sources_missed=sources_missed,
        collections_hit=sorted(actual_colls),
        collection_recall=coll_recall,
        top_k_sources=top_k_sources,
        latency_ms=latency_ms,
        difficulty=case.retrieval_difficulty,
    )

    if verbose:
        _print_case_detail(result)

    return result


def _print_case_detail(r: RetrievalResult):
    """Print detailed results for a single case."""
    import math
    recall_str = f"{r.recall:.0%}" if not math.isnan(r.recall) else "n/a"
    mrr_str = f"{r.mrr:.2f}" if not math.isnan(r.mrr) else "n/a"
    status = "HIT" if r.hit else "MISS"

    print(f"\n{'='*60}")
    print(f"[{r.case_id}] {r.query}")
    print(f"  Recall: {recall_str}  MRR: {mrr_str}  {status}  ({r.latency_ms:.0f}ms)")
    if r.sources_found:
        print(f"  Found:  {', '.join(r.sources_found)}")
    if r.sources_missed:
        print(f"  MISSED: {', '.join(r.sources_missed)}")
    print(f"  Collections hit: {', '.join(r.collections_hit)}")
    print(f"  Top results:")
    for i, s in enumerate(r.top_k_sources[:5]):
        print(f"    {i+1}. [{s['collection']}] {s['source']} ({s['score']}) {s['text_preview']}")


def generate_report(results: List[RetrievalResult], top_k: int) -> str:
    """Generate a markdown report from retrieval evaluation results."""
    import math
    lines = [
        "# Retrieval Evaluation Report",
        "",
        f"- **Date**: {time.strftime('%Y-%m-%d %H:%M')}",
        f"- **Top-K**: {top_k}",
        f"- **Cases**: {len(results)}",
        "",
    ]

    # Aggregate metrics (exclude NaN cases like B14/B15 with no expected sources)
    valid = [r for r in results if not math.isnan(r.recall)]
    if valid:
        avg_recall = sum(r.recall for r in valid) / len(valid)
        avg_mrr = sum(r.mrr for r in valid) / len(valid)
        hit_rate = sum(1 for r in valid if r.hit) / len(valid)
        avg_latency = sum(r.latency_ms for r in results) / len(results)

        lines.extend([
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Recall@{top_k} | {avg_recall:.1%} |",
            f"| MRR | {avg_mrr:.2f} |",
            f"| Hit Rate | {hit_rate:.0%} ({sum(1 for r in valid if r.hit)}/{len(valid)}) |",
            f"| Avg Latency | {avg_latency:.0f}ms |",
            "",
        ])

        # By difficulty
        for diff in ["easy", "medium", "hard"]:
            subset = [r for r in valid if r.difficulty == diff]
            if subset:
                dr = sum(r.recall for r in subset) / len(subset)
                dh = sum(1 for r in subset if r.hit) / len(subset)
                lines.append(f"- **{diff}**: recall={dr:.0%}, hit_rate={dh:.0%} (n={len(subset)})")
        lines.append("")

    # Per-case table
    lines.extend([
        "## Per-Case Results",
        "",
        "| ID | Difficulty | Recall | MRR | Hit | Missed Sources | Collections |",
        "|----|-----------|--------|-----|-----|----------------|-------------|",
    ])
    for r in results:
        recall_str = f"{r.recall:.0%}" if not math.isnan(r.recall) else "n/a"
        mrr_str = f"{r.mrr:.2f}" if not math.isnan(r.mrr) else "n/a"
        hit_str = "Y" if r.hit else "**N**"
        missed = ", ".join(r.sources_missed) if r.sources_missed else "-"
        colls = ", ".join(r.collections_hit)
        lines.append(f"| {r.case_id} | {r.difficulty} | {recall_str} | {mrr_str} | {hit_str} | {missed} | {colls} |")

    lines.append("")

    # Miss analysis
    misses = [r for r in results if not math.isnan(r.recall) and r.sources_missed]
    if misses:
        lines.extend([
            "## Miss Analysis",
            "",
            "Cases where expected sources were NOT found in top-K:",
            "",
        ])
        for r in misses:
            lines.append(f"### {r.case_id}: {r.query}")
            lines.append(f"- Missed: {', '.join(r.sources_missed)}")
            lines.append(f"- Found instead:")
            for s in r.top_k_sources[:5]:
                lines.append(f"  - [{s['collection']}] {s['source']} ({s['score']})")
            lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Evaluate retrieval quality (no LLM needed)")
    parser.add_argument("--cases", type=str, help="Comma-separated case IDs (e.g. B01,B08)")
    parser.add_argument("--top-k", type=int, default=10, help="Number of results to evaluate")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print per-case details")
    parser.add_argument("--output", "-o", type=str, help="Write markdown report to file")
    args = parser.parse_args()

    # Load dataset
    dataset = EvalDataset.load()
    cases = dataset.cases

    if args.cases:
        case_ids = set(args.cases.split(","))
        cases = [c for c in cases if c.id in case_ids]
        if not cases:
            print(f"No cases matched: {args.cases}")
            sys.exit(1)

    # Initialize retriever
    print(f"Initializing retriever (embedding: {EMBEDDING_MODEL})...")
    from src.rag.retriever import HybridRetriever
    retriever = HybridRetriever(
        qdrant_host=QDRANT_HOST,
        qdrant_port=QDRANT_PORT,
        embedding_model_name=EMBEDDING_MODEL,
    )

    ok, msg = retriever.check_health()
    if not ok:
        print(f"Qdrant unavailable: {msg}")
        sys.exit(1)

    # Run evaluation
    print(f"Evaluating {len(cases)} cases (top_k={args.top_k})...\n")
    results = []
    for case in cases:
        r = evaluate_single(retriever, case, top_k=args.top_k, verbose=args.verbose)
        results.append(r)
        import math
        recall_str = f"{r.recall:.0%}" if not math.isnan(r.recall) else "n/a"
        status = "HIT" if r.hit else "MISS"
        print(f"  {r.case_id}: recall={recall_str} {status} ({r.latency_ms:.0f}ms)")

    # Summary
    import math
    valid = [r for r in results if not math.isnan(r.recall)]
    if valid:
        avg_recall = sum(r.recall for r in valid) / len(valid)
        avg_mrr = sum(r.mrr for r in valid) / len(valid)
        hit_rate = sum(1 for r in valid if r.hit) / len(valid)
        print(f"\n{'='*40}")
        print(f"Recall@{args.top_k}: {avg_recall:.1%}")
        print(f"MRR:       {avg_mrr:.2f}")
        print(f"Hit Rate:  {hit_rate:.0%} ({sum(1 for r in valid if r.hit)}/{len(valid)})")

    # Write report
    if args.output:
        report = generate_report(results, args.top_k)
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"\nReport written to {args.output}")


if __name__ == "__main__":
    main()
