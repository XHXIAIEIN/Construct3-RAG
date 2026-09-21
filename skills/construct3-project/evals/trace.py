"""Read what a run did from its transcript: every tool call, what came back, what failed.

    python evals/trace.py TRANSCRIPT.jsonl [--out RUN_DIR] [--full]
    python evals/trace.py --list SESSION_DIR

A run's answer lists the commands it remembers; its transcript lists the ones
it made. Claude Code keeps the transcript of a subagent as
~/.claude/projects/<project>/<session id>/subagents/agent-<id>.jsonl, with
the description it was started under in agent-<id>.meta.json beside it;
--list prints both for every subagent of a session.

The trace shows where a run lost turns: a lookup that found nothing, an edit
that did not match, a script called for output it then could not use. A call
counts as lost when its result is an error, except a run of check_project.py,
whose exit code 1 is the findings it was asked for. --out writes the counts
to RUN_DIR/trace.json, which grade.py adds to the benchmark. --full prints
commands and results unshortened.

exit codes: 0 read, 1 the file holds no tool call
"""
import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT = re.compile(r"scripts[/\\](\w+)\.py\"?((?:\s+(?!\d*[<>])(?:\"[^\"]*\"|[^\s|;&<>]+))*)")     # 2>&1 is not an argument


def short(value, n: int) -> str:
    text = str(value).replace("\n", " \\n ")
    return text if len(text) <= n else f"{text[:n]} ...[{len(text)} chars]"


def calls_of(path: Path) -> list[dict]:
    """Tool calls in order, each with the size and the failure of its result."""
    calls, by_id = [], {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            content = (json.loads(line).get("message") or {}).get("content")
        except ValueError:
            continue
        for part in content if isinstance(content, list) else []:
            if part.get("type") == "tool_use":
                given = part.get("input", {})
                what = given.get("command") or given.get("file_path") or given.get("pattern") or given.get("skill") or given
                by_id[part["id"]] = {"tool": part.get("name"), "what": str(what), "chars": None, "failed": False, "result": ""}
                calls.append(by_id[part["id"]])
            elif part.get("type") == "tool_result" and part.get("tool_use_id") in by_id:
                body = part.get("content")
                if isinstance(body, list):
                    body = " ".join(b.get("text", "") for b in body if isinstance(b, dict))
                by_id[part["tool_use_id"]].update(chars=len(str(body or "")), failed=bool(part.get("is_error")),
                                                  result=str(body or ""))
    return calls


def summary(calls: list[dict]) -> dict:
    scripts = [{"script": m.group(1), "args": m.group(2).strip(), "failed": c["failed"], "chars": c["chars"]}
               for c in calls if c["tool"] == "Bash" for m in SCRIPT.finditer(c["what"])]
    by_tool: dict[str, dict[str, int]] = {}
    for c in calls:
        counts = by_tool.setdefault(c["tool"], {"calls": 0, "failed": 0})
        counts["calls"] += 1
        counts["failed"] += c["failed"]
    lost = [c for c in calls if c["failed"] and not (c["tool"] == "Bash" and "check_project.py" in c["what"])]
    return {"tool_calls": len(calls), "lost_calls": len(lost), "by_tool": by_tool, "scripts": scripts,
            "read_skill_md": any(c["tool"] in ("Read", "Skill") and "SKILL.md" in c["what"] for c in calls)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcript", nargs="?", metavar="TRANSCRIPT.jsonl")
    ap.add_argument("--out", metavar="RUN_DIR", help="write the counts to RUN_DIR/trace.json")
    ap.add_argument("--full", action="store_true", help="print commands and results unshortened")
    ap.add_argument("--list", metavar="SESSION_DIR", help="print the subagent transcripts of a session with their descriptions")
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")

    if args.list:
        for meta in sorted(Path(args.list).glob("subagents/agent-*.meta.json")):
            about = json.loads(meta.read_text(encoding="utf-8"))
            print(f"{meta.with_suffix('').with_suffix('.jsonl')}  {about.get('model', '')}  {about.get('description', '')}")
        return 0
    if not args.transcript:
        ap.error("TRANSCRIPT.jsonl is required unless --list is given")

    calls = calls_of(Path(args.transcript))
    if not calls:
        print(f"{args.transcript} holds no tool call", file=sys.stderr)
        return 1
    width = 100_000 if args.full else 240
    for n, c in enumerate(calls, 1):
        print(f"{n:>3} {c['tool']:<6} {short(c['what'], width)}")
        print(f"      -> {c['chars']} chars{' FAILED' if c['failed'] else ''}: {short(c['result'], width)}")
    counts = summary(calls)
    print(f"{counts['tool_calls']} tool calls, {counts['lost_calls']} lost; scripts run: "
          + ", ".join(f"{s['script']} {s['args']}".strip() + (" (failed)" if s["failed"] else "") for s in counts["scripts"]))
    if args.out:
        (Path(args.out) / "trace.json").write_text(json.dumps(counts, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
