# -*- coding: utf-8 -*-
"""Interactive CLI for Construct 3 RAG — manual testing."""
import sys
import os
import json
import logging
import threading
import time
import uuid
import urllib.request
from datetime import datetime
from pathlib import Path

os.environ["TQDM_DISABLE"] = "1"
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")

logging.disable(logging.WARNING)
import transformers
transformers.logging.set_verbosity_error()
transformers.utils.logging.disable_progress_bar()

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from src.config import LLM_MODEL, EMBEDDING_MODEL, RAG_SERVER_PORT

SERVER_URL = f"http://localhost:{RAG_SERVER_PORT}"
SESSION_ID = str(uuid.uuid4())
HEARTBEAT_INTERVAL = 20  # seconds; server IDLE_TIMEOUT is 30s

console = Console(highlight=False, no_color=True)

# ── Trace display ─────────────────────────────────────────────────────────────
_TRACE_LABEL: dict[str, str] = {
    "lookup":        "直接查找",
    "route":         "路由决策",
    "tokenize":      "分词结果",
    "term_hit":      "术语命中",
    "expand":        "术语扩展",
    "schema_match":  "字典匹配",
    "query":         "改写查询",
    "retrieve":      "检索结果",
    "ace":           "ACE补充",
    "filter":        "过滤结果",
    "filter_drop":   "已丢弃",
    "context":       "输入上下文",
    "reflect":       "验证结论",
    "reflect_issue": "验证问题",
    "confidence":    "最终置信度",
    "info":          "信息",
}

# 逻辑分组编号 — 组号变化时插入空行
_TRACE_GROUP: dict[str, int] = {
    "lookup":        1,
    "route":         2,
    "tokenize":      3, "term_hit":      3, "expand": 3, "schema_match": 3, "query": 3,
    "retrieve":      4, "ace":           4,
    "filter":        5, "filter_drop":   5,
    "context":       6,
    "reflect":       7, "reflect_issue": 7,
    "confidence":    8,
}

# 缩进子项（在主项下展示细节）
_TRACE_SUB = {"term_hit", "filter_drop", "reflect_issue"}

_GROUP_NAME: dict[int, str] = {
    1: "直接查找",
    2: "路由决策",
    3: "查询分析",
    4: "向量检索",
    5: "结果过滤",
    6: "输入上下文",
    7: "自我验证",
    8: "最终置信度",
}


def _wlen(s: str) -> int:
    """Terminal display width: CJK chars count as 2, others as 1."""
    return sum(2 if '\u2e80' <= c <= '\u9fff' else 1 for c in s)


def _print_trace(events: list) -> None:
    """Section headers + globally aligned label/value columns."""
    if not events:
        return

    from rich.markup import escape

    # Collect events into ordered groups
    groups: dict[int, list[tuple[str, str]]] = {}
    group_order: list[int] = []
    for phase, msg in events:
        g = _TRACE_GROUP.get(phase, 99)
        if g not in groups:
            groups[g] = []
            group_order.append(g)
        groups[g].append((phase, msg))

    # Global max label width (skip sub-items and single-value groups)
    max_lw = max(
        (_wlen(_TRACE_LABEL.get(phase, phase))
         for g, evts in groups.items() if g != 1
         for phase, _ in evts if phase not in _TRACE_SUB),
        default=4,
    )

    first = True
    for g in group_order:
        if not first:
            console.print()
        first = False

        name = _GROUP_NAME.get(g, f"步骤{g}")
        console.print(Rule(name, style="dim", align="left"))

        evts = groups[g]

        if g == 1:  # lookup: one line per tier, aligned
            for _, msg in evts:
                console.print(f"  {escape(msg)}")
        else:
            # Use table only when at least one row needs an explicit label
            needs_table = any(
                _TRACE_LABEL.get(ph, ph) != name and ph not in _TRACE_SUB
                for ph, _ in evts
            )
            if needs_table:
                tbl = Table(show_header=False, box=None, padding=(0, 2, 0, 2), show_edge=False)
                tbl.add_column("label", style="dim", no_wrap=True, min_width=max_lw)
                tbl.add_column("value")
                for phase, msg in evts:
                    label = _TRACE_LABEL.get(phase, phase)
                    safe = escape(msg)
                    if phase in _TRACE_SUB:
                        tbl.add_row("", safe, style="dim")
                    elif label == name:
                        tbl.add_row("", safe)
                    else:
                        tbl.add_row(label, safe)
                # Context section: append score distribution summary
                if g == 6:
                    import re as _re
                    scores = []
                    for _, msg in evts:
                        m = _re.search(r'\s(0\.\d+)\s', msg)
                        if m:
                            scores.append(float(m.group(1)))
                    if len(scores) >= 2:
                        tbl.add_row(
                            "分数分布",
                            f"max {max(scores):.2f}  min {min(scores):.2f}  "
                            f"avg {sum(scores)/len(scores):.2f}  共{len(scores)}条",
                            style="dim",
                        )
                console.print(tbl)
            else:
                # All rows are same-label or sub-items — print directly, strip redundant prefix
                prefix = f"{name}: "
                for phase, msg in evts:
                    safe = escape(msg)
                    if safe.startswith(prefix):
                        safe = safe[len(prefix):]
                    if phase in _TRACE_SUB:
                        console.print(f"    {safe}", style="dim")
                    else:
                        console.print(f"  {safe}")

