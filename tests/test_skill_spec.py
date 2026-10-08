"""The construct3-agent-plugin skill as the Agent Skills format defines it, and the trigger evaluation of its
description against a stand-in for the client."""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.skill_helpers import REPO, SKILL, run, install, new_project

SKILL_MD = SKILL / "SKILL.md"


# --- the skill as the Agent Skills format defines it (https://agentskills.io/specification) -----
def frontmatter() -> dict[str, str]:
    text = SKILL_MD.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    return dict(re.findall(r"^([a-z-]+): (.+)$", text.split("---\n")[1], re.M))


def skill_docs() -> list[tuple[str, str]]:
    """SKILL.md and the references, each file name with its text."""
    return [(doc.name, doc.read_text(encoding="utf-8"))
            for doc in [SKILL_MD, *(SKILL / "references").glob("*.md")]]


def test_skill_name_and_description_meet_the_specification():
    fields = frontmatter()
    assert fields["name"] == SKILL.name
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fields["name"]) and len(fields["name"]) <= 64
    assert 0 < len(fields["description"]) <= 1024
    assert len(fields["compatibility"]) <= 500
    # a plain scalar ends at ": " or " #"; a client with a strict YAML parser would drop the skill
    assert not re.search(r": | #", fields["description"] + fields["compatibility"])


def test_skill_body_stays_within_what_is_loaded_on_activation():
    assert len(SKILL_MD.read_text(encoding="utf-8").splitlines()) < 500


def test_skill_md_reads_under_any_locale_codec():
    """skills-ref and plain clients read SKILL.md without naming an encoding; under cp936 a UTF-8 sign does not decode."""
    SKILL_MD.read_bytes().decode("ascii")


def test_every_file_the_skill_names_is_in_it():
    for name, text in skill_docs():
        # a path of the clone, Construct3-RAG/prompts/references/..., is not one of the skill's own
        for rel in set(re.findall(r"(?<![\w/])((?:scripts|references|assets)/[\w.-]+\.\w+)", text)):
            assert (SKILL / rel).is_file(), f"{name} names {rel}"


def test_every_file_of_the_clone_the_skill_names_exists():
    """A copy of the skill reaches these through the project's Construct3-RAG line; a rename here breaks them in silence."""
    for name, text in skill_docs():
        for rel in set(re.findall(r"Construct3-RAG/([\w./-]+\.\w+)", text)):
            assert (REPO / rel).is_file(), f"{name} names Construct3-RAG/{rel}"


OTHER_PROGRAMS = {"--mute-audio", "--user-data-dir"}     # the browser's, where the skill says how one is started


def test_every_flag_the_skill_names_is_one_its_script_takes(tmp_path):
    """A flag renamed in a script and left in SKILL.md or a reference ends the agent's run in a usage error.
    A flag after a script's name on a line is that script's; one with no script before it, any script's."""
    takes: dict[str, set[str]] = {}
    for script in sorted((SKILL / "scripts").glob("*.py")):
        if script.stem != "c3project":
            code, out = run(tmp_path, script, "--help")
            assert code == 0, out
            takes[script.name] = set(re.findall(r"^\s+(?:-\w(?: \S+)?, )?(--[a-z][\w-]*)", out, re.M))
    any_script = set().union(*takes.values())
    for name, text in skill_docs():
        for line in text.splitlines():
            script = None
            for m in re.finditer(r"\b(\w+\.py)\b|(?<![\w-])(--[a-z][\w-]*)", line):
                if m.group(1):
                    script = m.group(1) if m.group(1) in takes else None
                elif m.group(2) not in OTHER_PROGRAMS:
                    assert m.group(2) in takes.get(script, any_script), f"{name}: {script or 'no script'} takes no {m.group(2)}: {line.strip()}"


