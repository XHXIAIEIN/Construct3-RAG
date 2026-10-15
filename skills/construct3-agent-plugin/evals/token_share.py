"""Share out the token cost of Claude Code transcripts among what filled the context.

    python evals/token_share.py TRANSCRIPT.jsonl ... [--out RESULT.json] [--top 40]
    python evals/token_share.py FOLDER ... --files
    python evals/token_share.py @LIST ... --targets

A transcript is a .jsonl file, a folder (every .jsonl under it), or @LIST, a
text file with one transcript path per line.

Every model response's usage gives the whole context it read: uncached input,
cache writes, cache reads, and its own output. Between two responses the
context grows by what was added in between: the previous response's own
output (its text and the tool inputs it wrote), the tool results, the
attachments, the user's text. That growth is shared out among those items by
an estimate of their size (a CJK character as one token, other text at 3.6
characters a token, an image by its pixels, an attachment at half its JSON),
so the estimate decides only the split, never the total. An item costs its
write when it enters the context and one cache read per later response, until
a compaction or a new context drops it. A context under 70% of the one before
starts a new one: its whole size is the baseline (system prompt, tool
definitions, skill and agent lists, the first messages) or, after a
compaction, the summary.

Units are input-token equivalents at Opus price ratios: uncached input 1,
cache write 1.25 (5 minutes) or 2 (1 hour), cache read 0.1, output 5. Context
written again although it was cached before, because the cache expired or
broke, costs its items the read they would have cost and the premium over it
goes to cache-rewrite. The shares add up to the cost computed from the usage
alone; the first line prints both, and a difference over 0.1% is a fault of
this script.

Sources:
  baseline, compaction-summary      what a context starts with
  output:thinking, output:visible   what the model wrote, at the output price
  model-call:<kind>                 the tool inputs the model wrote, read again on every later response
  script:<name>, script:<name> --help   what a script printed; a script of this skill is "skill script"
  read:<kind>                       a Read, by file kind: SKILL.md, skill-reference, project-json, py, image ...
  bash:<kind>                       the rest of the shell output: read-file, search, git, python-other ...
  skill-body:<name>, skill:<name>   a skill loaded through the Skill tool
  attachment:<type>, system-reminder, user-text, subagent-report, mcp:<server>:<tool> ...
  cache-rewrite                     the premium of rewriting context whose cache had expired

The "sources" view sums them into what a change can move: baseline, model
output, the model's tool inputs, skill script output (the scripts of this
skill, --help included), skill text and references (its SKILL.md, read or
loaded, and the references and prompts it points to), other reads, other
shell output, attachments, cache-rewrite. --targets groups the larger reads
(read:<kind> and bash:read-file) by the file or folder they read: game
design documents, project JSON, this skill's references, a game's tools/.
--files prints one line per transcript: responses, the first context, the
largest, the cost; the first context of a subagent is what it starts with.
--out writes everything as JSON, with the items over --items units.

exit codes: 0 counted, 1 no transcript held a model response
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import struct
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import c3project as c3  # noqa: E402

INPUT, WRITE_5M, WRITE_1H, READ, OUT = 1.0, 1.25, 2.0, 0.1, 5.0
NEW_CONTEXT = 0.7            # a context under this share of the previous one starts a new context
CALL_OVERHEAD = 20           # the tokens a tool_use block adds around its input
NOT_SENT = {"prompt_snapshot", "deferred_tools_record", "credential_org", "command_permissions", "auto_mode",
            "remote_session_change", "model", "frame-link"}     # attachments the transcript keeps, the model never reads
SCRIPT = re.compile(r"(?:scripts|tools)[/\\](\w+)\.py")
CJK = re.compile(r"[　-鿿＀-￯]")
SKILL_SCRIPTS = frozenset(p.stem for p in SCRIPTS.glob("*.py"))


def text_tokens(s: str) -> float:
    """An estimate: a CJK character is about one token, other text about 3.6 characters a token."""
    cjk = len(CJK.findall(s))
    return cjk + (len(s) - cjk) / 3.6


def image_tokens(b64: str) -> float:
    """An image's tokens from its pixels, as the API scales it (1568 px on the long side, 1.15 MP at most)."""
    try:
        raw = base64.b64decode(b64[:4000] + "=" * (-len(b64[:4000]) % 4))
    except ValueError:
        return 1600
    w = h = 0
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", raw[16:24])
    elif raw[:2] == b"\xff\xd8":
        i = 2
        while i < len(raw) - 9:
            if raw[i] == 0xFF and raw[i + 1] in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", raw[i + 5:i + 9])
                break
            i += 1
    if not w or not h:
        return 1600
    scale = min(1.0, 1568 / max(w, h), (1_150_000 / (w * h)) ** 0.5)
    return max(50, w * scale * h * scale / 750)


