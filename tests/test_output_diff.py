"""scripts/output_diff.py: the comparison and the masks, without the example clone."""
import json
import subprocess
import sys
from pathlib import Path

from scripts import output_diff as od

REPO = Path(__file__).resolve().parent.parent


def test_mask_replaces_every_spelling_of_a_path(tmp_path):
    rag = tmp_path / "clone"
    game = tmp_path / "side" / "game"
    text = "\n".join([f"python {rag / 'skills'}", f"{rag.as_posix()}/prompts/pitfalls/a.md:3",
                      json.dumps({"path": str(game / 'x')}), f"at {game}"])
    masked = od.mask(text, {rag: "<rag>", game: "<game>", tmp_path / "side": "<tmp>"})
    assert str(tmp_path) not in masked and tmp_path.as_posix() not in masked
    assert masked.splitlines()[1] == "<rag>/prompts/pitfalls/a.md:3"
    assert masked.splitlines()[3] == "at <game>"


def test_first_difference_names_the_line_on_each_side():
    assert od.first_difference("exit 0\na\nb", "exit 0\na\nb") is None
    assert od.first_difference("exit 0\na\nb", "exit 0\na\nc") == "line 3\n    - b\n    + c"
    assert od.first_difference("exit 0\na", "exit 1\na").startswith("line 1\n    - exit 0")
    assert od.first_difference("a", "a\nb") == "line 2\n    - (no more lines)\n    + b"
    long = od.first_difference("x" * 500, "y")
    assert "x" * od.EXCERPT + "..." in long and "x" * (od.EXCERPT + 1) not in long


def test_compare_reports_outputs_one_side_lacks():
    result = od.compare({"run": "a", "file a": "1", "file old": "2"}, {"run": "a", "file a": "9", "file new": "3"})
    assert result["run"] is None
    assert result["file a"].startswith("line 1")
    assert result["file old"] == "only on the REF side"
    assert result["file new"] == "only in the working tree"


def test_cases_cover_every_listed_sheet_and_layout(tmp_path):
    project = tmp_path / "example"
    project.mkdir()
    (project / "project.c3proj").write_text(json.dumps({
        "eventSheets": {"items": ["Main"], "subfolders": [{"items": ["Enemies"], "subfolders": []}]},
        "layouts": {"items": ["Level 1"], "subfolders": []}}), encoding="utf-8")
    matrix = od.cases(list(od.KINDS), [project], tmp_path / "plan.json")
    names = {(c.kind, c.name) for c in matrix}
    assert {("print_sheet", "example/Main"), ("print_sheet", "example/Enemies"),
            ("print_layout", "example/Level 1"), ("check_project", "example"), ("check_style", "example"),
            ("edit_sheet", "example")} <= names
    assert len([c for c in matrix if c.kind == "lookup_ace"]) == len(od.LOOKUPS["lookup_ace"])
    assert not od.cases(["print_layout"], [], tmp_path / "plan.json")


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPO / "scripts" / "output_diff.py"), *args], capture_output=True,
                          text=True, encoding="utf-8", timeout=60)


def test_a_ref_that_is_no_commit_stops_with_2():
    p = run("no-such-ref-of-this-repository")
    assert p.returncode == 2 and "is not a commit" in p.stderr


def test_a_missing_example_clone_stops_with_2(tmp_path):
    p = run("HEAD", "--examples", str(tmp_path), "--only", "print_sheet")
    assert p.returncode == 2 and "no official example" in p.stderr
