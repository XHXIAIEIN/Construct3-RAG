"""Evaluation runner: orchestrates heuristic + RAGAS evaluation."""
from __future__ import annotations
import logging
import time
from pathlib import Path
from typing import List, Optional

from src.evaluation import EvalResult, MetricResult
from src.evaluation.dataset import EvalDataset, EvalCase, DEFAULT_DATASET_PATH
from src.evaluation.heuristic_evaluator import HeuristicEvaluator
from src.evaluation.ragas_evaluator import RagasEvaluator
from src.rag.chain import RAGChain, RAGResponse

logger = logging.getLogger(__name__)


class EvaluationRunner:
    def __init__(
        self,
        chain: RAGChain,
        dataset_path: Path = DEFAULT_DATASET_PATH,
        ragas_evaluator: Optional[RagasEvaluator] = None,
    ):
        self._chain = chain
        self._dataset = EvalDataset.load(dataset_path)
        self._heuristic = HeuristicEvaluator()
        self._ragas = ragas_evaluator

    def run(
        self,
        mode: str = "all",           # "heuristic" | "ragas" | "all"
        case_ids: Optional[List[str]] = None,
        answer_mode: str = "smart",  # "smart" | "high" | "stream"
    ) -> List[EvalResult]:
        cases = self._dataset.cases
        if case_ids:
            wanted = set(case_ids)
            cases = [c for c in cases if c.id in wanted]

        results = []
        for case in cases:
            logger.info("Evaluating %s: %s", case.id, case.query[:50])
            result = self._eval_case(case, mode, answer_mode)
            results.append(result)
        return results

    def _eval_case(
        self, case: EvalCase, mode: str, answer_mode: str
    ) -> EvalResult:
        t0 = time.time()
        response, contexts = self._get_response_and_contexts(case, answer_mode)
        latency_ms = (time.time() - t0) * 1000

        metrics: List[MetricResult] = []

        if mode in ("heuristic", "all"):
            metrics += self._heuristic.evaluate(
                case.query, response, case, latency_ms=latency_ms,
            )

        if mode in ("ragas", "all") and self._ragas is not None:
            metrics += self._ragas.evaluate(
                case.query, response,
                contexts=contexts,
                ground_truth=case.ground_truth,
            )

        return EvalResult(
            query_id=case.id,
            query=case.query,
            answer=response.answer,
            metrics=metrics,
            latency_ms=latency_ms,
        )

    def _get_response_and_contexts(
        self, case: EvalCase, answer_mode: str
    ) -> tuple[RAGResponse, list[str]]:
        search_results = self._chain.retriever.search_all_with_rerank(case.query)
        contexts = [r.text for r in search_results]

        try:
            if answer_mode == "high":
                response = self._chain.answer_high_confidence(case.query)
            elif answer_mode == "stream":
                chunks = list(self._chain.answer_stream(case.query))
                response = RAGResponse(
                    answer="".join(chunks),
                    sources=[], query_type="stream", confidence="unknown",
                )
            else:
                response = self._chain.answer_smart(case.query)
        except Exception as e:
            response = RAGResponse(
                answer=f"[ERROR] {e}",
                sources=[], query_type="error", confidence="none",
            )

        return response, contexts

    def generate_ground_truth(self, save: bool = True) -> EvalDataset:
        """Use LLM to draft ground truth for cases with empty ground_truth."""
        prompt_tpl = (
            "请根据你的知识，用1-3句话简洁回答以下关于 Construct 3 的问题。"
            "只输出答案，不要解释。\n\n问题：{query}"
        )
        for case in self._dataset.cases:
            if case.ground_truth:
                continue
            try:
                prompt = prompt_tpl.format(query=case.query)
                answer = self._chain.llm.generate(prompt)
                case.ground_truth = answer.strip()
                logger.info("Generated ground truth for %s", case.id)
            except Exception:
                logger.warning("Failed to generate ground truth for %s", case.id)

        if save:
            self._dataset.save()
        return self._dataset
