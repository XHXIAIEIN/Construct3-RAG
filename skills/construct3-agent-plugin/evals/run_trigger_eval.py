"""Measure how often the skill's description makes Claude Code load the skill.

    python evals/run_trigger_eval.py QUERIES.json --project FOLDER [--runs 3] [--model MODEL] [--output FILE]

Each query of evals/train_queries.json or evals/validation_queries.json runs
--runs times as `claude -p QUERY` in FOLDER, a game project outside the clone
that holds the skill where Claude Code discovers it and no block, so that the
description alone decides:

    python scripts/install.py --project FOLDER --into .claude/skills --no-block

Each run works in a copy of FOLDER of its own, made for it and removed after
it, so that what one run writes is not what another one reads.

A run counts as triggered when the stream shows the Skill tool called with
this skill, or SKILL.md of this skill read, and the call's result is not an
error. It is stopped there, or after --max-tools other tool calls, or at the
client's result. Every run is recorded with what ended it: triggered, not
triggered at the client's result, or the tool budget spent, counted as not
triggered; or one of three that are no answer: the load failed, the run timed
out, or the client stopped without a result. The trigger rate is over the
runs that answered; the others are counted apart, with the end of the
client's stderr. A query passes when its rate is at least --threshold and it
should trigger, or below it and it should not
(https://agentskills.io/skill-creation/optimizing-descriptions); a query
without a run that answered does not pass.

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
import shutil
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent.name


class ClientError(RuntimeError):
    pass


def loads_skill(tool: dict) -> bool:
    """A tool call that puts this skill's SKILL.md in front of the model: the Skill tool with this
    skill's name, with a plugin's prefix or without, or a Read of SKILL.md in a folder of that name."""
    name, given = tool.get("name"), tool.get("input") or {}
    if name == "Skill":
        return str(given.get("skill", "")).split(":")[-1] == SKILL
    if name == "Read":
        return ("/" + str(given.get("file_path", "")).replace("\\", "/")).endswith(f"/{SKILL}/SKILL.md")
    return False


# What ended a run. The first three answer the query; the others are left out of its rate.
ANSWERED = ("triggered", "not triggered", "tool budget")
NO_ANSWER = ("load failed", "timed out", "client stopped")
IGNORED = shutil.ignore_patterns(".git", ".build", ".tmp")    # not what the client reads to decide


def run_once(client: str, query: str, project: Path, model: str | None, max_tools: int,
             timeout: int) -> tuple[str, str]:
    """What ended a run of query in a copy of project, and the end of the client's stderr when it
    did not answer."""
    cmd = [*shlex.split(client), "-p", query, "--output-format", "stream-json", "--verbose"]
    cmd += ["--model", model] if model else []
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}     # set inside a session, it refuses a nested one
    with tempfile.TemporaryDirectory(prefix="trigger-", ignore_cleanup_errors=True) as tmp:
        copy = Path(tmp) / project.name
        shutil.copytree(project, copy, ignore=IGNORED)
        with open(Path(tmp) / "stderr.txt", "w+", encoding="utf-8", errors="replace") as err:
            try:
                proc = subprocess.Popen(cmd, cwd=copy, env=env, stdout=subprocess.PIPE, stderr=err,
                                        text=True, encoding="utf-8", errors="replace")
            except OSError as e:
                raise ClientError(f"{client} could not be started: {e}") from e
            timed_out = threading.Event()

            def stop() -> None:
                timed_out.set()
                proc.kill()
            timer = threading.Timer(timeout, stop)
            timer.start()
            try:
                status = read_stream(proc, client, max_tools)
            finally:
                timer.cancel()
                if proc.poll() is None:
                    proc.kill()
                proc.wait()
            if status is None:
                status = "timed out" if timed_out.is_set() else "client stopped"
            err.seek(0)
            return status, err.read()[-2000:] if status in NO_ANSWER else ""


def read_stream(proc: subprocess.Popen, client: str, max_tools: int) -> str | None:
    """What the stream says ended the run; None when it ends without saying."""
    tools, known, loading = 0, False, None
    for line in proc.stdout:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get("type")
        if kind == "result":
            if event.get("is_error"):
                raise ClientError(str(event.get("result", "the client reported an error")))
            return "load failed" if loading else "not triggered"
        if kind not in ("assistant", "user"):
            continue
        known = True
        content = event.get("message", {}).get("content", [])
        for part in content if isinstance(content, list) else []:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "tool_result" and loading and part.get("tool_use_id") == loading:
                return "load failed" if part.get("is_error") else "triggered"
            if part.get("type") != "tool_use" or loading:
                continue
            if loads_skill(part):
                loading = part.get("id") or "?"     # its result says whether it loaded
                continue
            tools += 1
            if tools >= max_tools:
                return "tool budget"
    if not known:
        raise ClientError(f"the stream of {client} held no assistant or result event; its format may have changed")
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("queries", metavar="QUERIES.json", help='a list of {"query": ..., "should_trigger": true|false}')
    ap.add_argument("--project", required=True, metavar="FOLDER",
                    help="a game project outside the clone with the skill under .claude/skills/ and no block")
    ap.add_argument("--runs", type=int, default=3, help="runs per query (default: 3)")
    ap.add_argument("--threshold", type=float, default=0.5, help="trigger rate that counts as triggering (default: 0.5)")
    ap.add_argument("--model", help="model for claude -p (default: the client's own)")
    ap.add_argument("--max-tools", type=int, default=5,
                    help="other tool calls after which a run ends as tool budget, counted as not "
                         "triggered (default: 5)")
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
        runs = [run_once(args.client, item["query"], project, args.model, args.max_tools, args.timeout)
                for _ in range(args.runs)]
        ends = {status: sum(s == status for s, _ in runs) for status in (*ANSWERED, *NO_ANSWER)}
        answered, hits = sum(ends[s] for s in ANSWERED), ends["triggered"]
        rate = hits / answered if answered else None
        passed = rate is not None and (rate >= args.threshold) == item["should_trigger"]
        print(f"  {hits}/{answered} {'ok  ' if passed else 'FAIL'} "
              f"{'should' if item['should_trigger'] else 'should not'}: {item['query'][:80]}"
              + "".join(f"; {ends[s]} {s}" for s in NO_ANSWER if ends[s]), file=sys.stderr)
        return {**item, "triggers": hits, "runs": args.runs, "answered": answered,
                "trigger_rate": None if rate is None else round(rate, 3), "pass": passed,
                "ends": {s: n for s, n in ends.items() if n},
                "stderr": [e for s, e in runs if s in NO_ANSWER and e]}

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
