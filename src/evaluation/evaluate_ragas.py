#!/usr/bin/env python3
"""
Construct 3 RAG Evaluation — unified entry point.

Usage:
    python -m src.evaluation.evaluate_ragas --heuristic
    python -m src.evaluation.evaluate_ragas --ragas
    python -m src.evaluation.evaluate_ragas --all
    python -m src.evaluation.evaluate_ragas --generate-ground-truth
    python -m src.evaluation.evaluate_ragas --cases B01,B08
    python -m src.evaluation.evaluate_ragas --output report.md
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import (QDRANT_HOST, QDRANT_PORT,
                        LLM_MODEL, LLM_BASE_URL, LLM_API_KEY, LLM_PROVIDER)
from src.rag.chain import RAGChain
from src.evaluation.runner import EvaluationRunner
from src.evaluation.ragas_evaluator import RagasEvaluator
from src.evaluation.report import generate_report


def build_ragas_evaluator(chain: RAGChain) -> RagasEvaluator:
    embedder = chain.retriever.embedder
    llm = chain.llm
    return RagasEvaluator(embedder=embedder, llm=llm)


def main():
    parser = argparse.ArgumentParser(description="Construct 3 RAG Evaluation")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--heuristic", action="store_true",
                       help="Run heuristic evaluation only (fast, no LLM judge)")
    group.add_argument("--ragas", action="store_true",
                       help="Run RAGAS evaluation only")
    group.add_argument("--all", action="store_true",
                       help="Run both heuristic + RAGAS")
    group.add_argument("--generate-ground-truth", action="store_true",
                       help="Generate ground truth drafts using LLM")

    parser.add_argument("--mode", default="smart",
                        choices=["smart", "high", "stream"],
                        help="Answer mode: smart/high/stream (default: smart)")
    parser.add_argument("--cases", default="",
                        help="Comma-separated case IDs to run (e.g. B01,B08)")
    parser.add_argument("--output", default="",
                        help="Save report to file (default: print to stdout)")
    args = parser.parse_args()

    print("初始化 RAG 系统...")
    chain = RAGChain(
        qdrant_host=QDRANT_HOST, qdrant_port=QDRANT_PORT,
        llm_model=LLM_MODEL, llm_base_url=LLM_BASE_URL,
        llm_api_key=LLM_API_KEY, llm_provider=LLM_PROVIDER,
    )

    ragas_ev = None
    if args.ragas or args.all:
        ragas_ev = build_ragas_evaluator(chain)

    runner = EvaluationRunner(chain=chain, ragas_evaluator=ragas_ev)

    if args.generate_ground_truth:
        print("生成 ground truth 草稿...")
        runner.generate_ground_truth(save=True)
        print("已保存到 data/ragas_dataset.json，请人工审核后修改。")
        return

    if args.heuristic:
        mode = "heuristic"
    elif args.ragas:
        mode = "ragas"
    else:
        mode = "all"

    case_ids = [c.strip().upper() for c in args.cases.split(",") if c.strip()]

    print(f"评估模式: {mode} | 回答模式: {args.mode}")
    print("-" * 60)

    results = runner.run(mode=mode, case_ids=case_ids or None, answer_mode=args.mode)

    report = generate_report(results, mode=mode)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"报告已保存到: {args.output}")
    else:
        print(report)

    if results:
        avg = sum(r.composite_score for r in results) / len(results)
        print(f"\n综合得分: {avg:.2f}/1.00")


if __name__ == "__main__":
    main()