def classify_bash(cmd: str) -> str:
    m = SCRIPT.search(cmd)
    if m:
        name = m.group(1)
        return f"script:{name} --help" if "--help" in cmd or " -h" in cmd else f"script:{name}"
    if re.search(r"/memory/|skills/soul|\.agents/skills|CLAUDE\.md|AGENTS\.md", cmd):
        return "bash:read-instructions"
    first = cmd.strip().split()[0] if cmd.strip() else ""
    if first in ("git", "gh"):
        return "bash:git"
    if re.search(r"\b(cat|head|tail|sed -n|Get-Content|type)\b", cmd):
        return "bash:read-file"
    if re.search(r"\b(grep|rg|find|ls|Select-String|Get-ChildItem)\b", cmd):
        return "bash:search"
    if first.startswith("python") or "python" in cmd[:40]:
        return "bash:python-other"
    return "bash:other"


def classify_read(path: str) -> str:
    low = path.replace("\\", "/").lower()
    if "/tool-results/" in low:
        return "read:persisted-output"
    if ("/memory/" in low or "/.claude/skills/soul" in low or "/.agents/skills/soul" in low
            or low.endswith(("claude.md", "agents.md"))):
        return "read:instructions"
    if low.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
        return "read:image"
    if low.endswith("skill.md"):
        return "read:SKILL.md"
    if re.search(r"/(eventsheets|layouts|objecttypes|families|timelines)/", low) or low.endswith(".c3proj"):
        return "read:project-json"
    if "/references/" in low or "/prompts/" in low:
        return "read:skill-reference"
    for ends, kind in ((".md", "md-other"), (".py", "py"), ((".js", ".ts"), "js-ts"), (".json", "json-other")):
        if low.endswith(ends):
            return f"read:{kind}"
    return "read:other"


def tool_category(name: str, given: dict) -> str:
    if name in ("Bash", "PowerShell"):
        return classify_bash(str(given.get("command", "")))
    if name == "Read":
        return classify_read(str(given.get("file_path", "")))
    if name in ("Grep", "Glob"):
        return "search-tool"
    if name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        return "edit-result"
    if name in ("Agent", "Task"):
        return "subagent-report"
    if name == "Skill":
        return f"skill:{given.get('skill', '')}"
    if name.startswith("mcp__"):
        part = name.split("__")
        return f"mcp:{part[1][:20]}:{part[-1]}"
    return f"tool:{name}"


def call_category(name: str, given: dict) -> str:
    """What the model wrote as a tool's input: the tool's name, or for a shell call the kind of command."""
    return "model-call:" + (tool_category(name, given) if name in ("Bash", "PowerShell") else name)


def describe(name: str, given: dict) -> str:
    if name in ("Bash", "PowerShell"):
        return str(given.get("command", ""))[:400]
    if name == "Read":
        return str(given.get("file_path", ""))
    return f"{name} {json.dumps(given, ensure_ascii=False)[:120]}"


@dataclass
class Item:
    """Something that entered the context: its source, its estimated and its measured tokens, and its cost."""
    cat: str
    est: float
    what: str = ""
    tok: float = 0.0
    cost: float = 0.0
    mark: float = 0.0       # the running read rate of its context when it entered


def message_items(content: object, tools: dict) -> list[Item]:
    """The items of a user-side message: tool results, user text, skill bodies, system reminders, images."""
    if isinstance(content, str):
        return [Item("user-text", text_tokens(content), content[:100])]
    items = []
    for part in content if isinstance(content, list) else []:
        kind = part.get("type")
        if kind == "tool_result":
            name, given = tools.get(part.get("tool_use_id"), ("?", {}))
            inner, est = part.get("content"), 0.0
            if isinstance(inner, str):
                est += text_tokens(inner)
            for sub in inner if isinstance(inner, list) else []:
                if sub.get("type") == "text":
                    est += text_tokens(sub.get("text", ""))
                elif sub.get("type") == "image":
                    est += image_tokens((sub.get("source") or {}).get("data", ""))
            items.append(Item(tool_category(name, given), est, describe(name, given)))
        elif kind == "text":
            text = part.get("text", "")
            if text.lstrip().startswith("<system-reminder>"):
                cat = "system-reminder"
            elif text.startswith("Base directory for this skill:"):
                cat = "skill-body:" + text.splitlines()[0].replace("\\", "/").rstrip("/").split("/")[-1]
            else:
                cat = "user-text"
            items.append(Item(cat, text_tokens(text), text[:100]))
        elif kind == "image":
            items.append(Item("user-image", image_tokens((part.get("source") or {}).get("data", "")), "pasted image"))
    return items


