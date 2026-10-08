"""Label a set of screenshots with the questions of scripts/review_look.py through agents: labellers
answer each screenshot, an adjudicator settles where they differ, and the result is the labels that
evals/judge_look.py scores a judge against.

    python evals/label_look.py SET.json --briefs FOLDER
    python evals/label_look.py SET.json --briefs FOLDER --merge REPLIES [REPLIES ...] [--labels LABELS.json]
    python evals/label_look.py SET.json --briefs FOLDER --merge REPLIES ... --verdicts VERDICTS [--labels ...]

SET.json lists the screenshots, each path relative to the folder of SET.json:

    {"shots": [{"id": "g1-game", "file": "shots/g1/Game.png", "brief": "g1", "layout": "Game"},
               {"id": "g1-moved", "file": "shots/g1-moved/Game.png", "brief": "g1-moved",
                "layout": "Game", "broken": "the score moved over the level number"}]}

id names a screenshot in the labels. brief groups the screenshots that one brief of
review_look.py holds, the screenshots of one run, and layout is the name the brief gives each.
Any other key, such as what was broken on purpose, is for the reader of the set and reaches no
agent.

--briefs writes FOLDER/s01, s02 and on, one per screenshot, numbered in an order shuffled by its id:
a copy of the screenshot under a neutral name and a brief.md for a labeller. A labeller answers each
question of review_look.QUESTIONS, and whether the screen would ship, with a reason for every
answer, a no included. Give each brief to two labellers or more that do not see each other's
replies, a sub-agent of a strong model each, and save each reply as REPLIES/<s01>-1.txt, one
REPLIES folder per labeller.

--merge reads every labeller's replies. Where they all agree, that is the label. Where they differ,
it writes FOLDER/adjudicate/<s01>/brief.md: the screenshot, the question and each labeller's answer
with its reason under a letter, in an order shuffled per question. Give each to an adjudicator, a
sub-agent of a strong model, and save its reply as VERDICTS/<s01>-1.txt; then merge again with
--verdicts. The adjudicator sees the labellers' answers only, never a judge's, so the labels stay
apart from what they score. The labels go to LABELS.json (default: labels.json beside SET.json)
once no dispute is left open, with the wording of every question.

Exit codes: 0 done, 1 replies or verdicts missing (the output says which), 2 the set could not be read.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import c3project as c3              # noqa: E402
import review_look as rl            # noqa: E402

SHIP = "Would you ship this screen as it looks?"
# A line of a labeller's or an adjudicator's reply: the question's key, the answer and the reason.
LINE = re.compile(r"^\W*(?:q(?:uestion)?\s*)?(?P<q>\d+|ship)\s*[:.)\-][\s*]*(?P<a>yes|no)\b\W*(?P<why>.*)$", re.I)
GUIDE = ("Answer yes only for what a player would see as a mistake: art layered on purpose is none, such as a "
         "character in front of the ground or scenery that runs past the edge of the screen. If the picture "
         "does not show it, answer no.")


def questions() -> dict[str, str]:
    """Every question by its key: the numbered ones of review_look.py, ship and across."""
    return {**{str(n): q for n, q in enumerate(rl.QUESTIONS, 1)}, "ship": SHIP, "across": rl.ACROSS}


def asked() -> list[str]:
    """The keys a labeller answers for each screenshot."""
    return [str(n) for n in range(1, len(rl.QUESTIONS) + 1)] + ["ship"]


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


def shuffled(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def labeller_brief(shot: Path) -> str:
    lines = ["# Label a screenshot", "",
             "You label screenshots of games for a test of an automatic reviewer. Your answers are the reference "
             "it is scored against, so look at every part of the picture before you answer.", "",
             f"Open the screenshot with your image tool: {shot}", "",
             f"Answer every question yes or no, with the reason for each answer, a no included. {GUIDE}", ""]
    lines += [f"{n}. {q}" for n, q in enumerate(rl.QUESTIONS, 1)]
    lines += [f"ship. {SHIP}", "",
              "Reply with one line per question and nothing else. The form, not the content:", "", "```",
              "1: no - <why>", "2: yes - <where on the screenshot>: <what is wrong>", "...",
              "ship: yes - <why>", "```", ""]
    return "\n".join(lines)


def prepare(shots: list[dict], folder: Path) -> dict[str, str]:
    """Writes a folder per screenshot with its copy and the labeller's brief, and index.json; returns the index."""
    folder = folder.resolve()
    index = {}
    for n, s in enumerate(sorted(shots, key=lambda s: shuffled(s["id"])), 1):
        key, place = f"s{n:02d}", folder / f"s{n:02d}"
        if place.exists():
            shutil.rmtree(place)
        place.mkdir(parents=True)
        shot = place / f"{rl.file_name(s['layout'])}.png"
        shutil.copyfile(s["path"], shot)
        (place / "brief.md").write_text(labeller_brief(shot), encoding="utf-8")
        index[key] = s["id"]
    (folder / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    return index


def read_reply(path: Path) -> dict[str, tuple[bool, str]]:
    """A reply's answers by question key, each (yes, reason)."""
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = LINE.match(line.strip())
        if m:
            out[m["q"].lower()] = (m["a"].lower() == "yes", m["why"].strip())
    return out


def adjudicator_brief(shot: Path, disputed: list[tuple[str, list[tuple[bool, str]]]], key: str) -> str:
    lines = ["# Second look", "", f"Open this screenshot of a game with your image tool: {shot}", "",
             "Several labellers answered questions about it and did not agree. Any of them may be wrong. Judge "
             f"only from the picture and the words of each question. {GUIDE}", ""]
    for q, answers in disputed:
        lines += [f"Question {q}: {questions()[q]}", ""]
        order = sorted(range(len(answers)), key=lambda i: shuffled(f"{key}{q}{i}"))
        for letter, i in zip("ABCDEFGH", order):
            yes, why = answers[i]
            lines.append(f"- Labeller {letter}: {'yes' if yes else 'no'}" + (f" - {why}" if why else ""))
        lines.append("")
    lines += ["Reply with one line per question and nothing else. Start the line with the question's key, then "
              "yes or no, then where on the screenshot and why:", "", "```",
              f"{disputed[0][0]}: no - <where, and why>", "```", ""]
    return "\n".join(lines)


def merge(folder: Path, index: dict[str, str], replies: list[Path], verdicts: Path | None) -> tuple[dict, list[str]]:
    """The labels where every labeller agrees or a verdict settles it, and what is still missing; writes an
    adjudicator's brief for each screenshot with a dispute no verdict settles."""
    folder = folder.resolve()
    labels: dict[str, dict] = {}
    missing: list[str] = []
    for key, sid in index.items():
        files = [r / f"{key}-1.txt" for r in replies]
        missing += [f"no reply {f}" for f in files if not f.is_file()]
        if not all(f.is_file() for f in files):
            continue
        got = [read_reply(f) for f in files]
        settled, disputed = {}, []
        for q in asked():
            answers = [g.get(q) for g in got]
            if None in answers:
                missing.append(f"{key} ({sid}): a reply has no answer to {q}")
            elif len({a for a, _ in answers}) == 1:
                settled[q] = answers[0][0]
            else:
                disputed.append((q, answers))
        if disputed:
            given = verdicts / f"{key}-1.txt" if verdicts else None
            verdict = read_reply(given) if given and given.is_file() else {}
            settled.update({q: verdict[q][0] for q, _ in disputed if q in verdict})
            if not all(q in verdict for q, _ in disputed):
                place = folder / "adjudicate" / key
                place.mkdir(parents=True, exist_ok=True)
                shot = next((folder / key).glob("*.png"))
                (place / "brief.md").write_text(adjudicator_brief(shot, disputed, key), encoding="utf-8")
                missing.append(f"verdict for {key} ({sid}): {place / 'brief.md'}")
        labels[sid] = settled
    return labels, missing


def main() -> int:
    c3.utf8_output()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("set", type=Path, metavar="SET.json", help="the screenshots to label, in the form above")
    ap.add_argument("--briefs", type=Path, required=True, metavar="FOLDER",
                    help="the folder of the labellers' briefs, written from the set every time")
    ap.add_argument("--merge", type=Path, nargs="+", metavar="REPLIES", help="one folder of replies per labeller")
    ap.add_argument("--verdicts", type=Path, metavar="VERDICTS", help="the adjudicator's replies")
    ap.add_argument("--labels", type=Path, help="where the labels go (default: labels.json beside SET.json)")
    args = ap.parse_args()
    try:
        shots = load_set(args.set)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2
    index = prepare(shots, args.briefs)
    print(f"{len(index)} labelling briefs in {args.briefs.resolve()}, each a folder with its brief.md")
    if not args.merge:
        print("give each brief.md to two labellers or more, apart, and save each one's reply as "
              "<REPLIES>/<s01>-1.txt; then run again with --merge <REPLIES> ...")
        return 0
    labels, missing = merge(args.briefs, index, args.merge, args.verdicts)
    if missing:
        print(f"{len(missing)} still open:")
        print("\n".join(f"  {m}" for m in missing[:40]))
        print("save each adjudicator's reply as <VERDICTS>/<s01>-1.txt and run again with --verdicts <VERDICTS>")
        return 1
    out = args.labels or args.set.parent / "labels.json"
    out.write_text(json.dumps({"set": args.set.name, "questions": questions(),
                               "labellers": [str(r) for r in args.merge], "labels": labels},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"labels for {len(labels)} screenshots in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
