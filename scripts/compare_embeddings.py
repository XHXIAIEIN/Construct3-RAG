#!/usr/bin/env python3
"""
Compare fine-tuned vs base Qwen3-Embedding model on retrieval task.

Usage:
    python scripts/compare_embeddings.py [--n 200] [--k 5]

Loads query-positive pairs from Construct3-LoRA training data,
builds an in-memory corpus, and measures Hit@k / MRR for both models.
No Qdrant re-indexing required.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

LORA_DATA = Path("D:/Users/Administrator/Documents/GitHub/Construct3-LoRA/data/pairs")
FINETUNED_MODEL = "D:/Users/Administrator/Documents/GitHub/Construct3-LoRA/output/qwen3-embedding-4b-c3/merged"
BASE_MODEL = "Qwen/Qwen3-Embedding-4B"
QUERY_INSTRUCTION = "Instruct: Retrieve relevant Construct 3 documentation for the following query\nQuery: "


def load_pairs(n: int) -> list[dict]:
    pairs = []
    for f in LORA_DATA.glob("*.jsonl"):
        with open(f, encoding="utf-8") as fp:
            for line in fp:
                obj = json.loads(line)
                if "query" not in obj or "positive" not in obj:
                    continue
                pairs.append({"query": obj["query"], "positive": obj["positive"]})
    # Deduplicate by positive text to avoid trivially easy corpus
    seen = set()
    deduped = []
    for p in pairs:
        key = p["positive"][:100]
        if key not in seen:
            seen.add(key)
            deduped.append(p)
    return deduped[:n]


def cosine_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """a: (n, d), b: (m, d) → (n, m) similarity matrix."""
    a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-8)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-8)
    return a_norm @ b_norm.T


def evaluate(model_name: str, pairs: list[dict], k: int, device: str = "cuda") -> dict:
    from sentence_transformers import SentenceTransformer

    print(f"\n  加载模型: {Path(model_name).name if '/' not in model_name else model_name.split('/')[-1]}")
    t0 = time.time()
    model = SentenceTransformer(model_name, device=device, trust_remote_code=True)
    load_time = time.time() - t0
    print(f"  加载完成 ({load_time:.1f}s)，编码中...")

    queries = [QUERY_INSTRUCTION + p["query"] for p in pairs]
    positives = [p["positive"] for p in pairs]

    t1 = time.time()
    q_vecs = model.encode(queries, batch_size=16, show_progress_bar=True, normalize_embeddings=True)
    p_vecs = model.encode(positives, batch_size=16, show_progress_bar=True, normalize_embeddings=True)
    encode_time = time.time() - t1

    # (n, n) similarity — diagonal is the ground-truth positive
    sims = q_vecs @ p_vecs.T  # already normalized

    n = len(pairs)
    hits = {j: 0 for j in [1, 3, k]}
    rr_sum = 0.0

    for i in range(n):
        ranked = np.argsort(-sims[i])
        rank = int(np.where(ranked == i)[0][0]) + 1  # 1-indexed
        rr_sum += 1.0 / rank
        for j in hits:
            if rank <= j:
                hits[j] += 1

    dim = q_vecs.shape[1]
    return {
        "model": model_name,
        "dim": dim,
        "n": n,
        "encode_time": encode_time,
        "hit@1": hits[1] / n,
        "hit@3": hits[3] / n,
        f"hit@{k}": hits[k] / n,
        "mrr": rr_sum / n,
    }


def print_results(results: list[dict], k: int):
    print("\n" + "=" * 60)
    print("Embedding 模型对比结果")
    print("=" * 60)
    header = f"{'模型':<35} {'维度':>5} {'Hit@1':>6} {'Hit@3':>6} {f'Hit@{k}':>6} {'MRR':>6} {'编码(s)':>8}"
    print(header)
    print("-" * 60)
    for r in results:
        name = Path(r["model"]).name if "/" not in r["model"] else r["model"].split("/")[-1]
        # Use parent.name if last part is "merged"
        if name == "merged":
            name = Path(r["model"]).parent.name
        print(
            f"{name:<35} {r['dim']:>5} "
            f"{r['hit@1']:>6.3f} {r['hit@3']:>6.3f} {r[f'hit@{k}']:>6.3f} "
            f"{r['mrr']:>6.3f} {r['encode_time']:>8.1f}"
        )

    if len(results) == 2:
        print("-" * 60)
        ft = next((r for r in results if "merged" in r["model"] or "c3" in r["model"]), results[0])
        base = next((r for r in results if r is not ft), results[1])
        delta_hit1 = ft["hit@1"] - base["hit@1"]
        delta_mrr = ft["mrr"] - base["mrr"]
        print(f"  微调 vs 基础模型 △Hit@1={delta_hit1:+.3f}  △MRR={delta_mrr:+.3f}")
    print("=" * 60)
    print(f"  语料规模: {results[0]['n']} 条 query-positive 对")
    print("  数据来源: Construct3-LoRA 训练集（含训练集泄漏，仅供参考）")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=300, help="评估样本数 (default: 300)")
    parser.add_argument("--k", type=int, default=5, help="Hit@k 的 k 值 (default: 5)")
    parser.add_argument("--device", default="cuda", help="cuda / cpu (default: cuda)")
    parser.add_argument("--base-only", action="store_true", help="只测 base 模型")
    parser.add_argument("--ft-only", action="store_true", help="只测微调模型")
    args = parser.parse_args()

    print(f"加载训练对（最多 {args.n} 条，去重后）...")
    pairs = load_pairs(args.n)
    print(f"实际使用: {len(pairs)} 条")

    results = []
    if not args.base_only:
        results.append(evaluate(FINETUNED_MODEL, pairs, args.k, args.device))
    if not args.ft_only:
        results.append(evaluate(BASE_MODEL, pairs, args.k, args.device))

    print_results(results, args.k)


if __name__ == "__main__":
    main()