@dataclass
class Response:
    """One model response: its usage, the items added to the context before it, and the ones it wrote."""
    id: str
    uncached: int
    write_5m: int
    write_1h: int
    read: int
    out: int
    thinking: int
    before: list[Item]
    own: list[Item] = field(default_factory=list)

    @property
    def written(self) -> int:
        return self.uncached + self.write_5m + self.write_1h

    @property
    def context(self) -> int:
        return self.written + self.read

    @property
    def write_cost(self) -> float:
        return self.uncached * INPUT + self.write_5m * WRITE_5M + self.write_1h * WRITE_1H

    @property
    def exact(self) -> float:
        return self.write_cost + self.read * READ + self.out * OUT


def response_of(message: dict, before: list[Item]) -> Response:
    usage = message["usage"]
    created = usage.get("cache_creation_input_tokens", 0) or 0
    split = usage.get("cache_creation") or {}
    hour = split.get("ephemeral_1h_input_tokens", 0) or 0
    five = split.get("ephemeral_5m_input_tokens", 0) or 0
    if hour + five != created:       # no split, or one that does not add up: the 5-minute price for the rest
        five = max(0, created - hour)
    return Response(id=message.get("id") or "", uncached=usage.get("input_tokens", 0) or 0, write_5m=five,
                    write_1h=hour, read=usage.get("cache_read_input_tokens", 0) or 0,
                    out=usage.get("output_tokens", 0) or 0,
                    thinking=(usage.get("output_tokens_details") or {}).get("thinking_tokens", 0) or 0,
                    before=before)


def responses_of(path: Path) -> list[Response]:
    """The model's responses in order, each once although the transcript writes a line per content block."""
    tools: dict[str, tuple[str, dict]] = {}
    responses: list[Response] = []
    pending: list[Item] = []
    with path.open(encoding="utf-8") as lines:
        for line in lines:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            kind = entry.get("type")
            if kind == "assistant":
                message = entry.get("message") or {}
                if not isinstance(message.get("usage"), dict) or message.get("model") == "<synthetic>":
                    continue
                if not responses or responses[-1].id != message.get("id"):
                    responses.append(response_of(message, pending))
                    pending = []
                own = responses[-1].own
                for part in message.get("content") or []:
                    if part.get("type") == "tool_use":
                        name, given = part.get("name", "?"), part.get("input") or {}
                        tools[part.get("id")] = (name, given)
                        own.append(Item(call_category(name, given),
                                        text_tokens(json.dumps(given, ensure_ascii=False)) + CALL_OVERHEAD,
                                        "CALL " + describe(name, given)))
                    elif part.get("type") == "text":
                        own.append(Item("model-text", text_tokens(part.get("text", ""))))
            elif kind == "user":
                pending += message_items((entry.get("message") or {}).get("content"), tools)
            elif kind == "attachment":
                attachment = entry.get("attachment") or {}
                if attachment.get("type") not in NOT_SENT:
                    pending.append(Item(f"attachment:{attachment.get('type')}",
                                        text_tokens(json.dumps(attachment, ensure_ascii=False)) * 0.5))
    return responses


@dataclass
class Share:
    """The cost of one transcript or several, by source."""
    files: int = 0
    responses: int = 0
    exact: float = 0.0
    cost: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    tokens: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    items: list[tuple[float, str, str, str]] = field(default_factory=list)     # cost, file, source, what
    per_file: list[dict] = field(default_factory=list)

    @property
    def attributed(self) -> float:
        return sum(self.cost.values())

    def add(self, other: "Share") -> None:
        self.files += other.files
        self.responses += other.responses
        self.exact += other.exact
        for source, value in other.cost.items():
            self.cost[source] += value
        for source, value in other.tokens.items():
            self.tokens[source] += value
        self.items += other.items
        self.per_file += other.per_file


