"""evals/label_look.py and evals/judge_look.py on a set of stand-in screenshots: the labellers' briefs, how
their replies become labels, the briefs a judge gets, how a reply is read and how it is scored."""
import json
import sys
from pathlib import Path

import pytest

from tests.skill_helpers import SKILL

sys.path.insert(0, str(SKILL / "evals"))
sys.path.insert(0, str(SKILL / "scripts"))
import judge_look as jl  # noqa: E402
import label_look as ll  # noqa: E402
import review_look as rl  # noqa: E402

PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")


@pytest.fixture
def shots(tmp_path: Path) -> Path:
    """A set of four screenshots: two layouts of one game in one brief, and two copies broken on purpose."""
    entries = [("g1-menu", "g1", "Menu"), ("g1-map", "g1", "Map"), ("g2-moved", "g2-moved", "Layout 1"),
               ("g3-cut", "g3-cut", "Game")]
    for sid, brief, layout in entries:
        (tmp_path / "shots" / sid).mkdir(parents=True)
        (tmp_path / "shots" / sid / "shot.png").write_bytes(PNG)
    data = {"shots": [{"id": sid, "file": f"shots/{sid}/shot.png", "brief": brief, "layout": layout,
                       "broken": "a note no agent ever shows"} for sid, brief, layout in entries]}
    (tmp_path / "set.json").write_text(json.dumps(data), encoding="utf-8")
    return tmp_path / "set.json"


def test_each_screenshot_gets_a_labelling_brief_that_names_no_source(shots: Path, tmp_path: Path) -> None:
    index = ll.prepare(ll.load_set(shots), tmp_path / "label")
    assert sorted(index.values()) == ["g1-map", "g1-menu", "g2-moved", "g3-cut"]
    assert index == ll.prepare(ll.load_set(shots), tmp_path / "label")
    for key in index:
        text = (tmp_path / "label" / key / "brief.md").read_text(encoding="utf-8")
        assert not any(word in text for word in ("g2-moved", "g3-cut", "g1-m", "ever shows"))
        assert all(f"{n}. {q}" in text for n, q in enumerate(rl.QUESTIONS, 1)) and f"ship. {ll.SHIP}" in text


def test_a_set_entry_without_its_file_is_named(shots: Path) -> None:
    (shots.parent / "shots" / "g3-cut" / "shot.png").unlink()
    with pytest.raises(SystemExit, match="g3-cut: no file"):
        ll.load_set(shots)


def labeller(folder: Path, key: str, yes: set, ship: bool, why: str = "x") -> None:
    folder.mkdir(parents=True, exist_ok=True)
    lines = [f"{q}: {'yes' if q in yes else 'no'} - {why}" for q in ll.asked()[:-1]]
    lines.append(f"ship: {'yes' if ship else 'no'} - {why}")
    (folder / f"{key}-1.txt").write_text("\n".join(lines), encoding="utf-8")


def test_labellers_agreeing_make_the_label_and_a_dispute_waits_for_a_verdict(shots: Path, tmp_path: Path) -> None:
    briefs = tmp_path / "label"
    index = ll.prepare(ll.load_set(shots), briefs)
    by_id = {sid: key for key, sid in index.items()}
    for key, sid in index.items():
        labeller(tmp_path / "a", key, {"2"} if sid == "g2-moved" else set(), sid.startswith("g1"))
        labeller(tmp_path / "b", key, {"2", "3"} if sid == "g2-moved" else set(), sid.startswith("g1"), "y")
    labels, missing = ll.merge(briefs, index, [tmp_path / "a", tmp_path / "b"], None)
    assert labels["g1-menu"]["ship"] is True and labels["g3-cut"]["1"] is False
    assert labels["g2-moved"]["2"] is True and "3" not in labels["g2-moved"]
    assert missing == [f"verdict for {by_id['g2-moved']} (g2-moved): "
                       f"{(briefs / 'adjudicate' / by_id['g2-moved'] / 'brief.md').resolve()}"]
    text = (briefs / "adjudicate" / by_id["g2-moved"] / "brief.md").read_text(encoding="utf-8")
    assert f"Question 3: {rl.QUESTIONS[2]}" in text and "Question 2" not in text
    assert sorted(line for line in text.splitlines() if line.startswith("- Labeller")) in (
        ["- Labeller A: no - x", "- Labeller B: yes - y"], ["- Labeller A: yes - y", "- Labeller B: no - x"])
    (tmp_path / "v").mkdir()
    (tmp_path / "v" / f"{by_id['g2-moved']}-1.txt").write_text("3: yes - the edge cuts it", encoding="utf-8")
    labels, missing = ll.merge(briefs, index, [tmp_path / "a", tmp_path / "b"], tmp_path / "v")
    assert missing == [] and labels["g2-moved"]["3"] is True


