"""Serve a page on which a person answers the questions of scripts/review_look.py about a set
of screenshots, and keep the answers: the labels that evals/judge_look.py compares a judge with.

    python evals/label_look.py SET.json [--labels LABELS.json] [--words WORDS.json] [--port 8770]

SET.json lists the screenshots, each path relative to the folder of SET.json:

    {"shots": [{"id": "g1-game", "file": "shots/g1/Game.png", "brief": "g1", "layout": "Game"},
               {"id": "g1-moved", "file": "shots/g1-moved/Game.png", "brief": "g1-moved",
                "layout": "Game", "broken": "the score moved over the level number"}]}

id names a screenshot in the labels. brief groups the screenshots that one brief of
review_look.py holds, the screenshots of one run, and layout is the name the brief gives each.
Any other key, such as what was broken on purpose, is for the reader of the set and is never
shown on the page.

The page shows one screenshot at a time, in an order shuffled once by id, so that a broken copy
does not follow its original. It asks each question of review_look.QUESTIONS and one more,
whether the screen would ship as it looks, with a note for what is wrong. A brief of several
screenshots ends with a page that shows them together and asks review_look.ACROSS. Each answer
is written to LABELS.json (default: labels.json beside SET.json) when it is given, with the
wording of every question, so the labels say which wording they answer.

WORDS.json puts the page in the person's language: {"lang": "zh-CN", "questions": {"1": ..., "ship": ...,
"across": ...}, "page": {"yes": ..., "no": ..., "ship": ..., "not": ..., "note": ..., "keys": ...,
"open": ..., "of": ..., "answered": ..., "saving": ..., "saved": ..., "not saved": ...}}, any
key left out staying English. A translated question shows above its English wording, which is
what a judge reads and what the labels keep.

Keys on the page: 1 to 6 answer that question yes, and no at the next press; Y and N answer
whether it would ship; Enter answers no to every question still open and goes on; the arrow
keys move between screenshots.

Exit codes: 0 stopped with Ctrl+C, 2 the set, the labels or the words could not be read, or the
port is in use.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import c3project as c3              # noqa: E402
import review_look as rl            # noqa: E402

SHIP = "Would you ship this screen as it looks?"
NOTE = "If it would not ship, or a yes needs a word: what is wrong, and where?"


def questions() -> dict[str, str]:
    """Every question by its key: the numbered ones of review_look.py, ship and across."""
    return {**{str(n): q for n, q in enumerate(rl.QUESTIONS, 1)}, "ship": SHIP, "across": rl.ACROSS}


def load_set(path: Path) -> list[dict]:
    """The screenshots of the set, each with its file as an absolute path; SystemExit names a bad entry."""
    try:
        shots = json.loads(path.read_text(encoding="utf-8"))["shots"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise SystemExit(f"{path}: not a set of screenshots ({e}); see --help for its form")
    seen = set()
    for s in shots:
        missing = [k for k in ("id", "file", "brief", "layout") if not s.get(k)]
        if missing:
            raise SystemExit(f"{path}: an entry has no {', '.join(missing)}: {json.dumps(s)[:120]}")
        if s["id"] in seen:
            raise SystemExit(f"{path}: id {s['id']!r} comes twice; give each screenshot its own id")
        seen.add(s["id"])
        s["path"] = (path.parent / s["file"]).resolve()
        if not s["path"].is_file():
            raise SystemExit(f"{path}: {s['id']}: no file {s['path']}")
    return shots


def items(shots: list[dict]) -> list[dict]:
    """What the page asks, in order: each screenshot, shuffled by a hash of its id, then one page per
    brief of several screenshots."""
    numbered = [k for k in questions() if k.isdigit()]
    out = [{"id": s["id"], "shots": [s["id"]], "ask": numbered + ["ship"]}
           for s in sorted(shots, key=lambda s: hashlib.sha256(s["id"].encode()).hexdigest())]
    briefs: dict[str, list[str]] = {}
    for s in shots:
        briefs.setdefault(s["brief"], []).append(s["id"])
    out += [{"id": f"across:{b}", "shots": ids, "ask": ["across"]} for b, ids in briefs.items() if len(ids) > 1]
    return out


class Labels:
    """The labels file, written whole after every answer."""

    def __init__(self, path: Path, set_path: Path):
        self.path, self.lock = path, threading.Lock()
        try:
            self.data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, ValueError) as e:
            raise SystemExit(f"{path}: not readable as labels ({e}); move it aside or pass another --labels")
        self.data.setdefault("set", set_path.name)
        asked = self.data.setdefault("questions", {})
        self.changed = [k for k, q in questions().items() if k in asked and asked[k] != q]
        for k, q in questions().items():
            asked.setdefault(k, q)
        self.data.setdefault("labels", {})

    def answer(self, item: str, key: str, value) -> dict:
        with self.lock:
            got = self.data["labels"].setdefault(item, {})
            if value is None or value == "":
                got.pop(key, None)
            else:
                got[key] = value
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.path)
            return dict(got)


def load_words(path: Path | None) -> dict:
    """The page's words in the person's language; SystemExit names a bad file."""
    if not path:
        return {}
    try:
        words = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SystemExit(f"{path}: not readable as words ({e}); see --help for its form")
    unknown = sorted(set(words.get("questions", {})) - set(questions()))
    if unknown:
        raise SystemExit(f"{path}: no question {', '.join(unknown)}; the keys are {', '.join(questions())}")
    return words


def handler(shots: list[dict], labels: Labels, words: dict | None = None):
    by_id = {s["id"]: s for s in shots}
    state = {"questions": questions(), "note": NOTE, "items": items(shots), "words": words or {},
             "layouts": {s["id"]: s["layout"] for s in shots}}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):     # the console shows answers, not requests
            pass

        def send(self, body: bytes, kind: str, code: int = 200):
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self.send(PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif self.path == "/state":
                self.send(json.dumps({**state, "labels": labels.data["labels"]}).encode("utf-8"), "application/json")
            elif self.path.startswith("/shot/") and self.path[6:] in by_id:
                self.send(by_id[self.path[6:]]["path"].read_bytes(), "image/png")
            else:
                self.send(b"not found", "text/plain", 404)

        def do_POST(self):
            try:
                given = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                item, key, value = given["item"], given["key"], given.get("value")
                if key not in questions() and key != "note":
                    raise ValueError(f"no question {key!r}")
            except (ValueError, KeyError, TypeError) as e:
                self.send(json.dumps({"error": str(e)}).encode(), "application/json", 400)
                return
            self.send(json.dumps(labels.answer(item, key, value)).encode("utf-8"), "application/json")

    return Handler


class Server(ThreadingHTTPServer):
    # On Windows the address reuse that HTTPServer asks for lets a second server bind a port in use,
    # and the first one goes on answering.
    allow_reuse_address = os.name != "nt"


def progress(shots: list[dict], labels: Labels) -> str:
    asked = items(shots)
    done = sum(all(k in labels.data["labels"].get(i["id"], {}) for k in i["ask"]) for i in asked)
    return f"{done} of {len(asked)} pages answered in {labels.path}"


def main() -> int:
    c3.utf8_output()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("set", type=Path, metavar="SET.json", help="the screenshots to label, in the form above")
    ap.add_argument("--labels", type=Path, help="where the answers go (default: labels.json beside SET.json)")
    ap.add_argument("--words", type=Path, metavar="WORDS.json",
                    help="the questions and the page's words in the person's language, in the form above")
    ap.add_argument("--port", type=int, default=8770, help="the port on 127.0.0.1 (default 8770)")
    args = ap.parse_args()
    try:
        shots = load_set(args.set)
        words = load_words(args.words)
        labels = Labels(args.labels or args.set.parent / "labels.json", args.set)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2
    for k in labels.changed:
        print(f"warning: question {k} reads differently in review_look.py now; its labels answer the wording kept "
              f"in {labels.path}, so label the set again into a new --labels file to measure the new wording")
    try:
        server = Server(("127.0.0.1", args.port), handler(shots, labels, words))
    except OSError as e:
        print(f"port {args.port} is not free ({e}); stop the server on it or pass another --port", file=sys.stderr)
        return 2
    print(f"labelling {len(shots)} screenshots: open http://127.0.0.1:{args.port}/ ; {progress(shots, labels)}",
          flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    print(progress(shots, labels))
    return 0


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Look labels</title>
<style>
:root { --bg: #f6f6f4; --fg: #1d1d1b; --dim: #6b6b66; --line: #d9d9d4; --yes: #b4361f; --no: #2f6b3a; --sel: #ffffff; }
@media (prefers-color-scheme: dark) { :root { --bg: #1b1b1a; --fg: #ececea; --dim: #9a9a94; --line: #3a3a37;
  --yes: #ef7a62; --no: #7fc48a; --sel: #2a2a28; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); font: 15px/1.4 system-ui, sans-serif; }
header { display: flex; gap: 12px; align-items: center; padding: 8px 16px; border-bottom: 1px solid var(--line); }
header .grow { flex: 1; color: var(--dim); }
button { font: inherit; color: inherit; background: var(--sel); border: 1px solid var(--line); border-radius: 6px;
  padding: 4px 12px; cursor: pointer; }
main { display: flex; gap: 16px; padding: 16px; height: calc(100vh - 49px); }
.shots { flex: 1; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-content: center;
  min-width: 0; overflow: auto; }
.shots img { max-width: 100%; max-height: calc(100vh - 82px); object-fit: contain; border: 1px solid var(--line); }
.shots.several img { max-height: 40vh; max-width: 45%; }
.shots figure { margin: 0; text-align: center; color: var(--dim); }
aside { width: 460px; flex: none; overflow: auto; }
.q { display: grid; grid-template-columns: 22px 1fr auto; gap: 8px; padding: 10px 0; border-bottom: 1px solid var(--line); }
.q .n { color: var(--dim); }
.q .en { display: block; color: var(--dim); font-size: 13px; font-weight: 400; margin-top: 2px; }
.q .ab { display: flex; gap: 4px; }
.q button.on.yes { background: var(--yes); border-color: var(--yes); color: #fff; }
.q button.on.no { background: var(--no); border-color: var(--no); color: #fff; }
.q.open .text { font-weight: 600; }
textarea { width: 100%; min-height: 70px; margin-top: 10px; font: inherit; color: inherit; background: var(--sel);
  border: 1px solid var(--line); border-radius: 6px; padding: 6px; }
.keys { color: var(--dim); font-size: 13px; margin-top: 10px; }
.saved { color: var(--dim); font-size: 13px; }
@media (max-width: 900px) { main { flex-direction: column; height: auto; } aside { width: 100%; }
  .shots img { max-height: 60vh; } }
</style></head><body>
<header><button id="prev">&larr;</button><span id="where"></span><button id="next">&rarr;</button>
<button id="open">first open page</button><span class="grow" id="done"></span><span class="saved" id="saved"></span></header>
<main><div class="shots" id="shots"></div><aside id="panel"></aside></main>
<script>
let S, at = 0;
const $ = id => document.getElementById(id);
const W = (key, english) => (S.words.page || {})[key] || english;
const asked = k => { const t = (S.words.questions || {})[k];
  return t ? `${t}<span class="en">${S.questions[k]}</span>` : S.questions[k]; };
const answers = id => S.labels[id] || (S.labels[id] = {});
const complete = it => it.ask.every(k => k in answers(it.id));
async function post(item, key, value) {
  $('saved').textContent = W('saving', 'saving...');
  try {
    const r = await fetch('/answer', {method: 'POST', body: JSON.stringify({item, key, value})});
    if (!r.ok) throw new Error((await r.json()).error);
    S.labels[item] = await r.json();
    $('saved').textContent = W('saved', 'saved');
  } catch (e) { $('saved').textContent = W('not saved', 'not saved') + ': ' + e.message; }
  draw();
}
function set(key, value) { post(S.items[at].id, key, value); }
function draw() {
  const it = S.items[at], got = answers(it.id);
  $('where').textContent = `${at + 1} ${W('of', 'of')} ${S.items.length}`;
  $('done').textContent = `${S.items.filter(complete).length} ${W('of', 'of')} ${S.items.length} ${W('answered', 'answered')}`;
  const box = $('shots');
  if (box.dataset.item !== it.id) {
    box.dataset.item = it.id;
    box.className = 'shots' + (it.shots.length > 1 ? ' several' : '');
    box.innerHTML = it.shots.map(s => it.shots.length > 1
      ? `<figure><img src="/shot/${encodeURIComponent(s)}"><figcaption>${S.layouts[s]}</figcaption></figure>`
      : `<img src="/shot/${encodeURIComponent(s)}">`).join('');
  }
  const rows = it.ask.map((k, i) => {
    const v = got[k], label = k === 'ship' ? 'S' : k === 'across' ? 'A' : k;
    const yes = k === 'ship' ? W('ship', 'ship') : W('yes', 'yes'), no = k === 'ship' ? W('not', 'not') : W('no', 'no');
    return `<div class="q ${k in got ? '' : 'open'}"><span class="n">${label}</span><span class="text">${asked(k)}</span>
      <span class="ab"><button class="yes ${v === true ? 'on' : ''}" data-k="${k}" data-v="1">${yes}</button>
      <button class="no ${v === false ? 'on' : ''}" data-k="${k}" data-v="0">${no}</button></span></div>`;
  }).join('');
  const panel = $('panel'), note = document.activeElement && document.activeElement.id === 'note';
  if (!note) {
    panel.innerHTML = rows + `<textarea id="note" placeholder="${W('note', S.note)}"></textarea>` +
      `<div class="keys">${W('keys', '1-6: yes, then no &middot; Y / N: ship or not &middot; Enter: no to the rest, next &middot; arrows: move')}</div>`;
    $('note').value = got.note || '';
    $('note').addEventListener('change', e => set('note', e.target.value));
    panel.querySelectorAll('button').forEach(b => b.onclick = () => set(b.dataset.k, b.dataset.v === '1'));
  }
}
function go(n) { at = Math.max(0, Math.min(S.items.length - 1, n)); draw(); }
async function rest() {
  const it = S.items[at], got = answers(it.id);
  for (const k of it.ask) if (!(k in got) && k !== 'ship') await post(it.id, k, false);
  if ('ship' in answers(it.id) || !it.ask.includes('ship')) go(at + 1);
}
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'TEXTAREA') { if (e.key === 'Escape') e.target.blur(); return; }
  const it = S.items[at], got = answers(it.id);
  if (/^[1-9]$/.test(e.key) && it.ask.includes(e.key)) set(e.key, got[e.key] !== true);
  else if (e.key === 'a' && it.ask.includes('across')) set('across', got.across !== true);
  else if ((e.key === 'y' || e.key === 'n') && it.ask.includes('ship')) set('ship', e.key === 'y');
  else if (e.key === 'Enter') rest();
  else if (e.key === 'ArrowRight') go(at + 1);
  else if (e.key === 'ArrowLeft') go(at - 1);
  else return;
  e.preventDefault();
});
$('prev').onclick = () => go(at - 1);
$('next').onclick = () => go(at + 1);
$('open').onclick = () => { const n = S.items.findIndex(it => !complete(it)); go(n < 0 ? at : n); };
fetch('/state').then(r => r.json()).then(s => { S = s; $('open').textContent = W('open', 'first open page');
  document.documentElement.lang = S.words.lang || 'en'; const n = S.items.findIndex(it => !complete(it));
  go(n < 0 ? 0 : n); });
</script></body></html>
"""

if __name__ == "__main__":
    sys.exit(main())
