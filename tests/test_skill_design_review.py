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


def versions(root):
    return {q["id"]: q["input_version"] for q in bundle(root)["questions"]}


def test_unrelated_event_preserves_local_question_and_changes_coverage(tmp_path):
    root = fixture(tmp_path)
    before = versions(root)
    focused = next(q for q in bundle(root)["questions"] if q["location"]["rule"] == "conditions")
    edit(root, "eventSheets/Game.json", lambda s: s["events"][-2]["actions"][0]["parameters"].update(value="2"))
    after = versions(root)
    assert after[focused["id"]] == before[focused["id"]]
    assert any(after[key] != value for key, value in before.items() if key in after)


def test_shared_function_definition_and_caller_change_invalidate(tmp_path):
    root = fixture(tmp_path)
    before = versions(root)
    q = next(q for q in bundle(root)["questions"] if q["location"]["rule"] == "conditions")
    assert any(r["kind"] == "calls_function" and r["to"] == "Update" for r in q["relations"])
    assert all(r["evidence"] in {e["id"] for e in q["evidence"]} for r in q["relations"])
    edit(root, "eventSheets/Shared.json", lambda s: s["events"][0]["children"][0]["actions"][0]["parameters"].update(value="3"))
    assert versions(root)[q["id"]] != before[q["id"]]
    edit(root, "eventSheets/Shared.json", lambda s: s["events"].append(ev([], [{"callFunction": "Update", "parameters": []}])))
    item = next(x for x in bundle(root)["questions"] if x["id"] == q["id"])
    assert len([r for r in item["relations"] if r["kind"] == "calls_function"]) == 2


@pytest.mark.parametrize("dependency", ["global", "object", "family", "layout", "schema", "rules"])
def test_shared_dependencies_invalidate(tmp_path, monkeypatch, dependency):
    root = write(tmp_path, {"Game": [var("Limit"), ev([
        c("compare-eventvar", variable="Limit", comparison=0, value="0"),
        c("compare-x", "Token", comparison=0, value="10"),
        c("compare-y", "Token", comparison=0, value="10"),
        c("compare-width", "Token", comparison=0, value="10")])]}, {"Token": ("Sprite", [])})
    if dependency == "family":
        edit(root, "project.c3proj", lambda s: s.update(families={"items": ["Tokens"], "subfolders": []}))
        (root / "families").mkdir()
        (root / "families/Tokens.json").write_text(json.dumps({"name": "Tokens", "plugin-id": "Sprite", "members": ["Token"]}))
    before = versions(root)
    if dependency == "global":
        edit(root, "eventSheets/Game.json", lambda s: s["events"][0].update(initialValue="4"))
    elif dependency == "object":
        edit(root, "objectTypes/Token.json", lambda s: s.update(behaviorTypes=[{"name": "Tween", "behaviorId": "Tween"}]))
    elif dependency == "family":
        edit(root, "families/Tokens.json", lambda s: s.update(instanceVariables=[{"name": "Capacity", "type": "number"}]))
    elif dependency == "layout":
        edit(root, "layouts/Game.json", lambda s: s.update(viewportWidth=1000))
    elif dependency == "schema":
        original = c3.Project.ace_entry
        monkeypatch.setattr(c3.Project, "ace_entry", lambda p, kind, ace: {**original(p, kind, ace), "description": "Changed constraint"})
    else:
        original = pack.rules
        monkeypatch.setattr(pack, "rules", lambda p: {**original(p), "rule_version": "changed"})
    after = versions(root)
    assert all(after.get(key) != version for key, version in before.items())


