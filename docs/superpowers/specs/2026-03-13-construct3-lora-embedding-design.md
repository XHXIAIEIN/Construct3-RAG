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
    embedding/
      dataset.py              # build training dataset from pairs/
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
  config.yaml                 # paths + hyperparameters (see schema below)
  requirements.txt
```

**`config.yaml` schema:**
```yaml
paths:
  manual_dir: "D:/Users/Administrator/Documents/GitHub/Construct3-Manual/Construct3-Manual/"
  rag_project_dir: "D:/Users/Administrator/Documents/GitHub/Construct3-RAG/"
  output_dir: "./output/qwen3-embedding-4b-c3/"
model:
  base_model: "Qwen/Qwen3-Embedding-4B"
  query_instruction: "Instruct: Retrieve relevant Construct 3 documentation for the query.\nQuery: "
api:
  claude_api_key_env: "ANTHROPIC_API_KEY"
training:
  batch_size: 16
  learning_rate: 2e-4
  epochs: 5
  max_seq_length: 512
```

---

## Data Pipeline

### Primary Source: Lookup Chain Miner (`lookup_chain_miner.py`)

Traverses the existing RAG lookup chain systematically:

```
Chinese term (zh_r475.csv)
  → English translation
    → ACE Schema (ACE name, type, description, plugin)
      → Construct3-Manual (full H2 section text)