# ── Log file ──────────────────────────────────────────────────────────────────
log_dir = Path(__file__).parent.parent / ".log"
log_dir.mkdir(exist_ok=True)
_log = (log_dir / f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log").open("a", encoding="utf-8")

def log(text: str) -> None:
    _log.write(text + "\n")
    _log.flush()


# ── Server helpers ─────────────────────────────────────────────────────────────
def _post(path: str, data: dict, timeout: int = 2) -> dict:
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        SERVER_URL + path, data=body,
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def _start_heartbeat() -> None:
    def _beat():
        while True:
            time.sleep(HEARTBEAT_INTERVAL)
            try:
                _post("/heartbeat", {"session_id": SESSION_ID})
            except Exception:
                pass
    threading.Thread(target=_beat, daemon=True).start()


# ── Connect or load locally ────────────────────────────────────────────────────
try:
    _post("/connect", {"session_id": SESSION_ID})
    use_server = True
    _start_heartbeat()
    model_name = Path(LLM_MODEL).name
    chain = None
except Exception:
    use_server = False
    model_name = Path(LLM_MODEL).name
    from src.rag.chain import RAGChain
    with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                  TimeElapsedColumn(), console=console) as p:
        emb_name = Path(EMBEDDING_MODEL).name
        t = p.add_task(f"加载 Embedding 模型 ({emb_name})")
        chain = RAGChain()
        chain.retriever.embedder.encode_single("warmup")
        p.update(t, description=f"Embedding 模型 ({emb_name})  ✓", completed=100, total=100)

        t = p.add_task(f"加载 LLM ({model_name})")
        chain.llm._load_hf() if chain.llm.provider == "huggingface" else chain.llm.check_health()
        p.update(t, description=f"LLM ({model_name})  ✓", completed=100, total=100)

# ── Ready ─────────────────────────────────────────────────────────────────────
mode = "→ 服务器" if use_server else "本地"
console.print(Panel(
    f"Construct 3 RAG  ·  {model_name}  ·  {mode}  ·  输入 q 退出\n"
    f"[dim]日志: {_log.name}[/dim]",
    padding=(0, 1),
))
log(f"=== 会话开始 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ({mode}) ===\n")

# ── Main loop ─────────────────────────────────────────────────────────────────
thinking = Progress(SpinnerColumn(), TextColumn("{task.description}"),
                    TimeElapsedColumn(), console=console, transient=True)

try:
    while True:
        try:
            now = datetime.now()
            query = console.input(f"[dim]{now.strftime('%H:%M')}[/dim] > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not query:
            continue
        if query.lower() in ("q", "quit", "exit"):
            break

        # /paste — multi-line input mode for event sheet JSON or "Copy as text"
        if query.lower() == "/paste":
            console.print("[dim]粘贴事件表内容（JSON 或 Copy as text），输入空行结束:[/dim]")
            lines = []
            try:
                while True:
                    line = input()
                    if line == "" and lines and lines[-1] == "":
                        lines.pop()  # remove trailing empty line
                        break
                    lines.append(line)
            except (EOFError, KeyboardInterrupt):
                pass
            if not lines:
                continue
            pasted = "\n".join(lines)
            console.print("[dim]你的问题（直接回车跳过）:[/dim]")
            try:
                follow_up = input().strip()
            except (EOFError, KeyboardInterrupt):
                follow_up = ""
            query = pasted + ("\n---\n" + follow_up if follow_up else "")
            log_query = f"/paste ({len(lines)} 行)" + (f" + {follow_up}" if follow_up else "")
        else:
            log_query = query

        log(f"[{now.strftime('%H:%M:%S')}] >> {log_query}")

        with thinking:
            thinking.add_task("思考中")
            if use_server:
                data = _post("/", {"query": query}, timeout=120)
                answer, query_type, confidence = data["answer"], data["query_type"], data["confidence"]
                trace = [tuple(e) for e in data.get("trace", [])]
            else:
                resp = chain.answer_smart(query)
                answer, query_type, confidence = resp.answer, resp.query_type, resp.confidence
                trace = resp.trace

        console.print()
        _print_trace(trace)
        console.print(Panel(Markdown(answer), padding=(0, 1)))
        _confidence_label = {"high": "高 ✓", "medium": "中", "low": "低 ✗"}.get(confidence, confidence)
        console.print(Rule(f"[dim]{query_type}  置信度: {_confidence_label}[/dim]", style="dim"))

        trace_log = "\n".join(f"  [{p}] {m}" for p, m in trace) if trace else ""
        log(answer + f"\n[模式: {query_type} | 置信度: {confidence}]"
            + (f"\n[处理路径]\n{trace_log}" if trace_log else "")
            + "\n" + "-" * 60)

finally:
    if use_server:
        try:
            _post("/disconnect", {"session_id": SESSION_ID})
        except Exception:
            pass
    console.print(Rule(style="dim"))
    log(f"\n=== 会话结束 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    _log.close()
