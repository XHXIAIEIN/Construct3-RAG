#!/usr/bin/env python3
"""Lookup quality evaluation — fixed queries with expected results.

Run after any change to lookup scoring/filtering/synonyms to check for regressions.

Usage:
    python tests/eval_lookup.py
    python tests/eval_lookup.py -v          # verbose: show all matches
    python tests/eval_lookup.py -k collision # filter by keyword
"""
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class Case:
    query: str
    expect_plugin: str = ""          # expected plugin_id
    expect_intent: str = ""          # ace_list | ace_search | ...
    expect_ids: list[str] = field(default_factory=list)    # ACE IDs that MUST appear
    reject_ids: list[str] = field(default_factory=list)    # ACE IDs that must NOT appear
    expect_min: int = 0              # minimum match count
    expect_miss: bool = False        # True = should return None (fall through)


CASES = [
    # === Bare plugin names ===
    Case("Sprite", expect_plugin="sprite", expect_intent="ace_list", expect_min=10),
    Case("Platform", expect_plugin="platform", expect_intent="ace_list", expect_min=5),
    Case("Array", expect_plugin="arr", expect_intent="ace_list", expect_min=3),
    Case("Keyboard", expect_plugin="keyboard", expect_intent="ace_list", expect_min=1),

    # === Chinese keyword search ===
    Case("Sprite 碰撞检测", expect_plugin="sprite",
         expect_ids=["on-collision-with-another-object", "is-overlapping-another-object"],
         reject_ids=["is-animation-playing", "is-visible"]),

    Case("Sprite 动画", expect_plugin="sprite",
         expect_ids=["set-animation", "stop-animation", "start-animation"]),

    Case("Platform 跳跃", expect_plugin="platform",
         expect_ids=["is-jumping"]),

    Case("Array 排序", expect_plugin="arr",
         expect_ids=["sort2"]),

    # === English keyword search ===
    Case("Sprite collision", expect_plugin="sprite",
         expect_ids=["on-collision-with-another-object"]),

    Case("Sprite animation", expect_plugin="sprite",
         expect_ids=["set-animation"]),

    Case("Platform jump", expect_plugin="platform",
         expect_ids=["is-jumping"]),

    # === Mixed CJK/ASCII boundary ===
    Case("Sprite字体", expect_miss=True),  # Sprite has no font ACEs → should miss

    Case("Sprite碰撞", expect_plugin="sprite",
         expect_ids=["on-collision-with-another-object"]),

    # === Should fall through (not lookup) ===
    Case("如何制作一个平台跳跃游戏", expect_miss=True),
    Case("事件表和脚本的区别", expect_miss=True),

    # === Translation ===
    Case("翻译 Destroy", expect_intent="term_translate"),

    # === Properties (TODO: "属性" keyword not routed to prop_list) ===
    # Case("Platform 属性", expect_plugin="platform", expect_intent="prop_list"),

    # === Synonym expansion ===
    Case("Sprite 重叠", expect_plugin="sprite",
         expect_ids=["is-overlapping-another-object"]),  # 重叠 via synonym of 碰撞

    # === Category expansion ===
    Case("Sprite 碰撞", expect_plugin="sprite",
         expect_ids=["collisions-enabled", "on-collision-with-another-object",
                      "is-overlapping-another-object"]),

    # === Scripting API ===
    Case("callFunction", expect_intent="script_api",
         expect_ids=["callFunction"], expect_min=1),

    Case("setAnimation", expect_intent="script_api",
         expect_ids=["setAnimation"], expect_min=1),

    Case("simulateControl", expect_intent="script_api",
         expect_ids=["simulateControl"], expect_min=1),

    # === Ambiguous plugin names (should NOT match) ===
    Case("custom action", expect_miss=True),
]


def run_eval(verbose: bool = False, keyword: str = ""):
    from tests.test_lookup import make_engine

    engine = make_engine()

    passed = 0
    failed = 0
    total = 0

    for case in CASES:
        if keyword and keyword.lower() not in case.query.lower():
            continue
        total += 1
        t0 = time.time()
        resp = engine.try_lookup(case.query)
        ms = (time.time() - t0) * 1000

        errors = []

        if case.expect_miss:
            if resp is not None:
                errors.append(f"expected miss, got {resp.intent.intent_type}")
        else:
            if resp is None:
                errors.append("expected hit, got None")
            else:
                if case.expect_plugin and resp.intent.plugin_id != case.expect_plugin:
                    errors.append(f"plugin: {resp.intent.plugin_id} != {case.expect_plugin}")

                if case.expect_intent and resp.intent.intent_type != case.expect_intent:
                    errors.append(f"intent: {resp.intent.intent_type} != {case.expect_intent}")

                match_ids = {m.ace_id for m in resp.matches}

                for eid in case.expect_ids:
                    if eid not in match_ids:
                        errors.append(f"missing: {eid}")

                for rid in case.reject_ids:
                    if rid in match_ids:
                        errors.append(f"unwanted: {rid}")

                if case.expect_min and len(resp.matches) < case.expect_min:
                    errors.append(f"count: {len(resp.matches)} < {case.expect_min}")

        status = "PASS" if not errors else "FAIL"
        if status == "PASS":
            passed += 1
        else:
            failed += 1

        # Print
        if errors or verbose:
            mark = "✓" if not errors else "✗"
            count = len(resp.matches) if resp else 0
            print(f"  {mark} {case.query:30s} → {count:2d} matches  {ms:5.1f}ms", end="")
            if errors:
                print(f"  !! {'; '.join(errors)}")
            else:
                print()

            if verbose and resp:
                for m in resp.matches[:5]:
                    print(f"      {m.ace_type}/{m.ace_id} [{m.category}]")
                if len(resp.matches) > 5:
                    print(f"      ... +{len(resp.matches) - 5} more")

    print(f"\n{'=' * 50}")
    print(f"  {passed}/{total} passed", end="")
    if failed:
        print(f", {failed} FAILED")
    else:
        print(" — all good")
    print(f"{'=' * 50}")

    return failed == 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-k", "--keyword", type=str, default="")
    args = parser.parse_args()

    ok = run_eval(verbose=args.verbose, keyword=args.keyword)
    sys.exit(0 if ok else 1)