```

**Output format** (`pairs/lookup_chain.jsonl`):
```json
{
  "query": "碰撞检测",
  "positive": "[full Manual H2 section text for 'On collision with object']",
  "ace_type": "triggered_condition",
  "plugin": "Sprite"
}
```

The `positive` field must be the full Manual H2 section text — the same format indexed in Qdrant — not the short ACE schema description. If no Manual section is found for an ACE, fall back to: ACE description + parameter list from the schema JSON.

For each ACE, generate 3-5 Chinese paraphrase queries using Claude API (varying vocabulary and phrasing) to expand coverage. This is necessary to reach useful training volume.

**Hard negative strategy:** Within the same plugin, ACEs of the same type (e.g. other triggered conditions) serve as hard negatives. This uses C3's own taxonomy — looping / triggered / normal conditions — as a natural difficulty gradient, without requiring manual annotation.

**Scale:** ~2,400 unique ACE names × 3-5 query variants → **~8k-12k pairs** after deduplication (not 24k × direct traversal, as many CSV entries map to the same ACE).

### Secondary Source: Manual Chunker (`manual_chunker.py`)

Chunks all 335 Construct3-Manual markdown files at H2 boundaries (reusing `src/ingest/markdown_parser.py` logic from the RAG project). Average ~4 H2 sections per file.

For each chunk, Claude API generates 6-8 synthetic user queries in varied natural language:
- Direct Chinese questions ("什么是循环条件？")
- Vocabulary-bridging questions ("Unity 的 Update() 在 C3 里怎么写？")
- Troubleshooting questions ("为什么我的事件只触发一次？")

**Query instruction prefix** must be applied to all queries (same as RAG inference): `"Instruct: Retrieve relevant Construct 3 documentation for the query.\nQuery: "`. Document chunks are encoded without the prefix (asymmetric encoding, matching Qwen3-Embedding's documented usage).

**Output:** `(synthetic_query, document_chunk)` pairs. Adjacent H2 chunks in the same document serve as positives; BM25-retrieved non-adjacent chunks serve as hard negatives.

**Scale:** 335 files × ~4 H2 sections × 6 queries ≈ ~8k raw → **~5k after deduplication**.

### Tertiary Source: Knowledge Transfer Synthetic (`synthetic_gen.py`)

Claude API generates ~500 pairs mapping general game development concepts to C3 equivalents:

```json
{"query": "Unity Update() 相当于 C3 里的什么", "positive": "Every tick 事件是 looping condition，每帧执行一次，相当于 Unity 的 Update()"}
```

Covers: Unity/Godot/GameMaker analogies, JavaScript/TypeScript → C3 scripting patterns, general event-driven programming → C3 event sheet mapping.

These ~500 pairs are **upsampled 3× during training** across all curriculum stages (not confined to a final stage) to ensure cross-domain gradient signal is present throughout.

### Data Volume Summary

| Source | Pairs | Quality |
|--------|-------|---------|
| Lookup chain miner (with query augmentation) | ~8k-12k | Highest (real correspondences) |
| Manual chunker + synthetic queries | ~5k | High |
| Knowledge transfer synthetic (upsampled) | ~500 raw / ~1.5k effective | High (curated) |
| **Total Phase 1** | **~14k-18k** | |

### Curriculum Order

Training proceeds easy → hard to avoid early overfitting. Knowledge transfer pairs (~500) are upsampled and distributed across all stages:

1. **Epochs 1-2:** Translation-derived pairs + manual chunks (easy in-batch negatives, establish baseline alignment)
2. **Epochs 3-4:** ACE Schema type-stratified pairs (medium hard negatives — same plugin, same ACE type)
3. **Epoch 5:** Full mix including explicit hard negatives from lookup chain (same plugin, different ACE type boundary)

---

## Training Configuration

**Base model:** `Qwen/Qwen3-Embedding-4B` (2560 dims, decoder-based, instruction-aware)

### LoRA Integration

Qwen3-Embedding-4B is a decoder-based model. The training integration follows this pattern:

1. Load base model via `transformers.AutoModel.from_pretrained`
2. Apply LoRA via `peft.get_peft_model()` with config below
3. Wrap in a custom `sentence_transformers.models.Transformer` subclass that applies last-token pooling and the query instruction prefix
4. Train with `SentenceTransformerTrainer` + `MultipleNegativesRankingLoss`

This avoids bypassing sentence-transformers while correctly handling the asymmetric instruction encoding (query prefix applied at encode time, not hardcoded in the model).

**LoRA config:**
```yaml
r: 8
lora_alpha: 16
target_modules: [q_proj, k_proj, v_proj, o_proj]
lora_dropout: 0.05
bias: none
```

### Query Instruction Asymmetry

Qwen3-Embedding uses asymmetric encoding: queries are prefixed with a task instruction, document chunks are not. This must be preserved during training:

- All `query` fields in training pairs are prefixed with `query_instruction` from `config.yaml` before encoding
- All `positive` and `negative` fields are encoded as-is (no prefix)
- This matches the inference pattern in `src/ingest/indexer.py` (`_QWEN3_QUERY_INSTRUCTION`)

**Loss function:** `MultipleNegativesRankingLoss` (sentence-transformers)

Each batch treats other samples' positives as in-batch negatives. Combined with explicit hard negatives from the lookup chain, this provides strong gradient signal with `(query, positive)` pair format — no need for explicit triplet structure.

**Training hyperparameters (initial):**
```yaml
batch_size: 16        # safe starting point; 32 may exceed ~20GB peak VRAM
learning_rate: 2e-4
epochs: 5
warmup_ratio: 0.1
max_seq_length: 512
gradient_checkpointing: true   # recommended for decoder architecture
```

**VRAM estimate:** ~18-20GB peak with batch_size=16 (model weights ~8GB bf16 + LoRA params + activation memory for 16×16 similarity matrix + gradients). RTX 5090 (24GB) has ~4-6GB headroom. Scale batch_size up only after confirming headroom during first epoch.

**Hardware:** RTX 5090 (GB202, sm_120). Requires PyTorch nightly cu128. Training script checks torch version and CUDA capability at startup, warns if incorrect environment detected.

---

## Evaluation

### Held-out Eval Set

10% of pairs held out, stratified by source. Known limitation: the synthetic query eval subset (~50 pairs from knowledge transfer source) is too small for high-confidence signal. Phase 1 eval is best interpreted as directional.

A supplementary **manually curated eval set** of 30-50 questions should be created independently (not from the Claude generation process) to provide a clean signal. This can be drawn from real Scirra forum questions.

**Primary metrics:**
- `Recall@5`: fraction of queries where the correct document chunk appears in top 5 results
- `MRR@10`: mean reciprocal rank over top 10 results

**Baseline:** Current `Qwen3-Embedding-4B` without fine-tuning, evaluated on the same eval set.

A training run is considered successful if `Recall@5` improves by ≥5 percentage points over baseline on the held-out set.

**Eval script output:** Per-epoch CSV log + final markdown report comparing baseline vs fine-tuned.

---

## Integration with RAG Project

**Step 1 — Export:** After training, merge LoRA adapter into base model and export as a full HuggingFace model directory (`output/qwen3-embedding-4b-c3/`).

**Step 2 — Rebuild Qdrant:** Because `EMBEDDING_DIMENSION` changes (from 1024 to 2560 if previously using `Qwen3-Embedding-0.6B`, or unchanged if already using 4B), all Qdrant collections must be rebuilt:

```bash
python -m src.ingest.indexer --rebuild
```

**Step 3 — Update `.env`:**

```env
EMBEDDING_MODEL=D:/path/to/Construct3-LoRA/output/qwen3-embedding-4b-c3/
EMBEDDING_DIMENSION=2560
```

No RAG code changes required. The `EmbeddingModel` class already handles local paths via `SentenceTransformer(model_name, trust_remote_code=True)`.

> ⚠️ Qdrant collections store vectors at fixed dimensionality. Changing `EMBEDDING_MODEL` without `--rebuild` will cause silent failures or errors on every query.

---

## Phase 2 (Parallel Track)

While Phase 1 training runs, a parallel data collection track scrapes additional real-world data:

- **Scirra forum** (`scripts/collect_forum.py`): real user Q&A threads — provides genuine user vocabulary
- **Discord exports**: parsed from JSON exports of C3 community servers

Phase 2 data feeds into subsequent fine-tuning rounds to progressively improve the model with real user vocabulary.

---

## Out of Scope (This Phase)

- LLM LoRA fine-tuning (`sft/` — reserved, not implemented)
- Full-parameter fine-tuning of embedding model
- RAG query/answer logging infrastructure (prerequisite for future log-based training data)
- Automatic retraining pipeline / CI
- Model serving infrastructure