# --- the trigger evaluation of the description, against a stand-in for the client -------------
FAKE_CLIENT = '''
import json, pathlib, sys, time
query = sys.argv[sys.argv.index("-p") + 1]
def say(event): print(json.dumps(event), flush=True)
def tool(name, id="t", **given):
    say({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": id, "name": name, "input": given}]}})
def result(id, error=False):
    say({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": id, "is_error": error,
                                                  "content": "File does not exist." if error else "loaded"}]}})
pathlib.Path("written-by-a-run.txt").write_text(query)     # what a run writes stays in its own copy
if "signed out" in query:
    say({"type": "result", "is_error": True, "result": "Failed to authenticate: OAuth session expired"})
elif "silent" in query:
    print("not json")
elif "event sheet" in query:
    tool("Glob", id="g", pattern="**/*.json")
    tool("Skill", id="s", skill="construct3:construct3-agent-plugin")
    result("s")
elif "reads it" in query:
    tool("Read", id="r", file_path="C:\\\\game\\\\.claude\\\\skills\\\\construct3-agent-plugin\\\\SKILL.md")
    result("r")
elif "missing" in query:
    tool("Read", id="r", file_path="C:/game/.claude/skills/construct3-agent-plugin/SKILL.md")
    result("r", error=True)
elif "another skill" in query:
    tool("Read", id="r", file_path="C:/game/.claude/skills/my-construct3-agent-plugin/SKILL.md")
    result("r")
    say({"type": "result", "is_error": False, "result": "done"})
elif "slow" in query:
    tool("Bash", command="ls")
    sys.stderr.write("still thinking")
    sys.stderr.flush()
    time.sleep(30)
elif "stops" in query:
    tool("Bash", command="ls")
    sys.stderr.write("crashed")
elif "orphan" in query:     # a child that holds a file of the copy open and outlives the timeout
    import os, subprocess
    child = "import os, pathlib, time; f = open('held.txt', 'w'); time.sleep(60)"
    pid = subprocess.Popen([sys.executable, "-c", child]).pid
    pathlib.Path(os.environ["CHILD_PIDS"], str(pid)).touch()
    tool("Bash", command="ls")
    time.sleep(60)
else:
    tool("Bash", command="ls")
    say({"type": "result", "is_error": False, "result": "done"})
'''


def trigger_eval(tmp_path: Path, queries: list[dict], *extra: str) -> tuple[int, str, Path]:
    root = new_project(tmp_path / "game")
    code, out = install(root, "--into", ".claude/skills", "--no-block")
    assert code == 0, out
    client = tmp_path / "client.py"
    client.write_text(FAKE_CLIENT, encoding="utf-8")
    (tmp_path / "queries.json").write_text(json.dumps(queries), encoding="utf-8")
    report = tmp_path / "report.json"
    code, out = run(tmp_path, SKILL / "evals" / "run_trigger_eval.py", "queries.json", "--project", str(root),
                    "--client", f"{Path(sys.executable).as_posix()} {client.as_posix()}",
                    "--runs", "2", "--output", str(report), *extra)
    assert not (root / "written-by-a-run.txt").exists(), "a run wrote into the project the others read"
    return code, out, report


def test_trigger_eval_counts_a_skill_call_and_a_read_of_skill_md(tmp_path):
    code, out, report = trigger_eval(tmp_path, [
        {"query": "fix my event sheet", "should_trigger": True},
        {"query": "the agent reads it", "should_trigger": True},
        {"query": "zip the folder", "should_trigger": False},
        {"query": "zip the folder, which should have triggered", "should_trigger": True},
        {"query": "read another skill", "should_trigger": False}])
    assert code == 1, out
    results = json.loads(report.read_text(encoding="utf-8"))
    assert [r["trigger_rate"] for r in results["results"]] == [1.0, 1.0, 0.0, 0.0, 0.0]
    assert [r["pass"] for r in results["results"]] == [True, True, True, False, True] and results["passed"] == 4


def test_trigger_eval_leaves_a_run_without_an_answer_out_of_the_rate(tmp_path):
    """A read of SKILL.md that failed, a run stopped by --timeout after it spoke, and a client that stopped
    without a result have neither triggered nor declined (the audit of 2026-10-07 counted the first as
    triggered and the second as not): they are counted apart, with the client's stderr, and a query
    with no other run does not pass."""
    code, out, report = trigger_eval(tmp_path, [
        {"query": "the file is missing", "should_trigger": True},
        {"query": "a slow one", "should_trigger": False},
        {"query": "the client stops", "should_trigger": False}], "--timeout", "3")
    assert code == 1, out
    results = json.loads(report.read_text(encoding="utf-8"))["results"]
    assert [r["ends"] for r in results] == [{"load failed": 2}, {"timed out": 2}, {"client stopped": 2}]
    assert [(r["answered"], r["trigger_rate"], r["pass"]) for r in results] == [(0, None, False)] * 3
    assert results[1]["stderr"] == ["still thinking"] * 2 and results[2]["stderr"] == ["crashed"] * 2


def running(pid: int) -> bool:
    if sys.platform == "win32":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
                             timeout=60).stdout
        return str(pid) in out.split()
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def test_trigger_eval_stops_a_timed_out_run_with_its_children(tmp_path, monkeypatch):
    """A timeout ends the client and every process it started: a child left running holds the run's copy
    and its output pipe, so the run would wait on it and the copy would stay behind in the temp folder."""
    pids, temp = tmp_path / "pids", tmp_path / "temp"
    pids.mkdir()
    temp.mkdir()
    monkeypatch.setenv("CHILD_PIDS", str(pids))
    for name in ("TEMP", "TMP", "TMPDIR"):
        monkeypatch.setenv(name, str(temp))
    started = time.monotonic()
    try:
        code, out, report = trigger_eval(tmp_path, [{"query": "an orphan", "should_trigger": False}], "--timeout", "3")
        took = time.monotonic() - started
        assert [r["ends"] for r in json.loads(report.read_text(encoding="utf-8"))["results"]] == [{"timed out": 2}]
        assert [p.name for p in pids.iterdir() if running(int(p.name))] == []
        assert list(temp.glob("trigger-*")) == [], out
        assert took < 40, f"{took:.0f} s: the run waited for the child"
    finally:
        for p in pids.iterdir():
            if running(int(p.name)):
                subprocess.run(["taskkill", "/F", "/PID", p.name] if sys.platform == "win32" else
                               ["kill", "-9", p.name], capture_output=True, timeout=60)


