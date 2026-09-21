"""Measure how often the skill's description makes Claude Code load the skill.

    python evals/run_trigger_eval.py QUERIES.json --project FOLDER [--runs 3] [--model MODEL] [--output FILE]

Each query of evals/train_queries.json or evals/validation_queries.json runs
--runs times as `claude -p QUERY` in FOLDER, a game project outside the clone
that holds the skill where Claude Code discovers it and no block, so that the
description alone decides:

    python scripts/install.py --project FOLDER --into .claude/skills --no-block

A run counts as triggered when the stream shows the Skill tool called with
this skill, or SKILL.md of this skill read. It is stopped there, or after
--max-tools other tool calls, or at the client's result. A query passes when
its trigger rate is at least --threshold and it should trigger, or below it
and it should not (https://agentskills.io/skill-creation/optimizing-descriptions).

Revise the description from the failures of the train set only, and choose
between descriptions by the pass rate of the validation set.

exit codes: 0 every query passed, 1 some query failed, 2 the client could not
run a query: it is not signed in (run `claude` once and sign in), it is not
installed, or its stream held nothing this script knows. Nothing is written
for such a run; a client that cannot answer has not declined to trigger.
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent.name


class ClientError(RuntimeError):
    pass


def loads_skill(tool: dict) -> bool:
    """A tool call that puts this skill's SKILL.md in front of the model."""
    name, given = tool.get("name"), tool.get("input") or {}
    if name == "Skill":
        return str(given.get("skill", "")).split(":")[-1] == SKILL
    if name == "Read":
        return f"{SKILL}/SKILL.md" in str(given.get("file_path", "")).replace("\\", "/")
    return False


def run_once(client: str, query: str, project: Path, model: str | None, max_tools: int, timeout: int) -> bool:
    cmd = [*shlex.split(client), "-p", query, "--output-format", "stream-json", "--verbose"]
    cmd += ["--model", model] if model else []
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}     # set inside a session, it refuses a nested one
    try:
        proc = subprocess.Popen(cmd, cwd=project, env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, encoding="utf-8", errors="replace")
    except OSError as e:
        raise ClientError(f"{client} could not be started: {e}") from e
    timer = threading.Timer(timeout, proc.kill)
    timer.start()
    tools = known = 0
    try:
        for line in proc.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "result":
                known += 1
                if event.get("is_error"):
                    raise ClientError(str(event.get("result", "the client reported an error")))
                return False
            if event.get("type") != "assistant":
                continue
            known += 1
            for part in event.get("message", {}).get("content", []):
                if part.get("type") != "tool_use":
                    continue
                if loads_skill(part):
                    return True
                tools += 1
                if tools >= max_tools:
                    return False
        if not known:
            raise ClientError(f"the stream of {client} held no assistant or result event; its format may have changed")
        return False
    finally:
        timer.cancel()
        if proc.poll() is None:
            proc.kill()
        proc.wait()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("queries", metavar="QUERIES.json", help='a list of {"query": ..., "should_trigger": true|false}')
    ap.add_argument("--project", required=True, metavar="FOLDER",
                    help="a game project outside the clone with the skill under .claude/skills/ and no block")
    ap.add_argument("--runs", type=int, default=3, help="runs per query (default: 3)")
    ap.add_argument("--threshold", type=float, default=0.5, help="trigger rate that counts as triggering (default: 0.5)")
    ap.add_argument("--model", help="model for claude -p (default: the client's own)")
    ap.add_argument("--max-tools", type=int, default=5,
                    help="other tool calls after which a run counts as not triggered (default: 5)")
    ap.add_argument("--timeout", type=int, default=180, help="seconds before a run is stopped (default: 180)")
    ap.add_argument("--workers", type=int, default=4, help="runs in parallel (default: 4)")
    ap.add_argument("--client", default="claude",
                    help="the client's command, several words allowed, paths with forward slashes (default: claude)")
    ap.add_argument("--output", metavar="FILE", help="write the results here instead of stdout")
    args = ap.parse_args()

    project = Path(args.project).resolve()
    if not (project / ".claude" / "skills" / SKILL / "SKILL.md").is_file():
        sys.exit(f"{project} holds no .claude/skills/{SKILL}/SKILL.md; install it there first:\n"
                 f"  python scripts/install.py --project \"{project}\" --into .claude/skills --no-block")
    queries = json.loads(Path(args.queries).read_text(encoding="utf-8"))

    def rate(item: dict) -> dict:
        hits = sum(run_once(args.client, item["query"], project, args.model, args.max_tools, args.timeout)
                   for _ in range(args.runs))
        triggered = hits / args.runs >= args.threshold
        print(f"  {hits}/{args.runs} {'ok  ' if triggered == item['should_trigger'] else 'FAIL'} "
              f"{'should' if item['should_trigger'] else 'should not'}: {item['query'][:80]}", file=sys.stderr)
        return {**item, "triggers": hits, "runs": args.runs, "trigger_rate": round(hits / args.runs, 3),
                "pass": triggered == item["should_trigger"]}

    try:
        run_once(args.client, queries[0]["query"], project, args.model, 1, args.timeout)    # fail before sixty runs do
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            results = list(pool.map(rate, queries))
    except ClientError as e:
        print(f"no result written: {e}", file=sys.stderr)
        return 2

    passed = sum(r["pass"] for r in results)
    report = json.dumps({"skill": SKILL, "model": args.model, "queries": args.queries, "passed": passed,
                         "total": len(results), "pass_rate": round(passed / len(results), 3), "results": results},
                        indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(report + "\n", encoding="utf-8")
    else:
        print(report)
    print(f"{passed}/{len(results)} queries passed", file=sys.stderr)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
