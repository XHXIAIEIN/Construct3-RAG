# Construct3-LoRA Embedding Fine-tuning Design

**Goal:** Fine-tune `Qwen3-Embedding-4B` on Construct 3-specific data to improve semantic retrieval quality in the RAG system, with particular focus on bridging the vocabulary gap between Chinese user queries and English C3 documentation.

**Architecture:** Standalone repo `Construct3-LoRA` with a data collection pipeline feeding a LoRA-based embedding fine-tuning workflow. Trained artifacts integrate back into the RAG system via a single environment variable change. The `sft/` directory is reserved for future LLM LoRA fine-tuning but not implemented in this phase.

**Tech Stack:** Python 3.14, sentence-transformers, peft (LoRA), PyTorch nightly cu128 (RTX 5090 / sm_120), Claude API (synthetic data), Qwen3-Embedding-4B

---

## Goals

1. **C3 term understanding** — The embedding model should align Chinese user queries (e.g. "碰撞检测") with English C3 ACE names ("On collision with object") and their documentation.
2. **Cross-domain knowledge transfer** — Queries using general game dev vocabulary (Unity, Godot analogies) should map to equivalent C3 concepts.
3. **ACE-type awareness** — The model should distinguish between looping / triggered / normal conditions, and between action / condition / expression ACE types.
4. **Event sheet JSON quality** (indirect) — Better retrieval means better context for `answer_code()`, reducing hallucinated fields.

---

## Repo Structure

```
Construct3-LoRA/
  data/
    raw/               # scraped data — .gitignore
    processed/         # cleaned, deduplicated
    pairs/             # final training pairs (.jsonl) — .gitignore
  src/
    collect/
      lookup_chain_miner.py   # primary: CSV → ACE Schema → Manual chain
      manual_chunker.py       # Construct3-Manual H2 chunking + synthetic queries
      synthetic_gen.py        # Claude API: game-dev → C3 knowledge transfer pairs
      rag_log_collector.py    # RAG system logs → query/answer pairs (ongoing)
    embedding/
      dataset.py              # build triplet dataset from pairs/
      trainer.py              # Qwen3-Embedding-4B LoRA fine-tuning
      evaluate.py             # Recall@5, MRR@10 vs baseline
    sft/
      .gitkeep                # reserved for future Qwen3.5-9B LoRA
  scripts/
    collect_forum.py          # Phase 2: Scirra forum scraper (parallel track)
    generate_synthetic.py     # run synthetic_gen.py at scale
    train_embedding.py        # launch embedding training
    evaluate_embedding.py     # run evaluation against baseline
  output/                     # .gitignore
    qwen3-embedding-4b-c3/    # merged LoRA export, drop-in EMBEDDING_MODEL
  config.yaml
  requirements.txt
```

---

## Data Pipeline

### Primary Source: Lookup Chain Miner (`lookup_chain_miner.py`)

Traverses the existing RAG lookup chain systematically:

```
Chinese term (zh_r475.csv)
  → English translation
    → ACE Schema (ACE name, type, description, plugin)
      → Construct3-Manual (full section documentation)
```

**Output format** (`pairs/lookup_chain.jsonl`):
```json
{"query": "碰撞检测", "positive": "Triggered when this object overlaps with another object...", " ace_type": "triggered_condition", "plugin": "Sprite"}
```

**Hard negative strategy:** Within the same plugin, conditions of the same ACE type (e.g. other triggered conditions) serve as hard negatives. This uses C3's own taxonomy — looping / triggered / normal conditions — as a natural difficulty gradient, without requiring manual annotation.

**Scale:** 24k translation entries × traversal → ~15k high-quality pairs (deduplication removes redundant entries).

### Secondary Source: Manual Chunker (`manual_chunker.py`)

Chunks all 403 Construct3-Manual markdown files at H2 boundaries (reusing `src/ingest/markdown_parser.py` logic from the RAG project).

For each chunk, Claude API generates 6-8 synthetic user queries in varied natural language, including:
- Direct Chinese questions ("什么是循环条件？")
- Vocabulary-bridging questions ("Unity 的 Update() 在 C3 里怎么写？")
- Troubleshooting questions ("为什么我的事件只触发一次？")

**Output:** `(synthetic_query, document_chunk)` pairs. Adjacent H2 chunks in the same document serve as positives for cross-chunk queries; BM25-retrieved non-adjacent chunks serve as hard negatives.