@pytest.mark.parametrize("query, said", [("signed out", "Failed to authenticate"), ("silent", "no assistant or result event")])
def test_trigger_eval_writes_nothing_when_the_client_cannot_answer(tmp_path, query, said):
    """A client that is signed out has not declined to trigger: no rate of 0 is recorded for it."""
    code, out, report = trigger_eval(tmp_path, [{"query": query, "should_trigger": True}])
    assert code == 2 and "no result written" in out and said in out
    assert not report.exists()


@pytest.mark.parametrize("name, given, error, loaded", [
    ("Skill", {"skill": "construct3-agent-plugin"}, False, True),
    ("Skill", {"skill": "construct3:construct3-agent-plugin"}, False, True),
    ("Read", {"file_path": "C:\\game\\.claude\\skills\\construct3-agent-plugin\\SKILL.md"}, False, True),
    ("Read", {"file_path": "/game/.claude/skills/construct3-agent-plugin/SKILL.md"}, True, False),   # not there
    ("Read", {"file_path": "/game/.claude/skills/unrelated/SKILL.md"}, False, False),
    ("Skill", {"skill": "pdf"}, False, False),
])
def test_trace_counts_a_read_of_this_skill_that_came_back(tmp_path, name, given, error, loaded):
    """read_skill_md of trace.json is the trigger of run_trigger_eval.py: this skill's Skill call or SKILL.md,
    with a result that is no error (the audit of 2026-10-07 found the Skill call missed and another skill's
    SKILL.md counted)."""
    transcript = tmp_path / "agent.jsonl"
    transcript.write_text("\n".join(json.dumps(e) for e in [
        {"message": {"content": [{"type": "tool_use", "id": "t", "name": name, "input": given}]}},
        {"message": {"content": [{"type": "tool_result", "tool_use_id": "t", "is_error": error, "content": "text"}]}},
    ]), encoding="utf-8")
    code, out = run(tmp_path, SKILL / "evals" / "trace.py", str(transcript), "--out", str(tmp_path))
    assert code == 0, out
    assert json.loads((tmp_path / "trace.json").read_text(encoding="utf-8"))["read_skill_md"] is loaded


def test_trace_lists_writes_outside_the_run_folder(tmp_path):
    """A run that writes outside its folder changed something another run or the clone reads; trace.json
    names each such write, and a read outside is listed apart. A relative path and a variable in shell
    text are not resolved: the list is a floor."""
    run_dir = tmp_path / "case" / "with_skill"
    (run_dir / "project").mkdir(parents=True)
    elsewhere = (tmp_path / "clone" / "skills" / "notes.md").as_posix()
    inside = (run_dir / "project" / "eventSheets" / "Game.json").as_posix()
    calls = [
        ("Write", {"file_path": elsewhere, "content": "x"}),
        ("Edit", {"file_path": inside, "old_string": "a", "new_string": "b"}),
        ("Bash", {"command": f'python check.py > "{tmp_path.as_posix()}/scratch/out.txt" 2>&1'}),
        ("PowerShell", {"command": f"Copy-Item {inside} {tmp_path / 'clone' / 'Game.json'}"}),
        ("Bash", {"command": f"cat {tmp_path.as_posix()}/clone/data/c3-schemas/_index.json"}),
        ("Read", {"file_path": f"{tmp_path.as_posix()}/clone/AGENTS.md"}),
    ]
    transcript = tmp_path / "agent.jsonl"
    transcript.write_text("\n".join(json.dumps({"message": {"content": [
        {"type": "tool_use", "id": f"t{n}", "name": name, "input": given}]}}) for n, (name, given) in enumerate(calls)),
        encoding="utf-8")
    code, out = run(tmp_path, SKILL / "evals" / "trace.py", str(transcript), "--out", str(run_dir))
    assert code == 0, out
    trace = json.loads((run_dir / "trace.json").read_text(encoding="utf-8"))
    assert [(w["tool"], Path(w["path"])) for w in trace["outside"]] == [
        ("Write", Path(elsewhere)), ("Bash", tmp_path / "scratch" / "out.txt"),
        ("PowerShell", tmp_path / "clone" / "Game.json")]
    assert [Path(r["path"]) for r in trace["outside_reads"]] == [
        tmp_path / "clone" / "data" / "c3-schemas" / "_index.json", tmp_path / "clone" / "AGENTS.md"]
    assert "3 writes outside" in out, out
