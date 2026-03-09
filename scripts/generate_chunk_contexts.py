#!/usr/bin/env python3
"""
Generate contextual chunk summaries for improved embedding quality.
Anthropic technique: prepend "[Collection: Section > Subsection]" style
context to each chunk before embedding.

Usage:
    python scripts/generate_chunk_contexts.py --output data/chunk_contexts.json
    python scripts/generate_chunk_contexts.py --resume  # skip already done
"""
import sys
import json
import hashlib
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

CONTEXT_PROMPT = """以下是一段来自 Construct 3 文档的片段：

<document>
{document}
</document>

请用一句话描述这段内容所属的模块和主题，格式如下：
[插件/行为/文档: 功能名 > 子主题]

只输出这一行，不要解释。"""


def generate_context(llm, chunk_text: str) -> str:
    prompt = CONTEXT_PROMPT.format(document=chunk_text[:1000])
    try:
        return llm.generate(prompt, system="") + "\n"
    except Exception as e:
        return f"[Context generation failed: {e}]\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/chunk_contexts.json")
    parser.add_argument("--resume", action="store_true",
                        help="Skip chunks already in output file")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of chunks to process (0=all)")
    args = parser.parse_args()

    from src.config import QDRANT_HOST, QDRANT_PORT, LLM_PROVIDER, LLM_MODEL, LLM_BASE_URL, LLM_API_KEY
    from src.rag.chain import LLMClient
    from qdrant_client import QdrantClient

    output_path = Path(args.output)
    contexts: dict[str, str] = {}
    if args.resume and output_path.exists():
        contexts = json.loads(output_path.read_text(encoding="utf-8"))
        print(f"Resuming: {len(contexts)} chunks already done")

    llm = LLMClient(model=LLM_MODEL, base_url=LLM_BASE_URL,
                    api_key=LLM_API_KEY, provider=LLM_PROVIDER)
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    collections = [c.name for c in client.get_collections().collections]
    processed = 0

    for coll in collections:
        print(f"\n[{coll}] Processing...")
        offset = None
        while True:
            result = client.scroll(coll, limit=50, offset=offset, with_payload=True)
            points, offset = result
            if not points:
                break
            for pt in points:
                text = pt.payload.get("text", "")
                if not text:
                    continue
                key = hashlib.md5(text[:500].encode()).hexdigest()
                if key in contexts:
                    continue
                contexts[key] = generate_context(llm, text)
                processed += 1
                if processed % 10 == 0:
                    output_path.write_text(
                        json.dumps(contexts, ensure_ascii=False, indent=2),
                        encoding="utf-8"
                    )
                    print(f"  Saved {processed} chunks...")
                if args.limit and processed >= args.limit:
                    break
            if args.limit and processed >= args.limit:
                break

    output_path.write_text(
        json.dumps(contexts, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"\nDone. Generated {processed} new contexts → {output_path}")


if __name__ == "__main__":
    main()
