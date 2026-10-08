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
whose exit code 1 is the findings it was asked for. outside lists the writes
outside the run folder (--root, by default RUN_DIR of --out): an absolute
path given to Write, Edit or NotebookEdit, and one a shell command redirects
to or gives to a command that writes (cp, mv, mkdir, rm, tee, Set-Content,
Copy-Item ...); outside_reads lists the other absolute paths outside it. A
relative path, a variable and a path built inside a script are not
resolved, so the list is a floor: an empty one proves nothing. read_skill_md is true
when this skill's SKILL.md reached the model: the Skill tool called with this
skill, or its SKILL.md read, and the call's result came back without an
error, as run_trigger_eval.py counts a trigger. turns, output_tokens,
input_tokens (cache writes and reads included) and seconds, first entry to
last, are what the run cost, read from the model's responses in the
transcript. --out writes the counts to RUN_DIR/trace.json, which grade.py
adds to the benchmark. --full prints commands and results unshortened.

exit codes: 0 read, 1 the file holds no tool call
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from run_trigger_eval import loads_skill

SCRIPT = re.compile(r"scripts[/\\](\w+)\.py\"?((?:\s+(?!\d*[<>])(?:\"[^\"]*\"|[^\s|;&<>]+))*)")     # 2>&1 is not an argument


def short(value: object, n: int) -> str:
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
                by_id[part["id"]] = {"tool": part.get("name"), "what": str(what), "chars": None, "failed": False,
                                     "result": "", "loads_skill": loads_skill(part), "input": given}
                calls.append(by_id[part["id"]])
            elif part.get("type") == "tool_result" and part.get("tool_use_id") in by_id:
                body = part.get("content")
                if isinstance(body, list):
                    body = " ".join(b.get("text", "") for b in body if isinstance(b, dict))
                text = str(body or "")
                by_id[part["tool_use_id"]].update(chars=len(text), failed=bool(part.get("is_error")), result=text)
    return calls


# The tools a run starts a script with: Bash, or PowerShell on Windows.
SHELLS = ("Bash", "PowerShell")


# Shell text in words: 2>&1, a redirection, a separator, a quoted string, or a bare word.
WORD = re.compile(r"""\d?>>?&\d|\d?>>?|&&|\|\||[|;&\n]|"[^"]*"|'[^']*'|[^\s"'|;&>]+""")
REDIRECT = re.compile(r"\d?>>?")
SEPARATORS = {"&&", "||", "|", ";", "&", "\n"}
NOWHERE = {"/dev/null", "$null", "nul"}
WRITES_EVERY = {"mkdir", "md", "rm", "rmdir", "rd", "del", "erase", "touch", "tee", "tee-object", "new-item", "ni",
                "remove-item", "ri", "set-content", "sc", "add-content", "ac", "out-file"}
WRITES_LAST = {"cp", "mv", "copy", "move", "copy-item", "cpi", "move-item", "mi", "rsync"}
FILE_WRITES = {"Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path", "NotebookEdit": "notebook_path"}
FILE_READS = {"Read": "file_path", "Glob": "path", "Grep": "path"}


def absolute(word: str) -> str | None:
    """word as an absolute path, or None: a relative path or a variable is not resolved.
    Git Bash's /c/Users is C:/Users."""
    word = word.strip("\"'")
    if word.lower() in NOWHERE:
        return None
    word = re.sub(r"^/([A-Za-z])(?=/|$)", r"\1:", word)
    word = os.path.expanduser(word) if word.startswith("~") else word
    return os.path.abspath(word) if re.match(r"[A-Za-z]:[\\/]|/|\\\\", word) else None


def shell_paths(command: str) -> tuple[list[str], list[str]]:
    """The absolute paths a shell command writes and the ones it only names, as far as its words say."""
    writes, named = [], []
    segment: list[str] = []

    def close() -> None:
        words = [w.split("=", 1)[1] if w.startswith("-") and "=" in w else w for w in segment]
        paths = [p for w in words[1:] if not w.startswith("-") and (p := absolute(w))]
        name = Path(words[0].strip("\"'")).name.lower().removesuffix(".exe") if words else ""
        if name in WRITES_EVERY or (name == "sed" and any(w.startswith("-i") for w in words)):
            writes.extend(paths)
        elif name in WRITES_LAST and paths:
            writes.append(paths[-1])
            named.extend(paths[:-1])
        else:
            named.extend(paths)
        segment.clear()

    words = WORD.findall(command)
    i = 0
    while i < len(words):
        if words[i] in SEPARATORS:
            close()
        elif REDIRECT.fullmatch(words[i]):
            i += 1
            target = absolute(words[i]) if i < len(words) else None
            if target:
                writes.append(target)
        elif "&" not in words[i]:      # 2>&1
            segment.append(words[i])
        i += 1
    close()
    return writes, named


