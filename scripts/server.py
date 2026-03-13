# -*- coding: utf-8 -*-
"""RAG model server — load models once, serve multiple chat clients."""
import sys
import os
import json
import logging
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

os.environ["TQDM_DISABLE"] = "1"
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

logging.disable(logging.WARNING)
import transformers
transformers.logging.set_verbosity_error()
transformers.utils.logging.disable_progress_bar()

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from src.rag.chain import RAGChain
from src.config import LLM_MODEL, RAG_SERVER_PORT

SERVER_HOST = "localhost"
IDLE_TIMEOUT = 30       # seconds without heartbeat before shutdown
LOG_QUERY_MAX = 60      # max query chars shown in server log

console = Console(highlight=False)
_infer_lock = threading.Lock()   # serialize LLM inference
_hb_lock = threading.Lock()
_last_heartbeat: dict[str, float] = {}  # session_id -> last seen timestamp
chain: RAGChain = None  # type: ignore


def _watchdog(httpd: HTTPServer) -> None:
    """Shut down server when no heartbeats received for IDLE_TIMEOUT seconds."""
    while True:
        time.sleep(5)
        with _hb_lock:
            if not _last_heartbeat:
                continue
            cutoff = time.time() - IDLE_TIMEOUT
            for sid in [s for s, ts in _last_heartbeat.items() if ts < cutoff]:
                del _last_heartbeat[sid]
            if _last_heartbeat:
                continue
        # Lock released — now safe to trigger shutdown
        console.print("\n[dim]所有客户端已断开，服务器关闭[/dim]")
        threading.Thread(target=httpd.shutdown, daemon=True).start()
        return


class Handler(BaseHTTPRequestHandler):
    def _respond(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_POST(self):
        body = self._body()
        path = self.path

        if path in ("/connect", "/heartbeat"):
            sid = body.get("session_id", "")
            with _hb_lock:
                _last_heartbeat[sid] = time.time()
            self._respond({"ok": True})

        elif path == "/disconnect":
            sid = body.get("session_id", "")
            with _hb_lock:
                _last_heartbeat.pop(sid, None)
            self._respond({"ok": True})

        elif path == "/decompose":
            query = body.get("query", "")
            with _infer_lock:
                dq = chain.semantic_chain.decompose(query) if chain.semantic_chain else None
            if dq:
                self._respond({
                    "query_type": dq.query_type,
                    "c3_objects": dq.c3_objects,
                    "action_verbs": dq.action_verbs,
                    "intents": [
                        {"label": i.label, "keywords": i.keywords, "weight": i.weight}
                        for i in dq.intents
                    ],
                    "solution_rewrite": dq.solution_rewrite,
                    "confidence": dq.confidence,
                })
            else:
                self._respond({"error": "semantic chain unavailable"})

        elif path == "/search":
            query = body.get("query", "")
            top_k = int(body.get("top_k", 8))
            with _infer_lock:
                results = chain.retriever.search_all_with_rerank(
                    query, top_k_per_collection=3, final_top_k=top_k
                )
                dq = chain.semantic_chain.decompose(query) if chain.semantic_chain else None
            self._respond({
                "results": [
                    {"text": r.text, "source": r.source, "score": r.score}
                    for r in results
                ],
                "decomposed": {
                    "query_type": dq.query_type if dq else "unknown",
                    "c3_objects": dq.c3_objects if dq else [],
                    "intents": [
                        {"label": i.label, "keywords": i.keywords}
                        for i in dq.intents
                    ] if dq else [],
                    "confidence": dq.confidence if dq else 0.0,
                }
            })

        else:  # /  (answer_smart)
            query = body.get("query", "")
            with _infer_lock:
                resp = chain.answer_smart(query)
            self._respond({
                "answer": resp.answer,
                "query_type": resp.query_type,
                "confidence": resp.confidence,
                "trace": resp.trace,
            })
            preview = query[:LOG_QUERY_MAX] + ("…" if len(query) > LOG_QUERY_MAX else "")
            console.print(f"[dim]{datetime.now().strftime('%H:%M:%S')}  {preview}[/dim]")

    def log_message(self, *args):
        pass


# ── Warm-up ───────────────────────────────────────────────────────────────────
with Progress(SpinnerColumn(), TextColumn("{task.description}"),
              TimeElapsedColumn(), console=console) as p:
    t = p.add_task("加载 Embedding 模型 (bge-m3)")
    chain = RAGChain()
    chain.retriever.embedder.encode_single("warmup")
    p.update(t, description="Embedding 模型 (bge-m3)  ✓", completed=100, total=100)

    model_name = Path(LLM_MODEL).name
    t = p.add_task(f"加载 LLM ({model_name})")
    chain.llm._load_hf() if chain.llm.provider == "huggingface" else chain.llm.check_health()
    p.update(t, description=f"LLM ({model_name})  ✓", completed=100, total=100)

# ── Serve ─────────────────────────────────────────────────────────────────────
console.print(Panel(
    f"Construct 3 RAG Server  ·  {model_name} 就绪\n"
    f"[dim]监听 localhost:{RAG_SERVER_PORT}  ·  {IDLE_TIMEOUT}s 无客户端自动关闭  ·  Ctrl+C 强制关闭[/dim]",
    padding=(0, 1),
))

httpd = HTTPServer((SERVER_HOST, RAG_SERVER_PORT), Handler)
threading.Thread(target=_watchdog, args=(httpd,), daemon=True).start()

try:
    httpd.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    console.print("\n[dim]服务器已关闭[/dim]")