def test_a_missing_reply_is_named(shots: Path, tmp_path: Path) -> None:
    index = ll.prepare(ll.load_set(shots), tmp_path / "label")
    labels, missing = ll.merge(tmp_path / "label", index, [tmp_path / "none"], None)
    assert labels == {} and len(missing) == 4 and all(m.startswith("no reply ") for m in missing)


def test_a_brief_names_no_source_of_its_screenshots(shots: Path, tmp_path: Path) -> None:
    index = jl.prepare(ll.load_set(shots), tmp_path / "briefs")
    assert sorted(v["brief"] for v in index.values()) == ["g1", "g2-moved", "g3-cut"]
    for key, entry in index.items():
        text = (tmp_path / "briefs" / key / "brief.md").read_text(encoding="utf-8")
        assert not any(word in text for word in ("g2-moved", "g3-cut", "g1-m", "ever shows"))
        assert all((tmp_path / "briefs" / key / f"{rl.file_name(n)}.png").is_file() for n in entry["names"])
    several = next(k for k, v in index.items() if v["brief"] == "g1")
    assert rl.ACROSS in (tmp_path / "briefs" / several / "brief.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(("line", "shot", "q", "yes"), [
    ("Map 2: yes - top centre: the title covers a node", "b", "2", True),
    ("Menu 1: no", "a", "1", False),
    ("**Map 3:** no", "b", "3", False),
    ("- Map Q4: **yes** - left edge", "b", "4", True),
])
def test_a_reply_line_is_read_by_screenshot_and_question(line: str, shot: str, q: str, yes: bool) -> None:
    assert jl.parse(line, ["a", "b"], ["Menu", "Map"]) == {shot: {q: yes}}


def test_a_one_screenshot_reply_is_read_whatever_name_it_gives() -> None:
    assert jl.parse("Level 1: yes - x\nLevel 2: no", ["only"], ["Level"]) == {"only": {"1": True, "2": False}}
    assert jl.parse("Layout 1 3: yes - x", ["only"], ["Layout 1"]) == {"only": {"3": True}}


def test_the_score_counts_agreement_misses_and_the_ship_line(shots: Path, tmp_path: Path) -> None:
    index = jl.prepare(ll.load_set(shots), tmp_path / "briefs")
    key = {v["brief"]: k for k, v in index.items()}
    replies = tmp_path / "replies"
    replies.mkdir()
    n = len(rl.QUESTIONS)
    no_rest = lambda name, yes: "\n".join(f"{name} {q}: {'yes - x' if q in yes else 'no'}" for q in range(1, n + 1))
    (replies / f"{key['g2-moved']}-1.txt").write_text(no_rest("Layout 1", {2}), encoding="utf-8")
    (replies / f"{key['g3-cut']}-1.txt").write_text(no_rest("Game", set()), encoding="utf-8")
    (replies / f"{key['g1']}-1.txt").write_text(no_rest("Menu", set()), encoding="utf-8")
    person = lambda yes, ship: {**{str(q): q in yes for q in range(1, n + 1)}, "ship": ship}
    labels = {"g2-moved": person({2}, False), "g3-cut": person({1}, False), "g1-menu": person(set(), True),
              "g1-map": person(set(), True)}
    result = jl.score(replies, index, labels)
    assert result["questions"]["2"] == {"n": 3, "agree": 3, "labels_yes": 1, "judge_yes": 1, "missed": 0, "extra": 0,
                                        "always_no": 2}
    assert result["questions"]["1"]["missed"] == 1
    assert result["questions"]["ship"]["n"] == 3 and result["questions"]["ship"]["missed"] == 1
    assert result["unanswered"] == [f"{key['g1']}-1.txt: g1-map"]
    assert result["own"] == {"n": 4, "agree": 4, "labels_yes": 2, "judge_yes": 2, "missed": 0, "extra": 0,
                             "always_no": 2}