def share_of(path: Path) -> Share | None:
    """One transcript's cost by source, or None when it holds no model response."""
    responses = responses_of(path)
    if not responses:
        return None
    share = Share(files=1, responses=len(responses))
    live: list[Item] = []
    live_tokens = 0.0
    rate = 0.0         # read cost per token of context, summed over the responses of the current context

    def close() -> None:
        for it in live:
            it.cost += it.tok * (rate - it.mark)
            share.cost[it.cat] += it.cost
            share.tokens[it.cat] += it.tok
            if it.what:
                share.items.append((it.cost, path.name, it.cat, it.what[:400]))

    previous: Response | None = None
    for r in responses:
        share.exact += r.exact
        price = r.write_cost / r.written if r.written else 0.0
        if previous is None or r.context < NEW_CONTEXT * previous.context:
            close()
            # A prefix that other sessions share, the system prompt and the tools, is read from the cache, not written.
            base = Item("baseline" if previous is None else "compaction-summary", 0.0, tok=r.context,
                        cost=r.write_cost + r.read * READ)
            live, live_tokens, rate = [base], float(r.context), 0.0
        else:
            growth = max(0, r.context - previous.context)
            added = previous.own + r.before
            if growth and not added:
                added = [Item("unlisted-growth", 1.0)]
            estimate = sum(it.est for it in added) or 1.0
            new_written = min(r.written, growth)
            new_read = min(r.read, growth - new_written)
            rewritten = r.written - new_written         # context written again: its cache expired or broke
            old_read = r.read - new_read
            # Old items pay a read for what was read or rewritten; the rewrite's premium is cache-rewrite's.
            if live_tokens:
                rate += (old_read + rewritten) * READ / live_tokens
            share.cost["cache-rewrite"] += rewritten * (price - READ)
            arrival = new_written * price + new_read * READ
            for it in added:
                part = it.est / estimate
                it.tok, it.cost, it.mark = growth * part, arrival * part, rate
            live += added
            live_tokens += growth
        share.cost["output:thinking"] += r.thinking * OUT
        share.cost["output:visible"] += max(0, r.out - r.thinking) * OUT
        share.tokens["output:thinking"] += r.thinking
        share.tokens["output:visible"] += max(0, r.out - r.thinking)
        previous = r
    close()
    share.per_file.append({"file": str(path), "responses": len(responses), "first_context": responses[0].context,
                           "largest_context": max(r.context for r in responses), "exact": round(share.exact, 1)})
    return share


def transcripts(args: list[str]) -> list[Path]:
    files: list[Path] = []
    for a in args:
        if a.startswith("@"):
            files += [Path(x.strip().strip('"')) for x in Path(a[1:]).read_text(encoding="utf-8").splitlines()
                      if x.strip()]
            continue
        p = Path(a)
        files += sorted(p.rglob("*.jsonl")) if p.is_dir() else [p]
    return files


def measure(paths: list[Path]) -> Share:
    total = Share()
    for p in paths:
        one = share_of(p)
        if one:
            total.add(one)
    return total


# The views: sources summed into what a change can move.
SKILL_TEXT = ("read:SKILL.md", "read:skill-reference", "skill-body:construct3-agent-plugin")


def source_group(source: str) -> str:
    if source in ("baseline", "cache-rewrite"):
        return source
    if source == "compaction-summary":
        return "compaction summaries"
    if source.startswith("output:"):
        return "model output"
    if source.startswith("model-call:"):
        return "model's tool inputs"
    if source.startswith("script:"):
        name = source.split(":", 1)[1].split()[0]
        return "skill script output" if name in SKILL_SCRIPTS else "other script output"
    if source in SKILL_TEXT or source.endswith(":construct3-agent-plugin"):
        return "skill text and references"
    if source.startswith("read:"):
        return "other reads"
    if source.startswith("bash:") or source == "search-tool":
        return "other shell and search output"
    if source.startswith(("attachment:", "skill-body:", "skill:")) or source == "system-reminder":
        return "attachments, reminders, other skills"
    return "other"


def is_read(source: str) -> bool:
    """A source that read a file: a Read, or a shell command that printed one."""
    return source.startswith("read:") or source == "bash:read-file"


