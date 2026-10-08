"""evals/label_look.py and evals/judge_look.py on a set of stand-in screenshots: the order the page asks
in, the labels it keeps, the briefs a judge gets, how a reply is read and how it is scored."""
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
                       "broken": "a note the page never shows"} for sid, brief, layout in entries]}
    (tmp_path / "set.json").write_text(json.dumps(data), encoding="utf-8")
    return tmp_path / "set.json"


def test_the_page_asks_every_screenshot_then_each_brief_of_several(shots: Path) -> None:
    asked = ll.items(ll.load_set(shots))
    assert sorted(i["id"] for i in asked[:4]) == ["g1-map", "g1-menu", "g2-moved", "g3-cut"]
    assert asked[0]["ask"] == [str(n) for n in range(1, len(rl.QUESTIONS) + 1)] + ["ship"]
    assert asked[4:] == [{"id": "across:g1", "shots": ["g1-menu", "g1-map"], "ask": ["across"]}]
    assert [i["id"] for i in ll.items(ll.load_set(shots))] == [i["id"] for i in asked]


def test_a_set_entry_without_its_file_is_named(shots: Path) -> None:
    (shots.parent / "shots" / "g3-cut" / "shot.png").unlink()
    with pytest.raises(SystemExit, match="g3-cut: no file"):
        ll.load_set(shots)


def test_each_answer_is_written_with_the_wording_it_answers(shots: Path, tmp_path: Path) -> None:
    labels = ll.Labels(tmp_path / "labels.json", shots)
    labels.answer("g1-menu", "1", True)
    labels.answer("g1-menu", "ship", False)
    labels.answer("g1-menu", "1", None)
    kept = json.loads((tmp_path / "labels.json").read_text(encoding="utf-8"))
    assert kept["labels"] == {"g1-menu": {"ship": False}}
    assert kept["questions"]["1"] == rl.QUESTIONS[0]
    kept["questions"]["1"] = "an older wording"
    (tmp_path / "labels.json").write_text(json.dumps(kept), encoding="utf-8")
    assert ll.Labels(tmp_path / "labels.json", shots).changed == ["1"]


def test_a_brief_names_no_source_of_its_screenshots(shots: Path, tmp_path: Path) -> None:
    index = jl.prepare(ll.load_set(shots), tmp_path / "briefs")
    assert sorted(v["brief"] for v in index.values()) == ["g1", "g2-moved", "g3-cut"]
    for key, entry in index.items():
        text = (tmp_path / "briefs" / key / "brief.md").read_text(encoding="utf-8")
        assert not any(word in text for word in ("g2-moved", "g3-cut", "g1-m", "never shows"))
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
    assert result["questions"]["2"] == {"n": 3, "agree": 3, "person_yes": 1, "judge_yes": 1, "missed": 0, "extra": 0,
                                        "always_no": 2}
    assert result["questions"]["1"]["missed"] == 1
    assert result["questions"]["ship"]["n"] == 3 and result["questions"]["ship"]["missed"] == 1
    assert result["unanswered"] == [f"{key['g1']}-1.txt: g1-map"]
    assert result["own"] == {"n": 4, "agree": 4, "person_yes": 2, "judge_yes": 2, "missed": 0, "extra": 0,
                             "always_no": 2}