**Scale:** 403 files × ~10 H2 sections × 6 queries ≈ ~5k pairs after deduplication.

### Tertiary Source: Knowledge Transfer Synthetic (`synthetic_gen.py`)

Claude API generates ~500 pairs mapping general game development concepts to C3 equivalents:

```json
{"query": "Unity Update() 相当于 C3 里的什么", "positive": "Every tick 事件是 looping condition，每帧执行一次，相当于 Unity 的 Update()"}
```

Covers: Unity/Godot/GameMaker analogies, JavaScript/TypeScript → C3 scripting patterns, general event-driven programming → C3 event sheet mapping.

### Ongoing Source: RAG Log Collector (`rag_log_collector.py`)

Reads query/answer logs from the RAG system (requires logging to be enabled). Used to refine training data after initial deployment. Not required for Phase 1 training.

### Data Volume Summary

| Source | Triplets | Quality |
|--------|----------|---------|
| Lookup chain miner | ~15k | Highest (real correspondences) |
| Manual chunker + synthetic queries | ~5k | High |
| Knowledge transfer synthetic | ~500 | High (curated) |
| RAG logs (ongoing) | TBD | Medium |
| **Total Phase 1** | **~20k** | |

### Curriculum Order

Training proceeds easy → hard to avoid early overfitting:

1. Translation pairs + manual chunks (easy negatives, establish baseline alignment)
2. ACE Schema type-stratified pairs (medium hard negatives — same type, different ACE)
3. Synthetic knowledge-transfer queries (hardest — cross-vocabulary, cross-domain)

---

## Training Configuration

**Base model:** `Qwen/Qwen3-Embedding-4B` (2560 dims, decoder-based, instruction-aware)

**LoRA config:**
```yaml
r: 8
lora_alpha: 16
target_modules: [q_proj, k_proj, v_proj, o_proj]
lora_dropout: 0.05
bias: none
```

VRAM estimate: ~12-14GB with LoRA r=8, leaving headroom on RTX 5090 (24GB).

**Loss function:** `MultipleNegativesRankingLoss` (sentence-transformers)

Each batch treats other samples' positives as in-batch negatives. Combined with explicit hard negatives from the lookup chain, this provides strong gradient signal without requiring full triplet format — input can be simple `(query, positive)` pairs.

**Training hyperparameters (initial):**
```yaml
batch_size: 32
learning_rate: 2e-4
epochs: 5
warmup_ratio: 0.1
max_seq_length: 512
```

**Hardware:** RTX 5090 (GB202, sm_120). Requires PyTorch nightly cu128. Training script checks torch version and CUDA capability at startup, warns if incorrect environment detected.

---

## Evaluation

Evaluation runs automatically after each epoch against a held-out eval set (10% of pairs, stratified by source).

**Primary metrics:**
- `Recall@5`: fraction of queries where the correct document chunk appears in top 5 results
- `MRR@10`: mean reciprocal rank over top 10 results

**Baseline:** Current `Qwen3-Embedding-4B` without fine-tuning, evaluated on the same eval set.

A training run is considered successful if `Recall@5` improves by ≥5 percentage points over baseline.

**Eval script output:** Per-epoch CSV log + final markdown report comparing baseline vs fine-tuned.

---

## Integration with RAG Project

Single change in `Construct3-RAG/.env`:

```env
EMBEDDING_MODEL=D:/path/to/Construct3-LoRA/output/qwen3-embedding-4b-c3/
EMBEDDING_DIMENSION=2560
```

No code changes required. The RAG project's `EmbeddingModel` class already handles local paths via `SentenceTransformer(model_name, trust_remote_code=True)`.

After training, the LoRA adapter is merged and exported as a full model (not a separate adapter file) to simplify deployment.

---

## Phase 2 (Parallel Track)

While Phase 1 training runs, a parallel data collection track scrapes additional real-world data:

- **Scirra forum** (`scripts/collect_forum.py`): real user Q&A threads
- **Discord exports**: parsed from JSON exports of C3 community servers

Phase 2 data feeds into subsequent fine-tuning rounds to progressively improve the model with real user vocabulary.

---

## Out of Scope (This Phase)

- LLM LoRA fine-tuning (`sft/` — reserved, not implemented)
- Full-parameter fine-tuning of embedding model
- Automatic retraining pipeline / CI
- Model serving infrastructure
