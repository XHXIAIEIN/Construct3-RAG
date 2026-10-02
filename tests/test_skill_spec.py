"""The construct3-agent-plugin skill as the Agent Skills format defines it, and the trigger evaluation of its
description against a stand-in for the client."""
import json
import re
import sys
from pathlib import Path

import pytest

from tests.skill_helpers import REPO, SKILL, run, install, new_project


# --- the skill as the Agent Skills format defines it (https://agentskills.io/specification) -----
def frontmatter() -> dict[str, str]:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    return dict(re.findall(r"^([a-z-]+): (.+)$", text.split("---\n")[1], re.M))


def test_skill_name_and_description_meet_the_specification():
    fields = frontmatter()
    assert fields["name"] == SKILL.name
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fields["name"]) and len(fields["name"]) <= 64
    assert 0 < len(fields["description"]) <= 1024
    assert len(fields["compatibility"]) <= 500
    # a plain scalar ends at ": " or " #"; a client with a strict YAML parser would drop the skill
    assert not re.search(r": | #", fields["description"] + fields["compatibility"])


def test_skill_body_stays_within_what_is_loaded_on_activation():
    assert len((SKILL / "SKILL.md").read_text(encoding="utf-8").splitlines()) < 500


def test_skill_md_reads_under_any_locale_codec():
    """skills-ref and plain clients read SKILL.md without naming an encoding; under cp936 a UTF-8 sign does not decode."""
    (SKILL / "SKILL.md").read_bytes().decode("ascii")


def test_every_file_the_skill_names_is_in_it():
    for doc in [SKILL / "SKILL.md", *(SKILL / "references").glob("*.md")]:
        # a path of the clone, Construct3-RAG/prompts/references/..., is not one of the skill's own
        for rel in set(re.findall(r"(?<![\w/])((?:scripts|references|assets)/[\w.-]+\.\w+)", doc.read_text(encoding="utf-8"))):
            assert (SKILL / rel).is_file(), f"{doc.name} names {rel}"


def test_every_file_of_the_clone_the_skill_names_exists():
    """A copy of the skill reaches these through the project's Construct3-RAG line; a rename here breaks them in silence."""
    for doc in [SKILL / "SKILL.md", *(SKILL / "references").glob("*.md")]:
        for rel in set(re.findall(r"Construct3-RAG/([\w./-]+\.\w+)", doc.read_text(encoding="utf-8"))):
            assert (REPO / rel).is_file(), f"{doc.name} names Construct3-RAG/{rel}"


# --- the trigger evaluation of the description, against a stand-in for the client -------------
FAKE_CLIENT = '''
import json, sys
query = sys.argv[sys.argv.index("-p") + 1]
def say(event): print(json.dumps(event), flush=True)
def tool(name, **given): say({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": given}]}})
if "signed out" in query:
    say({"type": "result", "is_error": True, "result": "Failed to authenticate: OAuth session expired"})
elif "silent" in query:
    print("not json")
elif "event sheet" in query:
    tool("Glob", pattern="**/*.json")
    tool("Skill", skill="construct3-agent-plugin")
elif "reads it" in query:
    tool("Read", file_path="C:\\\\game\\\\.claude\\\\skills\\\\construct3-agent-plugin\\\\SKILL.md")
else:
    tool("Bash", command="ls")
    say({"type": "result", "is_error": False, "result": "done"})
'''


def trigger_eval(tmp_path: Path, queries: list[dict]) -> tuple[int, str, Path]:
    root = new_project(tmp_path / "game")
    code, out = install(root, "--into", ".claude/skills", "--no-block")
    assert code == 0, out
    (tmp_path / "client.py").write_text(FAKE_CLIENT, encoding="utf-8")
    (tmp_path / "queries.json").write_text(json.dumps(queries), encoding="utf-8")
    report = tmp_path / "report.json"
    code, out = run(tmp_path, SKILL / "evals" / "run_trigger_eval.py", "queries.json", "--project", str(root),
                    "--client", f"{Path(sys.executable).as_posix()} {(tmp_path / 'client.py').as_posix()}",
                    "--runs", "2", "--output", str(report))
    return code, out, report


def test_trigger_eval_counts_a_skill_call_and_a_read_of_skill_md(tmp_path):
    code, out, report = trigger_eval(tmp_path, [
        {"query": "fix my event sheet", "should_trigger": True},
        {"query": "the agent reads it", "should_trigger": True},
        {"query": "zip the folder", "should_trigger": False},
        {"query": "zip the folder, which should have triggered", "should_trigger": True}])
    assert code == 1, out
    results = json.loads(report.read_text(encoding="utf-8"))
    assert [r["trigger_rate"] for r in results["results"]] == [1.0, 1.0, 0.0, 0.0]
    assert [r["pass"] for r in results["results"]] == [True, True, True, False] and results["passed"] == 3


@pytest.mark.parametrize("query, said", [("signed out", "Failed to authenticate"), ("silent", "no assistant or result event")])
def test_trigger_eval_writes_nothing_when_the_client_cannot_answer(tmp_path, query, said):
    """A client that is signed out has not declined to trigger: no rate of 0 is recorded for it."""
    code, out, report = trigger_eval(tmp_path, [{"query": query, "should_trigger": True}])
    assert code == 2 and "no result written" in out and said in out
    assert not report.exists()