PATH = re.compile(r"[\w:./\\ -]*?[\w-]+\.(?:md|json|py|js|ts|txt|c3proj|csv|html)\b")
TARGETS = [
    (r"/tool-results/", "persisted tool output"),
    (r"/memory/|soul-|claude\.md", "instructions and memory"),
    (r"agents\.md", "AGENTS.md"),
    (r"skill\.md", "skill SKILL.md"),
    (r"construct3-agent-plugin/references/|/references/", "skill references"),
    (r"prompts/pitfalls|event-sheet-pitfalls", "skill pitfalls"),
    (r"prompts/", "skill prompts"),
    (r"c3-schemas|c3-lang|c3-ts-defs", "skill data"),
    (r"construct3-agent-plugin/scripts/|skills/construct3/", "skill script source"),
    (r"docs/0?1-plans|docs/plans", "game docs: plans"),
    (r"docs/0?2-design|docs/design", "game docs: design"),
    (r"docs/", "game docs: other"),
    (r"eventsheets/", "game eventSheets JSON"),
    (r"layouts/|objecttypes/|families/|timelines/|\.c3proj", "game project JSON (layouts, objects)"),
    (r"files/|data/run", "game data files"),
    (r"scripts/[\w-]+\.(js|ts)", "game scripts JS/TS"),
    (r"tools/", "game tools"),
]


def target_of(what: str) -> str:
    """The file or folder an item read, as a group: the first rule that matches the paths its command names."""
    w = what.replace("\\", "/").lower()
    found = PATH.findall(w)
    target = " ".join(found) if found else w
    for pattern, name in TARGETS:
        if re.search(pattern, target):
            return name
    return "other: " + (found[0][-40:] if found else w[:40])


def rows(values: dict[str, float], total: float, n: int) -> list[str]:
    return [f"{v / total:6.1%}  {v / 1e6:8.2f}M  {k}" for k, v in sorted(values.items(), key=lambda kv: -kv[1])[:n]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcripts", nargs="+", metavar="TRANSCRIPT", help="a .jsonl file, a folder, or @LIST")
    ap.add_argument("--out", metavar="RESULT.json", help="write the shares, the per-file lines and the items as JSON")
    ap.add_argument("--top", type=int, default=40, metavar="N", help="sources to print (default 40)")
    ap.add_argument("--items", type=float, default=2000, metavar="UNITS",
                    help="keep the items costing more than this in --out and --targets (default 2000)")
    ap.add_argument("--targets", action="store_true", help="also group the items by the file or folder they read")
    ap.add_argument("--files", action="store_true", help="also print one line per transcript")
    args = ap.parse_args()
    c3.utf8_output()

    share = measure(transcripts(args.transcripts))
    if not share.responses:
        print("no transcript held a model response", file=sys.stderr)
        return 1
    total = share.attributed
    gap = (total - share.exact) / share.exact if share.exact else 0.0
    print(f"{share.files} transcripts, {share.responses} responses, attributed {total / 1e6:.2f}M units, "
          f"exact from usage {share.exact / 1e6:.2f}M ({gap:+.3%})")
    groups: dict[str, float] = defaultdict(float)
    for source, value in share.cost.items():
        groups[source_group(source)] += value
    print("\nsources:")
    print("\n".join(rows(groups, total, 20)))
    print(f"\nby source (top {args.top}):")
    print("\n".join(rows(share.cost, total, args.top)))
    kept = [i for i in share.items if i[0] > args.items]
    if args.targets:
        by_target: dict[str, float] = defaultdict(float)
        for cost, _file, source, what in kept:
            if is_read(source):
                by_target[target_of(what)] += cost
        print(f"\nreads by target (items over {args.items:g} units):")
        print("\n".join(rows(by_target, total, 25)))
    if args.files:
        print("\nper transcript: responses, first context, largest context, units")
        for f in share.per_file:
            print(f"{f['responses']:6d} {f['first_context']:9d} {f['largest_context']:9d} {f['exact'] / 1e6:9.3f}M  {f['file']}")
    if args.out:
        result = {"files": share.files, "responses": share.responses, "exact": share.exact, "attributed": total,
                  "groups": dict(sorted(groups.items(), key=lambda kv: -kv[1])),
                  "cost": dict(sorted(share.cost.items(), key=lambda kv: -kv[1])), "tokens": dict(share.tokens),
                  "per_file": share.per_file,
                  "items": sorted(([round(c, 1), f, s, w] for c, f, s, w in kept), reverse=True)}
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
