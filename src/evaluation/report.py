"""Markdown report generation for evaluation results."""
from __future__ import annotations
from typing import List

from src.evaluation import EvalResult


def generate_report(results: List[EvalResult], mode: str = "all") -> str:
    if not results:
        return "# 无评估结果\n"

    total = len(results)
    avg_composite = sum(r.composite_score for r in results) / total
    avg_latency = sum(r.latency_ms for r in results) / total

    grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for r in results:
        grade_counts[r.grade] += 1

    # Collect weighted metric names in order of first appearance
    weighted_names: list[str] = []
    seen: set[str] = set()
    for r in results:
        for m in r.metrics:
            if m.weight > 0 and m.name not in seen:
                weighted_names.append(m.name)
                seen.add(m.name)

    lines = [
        "# Construct 3 RAG 评估报告",
        "",
        f"**模式**: `{mode}` | **题数**: {total} | "
        f"**平均耗时**: {avg_latency:.0f}ms",
        "",
        "## 总体评分",
        "",
        "| 指标 | 平均分 | 权重 |",
        "|------|--------|------|",
    ]

    for name in weighted_names:
        scores, weight = [], 0.0
        for r in results:
            m = next((m for m in r.metrics if m.name == name), None)
            if m:
                scores.append(m.score)
                weight = m.weight
        if scores:
            avg = sum(scores) / len(scores)
            lines.append(f"| {name} | {avg:.2f} | {weight:.0%} |")

    lines += [
        f"| **综合得分** | **{avg_composite:.2f}** | — |",
        "",
        f"等级分布: A={grade_counts['A']} B={grade_counts['B']} "
        f"C={grade_counts['C']} D={grade_counts['D']}",
        "",
        "## 逐题结果",
        "",
        "| ID | 综合 | 等级 | 耗时(ms) |",
        "|----|------|------|----------|",
    ]

    for r in results:
        lines.append(
            f"| {r.query_id} | {r.composite_score:.2f} | {r.grade} | {r.latency_ms:.0f} |"
        )

    lines += ["", "## 详细结果", ""]
    for r in results:
        lines += [
            f"### {r.query_id} [{r.grade}] {r.query}",
            "",
            f"**综合**: {r.composite_score:.2f} | **耗时**: {r.latency_ms:.0f}ms",
            "",
            "**指标明细**:",
            "",
        ]
        for m in sorted(r.metrics, key=lambda x: -x.weight):
            tag = " _(诊断)_" if m.weight == 0 else ""
            lines.append(f"- {m.name}: {m.score:.2f}{tag}")
        lines += ["", f"**回答**: {r.answer[:400]}", ""]

    return "\n".join(lines)
