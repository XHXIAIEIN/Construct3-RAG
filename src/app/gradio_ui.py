"""
Construct 3 RAG Assistant - 极简界面
With anti-hallucination features:
- 显示回答置信度
- 显示 Self-Reflection 验证结果
"""
from typing import List, Dict
import gradio as gr

try:
    from src.rag.chain import RAGChain, RAGResponse
    from src.config import QDRANT_HOST, QDRANT_PORT, LLM_MODEL, LLM_BASE_URL
except ImportError:
    import sys
    sys.path.insert(0, str(__file__).rsplit('/src/', 1)[0])
    from src.rag.chain import RAGChain, RAGResponse
    from src.config import QDRANT_HOST, QDRANT_PORT, LLM_MODEL, LLM_BASE_URL

_rag = None

CSS = """
.container { max-width: 900px; margin: 0 auto; }
.title { text-align: center; font-weight: 300; margin: 20px 0; }
.input-box textarea { border: 1px solid #ddd !important; border-radius: 4px !important; }
.output-box { border: 1px solid #eee; border-radius: 4px; padding: 16px;
              min-height: 300px; max-height: 60vh; overflow-y: auto;
              background: #fafafa; font-size: 14px; line-height: 1.6; }
.output-box:empty::before { content: "回答将显示在这里..."; color: #999; }
.submit-btn { border: 1px solid #333 !important; background: white !important;
              color: #333 !important; border-radius: 4px !important; }
.submit-btn:hover { background: #333 !important; color: white !important; }
footer { display: none !important; }
.confidence-high { color: #28a745; font-weight: bold; }
.confidence-medium { color: #ffc107; font-weight: bold; }
.confidence-low { color: #dc3545; font-weight: bold; }
.sources-box { border: 1px solid #e0e0e0; border-radius: 4px; padding: 12px;
               background: #f8f9fa; font-size: 12px; max-height: 200px; overflow-y: auto; }
.sources-box:empty::before { content: "无来源信息"; color: #999; }
.verification-box { border: 1px solid #17a2b8; border-radius: 4px; padding: 12px;
                    background: #e8f4f8; font-size: 12px; }
"""


def get_rag():
    global _rag
    if _rag is None:
        _rag = RAGChain(
            qdrant_host=QDRANT_HOST,
            qdrant_port=QDRANT_PORT,
            llm_model=LLM_MODEL,
            llm_base_url=LLM_BASE_URL
        )
    return _rag


def format_confidence(confidence: str) -> str:
    """Format confidence level for display"""
    labels = {
        "high": "✓ 高置信度",
        "medium": "⚠ 中置信度",
        "low": "⚠ 低置信度",
        "none": "✗ 无结果"
    }
    css_class = f"confidence-{confidence}"
    label = labels.get(confidence, confidence)
    return f'<span class="{css_class}">{label}</span>'


def format_sources(sources: List[Dict]) -> str:
    """Format sources for display"""
    if not sources:
        return ""

    lines = ["**来源:**"]
    for s in sources:
        source_type = s.get("type", "unknown")
        text = s.get("text", "")[:80]
        score = s.get("score", 0)
        lines.append(f"- [{s.get('id', '?')}] {source_type}: {text}... (相关性: {score:.2f})")

    return "\n".join(lines)


def ask_stream(question: str) -> List[str]:
    """流式生成回答，带防幻觉信息"""
    if not question.strip():
        return ["", "", ""]

    rag = get_rag()
    response = rag.answer(question)

    answer = response.answer
    sources_info = format_sources(response.sources)
    confidence_info = format_confidence(response.confidence)

    return [answer, sources_info, confidence_info]


def ask(question: str) -> List[str]:
    """非流式回答"""
    if not question.strip():
        return ["", "", ""]

    rag = get_rag()
    response = rag.answer(question)

    answer = response.answer
    sources_info = format_sources(response.sources)
    confidence_info = format_confidence(response.confidence)

    return [answer, sources_info, confidence_info]


def main():
    print("加载模型...")
    rag = get_rag()
    _ = rag.retriever.embedder
    print("就绪")

    with gr.Blocks(title="Construct 3 RAG (防幻觉版)", css=CSS) as demo:
        gr.HTML("<h2 class='title'>Construct 3 助手 <small>(防幻觉版)</small></h2>")

        with gr.Column(elem_classes="container"):
            inp = gr.Textbox(
                placeholder="输入关于 Construct 3 的问题...",
                label="问题",
                lines=3,
                elem_classes="input-box"
            )

            with gr.Row():
                btn_stream = gr.Button("流式回答", elem_classes="submit-btn")
                btn_normal = gr.Button("普通回答", elem_classes="submit-btn")
                btn_high = gr.Button("高置信度", elem_classes="submit-btn")

            out_answer = gr.Markdown(
                elem_classes="output-box",
                label="回答"
            )

            with gr.Row():
                out_confidence = gr.HTML(label="置信度")
                out_sources = gr.Markdown(elem_classes="sources-box", label="来源")

        # Event handlers
        btn_stream.click(ask_stream, inp, [out_answer, out_sources, out_confidence])
        btn_normal.click(ask, inp, [out_answer, out_sources, out_confidence])

        def ask_high_confidence(q: str) -> List[str]:
            if not q.strip():
                return ["", "", ""]
            rag = get_rag()
            response = rag.answer_high_confidence(q)
            return [response.answer,
                    format_sources(response.sources),
                    format_confidence(response.confidence)]

        btn_high.click(ask_high_confidence, inp, [out_answer, out_sources, out_confidence])
        inp.submit(ask_stream, inp, [out_answer, out_sources, out_confidence])

    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        mcp_server=True,
        css=CSS
    )


if __name__ == "__main__":
    main()
