"""Put the questions of scripts/review_look.py about a labelled set of screenshots to a judge that
has not seen the games, and measure how often its answers agree with the person's labels.

    python evals/judge_look.py SET.json --briefs FOLDER
    python evals/judge_look.py SET.json --briefs FOLDER --model MODEL --out REPLIES [--runs 1] [--jobs 4]
    python evals/judge_look.py SET.json --briefs FOLDER --score REPLIES [--labels LABELS.json]

SET.json is the set of evals/label_look.py; its labels.json holds the person's answers.

--briefs writes one folder per brief of the set, b01, b02 and on, numbered in an order shuffled
by the brief's id, each with copies of its screenshots and the brief.md that review_look.py would
write for them (review_look.brief), and FOLDER/index.json, which says which screenshots each one
holds. No name or path tells the judge where a screenshot came from or what was broken in it.

A judge answers a brief by its brief.md alone, and its reply goes to REPLIES/<b01>-<run>.txt. A
sub-agent given the brief as its whole task is such a judge. With --model the script is one:
`claude -p BRIEF --model MODEL --safe-mode --tools Read` in the brief's folder, without CLAUDE.md,
skills, plugins or any tool but Read, and what each run cost goes to REPLIES/<b01>-<run>.json. The
client must be signed in (run `claude` once).

--score reads every reply in REPLIES and prints, per question, the screenshots both answered and
how many agree, the person's yes and the judge's yes, the faults the judge missed and the ones it
saw that the person did not, and the agreement a judge that always answered no would reach. The
ship line compares "every answer no" with the person's "would ship"; the person's own answers are
compared with it too, which says what the questions leave out. A screenshot the reply does not
answer counts as unanswered, not as no. The whole score goes to REPLIES/score.json.

Exit codes: 0 done, 1 some run got no reply, 2 bad arguments, no labels, or no client.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))
import c3project as c3              # noqa: E402
import label_look as ll             # noqa: E402
import review_look as rl            # noqa: E402
import run_trigger_eval as rte      # noqa: E402

# A line of a reply: the screenshot's name, the question's number, the answer.
ANSWER = re.compile(r"^\W*(?P<shot>.+?)\W+(?:q(?:uestion)?\s*)?(?P<q>\d+)\s*[:.)\-][\s*]*(?P<a>yes|no)\b", re.I)


def names(group: list[dict]) -> list[str]:
    """The name each screenshot has in its brief: its layout, numbered when two share one."""
    seen: dict[str, int] = {}
    out = []
    for s in group:
        seen[s["layout"]] = seen.get(s["layout"], 0) + 1
        out.append(s["layout"] if seen[s["layout"]] == 1 else f"{s['layout']} {seen[s['layout']]}")
    return out


def prepare(shots: list[dict], folder: Path) -> dict[str, dict]:
    """Writes a folder per brief with its screenshots and brief.md, and index.json; returns the index."""
    folder = folder.resolve()
    groups: dict[str, list[dict]] = {}
    for s in shots:
        groups.setdefault(s["brief"], []).append(s)
    order = sorted(groups, key=lambda b: hashlib.sha256(b.encode()).hexdigest())
    index = {}
    for n, brief in enumerate(order, 1):
        key, group = f"b{n:02d}", groups[brief]
        place = folder / key
        if place.exists():
            shutil.rmtree(place)
        place.mkdir(parents=True)
        layouts = []
        for s, name in zip(group, names(group)):
            shot = place / f"{rl.file_name(name)}.png"
            shutil.copyfile(s["path"], shot)
            layouts.append({"layout": name, "shot": str(shot)})
        (place / "brief.md").write_text(rl.brief({"preview": {"layouts": layouts}, "places": []}), encoding="utf-8")
        index[key] = {"brief": brief, "shots": [s["id"] for s in group], "names": names(group)}
    (folder / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    return index


def judge(client: str, model: str, place: Path, timeout: int) -> dict:
    """One run of `claude -p` on the brief in place: its reply and what it cost."""
    cmd = [*client.split(), "-p", (place / "brief.md").read_text(encoding="utf-8"), "--model", model,
           "--safe-mode", "--tools", "Read", "--output-format", "json", "--no-session-persistence"]
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}     # set inside a session, it refuses a nested one
    start = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=place, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace", start_new_session=os.name != "nt",
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        rte.stop_tree(proc)
        return {"error": f"no reply in {timeout} s"}
    try:
        got = json.loads(out)
    except ValueError:
        return {"error": f"{client} printed no JSON: {(err or out)[-300:]}"}
    usage = got.get("usage") or {}
    if got.get("is_error") or not usage.get("output_tokens"):
        return {"error": f"{client} answered with an error: {str(got.get('result'))[:300]}"}
    return {"reply": got.get("result", ""), "model": model, "seconds": round(time.monotonic() - start, 1),
            "turns": got.get("num_turns"), "cost_usd": got.get("total_cost_usd"),
            "tokens": {k: usage.get(k) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                                 "cache_creation_input_tokens")}}


def run(args, index: dict) -> int:
    args.out.mkdir(parents=True, exist_ok=True)
    jobs = [(key, r) for key in index for r in range(1, args.runs + 1) if not (args.out / f"{key}-{r}.txt").is_file()]
    print(f"{len(jobs)} runs of {args.model} to make, {args.jobs} at a time, into {args.out}", flush=True)

    def one(job):
        key, r = job
        got = judge(args.client, args.model, args.briefs / key, args.timeout)
        if "reply" in got:
            (args.out / f"{key}-{r}.txt").write_text(got.pop("reply"), encoding="utf-8")
        (args.out / f"{key}-{r}.json").write_text(json.dumps(got, indent=1), encoding="utf-8")
        return key, r, got
    failed = 0
    with ThreadPoolExecutor(args.jobs) as pool:
        for key, r, got in pool.map(one, jobs):
            failed += "error" in got
            print(f"  {key} run {r}: {got.get('error') or str(got['seconds']) + ' s'}", flush=True)
    if failed:
        print(f"{failed} runs got no reply; their .json says why. Run again to retry only those.")
    return 1 if failed else 0


def parse(reply: str, ids: list[str], shown: list[str]) -> dict[str, dict[str, bool]]:
    """The answers of a reply by screenshot id and question number."""
    by_name = {n.lower(): i for i, n in zip(ids, shown)}
    out: dict[str, dict[str, bool]] = {}
    for line in reply.splitlines():
        m = ANSWER.match(line.strip())
        if not m:
            continue
        shot = m["shot"].strip(" *`#").lower()
        sid = by_name.get(shot) or next((v for k, v in sorted(by_name.items(), key=lambda kv: -len(kv[0]))
                                         if shot.endswith(k)), None)
        if sid is None and len(ids) == 1:
            sid = ids[0]
        if sid:
            out.setdefault(sid, {})[m["q"]] = m["a"].lower() == "yes"
    return out


def agreement(pairs: list[tuple[bool, bool]]) -> dict:
    """Counts over (person, judge) pairs of yes (True) and no (False)."""
    n = len(pairs)
    return {"n": n, "agree": sum(a == b for a, b in pairs), "person_yes": sum(a for a, _ in pairs),
            "judge_yes": sum(b for _, b in pairs), "missed": sum(a and not b for a, b in pairs),
            "extra": sum(b and not a for a, b in pairs), "always_no": sum(not a for a, _ in pairs)}


def score(replies: Path, index: dict, labels: dict) -> dict:
    """Agreement per question over every reply in replies, each run of a brief counted on its own."""
    numbered = [str(n) for n in range(1, len(rl.QUESTIONS) + 1)]
    across = str(len(rl.QUESTIONS) + 1)
    pairs: dict[str, list] = {q: [] for q in numbered + ["across", "ship"]}
    unanswered, rows = [], []
    for f in sorted(replies.glob("b*-*.txt")):
        key, run_no = f.stem.rsplit("-", 1)
        if key not in index:
            continue
        ids, shown = index[key]["shots"], index[key]["names"]
        answers = parse(f.read_text(encoding="utf-8"), ids, shown)
        for sid in ids:
            said, mine = answers.get(sid, {}), labels.get(sid, {})
            rows.append({"shot": sid, "reply": f.name, "judge": said, "person": mine})
            if not all(q in said for q in numbered):
                unanswered.append(f"{f.name}: {sid}")
            for q in numbered:
                if q in said and q in mine:
                    pairs[q].append((mine[q], said[q]))
            if "ship" in mine and all(q in said for q in numbered):
                pairs["ship"].append((not mine["ship"], any(said[q] for q in numbered)))
        mine = labels.get(f"across:{index[key]['brief']}", {})
        said = [a[across] for a in answers.values() if across in a]
        if len(ids) > 1 and "across" in mine and said:
            pairs["across"].append((mine["across"], any(said)))
    own = [(not m["ship"], any(m[q] for q in numbered)) for sid, m in labels.items()
           if not sid.startswith("across:") and "ship" in m and all(q in m for q in numbered)]
    return {"questions": {q: agreement(p) for q, p in pairs.items()}, "own": agreement(own),
            "unanswered": unanswered, "rows": rows}


def print_score(result: dict, wording: dict[str, str]) -> None:
    def line(key: str, a: dict) -> str:
        rate = f"{a['agree'] / a['n']:.0%}" if a["n"] else "-"
        base = f"{a['always_no'] / a['n']:.0%}" if a["n"] else "-"
        return (f"  {key:>6}: {a['agree']}/{a['n']} agree ({rate}; always no {base}), person yes {a['person_yes']}, "
                f"judge yes {a['judge_yes']}, missed {a['missed']}, extra {a['extra']}")
    for key, a in result["questions"].items():
        said = "any yes vs would not ship" if key == "ship" else wording.get(key, "")[:70]
        print(f"{line(key, a)}  {said}")
    print(f"{line('own', result['own'])}  the person's own answers: any yes vs would not ship")
    if result["unanswered"]:
        print(f"  unanswered: {len(result['unanswered'])}: {', '.join(result['unanswered'][:8])}")


def main() -> int:
    c3.utf8_output()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("set", type=Path, metavar="SET.json", help="the set of evals/label_look.py")
    ap.add_argument("--briefs", type=Path, required=True, metavar="FOLDER",
                    help="the folder of the briefs, written from the set every time")
    ap.add_argument("--model", help="run `claude -p` as the judge with this model")
    ap.add_argument("--out", type=Path, metavar="REPLIES", help="the folder for the replies of --model")
    ap.add_argument("--runs", type=int, default=1, help="runs per brief (default 1)")
    ap.add_argument("--jobs", type=int, default=4, help="runs at a time (default 4)")
    ap.add_argument("--timeout", type=int, default=300, help="seconds a run may take (default 300)")
    ap.add_argument("--client", default="claude", help="the client's command (default: claude)")
    ap.add_argument("--score", type=Path, metavar="REPLIES", help="score the replies in REPLIES")
    ap.add_argument("--labels", type=Path, help="the person's answers (default: labels.json beside SET.json)")
    args = ap.parse_args()
    try:
        shots = ll.load_set(args.set)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2
    index = prepare(shots, args.briefs)
    print(f"{len(index)} briefs in {args.briefs}, each a folder with its brief.md")
    if args.score:
        path = args.labels or args.set.parent / "labels.json"
        try:
            kept = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"{path}: no labels to score against ({e}); label the set with evals/label_look.py first",
                  file=sys.stderr)
            return 2
        changed = [k for k, q in ll.questions().items() if kept.get("questions", {}).get(k, q) != q]
        if changed:
            print(f"warning: questions {', '.join(changed)} read differently now than when they were labelled")
        result = score(args.score, index, kept.get("labels", {}))
        print(f"agreement of the replies in {args.score} with {path}:")
        print_score(result, kept.get("questions", {}))
        (args.score / "score.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
        return 0
    if args.model:
        if not args.out:
            print("pass --out REPLIES with --model", file=sys.stderr)
            return 2
        if not shutil.which(args.client.split()[0]):
            print(f"{args.client} is not on PATH; install Claude Code or pass --client", file=sys.stderr)
            return 2
        return run(args, index)
    print(f"give each judge one brief.md as its whole task and save its reply as <REPLIES>/<b01>-<run>.txt; "
          f"then score with --score <REPLIES>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