def outside(calls: list[dict], root: Path) -> tuple[list[dict], list[dict]]:
    """The writes and the reads of absolute paths outside root, each with its tool."""
    base = os.path.normcase(os.path.abspath(root)).rstrip("\\/")

    def out_of_root(path: str) -> bool:
        path = os.path.normcase(path)
        return path != base and not path.startswith(base + os.sep)

    writes, reads = [], []
    for c in calls:
        given = c["input"] if isinstance(c["input"], dict) else {}
        if c["tool"] in SHELLS:
            wrote, named = shell_paths(str(given.get("command", "")))
        else:
            path = absolute(str(given.get(FILE_WRITES.get(c["tool"]) or FILE_READS.get(c["tool"]) or "", "")))
            wrote, named = ([path], []) if c["tool"] in FILE_WRITES and path else ([], [path] if path else [])
        writes += [{"tool": c["tool"], "path": p} for p in wrote if out_of_root(p)]
        reads += [{"tool": c["tool"], "path": p} for p in named if out_of_root(p)]
    return writes, reads


def usage_of(path: Path) -> dict:
    """What the run cost, from its transcript: turns (one per model response, which the transcript writes once per
    content block, so counted by message id), output tokens, input tokens with cache writes and reads, the seconds
    from its first entry to its last, and the model."""
    seen: dict[str, dict] = {}
    times, model = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("timestamp"):
            times.append(entry["timestamp"])
        message = entry.get("message") or {}
        if entry.get("type") == "assistant" and message.get("id") and isinstance(message.get("usage"), dict):
            seen[message["id"]] = message["usage"]
            model = message.get("model") or model
    stamps = sorted(datetime.fromisoformat(t.replace("Z", "+00:00")) for t in times)
    return {"turns": len(seen), "output_tokens": sum(u.get("output_tokens", 0) for u in seen.values()),
            "input_tokens": sum(u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
                                + u.get("cache_read_input_tokens", 0) for u in seen.values()),
            "seconds": round((stamps[-1] - stamps[0]).total_seconds(), 1) if len(stamps) > 1 else None, "model": model}


def summary(calls: list[dict]) -> dict:
    scripts = [{"script": m.group(1), "args": m.group(2).strip(), "failed": c["failed"], "chars": c["chars"]}
               for c in calls if c["tool"] in SHELLS for m in SCRIPT.finditer(c["what"])]
    by_tool: dict[str, dict[str, int]] = {}
    for c in calls:
        counts = by_tool.setdefault(c["tool"], {"calls": 0, "failed": 0})
        counts["calls"] += 1
        counts["failed"] += c["failed"]
    lost = [c for c in calls if c["failed"] and not (c["tool"] in SHELLS and "check_project.py" in c["what"])]
    return {"tool_calls": len(calls), "lost_calls": len(lost), "by_tool": by_tool, "scripts": scripts,
            "read_skill_md": any(c["loads_skill"] and c["chars"] is not None and not c["failed"] for c in calls)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcript", nargs="?", metavar="TRANSCRIPT.jsonl")
    ap.add_argument("--out", metavar="RUN_DIR", help="write the counts to RUN_DIR/trace.json")
    ap.add_argument("--root", metavar="FOLDER",
                    help="the folder the run may write in, for outside (default: RUN_DIR of --out)")
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
    counts = summary(calls) | usage_of(Path(args.transcript))
    print(f"{counts['turns']} turns, {counts['output_tokens']} output tokens, {counts['input_tokens']} input tokens, "
          f"{counts['seconds']} s, {counts['model']}")
    print(f"{counts['tool_calls']} tool calls, {counts['lost_calls']} lost; scripts run: "
          + ", ".join(f"{s['script']} {s['args']}".strip() + (" (failed)" if s["failed"] else "") for s in counts["scripts"]))
    root = args.root or args.out
    if root:
        counts["outside"], counts["outside_reads"] = outside(calls, Path(root))
        writes = counts["outside"]
        print(f"{len(writes)} write{'s' if len(writes) != 1 else ''} outside {Path(root).resolve()}"
              + "".join(f"\n  {w['tool']}: {w['path']}" for w in writes))
    if args.out:
        (Path(args.out) / "trace.json").write_text(json.dumps(counts, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
