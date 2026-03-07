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

from src.config import LLM_MODEL, RAG_SERVER_PORT

SERVER_URL = f"http://localhost:{RAG_SERVER_PORT}"
SESSION_ID = str(uuid.uuid4())
HEARTBEAT_INTERVAL = 20  # seconds; server IDLE_TIMEOUT is 30s

console = Console(highlight=False, no_color=True)

# ── Trace display ─────────────────────────────────────────────────────────────
_TRACE_LABEL: dict[str, str] = {
    "lookup":        "Lookup",
    "route":         "路由",
    "tokenize":      "分词",
    "term_hit":      "",        # sub-item: indented, no label
    "expand":        "术语扩展",
    "schema_match":  "Schema命中",
    "query":         "检索查询",
    "retrieve":      "检索",
    "ace":           "ACE增强",
    "filter":        "过滤",
    "filter_drop":   "",        # sub-item
    "context":       "上下文",
    "reflect":       "反思",
    "reflect_issue": "",        # sub-item
    "confidence":    "置信度",
    "info":          "",
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


def _abbrev_tier(msg: str) -> str:
    """Shorten a Tier trace message for compact single-line display.

    Examples:
        "Tier1: 未命中"                     → "T1:✗"
        "Tier1.5: 跳过(触发词'怎么')"       → "T1.5:跳过('怎么')"
        "Tier1.5: 未命中"                   → "T1.5:✗"
        "Tier3: 跳过(未配置)"               → "T3:跳过"
        "Tier2: 命中(ace_detail)"           → "T2:✓(ace_detail)"
    """
    import re
    m = re.match(r"Tier(\S+?): (.+)", msg)
    if not m:
        return msg
    tier, rest = m.group(1), m.group(2)
    if rest == "未命中":
        return f"T{tier}:✗"
    if rest == "跳过(未配置)":
        return f"T{tier}:跳过"
    wm = re.search(r"触发词'([^']+)'", rest)
    if wm:
        return f"T{tier}:跳过('{wm.group(1)}')"
    if rest.startswith("命中"):
        return f"T{tier}:✓{rest[2:]}"
    return f"T{tier}:{rest}"


def _collapse_lookup(events: list) -> list:
    """Merge all lookup-phase events into a single compact row."""
    result: list = []
    lookup_buf: list[str] = []
    for phase, msg in events:
        if phase == "lookup":
            lookup_buf.append(_abbrev_tier(msg))
        else:
            if lookup_buf:
                result.append(("lookup", "  ".join(lookup_buf)))
                lookup_buf = []
            result.append((phase, msg))
    if lookup_buf:
        result.append(("lookup", "  ".join(lookup_buf)))
    return result


def _print_trace(events: list) -> None:
    """Render trace events as a spaced two-column table grouped by phase."""
    if not events:
        return

    from rich.markup import escape

    events = _collapse_lookup(events)

    table = Table(
        show_header=False, box=None,
        padding=(0, 2, 0, 1), show_edge=False,
    )
    table.add_column("label", style="dim", no_wrap=True, min_width=6)
    table.add_column("value", style="dim")

    last_phase = None
    last_group = None
    for phase, msg in events:
        label = _TRACE_LABEL.get(phase, "")
        safe = escape(msg)
        group = _TRACE_GROUP.get(phase, 99)

        if last_group is not None and group != last_group:
            table.add_row("", "")       # blank row between sections

        last_group = group
        is_sub = not label
        if is_sub:
            table.add_row("", "  " + safe)
        elif phase == last_phase:
            table.add_row("", safe)
        else:
            table.add_row(label, safe)
            last_phase = phase

    console.print(Rule("处理路径", style="dim"))
    console.print(table)
    console.print(Rule(style="dim"))

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
        t = p.add_task("加载 Embedding 模型 (bge-m3)")
        chain = RAGChain()
        chain.retriever.embedder.encode_single("warmup")
        p.update(t, description="Embedding 模型 (bge-m3)  ✓", completed=100, total=100)

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

        log(f"[{now.strftime('%H:%M:%S')}] >> {query}")

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
        console.print(Panel(Markdown(answer), padding=(0, 1)))
        console.print(f"[dim] 模式: {query_type}  |  置信度: {confidence}[/dim]")
        _print_trace(trace)

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
