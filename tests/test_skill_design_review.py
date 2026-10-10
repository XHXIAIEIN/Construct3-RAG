"""Complete review packets, answer rejection and dependency invalidation."""
import copy
import json

import pytest

from tests.skill_helpers import REPO, SKILL, edit, install, run, script_module
from tests.test_skill_review_design import c, ev, function, setv, var, write

c3 = script_module("c3project")
rd = script_module("review_design")
pack = script_module("design_review")
SCRIPT = SKILL / "scripts" / "review_design.py"


def fixture(root):
    return write(root, {"Game": [var("Shared"),
        ev([c("compare-eventvar", variable="Shared", comparison=0, value=str(n)) for n in range(4)],
           [{"callFunction": "Update", "parameters": [], "sid": 9001}]),
        ev([c("on-start-of-layout")]), ev([c("on-end-of-layout")]),
        ev([c("every-tick")], [setv("Unrelated", "1")]), var("Unrelated")],
        "Shared": [function("Update", [ev([], [setv("Shared", "2")])])]}, {})


def bundle(root):
    p = c3.Project(root, REPO, "en-US", c3.Findings())
    d = rd.Design.of(p)
    return pack.packets(p, d, rd.review(d), ["Game"], rd.QUESTIONS)


def answer(q, verdict="pass"):
    e = next(e for e in q["evidence"] if e["source"].startswith("eventSheets/"))
    return {"id": q["id"], "input_version": q["input_version"], "verdict": verdict,
            "evidence": [{"id": e["id"], "quote": e["text"].strip().splitlines()[0]}],
            "reason": "Keep this condition: it tests the existing state.", "suggestions": []}


def test_packet_has_printed_context_called_function_and_schema(tmp_path):
    q = next(q for q in bundle(fixture(tmp_path))["questions"] if q["location"]["rule"] == "conditions")
    assert any("function Update" in e["text"] for e in q["evidence"])
    assert any("global number Shared" in e["text"] for e in q["evidence"])
    assert any(e["source"].startswith("schema/") and '"params"' in e["text"] for e in q["evidence"])
    assert all(t["sid"] is not None for t in q["targets"])
    assert q["missing"] == []


@pytest.mark.parametrize("fault", ["missing", "duplicate", "stale", "evidence", "quote", "scope", "edit", "verdict"])
def test_invalid_answer_preserves_project_and_previous_outputs(tmp_path, fault):
    root = fixture(tmp_path)
    code, said = run(root, SCRIPT, "--rag", str(REPO), "--prepare", ".tmp/review", "--limit", "0")
    assert code == 0, said
    qs = bundle(root)["questions"]
    answers = [answer(q) for q in qs]
    if fault == "missing":
        answers.pop()
    elif fault == "duplicate":
        answers.append(copy.deepcopy(answers[0]))
    elif fault == "stale":
        answers[0]["input_version"] = "old"
    elif fault == "evidence":
        answers[0]["evidence"][0]["id"] = "invented"
    elif fault == "quote":
        answers[0]["evidence"][0]["quote"] = "This is invented evidence"
    elif fault == "scope":
        answers[0]["verdict"] = "needs_change"
        answers[0]["suggestions"] = [{"sheet": "Other", "sid": 999, "text": "Delete this event"}]
    elif fault == "edit":
        answers[0]["plan"] = [{"event": 1, "remove": True}]
    else:
        answers[0]["verdict"] = "yes"
    path = root / "answers.json"
    path.write_text(json.dumps(answers), encoding="utf-8")
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    code, said = run(root, SCRIPT, "--rag", str(REPO), "--prepare", ".tmp/review", "--answers", str(path), "--limit", "0")
    assert code == 2, said
    assert all(p.read_bytes() == raw for p, raw in before.items())
    assert not (root / ".tmp/review/accepted.json").exists()


def test_missing_call_cannot_pass_and_coverage_questions_remain(tmp_path):
    root = fixture(tmp_path)
    edit(root, "eventSheets/Shared.json", lambda s: s.update(events=[]))
    qs = bundle(root)["questions"]
    assert {q["location"]["question"] for q in qs} == set(rd.QUESTIONS)
    q = next(q for q in qs if q["missing"])
    with pytest.raises(ValueError, match="lacks dependencies"):
        pack.validate([q], [answer(q)])
    pack.validate([q], [answer(q, "insufficient_evidence")])


def test_complete_batches_and_installed_entry(tmp_path):
    root = fixture(tmp_path)
    assert install(root)[0] == 0
    script = root / ".agents/skills/construct3-agent-plugin/scripts/review_design.py"
    code, said = run(root, script, "--rag", str(REPO), "--sheets", "Game", "--prepare", ".tmp/review", "--limit", "1")
    assert code == 0, said
    manifest = json.loads((root / ".tmp/review/current.json").read_text(encoding="utf-8"))
    ids = []
    for filename in manifest["batches"]:
        batch = json.loads((root / ".tmp/review" / filename).read_text(encoding="utf-8"))
        ids += [q["id"] for q in batch["questions"]]
        assert all(q["evidence"] for q in batch["questions"])
    assert sorted(ids) == sorted(q["id"] for q in bundle(root)["questions"])
