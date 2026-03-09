"""
RAGAS-inspired evaluation metrics.

Embedding metrics (no LLM needed):
  - context_precision    (embedding cosine similarity: query vs contexts)
  - context_recall       (embedding coverage: ground_truth vs contexts)
  - answer_correctness   (embedding similarity: answer vs ground_truth)
  - answer_completeness  (diagnostic only, same as correctness)

LLM-judge metrics (uses local Qwen3.5-9B via LLMClient):
  - faithfulness         (is answer grounded in contexts?)
  - answer_relevance     (does answer address the question?)
"""
from __future__ import annotations
import logging
from typing import List

import numpy as np

from src.evaluation import MetricResult
from src.rag.chain import RAGResponse

logger = logging.getLogger(__name__)

_METRIC_WEIGHTS = {
    "faithfulness":          0.20,
    "answer_relevance":      0.20,
    "answer_correctness":    0.20,
    "context_precision":     0.15,
    "context_recall":        0.10,
    "answer_completeness":   0.0,   # diagnostic only
}

_FAITHFULNESS_PROMPT = (
    "你是一个评估助手。判断以下回答是否完全基于给定的参考文档，没有编造文档中没有的信息。\n\n"
    "参考文档：\n{contexts}\n\n"
    "回答：\n{answer}\n\n"
    "请只回答：1（完全基于文档）或 0（包含文档外的信息）。"
)

_RELEVANCE_PROMPT = (
    "你是一个评估助手。判断以下回答是否针对了给定的问题（没有跑题或答非所问）。\n\n"
    "问题：{query}\n"
    "回答：{answer}\n\n"
    "请给出 0.0 到 1.0 的评分（1.0=完全针对问题，0.0=完全跑题）。只输出数字。"
)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class RagasEvaluator:
    def __init__(self, embedder=None, llm=None):
        self._embedder = embedder
        self._llm = llm

    def _metric_weight(self, name: str) -> float:
        return _METRIC_WEIGHTS.get(name, 0.0)

    def _embed(self, texts: list[str]) -> np.ndarray:
        vecs = self._embedder.encode(texts)
        return np.array(vecs)

    def _compute_context_precision(
        self, query: str, contexts: list[str], threshold: float = 0.4
    ) -> float:
        if not contexts or self._embedder is None:
            return 0.0
        q_vec = self._embed([query])[0]
        c_vecs = self._embed(contexts)
        sims = [_cosine_similarity(q_vec, cv) for cv in c_vecs]
        relevant = sum(1 for s in sims if s >= threshold)
        return relevant / len(contexts)

    def _compute_context_recall(
        self, contexts: list[str], ground_truth: str
    ) -> float:
        if not ground_truth or not contexts or self._embedder is None:
            return 0.0
        gt_vec = self._embed([ground_truth])[0]
        c_vecs = self._embed(contexts)
        sims = [_cosine_similarity(gt_vec, cv) for cv in c_vecs]
        return min(1.0, max(sims))

    def _compute_answer_correctness(
        self, answer: str, ground_truth: str
    ) -> float:
        if not ground_truth or self._embedder is None:
            return 0.0
        a_vec = self._embed([answer])[0]
        gt_vec = self._embed([ground_truth])[0]
        return max(0.0, _cosine_similarity(a_vec, gt_vec))

    def _compute_answer_completeness(
        self, answer: str, ground_truth: str
    ) -> float:
        return self._compute_answer_correctness(answer, ground_truth)

    def _compute_faithfulness(
        self, answer: str, contexts: list[str]
    ) -> float:
        if not self._llm or not contexts:
            return 0.0
        ctx_text = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(contexts[:5]))
        prompt = _FAITHFULNESS_PROMPT.format(
            contexts=ctx_text, answer=answer[:800]
        )
        try:
            out = self._llm.generate(prompt, max_tokens=10).strip()
            return 1.0 if out.startswith("1") else 0.0
        except Exception:
            logger.warning("Faithfulness LLM call failed", exc_info=True)
            return 0.0

    def _compute_answer_relevance(
        self, query: str, answer: str
    ) -> float:
        if not self._llm:
            return 0.0
        prompt = _RELEVANCE_PROMPT.format(query=query, answer=answer[:800])
        try:
            out = self._llm.generate(prompt, max_tokens=10).strip()
            return min(1.0, max(0.0, float(out)))
        except (ValueError, Exception):
            logger.warning("Answer relevance LLM call failed", exc_info=True)
            return 0.0

    def evaluate(
        self,
        query: str,
        response: RAGResponse,
        contexts: list[str],
        ground_truth: str = "",
    ) -> List[MetricResult]:
        answer = response.answer

        return [
            MetricResult(
                name="faithfulness",
                score=self._compute_faithfulness(answer, contexts),
                weight=self._metric_weight("faithfulness"),
            ),
            MetricResult(
                name="answer_relevance",
                score=self._compute_answer_relevance(query, answer),
                weight=self._metric_weight("answer_relevance"),
            ),
            MetricResult(
                name="answer_correctness",
                score=self._compute_answer_correctness(answer, ground_truth),
                weight=self._metric_weight("answer_correctness"),
            ),
            MetricResult(
                name="context_precision",
                score=self._compute_context_precision(query, contexts),
                weight=self._metric_weight("context_precision"),
            ),
            MetricResult(
                name="context_recall",
                score=self._compute_context_recall(contexts, ground_truth),
                weight=self._metric_weight("context_recall"),
            ),
            MetricResult(
                name="answer_completeness",
                score=self._compute_answer_completeness(answer, ground_truth),
                weight=0.0,  # diagnostic only
            ),
        ]