def test_resume_and_partial_validation_preserve_saved_batches(tmp_path):
    root = fixture(tmp_path)
    args = ("--rag", str(REPO), "--sheets", "Game", "--prepare", ".tmp/review", "--limit", "1")
    assert run(root, SCRIPT, *args)[0] == 0
    folder = root / ".tmp/review"
    old_batches = {p: p.read_bytes() for p in folder.rglob("batch-*.json")}
    first = json.loads(next(iter(old_batches)).read_text(encoding="utf-8"))["questions"][0]["id"]
    q = next(q for q in bundle(root)["questions"] if q["id"] == first)
    path = root / "answers.json"
    path.write_text(json.dumps([answer(q)]), encoding="utf-8")
    assert run(root, SCRIPT, *args, "--batch", "1", "--answers", str(path))[0] == 0
    assert run(root, SCRIPT, *args, "--resume")[0] == 0
    current = json.loads((folder / "current.json").read_text(encoding="utf-8"))
    assert current["reused"] == [first]
    assert all(p.read_bytes() == data for p, data in old_batches.items())
    assert run(root, SCRIPT, *args, "--resume")[0] == 0
    edit(root, "eventSheets/Shared.json", lambda s: s["events"][0]["children"][0]["actions"][0]["parameters"].update(value="5"))
    assert run(root, SCRIPT, *args, "--resume")[0] == 0
    current = json.loads((folder / "current.json").read_text(encoding="utf-8"))
    assert first not in current["reused"] and current["invalidated"]
    assert all(p.read_bytes() == data for p, data in old_batches.items())


def test_dynamic_dispatch_needs_evidence_and_is_not_reused(tmp_path):
    root = fixture(tmp_path)
    edit(root, "eventSheets/Game.json", lambda s: s["events"][1]["actions"].append(
        {"id": "call-mapped-function", "objectClass": "Functions", "parameters": {"name": "Shared"}}))
    qs = bundle(root)["questions"]
    q = next(q for q in qs if q["location"]["rule"] == "conditions")
    assert any("unresolved" in m for m in q["missing"])
    with pytest.raises(ValueError):
        pack.validate([q], [answer(q)])
    path = root / "answers.json"
    path.write_text(json.dumps([answer(q, "insufficient_evidence") for q in qs]), encoding="utf-8")
    args = ("--rag", str(REPO), "--sheets", "Game", "--prepare", ".tmp/review", "--limit", "0")
    code, said = run(root, SCRIPT, *args, "--answers", str(path))
    assert code == 0, said
    assert run(root, SCRIPT, *args, "--resume")[0] == 0
    current = json.loads((root / ".tmp/review/current.json").read_text(encoding="utf-8"))
    assert current["reused"] == [] and current["batches"]


def test_check_and_prepare_stop_on_failure_and_record_full_log(project):
    assert install(project)[0] == 0
    args = ("--rag", str(REPO), "--check", "--prepare", ".tmp/review", "--limit", "0")
    code, said = run(project, SCRIPT, *args)
    assert code == 0, said
    path = project / ".tmp/review/current.json"
    before = path.read_bytes()
    edit(project, "project.c3proj", lambda p: p.update(viewportWidth=-1))
    code, said = run(project, SCRIPT, *args)
    assert code == 1, said
    log = json.loads((project / ".tmp/review/check.json").read_text(encoding="utf-8"))
    assert log["exit"] == 1 and log["stdout"]
    assert path.read_bytes() == before


def test_comments_without_sids_keep_distinct_evidence_and_invalidate(tmp_path):
    root = fixture(tmp_path)
    edit(root, "eventSheets/Game.json", lambda s: s["events"].extend([
        {"eventType": "comment", "text": "First constraint"},
        {"eventType": "comment", "text": "Second constraint"}]))
    old = bundle(root)
    q = next(q for q in old["questions"] if q["location"]["rule"] == "coverage")
    assert any("First constraint" in e["text"] for e in q["evidence"])
    assert any("Second constraint" in e["text"] for e in q["evidence"])
    edit(root, "eventSheets/Game.json", lambda s: s["events"][-1].update(text="Changed constraint"))
    assert versions(root)[q["id"]] != q["input_version"]


def test_output_cannot_replace_project_sources(tmp_path):
    root = fixture(tmp_path)
    before = (root / "eventSheets/Game.json").read_bytes()
    code, said = run(root, SCRIPT, "--rag", str(REPO), "--prepare", "eventSheets")
    assert code == 2 and "under the game's .tmp/" in said
    assert (root / "eventSheets/Game.json").read_bytes() == before
