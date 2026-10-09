"""The within-task permutation test of one column between two arms of an iteration.

    python evals/compare.py BENCHMARK.json METRIC [--arms with_skill old_skill] [--direction up|down] [--cases CASE ...]

The statistic is the sum over the cases of the arm's values less the other
arm's. Inside each case the runs of both arms are reassigned to the arms in
every way that keeps each arm's count, so a case with a harder fixture or a
slower day does not stand in for the change; the one-sided p is the share of
reassignments whose statistic is at least the observed one, in the direction
given (up: the arm is expected higher, down: lower). The test is exact up to
200 000 reassignments and sampled with a fixed seed above that, where p is
(hits + 1) / (samples + 1). A case that holds runs of one arm only is left
out, because it cannot be reassigned. grade.py runs the same test for the
verdict of an iteration's decision.json.

exit codes: 0 compared, 1 no case holds runs of both arms with the column
"""
import argparse
import itertools
import json
import math
import random
import sys
from pathlib import Path

EXACT_UP_TO = 200_000
SEED = 0


def permutation_test(by_task: dict[str, list[tuple[str, float]]], arm: str, direction: str = "up",
                     exact_up_to: int = EXACT_UP_TO) -> dict:
    """by_task maps a case to its runs as (arm, value). Returns the observed statistic (the arm's sum less the
    other arm's, over the cases), the one-sided p in the direction, the reassignments counted and whether all
    of them were."""
    sign = 1 if direction == "up" else -1
    tasks = {t: lst for t, lst in by_task.items() if {a == arm for a, _ in lst} == {True, False}}
    if not tasks:
        raise ValueError("no case holds runs of both arms")
    observed = sum(v if a == arm else -v for lst in tasks.values() for a, v in lst)
    counts = [(len(lst), sum(1 for a, _ in lst if a == arm)) for lst in tasks.values()]
    total = math.prod(math.comb(n, k) for n, k in counts)
    values = [[v for _, v in lst] for lst in tasks.values()]

    def statistic(chosen: tuple[tuple[int, ...], ...]) -> float:
        return sign * sum(sum(vs[i] for i in c) - sum(vs[i] for i in range(len(vs)) if i not in c)
                          for vs, c in zip(values, chosen))

    target = sign * observed - 1e-9
    if total <= exact_up_to:
        combos = [list(itertools.combinations(range(n), k)) for n, k in counts]
        hits = sum(statistic(chosen) >= target for chosen in itertools.product(*combos))
        return {"observed": observed, "p": hits / total, "permutations": total, "exact": True}
    rng = random.Random(SEED)
    hits = sum(statistic(tuple(tuple(sorted(rng.sample(range(n), k))) for n, k in counts)) >= target
               for _ in range(exact_up_to))
    return {"observed": observed, "p": (hits + 1) / (exact_up_to + 1), "permutations": exact_up_to, "exact": False}


def runs_of(benchmark: dict, metric: str, arms: list[str], cases: list[str] | None = None) -> dict:
    """The (arm, value) runs of each case in a benchmark.json, for the cases and arms asked for."""
    by_case = benchmark.get("by_case", {})
    return {case: [(arm, r[metric]) for arm in arms for r in by_case.get(case, {}).get(arm, {}).get("runs", [])
                   if r.get(metric) is not None]
            for case in (cases or sorted(by_case))}


def said(test: dict, metric: str, arms: list[str], direction: str, cases: int) -> str:
    return (f"{metric} {direction}: {arms[0]} - {arms[1]} = {test['observed']:+g} over {cases} case"
            f"{'' if cases == 1 else 's'}, one-sided p = {test['p']:.3f} "
            f"({'exact' if test['exact'] else 'sampled'}, {test['permutations']} reassignments)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("benchmark", type=Path, metavar="BENCHMARK.json")
    ap.add_argument("metric", metavar="METRIC", help="a column of the runs, such as chain_depth or lost_calls")
    ap.add_argument("--arms", nargs=2, default=["with_skill", "old_skill"], metavar=("ARM", "OTHER"))
    ap.add_argument("--direction", choices=("up", "down"), default="up",
                    help="where ARM is expected against OTHER (default: up)")
    ap.add_argument("--cases", nargs="+", metavar="CASE", help="the cases to compare (default: every case)")
    args = ap.parse_args()
    benchmark = json.loads(args.benchmark.read_text(encoding="utf-8"))
    by_task = runs_of(benchmark, args.metric, args.arms, args.cases)
    try:
        test = permutation_test(by_task, args.arms[0], args.direction)
    except ValueError as e:
        print(f"{e}: {args.metric} between {args.arms[0]} and {args.arms[1]} in {args.benchmark}", file=sys.stderr)
        return 1
    both = sum(1 for lst in by_task.values() if {a == args.arms[0] for a, _ in lst} == {True, False})
    print(said(test, args.metric, args.arms, args.direction, both))
    return 0


if __name__ == "__main__":
    sys.exit(main())
