"""Ranking, latency, aggregation, and paired-comparison metrics.

The evaluator reports query-level values first and derives every macro number
from those rows.  Negative-only judgments stay in noise/error denominators but
are deliberately excluded from positive-ranking denominators.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .models import GoldCase


_CUTS = (1, 3, 5, 10)


def _first_ranks(ordered_ids: Sequence[str]) -> dict[str, int]:
    ranks: dict[str, int] = {}
    for rank, stable_id in enumerate(ordered_ids, 1):
        ranks.setdefault(stable_id, rank)
    return ranks


def _positive_grades(case: GoldCase) -> dict[str, float]:
    grades = dict(case.graded_relevance)
    for judgment in case.relevant_results:
        target_grade = grades.get(judgment.stable_id, 3.0)
        grades.setdefault(judgment.stable_id, target_grade)
        for alternative in judgment.alternatives:
            grades.setdefault(alternative, target_grade)
    for stable_id in case.allowed_alternatives:
        grades.setdefault(stable_id, 1.0)
    return {stable_id: grade for stable_id, grade in grades.items() if grade > 0}


def _ndcg(ordered_ids: Sequence[str], grades: Mapping[str, float], k: int) -> float | None:
    if not grades:
        return None
    gains = [float(grades.get(stable_id, 0.0)) for stable_id in ordered_ids[:k]]
    dcg = sum((2.0**grade - 1.0) / math.log2(rank + 1) for rank, grade in enumerate(gains, 1))
    ideal = sorted(grades.values(), reverse=True)[:k]
    idcg = sum((2.0**grade - 1.0) / math.log2(rank + 1) for rank, grade in enumerate(ideal, 1))
    return dcg / idcg if idcg else None


def evaluate_ranking(ordered_ids: Sequence[str], case: GoldCase) -> dict[str, Any]:
    """Evaluate an ordered, already-deduplicated stable-ID result list."""

    ordered = list(ordered_ids)
    ranks = _first_ranks(ordered)
    duplicate_count = len(ordered) - len(ranks)
    grades = _positive_grades(case)
    positive_ranks = [ranks[stable_id] for stable_id in grades if stable_id in ranks]

    group_rows: list[dict[str, Any]] = []
    for judgment in case.relevant_results:
        accepted = (judgment.stable_id, *judgment.alternatives)
        accepted_ranks = [ranks[item] for item in accepted if item in ranks]
        best_rank = min(accepted_ranks) if accepted_ranks else None
        limit = judgment.within_top_k or case.max_rank
        group_rows.append(
            {
                "stable_id": judgment.stable_id,
                "accepted_ids": list(accepted),
                "best_rank": best_rank,
                "rank_limit": limit,
                "passes_rank_limit": (
                    best_rank is not None and limit is not None and best_rank <= limit
                ),
            }
        )

    forbidden_rows: list[dict[str, Any]] = []
    for judgment in case.forbidden_results:
        rank = ranks.get(judgment.stable_id)
        limit = judgment.within_top_k or 10
        violation = rank is not None and rank <= limit
        forbidden_rows.append(
            {
                "stable_id": judgment.stable_id,
                "rank": rank,
                "within_top_k": limit,
                "violation": violation,
            }
        )

    positive_case = bool(case.relevant_results)
    hit_at: dict[str, float | None] = {}
    recall_at: dict[str, float | None] = {}
    all_relevant_at: dict[str, float | None] = {}
    for k in _CUTS:
        hit_at[str(k)] = (
            float(any(rank <= k for rank in positive_ranks)) if positive_case else None
        )
        if positive_case:
            satisfied = sum(
                1
                for row in group_rows
                if row["best_rank"] is not None and row["best_rank"] <= k
            )
            recall_at[str(k)] = satisfied / len(group_rows)
            all_relevant_at[str(k)] = float(satisfied == len(group_rows))
        else:
            recall_at[str(k)] = None
            all_relevant_at[str(k)] = None

    return {
        "positive_case": positive_case,
        "negative_only": not positive_case,
        "result_count": len(ordered),
        "duplicate_count": duplicate_count,
        "hit_at": hit_at,
        "recall_at": recall_at,
        "all_relevant_at": all_relevant_at,
        "mrr": (1.0 / min(positive_ranks)) if positive_ranks else (0.0 if positive_case else None),
        "ndcg_at_5": _ndcg(ordered, grades, 5),
        "ndcg_at_10": _ndcg(ordered, grades, 10),
        "max_rank_pass": (
            float(all(row["passes_rank_limit"] for row in group_rows))
            if positive_case
            else None
        ),
        "relevant": group_rows,
        "allowed_alternative_hits": [
            {"stable_id": stable_id, "rank": ranks[stable_id]}
            for stable_id in case.allowed_alternatives
            if stable_id in ranks
        ],
        "forbidden": forbidden_rows,
        "forbidden_violation": any(row["violation"] for row in forbidden_rows),
        "forbidden_violation_ids": [
            row["stable_id"] for row in forbidden_rows if row["violation"]
        ],
    }


def evaluate_dedup_expectations(
    expectations: dict[str, Any] | tuple[dict[str, Any], ...],
    lookup_ids: Sequence[str],
    semantic_ids: Sequence[str],
) -> dict[str, Any]:
    """Evaluate fixture-provided lookup/semantic exact-ID assertions."""

    if isinstance(expectations, dict):
        rows = [expectations] if expectations else []
    else:
        rows = list(expectations)
    lookup_counts = Counter(lookup_ids)
    semantic_counts = Counter(semantic_ids)
    checks: list[dict[str, Any]] = []
    for row in rows:
        stable_id = row.get("id") or row.get("stable_id") or row.get("result_id")
        if not isinstance(stable_id, str):
            checks.append({"expectation": row, "passes": False, "error": "missing stable ID"})
            continue
        lookup_count = lookup_counts[stable_id]
        semantic_count = semantic_counts[stable_id]
        total = lookup_count + semantic_count
        failures: list[str] = []
        maximum = row.get("max_occurrences_total")
        if isinstance(maximum, int) and not isinstance(maximum, bool) and total > maximum:
            failures.append(f"total occurrences {total} exceed {maximum}")
        forbidden_route = row.get("forbidden_in_route")
        if forbidden_route == "semantic" and semantic_count:
            failures.append("stable ID remains in semantic route")
        if forbidden_route == "lookup" and lookup_count:
            failures.append("stable ID remains in lookup route")
        required_route = row.get("required_in_route")
        if required_route == "semantic" and not semantic_count:
            failures.append("stable ID missing from semantic route")
        if required_route == "lookup" and not lookup_count:
            failures.append("stable ID missing from lookup route")
        checks.append(
            {
                "stable_id": stable_id,
                "lookup_occurrences": lookup_count,
                "semantic_occurrences": semantic_count,
                "total_occurrences": total,
                "passes": not failures,
                "failures": failures,
                "expectation": row,
            }
        )
    return {
        "applicable": bool(checks),
        "passes": all(row["passes"] for row in checks),
        "checks": checks,
    }


def percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def latency_stats(values: Sequence[float]) -> dict[str, float | int | None]:
    values = [float(value) for value in values]
    if not values:
        return {
            "count": 0,
            "mean_ms": None,
            "p50_ms": None,
            "p95_ms": None,
            "p99_ms": None,
            "max_ms": None,
        }
    return {
        "count": len(values),
        "mean_ms": statistics.fmean(values),
        "p50_ms": percentile(values, 0.50),
        "p95_ms": percentile(values, 0.95),
        "p99_ms": percentile(values, 0.99),
        "max_ms": max(values),
    }


def _mean_non_null(values: Iterable[float | None]) -> float | None:
    selected = [float(value) for value in values if value is not None]
    return statistics.fmean(selected) if selected else None


def aggregate_strategy_rows(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate one strategy's per-query rows without hiding denominators."""

    primary = [row["metrics"]["semantic_pre_lookup"] for row in rows]
    post = [row["metrics"]["semantic_post_lookup"] for row in rows]
    orchestrated = [row["metrics"]["lookup_then_semantic_projection"] for row in rows]
    attempts = sum(row["collection_accounting"]["attempted"] for row in rows)
    errors = sum(row["collection_accounting"]["errors"] for row in rows)
    raw_candidates = sum(row["exact_dedup"]["input_count"] for row in rows)
    duplicates = sum(row["exact_dedup"]["removed_count"] for row in rows)
    query_errors = [row for row in rows if row.get("errors")]
    contract_failures = [row for row in rows if row.get("contract_failures")]
    negative_rows = [
        row
        for row in rows
        if row["metrics"]["semantic_post_lookup"]["negative_only"]
    ]
    dedup_rows = [row for row in rows if row["dedup_expectations"]["applicable"]]

    def quality(metric_rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
        positive = sum(bool(metric["positive_case"]) for metric in metric_rows)
        return {
            "positive_query_count": positive,
            "negative_only_query_count": len(metric_rows) - positive,
            "hit_at_1": _mean_non_null(metric["hit_at"]["1"] for metric in metric_rows),
            "hit_at_3": _mean_non_null(metric["hit_at"]["3"] for metric in metric_rows),
            "hit_at_5": _mean_non_null(metric["hit_at"]["5"] for metric in metric_rows),
            "hit_at_10": _mean_non_null(metric["hit_at"]["10"] for metric in metric_rows),
            "recall_at_5": _mean_non_null(metric["recall_at"]["5"] for metric in metric_rows),
            "recall_at_10": _mean_non_null(metric["recall_at"]["10"] for metric in metric_rows),
            "mrr": _mean_non_null(metric["mrr"] for metric in metric_rows),
            "ndcg_at_5": _mean_non_null(metric["ndcg_at_5"] for metric in metric_rows),
            "ndcg_at_10": _mean_non_null(metric["ndcg_at_10"] for metric in metric_rows),
            "max_rank_pass_rate": _mean_non_null(
                metric["max_rank_pass"] for metric in metric_rows
            ),
            "forbidden_violation_rate": (
                sum(bool(metric["forbidden_violation"]) for metric in metric_rows)
                / len(metric_rows)
                if metric_rows
                else None
            ),
        }

    latencies = [row["timings_ms"]["semantic_total"] for row in rows]
    warm_latencies = [
        row["timings_ms"]["semantic_total"] for row in rows if not row.get("cold_query")
    ]
    return {
        "query_count": len(rows),
        "quality": {
            "semantic_pre_lookup": quality(primary),
            "semantic_post_lookup": quality(post),
            "lookup_then_semantic_projection": quality(orchestrated),
        },
        "no_result_rate": (
            sum(not row["ordered_stable_ids"] for row in rows) / len(rows) if rows else None
        ),
        "no_result_count": sum(not row["ordered_stable_ids"] for row in rows),
        "query_error_rate": len(query_errors) / len(rows) if rows else None,
        "query_error_count": len(query_errors),
        "query_error_ids": [row["case_id"] for row in query_errors],
        "contract_failure_rate": (
            len(contract_failures) / len(rows) if rows else None
        ),
        "contract_failure_count": len(contract_failures),
        "contract_failure_ids": [row["case_id"] for row in contract_failures],
        "collection_error_rate": errors / attempts if attempts else None,
        "collection_attempts": attempts,
        "collection_errors": errors,
        "exact_duplicate_rate": duplicates / raw_candidates if raw_candidates else 0.0,
        "exact_duplicates_removed": duplicates,
        "filter_violation_rate": (
            sum(bool(row["filter_validation"]["violation_ids"]) for row in rows) / len(rows)
            if rows
            else None
        ),
        "dedup_expectation_pass_rate": (
            sum(bool(row["dedup_expectations"]["passes"]) for row in dedup_rows)
            / len(dedup_rows)
            if dedup_rows
            else None
        ),
        "dedup_expectation_applicable_count": len(dedup_rows),
        "negative_only_outcomes": {
            "query_count": len(negative_rows),
            "no_result_count": sum(not row["ordered_stable_ids"] for row in negative_rows),
            "no_result_rate": (
                sum(not row["ordered_stable_ids"] for row in negative_rows)
                / len(negative_rows)
                if negative_rows
                else None
            ),
            "returned_result_noise_count": sum(
                bool(row["ordered_stable_ids"]) for row in negative_rows
            ),
            "returned_result_noise_rate": (
                sum(bool(row["ordered_stable_ids"]) for row in negative_rows)
                / len(negative_rows)
                if negative_rows
                else None
            ),
            "query_error_count": sum(bool(row.get("errors")) for row in negative_rows),
            "forbidden_violation_count": sum(
                bool(row["metrics"]["semantic_post_lookup"]["forbidden_violation"])
                for row in negative_rows
            ),
            "noise_case_ids": [
                row["case_id"] for row in negative_rows if row["ordered_stable_ids"]
            ],
        },
        "final_budget_violation_count": sum(
            len(row["ordered_stable_ids"]) > row["final_budget"] for row in rows
        ),
        "latency": {
            "all": latency_stats(latencies),
            "warm": latency_stats(warm_latencies),
            "embedding": latency_stats([row["timings_ms"]["embedding"] for row in rows]),
            "sparse": latency_stats([row["timings_ms"]["sparse"] for row in rows]),
            "qdrant": latency_stats([row["timings_ms"]["qdrant"] for row in rows]),
            "fusion": latency_stats([row["timings_ms"]["fusion"] for row in rows]),
            "reranker": latency_stats([row["timings_ms"]["reranker"] for row in rows]),
        },
    }


def stratified_summaries(
    query_rows: Sequence[dict[str, Any]], strategies: Sequence[str]
) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for strategy in strategies:
        strategy_rows = [
            {**query["strategies"][strategy], "case_id": query["case"]["id"]}
            for query in query_rows
            if strategy in query["strategies"]
        ]
        by_split: dict[str, Any] = {}
        by_family: dict[str, Any] = {}
        for split in sorted({query["case"]["split"] for query in query_rows}):
            selected = [
                {**query["strategies"][strategy], "case_id": query["case"]["id"]}
                for query in query_rows
                if query["case"]["split"] == split and strategy in query["strategies"]
            ]
            by_split[split] = aggregate_strategy_rows(selected)
        for family in sorted({query["case"]["task_family"] for query in query_rows}):
            selected = [
                {**query["strategies"][strategy], "case_id": query["case"]["id"]}
                for query in query_rows
                if query["case"]["task_family"] == family and strategy in query["strategies"]
            ]
            by_family[family] = aggregate_strategy_rows(selected)
        summaries[strategy] = {
            "overall": aggregate_strategy_rows(strategy_rows),
            "by_split": by_split,
            "by_task_family": by_family,
        }
    return summaries


def paired_comparisons(
    query_rows: Sequence[dict[str, Any]], strategies: Sequence[str]
) -> dict[str, Any]:
    requested = set(strategies)
    pairs = [
        ("limited", "fanout"),
        ("fanout", "rrf"),
        ("rrf", "rerank"),
    ]
    output: dict[str, Any] = {}
    for baseline, candidate in pairs:
        if baseline not in requested or candidate not in requested:
            continue
        rows: list[dict[str, Any]] = []
        for query in query_rows:
            left = query["strategies"][baseline]
            right = query["strategies"][candidate]
            left_metrics = left["metrics"]["semantic_pre_lookup"]
            right_metrics = right["metrics"]["semantic_pre_lookup"]

            def delta(name: str) -> float | None:
                left_value = left_metrics.get(name)
                right_value = right_metrics.get(name)
                if left_value is None or right_value is None:
                    return None
                return float(right_value) - float(left_value)

            ndcg_delta = delta("ndcg_at_10")
            recall_left = left_metrics["recall_at"]["10"]
            recall_right = right_metrics["recall_at"]["10"]
            recall_delta = (
                float(recall_right) - float(recall_left)
                if recall_left is not None and recall_right is not None
                else None
            )
            mrr_delta = delta("mrr")
            signal = next(
                (value for value in (ndcg_delta, recall_delta, mrr_delta) if value not in (None, 0.0)),
                0.0,
            )
            verdict = "improved" if signal > 0 else "regressed" if signal < 0 else "tied"

            left_ranks = _first_ranks(left["ordered_pre_lookup_stable_ids"])
            right_ranks = _first_ranks(right["ordered_pre_lookup_stable_ids"])
            rank_changes = []
            for judgment in left_metrics["relevant"]:
                accepted = tuple(judgment["accepted_ids"])
                left_rank = min((left_ranks[x] for x in accepted if x in left_ranks), default=None)
                right_rank = min((right_ranks[x] for x in accepted if x in right_ranks), default=None)
                rank_changes.append(
                    {
                        "stable_id": judgment["stable_id"],
                        "baseline_rank": left_rank,
                        "candidate_rank": right_rank,
                        "rank_delta": (
                            left_rank - right_rank
                            if left_rank is not None and right_rank is not None
                            else None
                        ),
                    }
                )
            rows.append(
                {
                    "case_id": query["case"]["id"],
                    "query": query["case"]["query"],
                    "split": query["case"]["split"],
                    "task_family": query["case"]["task_family"],
                    "candidate_batch_digest_equal": (
                        left["candidate_batch_digest"] == right["candidate_batch_digest"]
                    ),
                    "ndcg_at_10_delta": ndcg_delta,
                    "recall_at_10_delta": recall_delta,
                    "mrr_delta": mrr_delta,
                    "semantic_latency_delta_ms": (
                        right["timings_ms"]["semantic_total"]
                        - left["timings_ms"]["semantic_total"]
                    ),
                    "verdict": verdict,
                    "rank_changes": rank_changes,
                }
            )
        output[f"{candidate}_vs_{baseline}"] = {
            "baseline": baseline,
            "candidate": candidate,
            "query_count": len(rows),
            "candidate_batch_digest_all_equal": all(
                row["candidate_batch_digest_equal"] for row in rows
            ),
            "improved_queries": [row["case_id"] for row in rows if row["verdict"] == "improved"],
            "regressed_queries": [row["case_id"] for row in rows if row["verdict"] == "regressed"],
            "tied_queries": [row["case_id"] for row in rows if row["verdict"] == "tied"],
            "mean_ndcg_at_10_delta": _mean_non_null(row["ndcg_at_10_delta"] for row in rows),
            "mean_recall_at_10_delta": _mean_non_null(row["recall_at_10_delta"] for row in rows),
            "mean_mrr_delta": _mean_non_null(row["mrr_delta"] for row in rows),
            "mean_semantic_latency_delta_ms": _mean_non_null(
                row["semantic_latency_delta_ms"] for row in rows
            ),
            "per_query": rows,
        }
    return output
